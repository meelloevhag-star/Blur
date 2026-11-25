"""Maquetas de terreno por celda hexagonal para la vista 3D del Atlas.

Para cada celda se muestrea el DEM Copernicus en una ventana de VENTANA_KM × VENTANA_KM centrada en
la celda y orientada con el mar al frente:
  u: a lo largo de la costa;  v: tierra adentro (del punto de costa más cercano hacia la celda).
Las alturas van como Int16 en base64 (metros; −1 = mar). Junto va el contorno del hexágono en km
locales, para resaltarlo sobre el terreno. Se guarda por departamento en
atlas/salida/web/terreno/<depto>.json.

    python -m atlas.terreno
"""
from __future__ import annotations

import base64
import json
import math

import numpy as np

from atlas.cli import _slug
from atlas.relieve import Mosaico
from atlas.rutas import GEO, SALIDA
from atlas.zonas import TAM_HEX_KM, cargar_zonas

N = 48                      # resolución de la rejilla (N × N)
VENTANA_KM = 16.0


def generar(pais="PER"):
    from shapely.geometry import LineString, Point
    from shapely.ops import nearest_points
    linea = LineString(json.loads((GEO / f"costa_{pais.lower()}.geojson").read_text(encoding="utf-8"))["geometry"]["coordinates"])
    dem = Mosaico(max_mem=12)
    s = np.linspace(-VENTANA_KM / 2, VENTANA_KM / 2, N)
    U, V = np.meshgrid(s, s, indexing="ij")
    salida: dict[str, dict] = {}
    for z in cargar_zonas(pais):
        kx = 111.32 * math.cos(math.radians(z.lat))
        c = nearest_points(linea, Point(z.lon, z.lat))[0]
        vx, vy = (z.lon - c.x) * kx, (z.lat - c.y) * 111.32
        n = math.hypot(vx, vy)
        vx, vy = (vx / n, vy / n) if n > 1e-6 else (1.0, 0.0)
        ax, ay = vy, -vx                                  # a lo largo de la costa
        este, norte = U * ax + V * vx, U * ay + V * vy
        h = dem.muestrear((z.lon + este / kx).ravel(), (z.lat + norte / 111.32).ravel()).reshape(U.shape)
        h = np.clip(np.where(h > 0, np.round(h), -1), -1, 32767).astype("<i2")
        # contorno de la celda en (u, v) km
        cont = []
        for lon, lat in z.poligono[:-1]:
            e, nn = (lon - z.lon) * kx, (lat - z.lat) * 111.32
            cont.append([round(e * ax + nn * ay, 2), round(e * vx + nn * vy, 2)])
        salida.setdefault(_slug(z.departamento), {})[z.id] = {
            "nu": N, "nv": N, "u_km": [-VENTANA_KM / 2, VENTANA_KM / 2], "v_km": [-VENTANA_KM / 2, VENTANA_KM / 2],
            "h64": base64.b64encode(h.tobytes()).decode(), "celda": cont,
            "dist_mar_km": z.dist_mar_km, "tam_km": TAM_HEX_KM}
    d = SALIDA / "web" / "terreno"
    import shutil
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True)
    for depto, celdas in salida.items():
        (d / f"{depto}.json").write_text(json.dumps(celdas, separators=(",", ":")), encoding="utf-8")
    return d


if __name__ == "__main__":
    r = generar()
    print(r, sum(p.stat().st_size for p in r.glob("*.json")) // 1024, "KB")
