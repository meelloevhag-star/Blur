"""Clima por zona desde el archivo histórico de Open-Meteo (reanálisis ERA5/ERA5-Land, CC BY 4.0).

Por cada centro de zona se descarga un año horario y se resume en indicadores para durabilidad
y niebla. Se guarda en caché (atlas/datos/ambiente_<pais>.json) y solo se descargan las zonas que
faltan, así que se puede re-ejecutar sin coste.

    python -m atlas.ambiente --pais PER --anio 2024
"""
from __future__ import annotations

import argparse
import json
import math
import time
import urllib.request
import urllib.error

from atlas.rutas import DATOS
from atlas.zonas import cargar_zonas

URL = "https://archive-api.open-meteo.com/v1/archive"
VARIABLES = ["temperature_2m", "relative_humidity_2m", "dew_point_2m", "cloud_cover_low",
             "wind_speed_10m", "wind_direction_10m", "precipitation"]
LOTE = 10


def _resumir(h: dict, elev: float) -> dict:
    T, RH, TD = h["temperature_2m"], h["relative_humidity_2m"], h["dew_point_2m"]
    CL, WS, WD, PP = h["cloud_cover_low"], h["wind_speed_10m"], h["wind_direction_10m"], h["precipitation"]
    ok = [i for i in range(len(T)) if None not in (T[i], RH[i], TD[i])]
    n = len(ok) or 1
    niebla = sum(1 for i in ok if RH[i] >= 95 and (T[i] - TD[i]) <= 1.0) / n
    humedo = sum(1 for i in ok if RH[i] >= 85) / n
    cl = [c for c in CL if c is not None]
    # viento medio vectorial (dirección meteorológica: desde dónde sopla)
    u = [-w * math.sin(math.radians(d)) for w, d in zip(WS, WD) if w is not None and d is not None]
    v = [-w * math.cos(math.radians(d)) for w, d in zip(WS, WD) if w is not None and d is not None]
    um, vm = sum(u) / len(u), sum(v) / len(v)
    return {
        "elevacion_m": elev,
        "t_media_c": round(sum(T[i] for i in ok) / n, 2),
        "t_min_c": round(min(T[i] for i in ok), 1),
        "hr_media_pct": round(sum(RH[i] for i in ok) / n, 1),
        "frac_horas_niebla": round(niebla, 4),          # HR ≥ 95 % y T−Td ≤ 1 °C
        "frac_horas_hr85": round(humedo, 4),
        "nubes_bajas_media_pct": round(sum(cl) / len(cl), 1) if cl else None,
        "viento_medio_ms": round(sum(w for w in WS if w is not None) / len(WS) / 3.6, 2),
        "viento_dir_desde_grados": round((math.degrees(math.atan2(-um, -vm)) + 360) % 360, 0),
        "precip_anual_mm": round(sum(p for p in PP if p is not None), 1),
    }


def descargar(pais="PER", anio=2024, pausa=2.0):
    ruta = DATOS / f"ambiente_{pais.lower()}.json"
    cache = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    pend = [z for z in cargar_zonas(pais) if z.id not in cache]
    for k in range(0, len(pend), LOTE):
        lote = pend[k:k + LOTE]
        q = (f"{URL}?latitude={','.join(str(z.lat) for z in lote)}&longitude={','.join(str(z.lon) for z in lote)}"
             f"&start_date={anio}-01-01&end_date={anio}-12-31&hourly={','.join(VARIABLES)}&timezone=GMT")
        for intento in range(5):
            try:
                with urllib.request.urlopen(q, timeout=120) as r:
                    res = json.loads(r.read())
                break
            except urllib.error.HTTPError as e:
                if e.code != 429 or intento == 4:
                    raise
                time.sleep(30 * (intento + 1))
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                if intento == 4:
                    raise
                time.sleep(10 * (intento + 1))
        res = res if isinstance(res, list) else [res]
        for z, d in zip(lote, res):
            cache[z.id] = _resumir(d["hourly"], d.get("elevation"))
            cache[z.id]["fuente"] = f"Open-Meteo Historical Weather API (ERA5), {anio}"
        ruta.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
        print(f"{len(cache)} zonas con clima", flush=True)
        time.sleep(pausa)
    return cache


def cargar(pais="PER") -> dict:
    return json.loads((DATOS / f"ambiente_{pais.lower()}.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pais", default="PER")
    ap.add_argument("--anio", type=int, default=2024)
    a = ap.parse_args()
    descargar(a.pais, a.anio)
