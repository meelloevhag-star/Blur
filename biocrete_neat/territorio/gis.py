"""Blur · capas GIS (ArcGIS REST del Estado y OpenStreetMap). Inventario en INVENTARIO_GIS.md.

Solo usa la biblioteca estándar, para poder correrlo en cualquier computadora o en GitHub Actions:

    python -m biocrete_neat.territorio gis                 # todas las fuentes
    python -m biocrete_neat.territorio gis --solo ingemmet osm

Guarda GeoJSON en biocrete_neat/datos/territorio/gis/<fuente>/<capa>.geojson y anota cada capa en el
registro común de Blur (registro.json). Cada corrida reemplaza lo que había de esa fuente.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse

from biocrete_neat.territorio.red import abrir
from biocrete_neat.territorio.registro import DIR, RAIZ, Registro

SALIDA = DIR / "gis"
# Franja costera del Atlas (Tumbes–Tacna), con margen. Se recorta finamente después.
BBOX = (-81.6, -18.6, -69.8, -3.2)

ARCGIS = {
    "ingemmet": [
        "https://geocatmin.ingemmet.gob.pe/arcgis/rest/services/SERV_ROCAS_MINERALES_INDUSTRIALES/MapServer",
    ],
    "minam": [
        "https://geoservidorperu.minam.gob.pe/arcgis/rest/services/ServicioPMIZMC/MapServer",
    ],
    # INEI (arcgis.inei.gob.pe:6443) no resuelve en internet público: las manzanas 2025 se toman de SIGRID
}
FILTRO_CAPAS: dict[str, re.Pattern] = {}

OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
CONSULTAS_OSM = {
    "plantas_concreto": 'nwr["industrial"="concrete_plant"]({b});nwr["man_made"="works"]["product"~"concrete|cement",i]({b});nwr["landuse"="industrial"]["name"~"concret|premezcl|cement",i]({b});',
    "canteras": 'nwr["landuse"="quarry"]({b});',
    "puertos": 'nwr["industrial"="port"]({b});nwr["landuse"="port"]({b});nwr["harbour"]({b});',
    "puentes": 'way["bridge"="yes"]["highway"~"motorway|trunk|primary|secondary"]({b});',
}


def capas_arcgis(servicio: str) -> list[dict]:
    d = json.loads(abrir(servicio + "?f=pjson"))
    return [l for l in d.get("layers", []) if not l.get("subLayerIds")]


def descargar_capa(servicio: str, capa: dict) -> dict:
    url = f"{servicio}/{capa['id']}/query"
    base = {"where": "1=1", "geometry": ",".join(map(str, BBOX)), "geometryType": "esriGeometryEnvelope",
            "inSR": "4326", "spatialRel": "esriSpatialRelIntersects", "outFields": "*", "returnGeometry": "true",
            "outSR": "4326", "f": "geojson"}
    ids = json.loads(abrir(url + "?" + urllib.parse.urlencode(base | {"returnIdsOnly": "true", "f": "json"})))
    oids = sorted(ids.get("objectIds") or [])
    campo = ids.get("objectIdFieldName", "OBJECTID")
    feats = []
    for k in range(0, len(oids), 500):          # por bloques de ids: evita el límite de registros
        lote = oids[k:k + 500]
        q = base | {"where": f"{campo} >= {lote[0]} AND {campo} <= {lote[-1]}"}
        feats += json.loads(abrir(url + "?" + urllib.parse.urlencode(q))).get("features", [])
    return {"type": "FeatureCollection", "features": feats}


def nombre_archivo(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", texto.lower()).strip("_")[:60] or "capa"


def fuente_arcgis(clave: str, registro: dict):
    for servicio in ARCGIS[clave]:
        try:
            capas = capas_arcgis(servicio)
        except Exception as e:  # noqa: BLE001
            registro[f"{clave}:{servicio}"] = {"estado": "error", "detalle": str(e), "url": servicio}
            print(f"  ✗ {servicio}: {e}")
            continue
        for c in capas:
            if clave in FILTRO_CAPAS and not FILTRO_CAPAS[clave].search(c["name"]):
                continue
            try:
                fc = descargar_capa(servicio, c)
                destino = SALIDA / clave / f"{c['id']}_{nombre_archivo(c['name'])}.geojson"
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
                registro[f"{clave}:{c['name']}"] = {"estado": "ok", "elementos": len(fc["features"]),
                                                     "archivo": str(destino.relative_to(RAIZ)), "url": servicio}
                print(f"  ✓ {c['name']}: {len(fc['features'])} elementos")
            except Exception as e:  # noqa: BLE001
                registro[f"{clave}:{c['name']}"] = {"estado": "error", "detalle": str(e)}
                print(f"  ✗ {c['name']}: {e}")


def fuente_osm(registro: dict):
    b = f"{BBOX[1]},{BBOX[0]},{BBOX[3]},{BBOX[2]}"
    for nombre, cuerpo in CONSULTAS_OSM.items():
        q = f"[out:json][timeout:300];({cuerpo.format(b=b)});out center tags;"
        for ep in OVERPASS:
            try:
                d = json.loads(abrir(ep, urllib.parse.urlencode({"data": q}).encode(), tiempo=320))
                feats = []
                for e in d.get("elements", []):
                    lat = e.get("lat", e.get("center", {}).get("lat"))
                    lon = e.get("lon", e.get("center", {}).get("lon"))
                    if lat is None:
                        continue
                    feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
                                  "properties": {"osm_id": f"{e['type']}/{e['id']}", **e.get("tags", {})}})
                destino = SALIDA / "osm" / f"{nombre}.geojson"
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False),
                                   encoding="utf-8")
                registro[f"osm:{nombre}"] = {"estado": "ok", "elementos": len(feats), "url": ep,
                                             "archivo": str(destino.relative_to(RAIZ)), "licencia": "ODbL"}
                print(f"  ✓ {nombre}: {len(feats)} elementos")
                break
            except Exception as e:  # noqa: BLE001
                registro[f"osm:{nombre}"] = {"estado": "error", "detalle": f"{ep}: {e}"}
                print(f"  ✗ {nombre} en {ep}: {e}")


LICENCIAS = {"ingemmet": "datos abiertos del Estado peruano (INGEMMET, GEOCATMIN)",
             "minam": "datos abiertos del Estado peruano (MINAM)", "osm": "ODbL (© colaboradores de OpenStreetMap)"}


def recolectar(solo: list[str] | None = None) -> dict:
    reg = Registro()
    for f in solo or [*ARCGIS, "osm"]:
        print(f"== {f}")
        capas: dict = {}
        fuente_osm(capas) if f == "osm" else fuente_arcgis(f, capas)
        # en OSM se prueban varios servidores: un error previo se borra si otro servidor respondió
        reg.reemplazar(f"gis:{f}", {k: v | {"licencia": LICENCIAS[f]} for k, v in capas.items()})
    reg.guardar()
    return reg.datos


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo", nargs="*", choices=[*ARCGIS, "osm"], help="fuentes a descargar")
    a = ap.parse_args(argv)
    recolectar(a.solo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
