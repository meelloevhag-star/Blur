"""Fondo del mapa: relieve sombreado (hillshade) de la costa desde el DEM Copernicus en caché.

Genera una sola imagen PNG con transparencia en proyección Web Mercator (filas equiespaciadas en y
de Mercator), para superponerla en Leaflet con L.imageOverlay sin desalinearse. Solo sombras (negro
con alfa) para que funcione sobre el tema claro y el oscuro.

    python -m atlas.fondo [--res 0.006]
"""
from __future__ import annotations

import argparse
import json
import math

import numpy as np

from atlas.relieve import CACHE as DEM_CACHE
from atlas.rutas import RAIZ

SALIDA = RAIZ / "web" / "public" / "fondo"


def _merc_y(lat):
    return np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))


def _mascara_costa(lons, lats, ancho, alto, margen_deg=0.12, difuminado_px=18):
    from PIL import Image, ImageDraw, ImageFilter
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from atlas.zonas import cargar_zonas
    banda = unary_union([Polygon(z.poligono) for z in cargar_zonas()]).buffer(margen_deg)
    m = Image.new("L", (ancho, alto), 0)
    d = ImageDraw.Draw(m)
    lon0, lon1 = lons[0], lons[-1]
    y0, y1 = _merc_y(lats[-1]), _merc_y(lats[0])

    def px(x, y):
        return ((x - lon0) / (lon1 - lon0) * (ancho - 1),
                (y1 - _merc_y(np.array(y))) / (y1 - y0) * (alto - 1))
    for g in getattr(banda, "geoms", [banda]):
        d.polygon([px(x, y) for x, y in g.exterior.coords], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(difuminado_px))
    return np.asarray(m, dtype=np.float32) / 255.0


def generar(res=0.006, lat0=-18.6, lat1=-3.2, lon0=-81.5, lon1=-69.6):
    import rasterio
    from PIL import Image
    ancho = int((lon1 - lon0) / res)
    y0, y1 = _merc_y(lat0), _merc_y(lat1)
    alto = int(ancho * (y1 - y0) / math.radians(lon1 - lon0))
    lats = np.degrees(2 * np.arctan(np.exp(np.linspace(y1, y0, alto))) - np.pi / 2)
    lons = np.linspace(lon0, lon1, ancho)
    z = np.zeros((alto, ancho), dtype=np.float32)
    hay = np.zeros((alto, ancho), dtype=bool)
    for t in sorted(DEM_CACHE.glob("*.tif")):
        with rasterio.open(t) as r:
            a = r.read(1).astype(np.float32)
            tr = r.transform
        a[~np.isfinite(a)] = 0
        b = r.bounds
        ci = np.flatnonzero((lons >= b.left) & (lons < b.right))
        fi = np.flatnonzero((lats > b.bottom) & (lats <= b.top))
        if not len(ci) or not len(fi):
            continue
        cc = ((lons[ci] - tr.c) / tr.a).astype(int).clip(0, a.shape[1] - 1)
        ff = ((lats[fi] - tr.f) / tr.e).astype(int).clip(0, a.shape[0] - 1)
        z[np.ix_(fi, ci)] = a[np.ix_(ff, cc)]
        hay[np.ix_(fi, ci)] = True
    # hillshade con luz del noroeste (azimut 315°, altura 45°)
    dx = res * 111320 * np.cos(np.radians(lats))[:, None]
    dy = np.abs(np.gradient(lats))[:, None] * 111320
    gy, gx = np.gradient(z * 2.0)          # exageración vertical ×2 para leer cerros a escala país
    sx, sy = gx / dx, -gy / dy
    pend = np.arctan(np.hypot(sx, sy))
    aspecto = np.arctan2(sy, -sx)
    az, alt = np.radians(315.0), np.radians(45.0)
    luz = np.sin(alt) * np.cos(pend) + np.cos(alt) * np.sin(pend) * np.cos(az - np.pi / 2 - aspecto)
    sombra = np.clip(1 - luz, 0, 1)
    sombra = np.clip((sombra - 0.25) / 0.75, 0, 1) ** 1.2
    # se desvanece suavemente fuera de la franja de 35 km del Atlas (sin bordes de tesela)
    mascara = _mascara_costa(lons, lats, ancho, alto)
    alfa = (sombra * 190 * mascara).astype(np.uint8)
    alfa[~hay | (z <= 0)] = 0
    rgba = np.zeros((alto, ancho, 4), dtype=np.uint8)
    rgba[..., 3] = alfa
    SALIDA.mkdir(parents=True, exist_ok=True)
    img = Image.fromarray(rgba, "RGBA")
    ruta = SALIDA / "relieve.png"
    img.save(ruta, optimize=True)
    (SALIDA / "relieve.json").write_text(json.dumps({
        "limites": [[lat0, lon0], [lat1, lon1]], "ancho": ancho, "alto": alto,
        "fuente": "Copernicus DEM GLO-90, sombreado del Atlas"}), encoding="utf-8")
    return ruta


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", type=float, default=0.006)
    a = ap.parse_args()
    r = generar(a.res)
    print(r, r.stat().st_size // 1024, "KB")


def portada(lon0=-77.62, lon1=-77.02, lat0=-11.62, lat1=-11.12, nx=180, ny=110, nombre="lachay"):
    """Rejilla de alturas para la portada (relieve grabado): mar al frente (oeste) y lomas detrás.

    Filas = distancia tierra adentro (oeste→este), columnas = a lo largo de la costa (sur→norte).
    """
    from atlas.relieve import Mosaico
    dem = Mosaico(max_mem=8)
    lons = np.linspace(lon0, lon1, ny)          # filas: del mar hacia el interior
    lats = np.linspace(lat0, lat1, nx)          # columnas
    L, A = np.meshgrid(lons, lats, indexing="ij")
    h = dem.muestrear(L.ravel(), A.ravel()).reshape(L.shape)
    SALIDA.mkdir(parents=True, exist_ok=True)
    datos = {"nombre": nombre, "nx": nx, "ny": ny, "lon": [lon0, lon1], "lat": [lat0, lat1],
             "h": np.round(np.where(h > 0, h, -1)).astype(int).ravel().tolist(),
             "fuente": "Copernicus DEM GLO-90", "lugar": "Lomas de Lachay, Huaura (Lima)"}
    (SALIDA / f"portada_{nombre}.json").write_text(json.dumps(datos, separators=(",", ":")), encoding="utf-8")
    return datos


def curvas(paso_m=100, max_m=2500, paso_px=3, buffer_km=40.0, tolerancia=0.0018, pais="PER"):
    """Curvas de nivel del DEM de Blur en la franja costera → web/public/fondo/curvas.json.

    Formato compacto: {"paso": 100, "maestra": 500, "lineas": [[cota, [lon, lat, lon, lat, ...]], ...]}.
    Cada tesela se submuestrea (~270 m), se enmascara fuera de `buffer_km` del mar y se contornea con
    matplotlib; las líneas se simplifican (Douglas-Peucker) y se redondean a 3 decimales.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import rasterio
    from shapely import contains_xy
    from shapely.geometry import LineString, shape
    from atlas.rutas import GEO
    costa = LineString(json.loads((GEO / f"costa_{pais.lower()}.geojson").read_text(encoding="utf-8"))["geometry"]["coordinates"])
    tierra = shape(json.loads((GEO / f"pais_{pais.lower()}.geojson").read_text(encoding="utf-8"))["geometry"])
    franja = tierra.intersection(costa.buffer(buffer_km / 111.0)).buffer(0.01)
    niveles = list(range(paso_m, max_m + 1, paso_m))
    lineas = []
    for t in sorted(DEM_CACHE.glob("*.tif")):
        with rasterio.open(t) as r:
            a = r.read(1).astype(np.float32)[::paso_px, ::paso_px]
            tr = r.transform
        lon = tr.c + tr.a * paso_px * (np.arange(a.shape[1]) + 0.5)
        lat = tr.f + tr.e * paso_px * (np.arange(a.shape[0]) + 0.5)
        X, Y = np.meshgrid(lon, lat)
        dentro = contains_xy(franja, X, Y)
        if not dentro.any():
            continue
        a[~np.isfinite(a)] = 0
        a = np.where(dentro, a, np.nan)
        fig = plt.figure()
        cs = plt.contour(X, Y, a, levels=[n for n in niveles if n <= np.nanmax(a)] or [niveles[0]])
        for cota, segs in zip(cs.levels, cs.allsegs):
            for s in segs:
                if len(s) < 4:
                    continue
                g = LineString(s).simplify(tolerancia)
                if g.length < 0.01:
                    continue
                plano = [round(v, 3) for xy in g.coords for v in xy]
                lineas.append([int(cota), plano])
        plt.close(fig)
    SALIDA.mkdir(parents=True, exist_ok=True)
    ruta = SALIDA / "curvas.json"
    ruta.write_text(json.dumps({"paso": paso_m, "maestra": 500, "franja_nubes": [300, 1000],
                                "fuente": "Copernicus DEM GLO-90 (vía Blur), curvas del Atlas", "lineas": lineas},
                               separators=(",", ":")), encoding="utf-8")
    return ruta
