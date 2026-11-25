"""Blur · clima por celda ERA5 (0,25°) desde el archivo histórico de Open-Meteo (ERA5/ERA5-Land, CC BY 4.0).

ERA5 no resuelve detalles más finos que su celda, así que se descarga un año horario por celda que
toque la franja costera (tierra a menos de BUFFER_KM del mar) y se resume. El Atlas reparte luego ese
clima entre sus zonas y lo corrige por altitud con el DEM. Solo se descarga lo que falta.

Salida: biocrete_neat/datos/territorio/clima_era5_<pais>.json → {"celdas": {"lat,lon": {...}}}
"""
from __future__ import annotations

import json
import math
import time
import urllib.error

from biocrete_neat.territorio.red import abrir
from biocrete_neat.territorio.registro import DIR, Registro, huella

URL = "https://archive-api.open-meteo.com/v1/archive"
VARIABLES = ["temperature_2m", "relative_humidity_2m", "dew_point_2m", "cloud_cover_low",
             "wind_speed_10m", "wind_direction_10m", "precipitation"]
LOTE = 10
GRADO_CELDA = 0.25
BUFFER_KM = 40.0


def celda(lat: float, lon: float) -> str:
    return f"{round(lat / GRADO_CELDA) * GRADO_CELDA:.2f},{round(lon / GRADO_CELDA) * GRADO_CELDA:.2f}"


def ruta(pais="PER"):
    return DIR / f"clima_era5_{pais.lower()}.json"


def leer(pais="PER") -> dict:
    r = ruta(pais)
    c = json.loads(r.read_text(encoding="utf-8")) if r.exists() else {}
    return c if "celdas" in c else {"celdas": {}}


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


def celdas_costeras(pais="PER", buffer_km=BUFFER_KM) -> dict[str, tuple[float, float]]:
    """Celdas ERA5 con tierra a menos de `buffer_km` del mar y un punto representativo en tierra de cada una."""
    from shapely.geometry import LineString, Point, box, shape
    from shapely.ops import nearest_points
    geo = DIR / "geo"
    costa = LineString(json.loads((geo / f"costa_{pais.lower()}.geojson").read_text(encoding="utf-8"))["geometry"]["coordinates"])
    tierra = shape(json.loads((geo / f"pais_{pais.lower()}.geojson").read_text(encoding="utf-8"))["geometry"])
    franja = tierra.intersection(costa.buffer(buffer_km / 111.0))
    x0, y0, x1, y1 = franja.bounds
    g = GRADO_CELDA
    out = {}
    lat = math.floor(y0 / g) * g
    while lat <= y1 + g:
        lon = math.floor(x0 / g) * g
        while lon <= x1 + g:
            c = box(lon - g / 2, lat - g / 2, lon + g / 2, lat + g / 2)
            parte = franja.intersection(c)
            if not parte.is_empty and parte.area > 0:
                p = Point(lon, lat)
                q = p if parte.contains(p) else nearest_points(parte, p)[0]
                out[celda(lat, lon)] = (round(q.y, 4), round(q.x, 4))
            lon += g
        lat += g
    return out


def recolectar(pais="PER", anio=2024, pausa=2.0) -> dict:
    cache = leer(pais)
    objetivo = celdas_costeras(pais)
    pend = [(k, p) for k, p in objetivo.items() if k not in cache["celdas"]]
    print(f"clima: {len(objetivo)} celdas costeras, {len(cache['celdas'])} ya en caché, {len(pend)} por bajar")
    error = None
    for k in range(0, len(pend), LOTE):
        lote = pend[k:k + LOTE]
        q = (f"{URL}?latitude={','.join(str(p[0]) for _, p in lote)}&longitude={','.join(str(p[1]) for _, p in lote)}"
             f"&start_date={anio}-01-01&end_date={anio}-12-31&hourly={','.join(VARIABLES)}&timezone=GMT")
        try:
            for intento in range(5):
                try:
                    res = json.loads(abrir(q, tiempo=120))
                    break
                except urllib.error.HTTPError as e:
                    if e.code != 429 or intento == 4:
                        raise
                    time.sleep(30 * (intento + 1))
        except Exception as e:  # noqa: BLE001
            error = str(e)
            print(f"  ✗ {error}")
            break
        res = res if isinstance(res, list) else [res]
        for (c, p), d in zip(lote, res):
            cache["celdas"][c] = _resumir(d["hourly"], d.get("elevation")) | {
                "lat": p[0], "lon": p[1], "fuente": f"Open-Meteo Historical Weather API (ERA5), {anio}"}
        ruta(pais).write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        print(f"  {len(cache['celdas'])} celdas con clima", flush=True)
        time.sleep(pausa)
    if not ruta(pais).exists():
        ruta(pais).write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    faltan = sum(1 for k in objetivo if k not in cache["celdas"])
    reg = Registro()
    reg.reemplazar("clima", {"estado": "ok" if not faltan else "incompleto", "url": URL, "anio": anio,
                             "licencia": "CC BY 4.0 (Open-Meteo / Copernicus ERA5)", "celdas": len(cache["celdas"]),
                             "celdas_costeras": len(objetivo), "faltan": faltan,
                             "archivo": str(ruta(pais).relative_to(DIR.parents[2])), "huella": huella(ruta(pais)),
                             **({"detalle": error} if error else {})})
    reg.guardar()
    return cache
