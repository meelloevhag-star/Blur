"""Zonas costeras: malla hexagonal de 10 km sobre la franja de 35 km tierra adentro.

La costa, el país, los departamentos y los distritos los recoge Blur
(python -m biocrete_neat.territorio geo → biocrete_neat/datos/territorio/geo/); aquí solo se leen
para armar la malla, que se guarda en atlas/datos/zonas_<pais>.json. Todo está parametrizado por
país (ISO-3) para poder sumar Ecuador, Chile, etc. sin cambiar código.

    python -m atlas.zonas --pais PER
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, asdict

from atlas.rutas import DATOS, GEO

# Malla hexagonal: celdas de TAM_HEX_KM entre lados planos (10 km ≈ 87 km²) hasta PROF_KM tierra adentro.
TAM_HEX_KM = 10.0
PROF_KM = 35.0
MIN_FRAC = 0.15            # una celda entra si al menos este % de su área cae en la franja costera
DIST_FRENTE_KM = 0.25      # distancia de evaluación del frente marino (salpicadura, < 500 m)
R_TIERRA = 6371.0


@dataclass
class Zona:
    id: str
    pais: str
    departamento: str
    dist_mar_km: float          # distancia del centro de la celda al mar
    lat: float
    lon: float
    poligono: list               # [[lon, lat], ...] cerrado
    anillo: int = 0             # 0 = la celda toca el mar; 1, 2… celdas hacia el interior
    q: int = 0                  # coordenadas axiales del hexágono
    r: int = 0
    dist_mar_min_km: float = 0.0
    frente_marino: bool = False  # la celda tiene orilla: se evalúa también a < 500 m del mar
    provincia: str = ""
    distrito: str = ""
    ubigeo: str = ""


def _proyeccion():
    """Lambert acimutal equivalente centrada en Perú: km reales y áreas iguales en toda la costa."""
    from pyproj import Transformer
    crs = "+proj=laea +lat_0=-10 +lon_0=-76 +units=km +ellps=WGS84"
    return (Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform,
            Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform)


def _hexagono(q, r, s):
    """Hexágono de punta arriba; s = distancia centro-vértice (km)."""
    cx, cy = s * math.sqrt(3) * (q + r / 2), s * 1.5 * r
    return cx, cy, [(cx + s * math.cos(math.radians(60 * k - 30)), cy + s * math.sin(math.radians(60 * k - 30)))
                    for k in range(6)]


VECINOS = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]


def generar_zonas(pais: str = "PER", tam_km: float = TAM_HEX_KM, prof_km: float = PROF_KM) -> list[Zona]:
    """Hexágonos de `tam_km` (entre lados planos) que cubren tierra ∩ [0, prof_km] km del mar.

    El lado del mar se recorta a la costa; el lado interior queda como hexágono entero. Los
    pedazos con menos de MIN_FRAC de su área en la franja se suman al vecino con el que más borde
    comparten, así la cobertura queda continua, sin huecos ni solapes."""
    from shapely.geometry import shape, Point, Polygon, LineString
    from shapely.ops import transform, unary_union
    from collections import deque

    a_proj, a_geo = _proyeccion()
    costa_ll = json.loads((GEO / f"costa_{pais.lower()}.geojson").read_text(encoding="utf-8"))["geometry"]["coordinates"]
    pais_ll = shape(json.loads((GEO / f"pais_{pais.lower()}.geojson").read_text(encoding="utf-8"))["geometry"])
    deptos = [(f["properties"]["nombre"], shape(f["geometry"])) for f in
              json.loads((GEO / f"departamentos_{pais.lower()}.geojson").read_text(encoding="utf-8"))["features"]]
    distritos = _distritos(pais)
    costa = transform(a_proj, LineString(costa_ll))
    tierra = transform(a_proj, pais_ll).buffer(0)
    franja = tierra.intersection(costa.buffer(prof_km))

    s = tam_km / math.sqrt(3)
    area_hex = 1.5 * math.sqrt(3) * s * s
    x0, y0, x1, y1 = franja.bounds
    r0, r1 = int(y0 / (1.5 * s)) - 2, int(y1 / (1.5 * s)) + 2
    celdas, sobras = {}, {}
    from shapely.prepared import prep
    pf = prep(franja)
    for r in range(r0, r1 + 1):
        q0 = int((x0 / (s * math.sqrt(3))) - r / 2) - 2
        q1 = int((x1 / (s * math.sqrt(3))) - r / 2) + 2
        for q in range(q0, q1 + 1):
            cx, cy, vs = _hexagono(q, r, s)
            h = Polygon(vs)
            if not pf.intersects(h):
                continue
            dentro = h.intersection(franja)
            if dentro.is_empty:
                continue
            if dentro.area >= MIN_FRAC * area_hex:
                celdas[(q, r)] = h.intersection(tierra)        # recorte solo contra el mar / fronteras
            else:
                sobras[(q, r)] = dentro
    # pedazos chicos → vecino aceptado con el que más borde comparten
    for (q, r), g in sobras.items():
        vec = [(q + dq, r + dr) for dq, dr in VECINOS if (q + dq, r + dr) in celdas]
        if not vec:
            continue
        mejor = max(vec, key=lambda k: celdas[k].intersection(g.buffer(1e-3)).length + celdas[k].buffer(1e-3).intersection(g).area)
        celdas[mejor] = unary_union([celdas[mejor], g])
    # la parte principal de cada celda (descarta islotes sueltos)
    for k, g in list(celdas.items()):
        g = g.buffer(0)
        celdas[k] = max(getattr(g, "geoms", [g]), key=lambda x: x.area)
    # anillos: celdas con orilla = 0; el resto por saltos de vecino
    anillo = {}
    cola = deque()
    for k, g in celdas.items():
        if g.distance(costa) < 0.5:
            anillo[k] = 0
            cola.append(k)
    while cola:
        q, r = cola.popleft()
        for dq, dr in VECINOS:
            n = (q + dq, r + dr)
            if n in celdas and n not in anillo:
                anillo[n] = anillo[(q, r)] + 1
                cola.append(n)

    zonas = []
    for (q, r), g in sorted(celdas.items(), key=lambda kv: (-kv[0][1], kv[0][0])):
        c = g.centroid if g.contains(g.centroid) else g.representative_point()
        lon, lat = a_geo(c.x, c.y)
        ll = transform(a_geo, g).simplify(0.0003)
        ll = max(getattr(ll.buffer(0), "geoms", [ll.buffer(0)]), key=lambda x: x.area)
        anillo_ll = [[round(x, 5), round(y, 5)] for x, y in ll.exterior.coords]
        depto = next((n for n, gd in deptos if gd.contains(Point(lon, lat))), None) or \
            min(deptos, key=lambda d: d[1].distance(Point(lon, lat)))[0]
        dist = _distrito_de(distritos, (lon, lat))
        zonas.append(Zona(id=f"{pais}-H{q}_{r}", pais=pais, departamento=dist[3] or depto,
                          dist_mar_km=round(c.distance(costa), 2), lat=round(lat, 4), lon=round(lon, 4),
                          poligono=anillo_ll, anillo=anillo.get((q, r), max(1, round(g.distance(costa) / tam_km))), q=q, r=r,
                          dist_mar_min_km=round(g.distance(costa), 2), frente_marino=anillo.get((q, r)) == 0,
                          provincia=dist[1], distrito=dist[0], ubigeo=dist[2]))
    return zonas


def _distritos(pais: str):
    """Límites distritales (UBIGEO) desde GEO/distritos_<pais>.geojson si existe (ver construir_costa)."""
    from shapely.geometry import shape
    from shapely.strtree import STRtree
    ruta = GEO / f"distritos_{pais.lower()}.geojson"
    if not ruta.exists():
        return None
    feats = json.loads(ruta.read_text(encoding="utf-8"))["features"]
    geoms = [shape(f["geometry"]) for f in feats]
    return STRtree(geoms), geoms, [f["properties"] for f in feats]


def _distrito_de(distritos, c):
    from shapely.geometry import Point
    if distritos is None:
        return ("", "", "", "")
    arbol, geoms, props = distritos
    p = Point(c)
    cand = [i for i in arbol.query(p) if geoms[i].contains(p)]
    i = cand[0] if cand else int(arbol.nearest(p))
    pr = props[i]
    return (pr.get("distrito", ""), pr.get("provincia", ""), pr.get("ubigeo", ""), pr.get("departamento", ""))


def guardar_zonas(zonas: list[Zona], pais: str = "PER"):
    ruta = DATOS / f"zonas_{pais.lower()}.json"
    ruta.write_text(json.dumps([asdict(z) for z in zonas], ensure_ascii=False), encoding="utf-8")
    return ruta


def cargar_zonas(pais: str = "PER") -> list[Zona]:
    return [Zona(**z) for z in json.loads((DATOS / f"zonas_{pais.lower()}.json").read_text(encoding="utf-8"))]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pais", default="PER")
    a = ap.parse_args()
    z = generar_zonas(a.pais)
    print(f"{len(z)} zonas → {guardar_zonas(z, a.pais)}")
