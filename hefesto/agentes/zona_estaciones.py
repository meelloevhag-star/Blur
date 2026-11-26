"""
Agente ZONA · extractor de estaciones meteorológicas (NOAA ISD global-hourly, abierto y sin clave).

Para cada estación calcula, sobre los años pedidos: humedad relativa media (Magnus, a partir de TMP y
DEW), porcentaje de observaciones y días/año con neblina (código 10), niebla (40–49) y llovizna o garúa
(50–59) según el tiempo presente manual (MW1), y viento medio (WND).

Salidas:
    datos/zona/estaciones_isd.json          resumen por estación
    datos/entrantes/zona_estaciones.csv      filas en el esquema unificado (las procesa el curador)

Uso:
    python -m hefesto.agentes.zona_estaciones [--desde 2015 --hasta 2024]
"""

import argparse
import csv
import json
import math
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ESTACIONES = {  # código ISD: (nombre, región, lat, lon)
    "84390099999": ("Talara · aeropuerto Capitán Montes", "Piura · Talara", -4.5766, -81.2541),
    "84401099999": ("Piura · aeropuerto Concha Ibérico", "Piura · Piura", -5.2058, -80.6164),
}
URL = ("https://www.ncei.noaa.gov/access/services/data/v1?dataset=global-hourly&stations={st}"
       "&startDate={y}-01-01&endDate={y}-12-31T23:59:59&format=json")


def humedad_relativa(T: float, D: float) -> float:
    return 100 * math.exp(17.625 * D / (243.04 + D)) / math.exp(17.625 * T / (243.04 + T))


def resumir(registros: list[dict], anios: int) -> dict:
    rh, viento, horas, cuenta, dias = [], [], 0, defaultdict(int), defaultdict(set)
    for r in registros:
        try:
            T, D = int(r["TMP"].split(",")[0]) / 10, int(r["DEW"].split(",")[0]) / 10
            if abs(T) < 60 and abs(D) < 60:
                rh.append(humedad_relativa(T, D))
        except (KeyError, ValueError):
            pass
        try:
            w = r["WND"].split(",")
            if w[3] != "9999":
                viento.append(int(w[3]) / 10)
        except (KeyError, IndexError, ValueError):
            pass
        codigo = (r.get("MW1") or "").split(",")[0]
        if codigo.isdigit():
            horas += 1
            c = int(codigo)
            tipo = "neblina" if c == 10 else "niebla" if 40 <= c <= 49 else "llovizna" if 50 <= c <= 59 else None
            if tipo:
                cuenta[tipo] += 1
                dias[tipo].add(r["DATE"][:10])
    res = {"anios_con_datos": anios, "n_obs_humedad": len(rh), "obs_tiempo_presente": horas,
           "hr_media_pct": round(sum(rh) / len(rh), 1) if rh else None,
           "viento_medio_ms": round(sum(viento) / len(viento), 1) if viento else None}
    for tipo in ("neblina", "niebla", "llovizna"):
        res[f"pct_obs_{tipo}"] = round(100 * cuenta[tipo] / horas, 2) if horas else None
        res[f"dias_{tipo}_por_anio"] = round(len(dias[tipo]) / max(anios, 1), 1)
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", type=int, default=2015)
    ap.add_argument("--hasta", type=int, default=2024)
    a = ap.parse_args(argv)
    resumen, filas = {}, []
    for st, (nombre, region, lat, lon) in ESTACIONES.items():
        registros, anios = [], 0
        for y in range(a.desde, a.hasta + 1):
            try:
                datos = json.load(urllib.request.urlopen(URL.format(st=st, y=y), timeout=120))
            except Exception as e:  # noqa: BLE001 — se informa y se sigue con el resto
                print(f"{st} {y}: {e}", file=sys.stderr)
                continue
            anios += bool(datos)
            registros += datos
        res = resumir(registros, anios)
        resumen[st] = {"estacion": nombre, **res}
        print(json.dumps(resumen[st], ensure_ascii=False), flush=True)
        filas.append({
            "fuente": "NOAA-ISD", "id_grupo": st, "zona_region": region, "zona_lat": lat, "zona_lon": lon,
            "zona_humedad_relativa_pct": res["hr_media_pct"],
            "zona_dias_niebla_anio": round(res["dias_neblina_por_anio"] + res["dias_niebla_por_anio"], 1),
            "procedencia_doi_o_url": f"https://www.ncei.noaa.gov/access/services/data/v1?dataset=global-hourly&stations={st}",
            "procedencia_tipo": "clima",
            "procedencia_ubicacion": f"global-hourly {a.desde}-{a.hasta}; campos TMP, DEW, MW1, WND",
            "procedencia_verificado": "si",
            "procedencia_notas": (f"{nombre}. Viento medio {res['viento_medio_ms']} m/s; días/año con llovizna "
                                  f"{res['dias_llovizna_por_anio']}; tiempo presente manual solo en "
                                  f"{res['obs_tiempo_presente']} observaciones (cobertura parcial)."),
        })
    (RAIZ / "datos" / "zona").mkdir(parents=True, exist_ok=True)
    (RAIZ / "datos" / "zona" / "estaciones_isd.json").write_text(
        json.dumps({"periodo": [a.desde, a.hasta], "estaciones": resumen}, ensure_ascii=False, indent=2), encoding="utf-8")
    esquema = json.loads((RAIZ / "hefesto" / "esquema" / "esquema_datos.json").read_text(encoding="utf-8"))
    destino = RAIZ / "datos" / "entrantes" / "zona_estaciones.csv"
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(esquema["properties"]))
        w.writeheader()
        w.writerows({k: ("" if f.get(k) is None else f.get(k, "")) for k in esquema["properties"]} for f in filas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
