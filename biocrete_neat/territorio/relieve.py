"""Blur · relieve: teselas Copernicus DEM GLO-90 (90 m, © DLR/Airbus, licencia abierta Copernicus).

Descarga las teselas de 1° que tocan la franja costera (y el rectángulo del sombreado del mapa) a
biocrete_neat/datos/territorio/dem/ (no se versionan: ~1 GB). En el registro queda la lista de
teselas, cuáles son mar y su tamaño. El Atlas las lee para sus estadísticas por zona.
"""
from __future__ import annotations

import json
import math
import urllib.error

from biocrete_neat.territorio.red import bajar_archivo
from biocrete_neat.territorio.registro import DIR, Registro

DEM = DIR / "dem"
URL = "https://copernicus-dem-90m.s3.amazonaws.com/{n}/{n}.tif"
BUFFER_KM = 45.0
SOMBREADO = (-81.5, -18.6, -69.6, -3.2)     # lon0, lat0, lon1, lat1 del fondo del mapa (atlas/fondo.py)


def nombre(lat_floor: int, lon_floor: int) -> str:
    ns = "N" if lat_floor >= 0 else "S"
    ew = "E" if lon_floor >= 0 else "W"
    return f"Copernicus_DSM_COG_30_{ns}{abs(lat_floor):02d}_00_{ew}{abs(lon_floor):03d}_00_DEM"


def teselas(pais="PER") -> list[tuple[int, int]]:
    from shapely.geometry import LineString, box, shape
    geo = DIR / "geo"
    costa = LineString(json.loads((geo / f"costa_{pais.lower()}.geojson").read_text(encoding="utf-8"))["geometry"]["coordinates"])
    tierra = shape(json.loads((geo / f"pais_{pais.lower()}.geojson").read_text(encoding="utf-8"))["geometry"])
    franja = tierra.intersection(costa.buffer(BUFFER_KM / 111.0)).buffer(0.05)
    x0, y0, x1, y1 = franja.bounds
    return [(la, lo) for la in range(math.floor(y0), math.ceil(y1)) for lo in range(math.floor(x0), math.ceil(x1))
            if franja.intersects(box(lo, la, lo + 1, la + 1))]


def recolectar(pais="PER") -> dict:
    DEM.mkdir(parents=True, exist_ok=True)
    estado, errores = {}, []
    for la, lo in teselas(pais):
        n = nombre(la, lo)
        tif, mar = DEM / f"{n}.tif", DEM / f"{n}.mar"
        if not tif.exists() and not mar.exists():
            try:
                bajar_archivo(URL.format(n=n), tif)
                print(f"  ✓ {n}")
            except urllib.error.HTTPError as e:
                if e.code in (403, 404):            # tesela de océano: no existe
                    mar.touch()
                else:
                    errores.append(f"{n}: {e}")
            except Exception as e:  # noqa: BLE001
                errores.append(f"{n}: {e}")
        estado[n] = ({"tif": True, "bytes": tif.stat().st_size} if tif.exists()
                     else {"tif": False, "mar": True} if mar.exists() else {"tif": False, "error": True})
    reg = Registro()
    reg.reemplazar("relieve", {"estado": "ok" if not errores else "incompleto", "url": URL.split("{")[0],
                               "licencia": "Copernicus DEM GLO-90 (licencia abierta Copernicus, © DLR/Airbus)",
                               "carpeta": str(DEM.relative_to(DIR.parents[2])), "teselas": len(estado),
                               "con_tierra": sum(1 for v in estado.values() if v.get("tif")),
                               "lista": estado, **({"detalle": "; ".join(errores)} if errores else {})})
    reg.guardar()
    return estado
