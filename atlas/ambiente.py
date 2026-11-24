"""Clima por celda ERA5 (0,25°) desde el archivo histórico de Open-Meteo (ERA5/ERA5-Land, CC BY 4.0).

ERA5 no resuelve detalles más finos que su celda, así que el clima se descarga una vez por celda
(en el centro de la zona más cercano al centro de la celda) y todas las zonas de la celda lo
comparten; el relieve (DEM de 90 m) aporta luego la variación local: corrección de temperatura por
altitud y niebla orográfica. Caché en atlas/datos/ambiente_<pais>.json: {"celdas": {...}}; solo se
descarga lo que falta.

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


GRADO_CELDA = 0.25
GRADIENTE_T = -6.5 / 1000      # °C/m (atmósfera estándar)


def celda(lat: float, lon: float) -> str:
    return f"{round(lat / GRADO_CELDA) * GRADO_CELDA:.2f},{round(lon / GRADO_CELDA) * GRADO_CELDA:.2f}"


def _leer_cache(ruta):
    c = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    return c if "celdas" in c else {"celdas": {}}


def migrar_v1(ruta_zonas_v1: str, pais="PER"):
    """Convierte la caché v1 (por id de zona de 20 km) a celdas sin volver a descargar."""
    ruta = DATOS / f"ambiente_{pais.lower()}.json"
    viejo = json.loads(ruta.read_text(encoding="utf-8"))
    if "celdas" in viejo:
        return
    zonas_v1 = json.loads(open(ruta_zonas_v1, encoding="utf-8").read())
    celdas = {}
    for z in zonas_v1:
        if z["id"] not in viejo:
            continue
        k = celda(z["lat"], z["lon"])
        cla, clo = map(float, k.split(","))
        d = (z["lat"] - cla) ** 2 + (z["lon"] - clo) ** 2
        if k not in celdas or d < celdas[k]["_d"]:
            celdas[k] = viejo[z["id"]] | {"lat": z["lat"], "lon": z["lon"], "_d": d}
    for v in celdas.values():
        v.pop("_d")
    ruta.write_text(json.dumps({"celdas": celdas}, ensure_ascii=False), encoding="utf-8")


def descargar(pais="PER", anio=2024, pausa=2.0):
    ruta = DATOS / f"ambiente_{pais.lower()}.json"
    cache = _leer_cache(ruta)
    # punto representativo de cada celda: centro de zona más cercano al centro de la celda
    rep = {}
    for z in cargar_zonas(pais):
        k = celda(z.lat, z.lon)
        cla, clo = map(float, k.split(","))
        d = (z.lat - cla) ** 2 + (z.lon - clo) ** 2
        if k not in rep or d < rep[k][0]:
            rep[k] = (d, z)
    pend = [(k, z) for k, (_, z) in rep.items() if k not in cache["celdas"]]
    for k in range(0, len(pend), LOTE):
        lote = [z for _, z in pend[k:k + LOTE]]
        claves = [c for c, _ in pend[k:k + LOTE]]
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
        for c, z, d in zip(claves, lote, res):
            cache["celdas"][c] = _resumir(d["hourly"], d.get("elevation")) | {
                "lat": z.lat, "lon": z.lon, "fuente": f"Open-Meteo Historical Weather API (ERA5), {anio}"}
        ruta.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        print(f"{len(cache['celdas'])} celdas con clima", flush=True)
        time.sleep(pausa)
    return cache


def cargar(pais="PER") -> dict:
    return _leer_cache(DATOS / f"ambiente_{pais.lower()}.json")["celdas"]


def clima_zona(z, celdas: dict, elev_zona_m: float | None) -> dict:
    """Clima de la celda de la zona (o de la celda más cercana) corregido por altitud con el DEM."""
    k = celda(z.lat, z.lon)
    origen = k
    if k not in celdas:
        origen = min(celdas, key=lambda c: (float(c.split(",")[0]) - z.lat) ** 2 + (float(c.split(",")[1]) - z.lon) ** 2)
    a = dict(celdas[origen])
    a["celda_era5"] = origen
    a["celda_propia"] = origen == k
    if elev_zona_m is not None and a.get("elevacion_m") is not None:
        dz = elev_zona_m - a["elevacion_m"]
        a["t_media_c"] = round(a["t_media_c"] + GRADIENTE_T * dz, 2)
        a["t_min_c"] = round(a["t_min_c"] + GRADIENTE_T * dz, 1)
        a["correccion_altitud_c"] = round(GRADIENTE_T * dz, 2)
    return a


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pais", default="PER")
    ap.add_argument("--anio", type=int, default=2024)
    ap.add_argument("--migrar-v1", help="zonas_per.json de la malla v1 para convertir la caché")
    a = ap.parse_args()
    if a.migrar_v1:
        migrar_v1(a.migrar_v1, a.pais)
    descargar(a.pais, a.anio)
