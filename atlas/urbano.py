"""Población y uso urbano por zona.

  - Población: WorldPop 2022, 1 km, ajustada a la ONU (CC BY 4.0). WorldPop distribuye los totales del
    Censo Nacional 2017 (INEI) y sus proyecciones con covariables satelitales. El ráster lo recoge
    Blur (biocrete_neat/territorio/poblacion.py) y aquí se resume por zona.
  - Clase urbana: umbrales de densidad del Grado de Urbanización (ONU-Eurostat, 2020):
    urbano ≥ 1 500 hab/km², periurbano ≥ 300, rural ≥ 25, deshabitado < 25.
  - Ciudad más cercana y distancia a una carretera principal: Natural Earth 10m
    recogidas por Blur (biocrete_neat/datos/territorio/geo/ciudades_per.json, vias_per.geojson).

    python -m atlas.urbano [--pais PER]
"""
from __future__ import annotations

import argparse
import json
import math

import numpy as np

from atlas.relieve import _rejilla_en_poligono
from atlas.rutas import AVISO_BLUR, DATOS, GEO, WORLDPOP_DIR
from atlas.zonas import cargar_zonas

RASTER = {"PER": "per_ppp_2022_1km_UNadj.tif"}
UMBRALES = [(1500, "urbano"), (300, "periurbano"), (25, "rural"), (0, "deshabitado")]


def clase_urbana(densidad: float) -> str:
    return next(c for u, c in UMBRALES if densidad >= u)


def _area_km2(pol) -> float:
    lat0 = sum(p[1] for p in pol) / len(pol)
    kx, ky = 111.32 * math.cos(math.radians(lat0)), 111.32
    xs = [p[0] * kx for p in pol]
    ys = [p[1] * ky for p in pol]
    return abs(sum(xs[i] * ys[i + 1] - xs[i + 1] * ys[i] for i in range(len(pol) - 1))) / 2


class Poblacion:
    def __init__(self, pais="PER"):
        import rasterio
        ruta = WORLDPOP_DIR / RASTER[pais]
        if not ruta.exists():
            raise FileNotFoundError(f"{ruta}: {AVISO_BLUR.format(que='poblacion')}")
        with rasterio.open(ruta) as r:
            self.a = r.read(1).astype(np.float64)
            self.tr = r.transform
        self.a[self.a < 0] = 0

    def densidad(self, lon, lat):
        """hab/km² en los puntos (valor de la celda / área de la celda)."""
        col = ((lon - self.tr.c) / self.tr.a).astype(int).clip(0, self.a.shape[1] - 1)
        fil = ((lat - self.tr.f) / self.tr.e).astype(int).clip(0, self.a.shape[0] - 1)
        area = (abs(self.tr.a) * 111.32) * (abs(self.tr.e) * 111.32) * np.cos(np.radians(lat))
        return self.a[fil, col] / area


def calcular(pais="PER") -> dict:
    from shapely.geometry import shape, Point
    from shapely.strtree import STRtree
    zonas = cargar_zonas(pais)
    pob = Poblacion(pais)
    ciudades = json.loads((GEO / f"ciudades_{pais.lower()}.json").read_text(encoding="utf-8"))["lugares"]
    vias = [shape(f["geometry"]) for f in
            json.loads((GEO / f"vias_{pais.lower()}.geojson").read_text(encoding="utf-8"))["features"]]
    arbol = STRtree(vias)
    out = {}
    for z in zonas:
        lon, lat = _rejilla_en_poligono(z.poligono)
        d = pob.densidad(lon, lat)
        area = _area_km2(z.poligono)
        dens = float(d.mean())
        kx = 111.32 * math.cos(math.radians(z.lat))
        c = min(ciudades, key=lambda q: ((q["lon"] - z.lon) * kx) ** 2 + ((q["lat"] - z.lat) * 111.32) ** 2)
        dc = math.hypot((c["lon"] - z.lon) * kx, (c["lat"] - z.lat) * 111.32)
        p = Point(z.lon, z.lat)
        v = vias[int(arbol.nearest(p))]
        q = v.interpolate(v.project(p))
        dv = math.hypot((q.x - z.lon) * kx, (q.y - z.lat) * 111.32)
        out[z.id] = {
            "area_km2": round(area, 2), "poblacion": int(round(dens * area)), "densidad_hab_km2": round(dens, 1),
            "frac_area_urbana": round(float((d >= 1500).mean()), 3), "clase_urbana": clase_urbana(dens),
            "ciudad_cercana": c["nombre"], "ciudad_pob": c["pob"], "dist_ciudad_km": round(dc, 1),
            "dist_via_principal_km": round(dv, 1),
        }
    out["_meta"] = {"fuente_poblacion": "WorldPop 2022 1km UN-adjusted (Censo 2017 INEI + proyección)",
                    "fuente_vias": "Natural Earth 10m", "poblacion_pais": int(pob.a.sum()),
                    "umbrales_hab_km2": {c: u for u, c in UMBRALES}}
    (DATOS / f"urbano_{pais.lower()}.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def cargar(pais="PER") -> dict:
    ruta = DATOS / f"urbano_{pais.lower()}.json"
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pais", default="PER")
    a = ap.parse_args()
    r = calcular(a.pais)
    tot = sum(v["poblacion"] for k, v in r.items() if not k.startswith("_"))
    print(f"población en las zonas: {tot:,} de {r['_meta']['poblacion_pais']:,} "
          f"({100 * tot / r['_meta']['poblacion_pais']:.1f} %)")
