"""Relieve por zona desde el DEM Copernicus GLO-90 (90 m, © DLR/Airbus, licencia abierta Copernicus).

Por qué importa: en la costa peruana la capa de estratocúmulos queda atrapada bajo la inversión
térmica (~600–1000 m). Donde los cerros cortan esa capa, sobre todo en laderas que miran al mar,
la nube toca el suelo (niebla de advección/orográfica, "camanchaca") y forma las lomas. Las zonas
llanas del desierto apenas la reciben, y las crestas altas frenan el aerosol salino hacia el interior.

Por zona se guarda (atlas/datos/relieve_<pais>.json, sin los rásters):
  - elevación media, p10 y p90 (m) y pendiente media (°);
  - frac_cinturon_niebla: fracción del área entre COTA_NIEBLA_MIN y COTA_NIEBLA_MAX;
  - frac_barlovento: fracción del área con pendiente > 3° cuya ladera mira al mar (±60°);
  - frac_loma: fracción que cumple ambas a la vez (ladera al mar dentro del cinturón);
  - barrera_m: elevación máxima del terreno entre la costa y la zona (por encima de la zona).

    python -m atlas.relieve [--pais PER]
"""
from __future__ import annotations

import argparse
import json
import math
import urllib.error
import urllib.request
from collections import OrderedDict
from pathlib import Path

import numpy as np

from atlas.rutas import ATLAS, DATOS
from atlas.zonas import cargar_zonas

CACHE = ATLAS / ".cache" / "dem"
URL = "https://copernicus-dem-90m.s3.amazonaws.com/{n}/{n}.tif"
# Cinturón de niebla de las lomas costeras peruanas: base de la capa de estratos ~300 m y techo en la
# inversión ~1000 m (rango habitual en la literatura de lomas; parámetro a calibrar por latitud).
COTA_NIEBLA_MIN = 300.0
COTA_NIEBLA_MAX = 1000.0


def _nombre(lat_floor: int, lon_floor: int) -> str:
    ns = "N" if lat_floor >= 0 else "S"
    ew = "E" if lon_floor >= 0 else "W"
    return f"Copernicus_DSM_COG_30_{ns}{abs(lat_floor):02d}_00_{ew}{abs(lon_floor):03d}_00_DEM"


class Mosaico:
    """Teselas de 1° cargadas bajo demanda (con caché en disco y LRU en memoria). Mar/ausente = 0 m."""

    def __init__(self, max_mem=8):
        self.mem: OrderedDict = OrderedDict()
        self.max_mem = max_mem
        CACHE.mkdir(parents=True, exist_ok=True)

    def _cargar(self, lat_f: int, lon_f: int):
        clave = (lat_f, lon_f)
        if clave in self.mem:
            self.mem.move_to_end(clave)
            return self.mem[clave]
        n = _nombre(lat_f, lon_f)
        ruta = CACHE / f"{n}.tif"
        if not ruta.exists() and not (CACHE / f"{n}.mar").exists():
            try:
                urllib.request.urlretrieve(URL.format(n=n), ruta)
            except urllib.error.HTTPError as e:
                if e.code in (403, 404):            # tesela de océano: no existe
                    (CACHE / f"{n}.mar").touch()
                else:
                    raise
        if ruta.exists():
            import rasterio
            with rasterio.open(ruta) as r:
                z = r.read(1).astype(np.float32)
                tr = r.transform
            z[~np.isfinite(z)] = 0
            z[z < -100] = 0
        else:
            z, tr = None, None
        self.mem[clave] = (z, tr)
        if len(self.mem) > self.max_mem:
            self.mem.popitem(last=False)
        return self.mem[clave]

    def muestrear(self, lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
        """Elevación (vecino más cercano) en puntos arbitrarios."""
        out = np.zeros(len(lon), dtype=np.float32)
        lf, of = np.floor(lat).astype(int), np.floor(lon).astype(int)
        for (a, b) in set(zip(lf.tolist(), of.tolist())):
            sel = (lf == a) & (of == b)
            z, tr = self._cargar(a, b)
            if z is None:
                continue
            col = ((lon[sel] - tr.c) / tr.a).astype(int).clip(0, z.shape[1] - 1)
            fil = ((lat[sel] - tr.f) / tr.e).astype(int).clip(0, z.shape[0] - 1)
            out[sel] = z[fil, col]
        return out


def _rejilla_en_poligono(pol, paso_deg=0.0025):
    """Puntos regulares (~275 m) dentro del polígono de la zona."""
    from shapely import contains_xy
    from shapely.geometry import Polygon
    p = Polygon(pol)
    x0, y0, x1, y1 = p.bounds
    xs = np.arange(x0 + paso_deg / 2, x1, paso_deg)
    ys = np.arange(y0 + paso_deg / 2, y1, paso_deg)
    X, Y = np.meshgrid(xs, ys)
    m = contains_xy(p, X, Y)
    if not m.any():
        c = p.representative_point()
        return np.array([c.x]), np.array([c.y])
    return X[m], Y[m]


def estadisticas_zona(dem: Mosaico, z, costa_lonlat, d=0.0009) -> dict:
    """d ≈ 100 m: separación para diferencias finitas de pendiente/aspecto."""
    lon, lat = _rejilla_en_poligono(z.poligono)
    h = dem.muestrear(lon, lat)
    hx = (dem.muestrear(lon + d, lat) - dem.muestrear(lon - d, lat)) / (2 * d * 111320 * math.cos(math.radians(z.lat)))
    hy = (dem.muestrear(lon, lat + d) - dem.muestrear(lon, lat - d)) / (2 * d * 111320)
    pend = np.degrees(np.arctan(np.hypot(hx, hy)))
    # dirección cuesta abajo (hacia donde "mira" la ladera) y dirección al mar
    abajo = np.arctan2(-hy, -hx)
    cx, cy = costa_lonlat
    al_mar = math.atan2(cy - z.lat, (cx - z.lon) * math.cos(math.radians(z.lat)))
    dif = np.abs((abajo - al_mar + np.pi) % (2 * np.pi) - np.pi)
    barlov = (pend > 3) & (dif < math.radians(60))
    cint = (h >= COTA_NIEBLA_MIN) & (h <= COTA_NIEBLA_MAX)
    # barrera: perfil costa → centro de la zona
    t = np.linspace(0, 1, 60)
    perfil = dem.muestrear(cx + t * (z.lon - cx), cy + t * (z.lat - cy))
    tierra = h > 0
    return {
        "elev_media_m": round(float(h[tierra].mean()) if tierra.any() else 0.0, 1),
        "elev_p10_m": round(float(np.percentile(h, 10)), 1),
        "elev_p90_m": round(float(np.percentile(h, 90)), 1),
        "pendiente_media_grados": round(float(pend.mean()), 2),
        "frac_cinturon_niebla": round(float(cint.mean()), 3),
        "frac_barlovento": round(float(barlov.mean()), 3),
        "frac_loma": round(float((cint & barlov).mean()), 3),
        "barrera_m": round(float(max(perfil.max() - max(float(np.percentile(h, 50)), 0.0), 0.0)), 1),
        "n_muestras": int(len(h)),
    }


def calcular(pais="PER") -> dict:
    zonas = cargar_zonas(pais)
    costa = {}
    for z in sorted(zonas, key=lambda z: z.franja):   # punto de costa de cada tramo ≈ centro de su franja 0
        costa.setdefault(z.tramo, (z.lon, z.lat))
    dem = Mosaico()
    ruta = DATOS / f"relieve_{pais.lower()}.json"
    out = {}
    for i, z in enumerate(zonas):
        out[z.id] = estadisticas_zona(dem, z, costa[z.tramo])
        if i % 200 == 0:
            print(f"{i}/{len(zonas)} zonas", flush=True)
    out["_meta"] = {"fuente": "Copernicus DEM GLO-90 (AWS copernicus-dem-90m)",
                    "cinturon_niebla_m": [COTA_NIEBLA_MIN, COTA_NIEBLA_MAX]}
    ruta.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def cargar(pais="PER") -> dict:
    ruta = DATOS / f"relieve_{pais.lower()}.json"
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pais", default="PER")
    a = ap.parse_args()
    r = calcular(a.pais)
    print(f"{len(r) - 1} zonas con relieve")
