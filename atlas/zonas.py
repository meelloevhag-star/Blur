"""Zonas costeras: tramos de ~10 km a lo largo de la costa y 6 franjas tierra adentro.

La línea de costa se obtiene una sola vez de Natural Earth 10m (dominio público) y se guarda
recortada y simplificada en atlas/datos/geo/. Todo está parametrizado por país (ISO-3) para
poder sumar Ecuador, Chile, etc. sin cambiar código.

    python -m atlas.zonas --ne /ruta/a/naturalearth --pais PER
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, asdict

from atlas.rutas import GEO

# Franjas de distancia al mar (km). La 1.ª concentra mareas/salpicadura; las siguientes cubren la
# costa urbana, los cerros y las lomas (cinturón de niebla, ≈ 2–30 km tierra adentro).
FRANJAS_KM = [(0.0, 0.5), (0.5, 2.0), (2.0, 5.0), (5.0, 10.0), (10.0, 20.0), (20.0, 35.0)]
PASO_KM = 10.0
R_TIERRA = 6371.0


@dataclass
class Zona:
    id: str
    pais: str
    departamento: str
    franja: int
    dist_mar_km: float          # distancia representativa (centro de franja)
    lat: float
    lon: float
    poligono: list               # [[lon, lat], ...] cerrado
    tramo: int = 0
    provincia: str = ""
    distrito: str = ""
    ubigeo: str = ""


def _km(lat0):
    """km por grado (lat, lon) alrededor de lat0."""
    return 111.32, 111.32 * math.cos(math.radians(lat0))


def _dist(a, b):
    ky, kx = _km((a[1] + b[1]) / 2)
    return math.hypot((a[0] - b[0]) * kx, (a[1] - b[1]) * ky)


def _remuestrear(linea, paso):
    """Puntos equiespaciados cada `paso` km a lo largo de una polilínea [[lon,lat],...]."""
    out = [linea[0]]
    resto = 0.0
    for p, q in zip(linea, linea[1:]):
        d = _dist(p, q)
        t = paso - resto
        while t <= d:
            f = t / d
            out.append([p[0] + f * (q[0] - p[0]), p[1] + f * (q[1] - p[1])])
            t += paso
        resto = (resto + d) % paso if d else resto
        resto = d - (t - paso)
    return out


def construir_costa(dir_ne: str, pais: str = "PER"):
    """Recorta la costa de Natural Earth al país y guarda costa_<pais>.geojson y límites."""
    import shapefile
    from shapely.geometry import shape, LineString, mapping
    from shapely.ops import linemerge, unary_union

    adm0 = shapefile.Reader(f"{dir_ne}/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp", encoding="utf-8")
    poli = next(shape(s.shape.__geo_interface__) for s in adm0.iterShapeRecords() if s.record["ADM0_A3"] == pais)
    adm1 = shapefile.Reader(f"{dir_ne}/ne_10m_admin_1_states_provinces/ne_10m_admin_1_states_provinces.shp",
                            encoding="utf-8")
    deptos = [{"type": "Feature", "properties": {"nombre": s.record["name"], "pais": pais},
               "geometry": mapping(shape(s.shape.__geo_interface__).simplify(0.01))}
              for s in adm1.iterShapeRecords() if s.record["adm0_a3"] == pais]

    costa = shapefile.Reader(f"{dir_ne}/ne_10m_coastline/ne_10m_coastline.shp")
    borde = poli.buffer(0.02)
    tramos = []
    for s in costa.shapes():
        g = LineString(s.points).intersection(borde)
        if not g.is_empty:
            tramos.append(g)
    linea = linemerge(unary_union(tramos))
    if linea.geom_type == "MultiLineString":
        linea = max(linea.geoms, key=lambda g: g.length)   # costa continental (descarta islotes)
    coords = [list(c) for c in linea.simplify(0.002).coords]
    if coords[0][1] < coords[-1][1]:
        coords.reverse()                                   # de norte a sur
    GEO.mkdir(parents=True, exist_ok=True)
    (GEO / f"costa_{pais.lower()}.geojson").write_text(json.dumps(
        {"type": "Feature", "properties": {"pais": pais, "fuente": "Natural Earth 10m coastline (dominio público)"},
         "geometry": {"type": "LineString", "coordinates": coords}}), encoding="utf-8")
    (GEO / f"departamentos_{pais.lower()}.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "features": deptos}, ensure_ascii=False), encoding="utf-8")
    (GEO / f"pais_{pais.lower()}.geojson").write_text(json.dumps(
        {"type": "Feature", "properties": {"pais": pais}, "geometry": mapping(poli.simplify(0.01))}), encoding="utf-8")


def _desplazar(p, normal, km):
    ky, kx = _km(p[1])
    return [p[0] + normal[0] * km / kx, p[1] + normal[1] * km / ky]


def generar_zonas(pais: str = "PER") -> list[Zona]:
    from shapely.geometry import shape, Point

    costa = json.loads((GEO / f"costa_{pais.lower()}.geojson").read_text(encoding="utf-8"))["geometry"]["coordinates"]
    poli = shape(json.loads((GEO / f"pais_{pais.lower()}.geojson").read_text(encoding="utf-8"))["geometry"])
    deptos = [(f["properties"]["nombre"], shape(f["geometry"])) for f in
              json.loads((GEO / f"departamentos_{pais.lower()}.geojson").read_text(encoding="utf-8"))["features"]]
    distritos = _distritos(pais)

    pts = _remuestrear(costa, PASO_KM / 2)   # puntos a medio paso: pares = centros, impares = bordes
    # normales hacia tierra
    normales = []
    for i, p in enumerate(pts):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        ky, kx = _km(p[1])
        tx, ty = (b[0] - a[0]) * kx, (b[1] - a[1]) * ky
        n = math.hypot(tx, ty) or 1.0
        cand = (-ty / n, tx / n)
        prueba = _desplazar(p, cand, 3.0)
        if not poli.contains(Point(prueba)):
            cand = (ty / n, -tx / n)
        normales.append(cand)

    zonas = []
    for k, i in enumerate(range(1, len(pts) - 1, 2)):
        izq, cen, der = i - 1, i, i + 1
        for f, (d0, d1) in enumerate(FRANJAS_KM):
            anillo = [_desplazar(pts[izq], normales[izq], d0), _desplazar(pts[der], normales[der], d0),
                      _desplazar(pts[der], normales[der], d1), _desplazar(pts[izq], normales[izq], d1)]
            anillo.append(anillo[0])
            dm = (d0 + d1) / 2
            c = _desplazar(pts[cen], normales[cen], dm)
            depto = next((n for n, g in deptos if g.contains(Point(c))), None)
            if depto is None:  # punto de la 1.ª franja cae en el mar por la simplificación
                depto = min(deptos, key=lambda d: d[1].distance(Point(c)))[0]
            dist = _distrito_de(distritos, c)
            zonas.append(Zona(id=f"{pais}-{k:03d}-{f}", pais=pais, departamento=dist[3] or depto, franja=f,
                              dist_mar_km=round(dm, 2), lat=round(c[1], 4), lon=round(c[0], 4),
                              poligono=[[round(x, 5), round(y, 5)] for x, y in anillo], tramo=k,
                              provincia=dist[1], distrito=dist[0], ubigeo=dist[2]))
    return _sin_solapes(zonas, poli)


def _sin_solapes(zonas: list[Zona], pais_poli) -> list[Zona]:
    """En curvas cerradas de la costa las franjas de tramos vecinos se cruzan. Se corrige así:
    polígonos válidos, recortados a tierra, y cada zona pierde el área ya asignada a otra
    (las franjas más cercanas al mar tienen prioridad). Las zonas que quedan vacías se descartan."""
    from shapely.geometry import Polygon, Point
    from shapely.ops import unary_union
    tierra = pais_poli.buffer(0.004)
    ocupado = None
    salida = []
    for z in sorted(zonas, key=lambda z: (z.franja, z.tramo)):
        g = Polygon(z.poligono).buffer(0).intersection(tierra)
        if ocupado is not None:
            g = g.difference(ocupado)
        if g.is_empty or g.area < 1e-6:
            continue
        parte = max(getattr(g, "geoms", [g]), key=lambda x: x.area)
        if parte.geom_type != "Polygon":
            continue
        ocupado = parte if ocupado is None else unary_union([ocupado, parte])
        c = parte.representative_point() if not parte.contains(Point(z.lon, z.lat)) else Point(z.lon, z.lat)
        # redondear puede volver inválido el anillo: se repara y se guarda la parte mayor
        r = Polygon([(round(x, 5), round(y, 5)) for x, y in parte.exterior.coords]).buffer(0)
        r = max(getattr(r, "geoms", [r]), key=lambda x: x.area)
        z.poligono = [[x, y] for x, y in r.exterior.coords]
        z.lat, z.lon = round(c.y, 4), round(c.x, 4)
        salida.append(z)
    return sorted(salida, key=lambda z: (z.tramo, z.franja))


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


def importar_distritos(ruta_geojson: str, pais: str = "PER"):
    """Distritos de INEI (juaneladio/peru-geojson, campos IDDIST/NOMBDIST/NOMBPROV/NOMBDEP) → GEO, simplificados."""
    from shapely.geometry import shape, mapping
    src = json.loads(open(ruta_geojson, encoding="utf-8").read())
    feats = []
    for f in src["features"]:
        if not f.get("geometry"):
            continue
        p = f["properties"]
        feats.append({"type": "Feature", "properties": {
            "ubigeo": p["IDDIST"], "distrito": p["NOMBDIST"].title(), "provincia": p["NOMBPROV"].title(),
            "departamento": p["NOMBDEP"].title()},
            "geometry": mapping(shape(f["geometry"]).simplify(0.002))})
    (GEO / f"distritos_{pais.lower()}.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "fuente": "INEI vía github.com/juaneladio/peru-geojson", "features": feats},
        ensure_ascii=False), encoding="utf-8")


def guardar_zonas(zonas: list[Zona], pais: str = "PER"):
    ruta = GEO / f"zonas_{pais.lower()}.json"
    ruta.write_text(json.dumps([asdict(z) for z in zonas], ensure_ascii=False), encoding="utf-8")
    return ruta


def cargar_zonas(pais: str = "PER") -> list[Zona]:
    return [Zona(**z) for z in json.loads((GEO / f"zonas_{pais.lower()}.json").read_text(encoding="utf-8"))]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ne", help="carpeta con los shapefiles de Natural Earth descomprimidos")
    ap.add_argument("--pais", default="PER")
    ap.add_argument("--distritos", help="GeoJSON de distritos (UBIGEO) a importar")
    a = ap.parse_args()
    if a.ne:
        construir_costa(a.ne, a.pais)
    if a.distritos:
        importar_distritos(a.distritos, a.pais)
    z = generar_zonas(a.pais)
    print(f"{len(z)} zonas → {guardar_zonas(z, a.pais)}")
