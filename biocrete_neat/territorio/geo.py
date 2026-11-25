"""Blur · geografía base: costa, país, departamentos y distritos, ciudades y vías.

  - Natural Earth 10m (dominio público): costa, país, departamentos, ciudades y vías.
  - Distritos INEI (UBIGEO) desde github.com/juaneladio/peru-geojson.
Los archivos crudos se bajan a biocrete_neat/datos/territorio/crudo/ (no se versiona) y lo
recortado al país queda en biocrete_neat/datos/territorio/geo/.

    python -m biocrete_neat.territorio geo [--forzar]
"""
from __future__ import annotations

import json
import zipfile

from biocrete_neat.territorio.red import bajar_archivo
from biocrete_neat.territorio.registro import DIR, Registro, huella

GEO = DIR / "geo"
CRUDO = DIR / "crudo"
NE = "https://naciscdn.org/naturalearth/10m/{tema}/{capa}.zip"
CAPAS_NE = {"ne_10m_admin_0_countries": "cultural", "ne_10m_admin_1_states_provinces": "cultural",
            "ne_10m_coastline": "physical", "ne_10m_populated_places": "cultural", "ne_10m_roads": "cultural"}
DISTRITOS = "https://raw.githubusercontent.com/juaneladio/peru-geojson/master/peru_distrital_simple.geojson"
ARCHIVOS = ["costa", "pais", "departamentos", "distritos", "ciudades", "vias"]


def _natural_earth() -> str:
    for capa, tema in CAPAS_NE.items():
        carpeta = CRUDO / "naturalearth" / capa
        if (carpeta / f"{capa}.shp").exists():
            continue
        carpeta.mkdir(parents=True, exist_ok=True)
        z = carpeta.with_suffix(".zip")
        bajar_archivo(NE.format(tema=tema, capa=capa), z)
        with zipfile.ZipFile(z) as f:
            f.extractall(carpeta)
        z.unlink()
    return str(CRUDO / "naturalearth")


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


def ciudades_y_vias(dir_ne: str, pais: str = "PER"):
    """Ciudades (populated places) y vías de Natural Earth dentro del país."""
    import shapefile
    from shapely.geometry import shape, mapping
    poli = shape(json.loads((GEO / f"pais_{pais.lower()}.geojson").read_text(encoding="utf-8"))["geometry"]).buffer(0.05)
    pp = shapefile.Reader(f"{dir_ne}/ne_10m_populated_places/ne_10m_populated_places.shp", encoding="utf-8")
    lugares = [{"nombre": s.record["NAME"], "pob": int(s.record["POP_MAX"]), "lon": s.shape.points[0][0],
                "lat": s.shape.points[0][1]} for s in pp.iterShapeRecords() if s.record["ADM0_A3"] == pais]
    (GEO / f"ciudades_{pais.lower()}.json").write_text(json.dumps(
        {"fuente": "Natural Earth 10m populated places (dominio público)", "lugares": lugares}, ensure_ascii=False),
        encoding="utf-8")
    rd = shapefile.Reader(f"{dir_ne}/ne_10m_roads/ne_10m_roads.shp", encoding="utf-8")
    feats = []
    for s in rd.iterShapeRecords():
        g = shape(s.shape.__geo_interface__)
        if g.intersects(poli):
            feats.append({"type": "Feature", "properties": {"nombre": s.record["name"] or "", "tipo": s.record["type"]},
                          "geometry": mapping(g.intersection(poli))})
    (GEO / f"vias_{pais.lower()}.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "fuente": "Natural Earth 10m roads (dominio público)", "features": feats},
        ensure_ascii=False), encoding="utf-8")


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


def recolectar(pais: str = "PER", forzar: bool = False) -> dict:
    GEO.mkdir(parents=True, exist_ok=True)
    faltan = [a for a in ARCHIVOS if not any(GEO.glob(f"{a}_{pais.lower()}.*"))]
    error = None
    if forzar or faltan:
        try:
            ne = _natural_earth()
            construir_costa(ne, pais)
            ciudades_y_vias(ne, pais)
            crudo = CRUDO / "peru_distrital_simple.geojson"
            if forzar or not crudo.exists():
                bajar_archivo(DISTRITOS, crudo)
            importar_distritos(str(crudo), pais)
        except Exception as e:  # noqa: BLE001
            error = str(e)
    archivos = {p.name: huella(p) for p in sorted(GEO.glob(f"*_{pais.lower()}.*"))}
    reg = Registro()
    reg.reemplazar("geo", {"estado": "error" if error else "ok", "url": "https://www.naturalearthdata.com · " + DISTRITOS,
                           "licencia": "Natural Earth: dominio público · distritos INEI vía juaneladio/peru-geojson",
                           "archivos": archivos, **({"detalle": error} if error else {})})
    reg.guardar()
    return archivos
