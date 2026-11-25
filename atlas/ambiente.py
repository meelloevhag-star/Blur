"""Clima por zona a partir de las celdas ERA5 que recoge Blur (biocrete_neat/territorio/clima.py).

ERA5 no resuelve detalles más finos que su celda de 0,25°: todas las zonas de una celda comparten su
clima y el relieve (DEM de 90 m) aporta la variación local, con corrección de temperatura por altitud.
El Atlas no descarga nada: lee biocrete_neat/datos/territorio/clima_era5_<pais>.json.
"""
from __future__ import annotations

import json
import math

from atlas.rutas import AVISO_BLUR, CLIMA

GRADO_CELDA = 0.25
GRADIENTE_T = -6.5 / 1000      # °C/m (atmósfera estándar)


def celda(lat: float, lon: float) -> str:
    return f"{round(lat / GRADO_CELDA) * GRADO_CELDA:.2f},{round(lon / GRADO_CELDA) * GRADO_CELDA:.2f}"


def cargar(pais="PER") -> dict:
    ruta = CLIMA.with_name(CLIMA.name.format(pais=pais.lower()))
    if not ruta.exists():
        raise FileNotFoundError(f"{ruta}: {AVISO_BLUR.format(que='clima')}")
    return json.loads(ruta.read_text(encoding="utf-8"))["celdas"]


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
