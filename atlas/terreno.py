"""Maquetas de terreno por tramo para la vista 3D del Atlas.

Para cada tramo (10 km de costa) se muestrea el DEM Copernicus en una rejilla local:
  u: a lo largo de la costa, de −5 a +5 km;  v: tierra adentro, de −3 km (mar) a +35 km.
Se guarda por departamento en atlas/salida/web/terreno/<depto>.json como enteros (metros), junto
con la orientación de la rejilla, para que el navegador construya la malla sin otro cálculo.

    python -m atlas.terreno
"""
from __future__ import annotations

import json
import math

import numpy as np

from atlas.cli import _slug
from atlas.relieve import Mosaico
from atlas.rutas import SALIDA
from atlas.zonas import cargar_zonas

NU, NV = 33, 97              # resolución de la rejilla (u × v)
U_KM = (-5.0, 5.0)
V_KM = (-3.0, 35.0)


def _ejes(tramo_zonas):
    """Punto de costa y vectores unitarios (este, norte en km) hacia tierra y a lo largo de la costa."""
    z0 = min(tramo_zonas, key=lambda z: z.franja)
    zl = max(tramo_zonas, key=lambda z: z.franja)
    kx = 111.32 * math.cos(math.radians(z0.lat))
    vx, vy = (zl.lon - z0.lon) * kx, (zl.lat - z0.lat) * 111.32
    n = math.hypot(vx, vy) or 1.0
    vx, vy = vx / n, vy / n
    ox = z0.lon - vx * z0.dist_mar_km / kx
    oy = z0.lat - vy * z0.dist_mar_km / 111.32
    return (ox, oy), (vx, vy), (vy, -vx), kx


def generar(pais="PER"):
    zonas = cargar_zonas(pais)
    por_tramo: dict[int, list] = {}
    for z in zonas:
        por_tramo.setdefault(z.tramo, []).append(z)
    dem = Mosaico(max_mem=12)
    us = np.linspace(*U_KM, NU)
    vs = np.linspace(*V_KM, NV)
    U, V = np.meshgrid(us, vs, indexing="ij")
    salida: dict[str, dict] = {}
    for t, zs in sorted(por_tramo.items()):
        (ox, oy), (vx, vy), (ax, ay), kx = _ejes(zs)
        este = U * ax + V * vx
        norte = U * ay + V * vy
        lon = ox + este / kx
        lat = oy + norte / 111.32
        h = dem.muestrear(lon.ravel(), lat.ravel()).reshape(U.shape)
        h = np.where(h > 0, h, -1)            # −1 = mar
        # el tramo se guarda en cada departamento al que pertenecen sus franjas (la web lo busca por el
        # departamento de la zona elegida)
        datos = {
            "nu": NU, "nv": NV, "u_km": list(U_KM), "v_km": list(V_KM),
            "origen": [round(ox, 5), round(oy, 5)], "tierra_adentro": [round(vx, 4), round(vy, 4)],
            "h": np.round(h).astype(int).ravel().tolist(),
            "franjas": sorted([[z.franja, z.id, z.dist_mar_km] for z in zs]),
        }
        for depto in {_slug(z.departamento) for z in zs}:
            salida.setdefault(depto, {})[str(t)] = datos
    d = SALIDA / "web" / "terreno"
    import shutil
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True)
    for depto, tramos in salida.items():
        (d / f"{depto}.json").write_text(json.dumps(tramos, separators=(",", ":")), encoding="utf-8")
    return d


if __name__ == "__main__":
    r = generar()
    print(r, sum(p.stat().st_size for p in r.glob("*.json")) // 1024, "KB")
