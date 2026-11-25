"""Descarga de capas GIS que no son accesibles desde la nube (ver INVENTARIO_GIS.md).

Solo usa la biblioteca estándar de Python 3.9+ para poder correrlo en cualquier computadora:

    python atlas/descargar_gis.py                # todas las fuentes
    python atlas/descargar_gis.py --solo ingemmet osm

Guarda GeoJSON recortado a la costa en atlas/datos/gis/<fuente>/<capa>.geojson y un
registro de lo descargado en atlas/datos/gis/registro.json.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
SALIDA = RAIZ / "datos" / "gis"
# Franja costera del Atlas (Tumbes–Tacna), con margen. Se recorta finamente después.
BBOX = (-81.6, -18.6, -69.8, -3.2)
UA = "BioCrete-Atlas/1.0 (investigacion academica)"

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


_CONTEXTOS: dict[str, ssl.SSLContext] = {}


def _contexto_con_intermedio(host: str) -> ssl.SSLContext | None:
    """Servidores que no envían su certificado intermedio (frecuente en sitios del Estado).

    Se hace lo mismo que un navegador ("AIA fetching"): se lee la URL del emisor que trae el propio
    certificado del servidor, se descarga ese intermedio y se agrega a las CA de confianza. La
    verificación sigue activa: el intermedio solo se acepta si encadena con una raíz de confianza.
    """
    if host in _CONTEXTOS:
        return _CONTEXTOS[host]
    if not shutil.which("openssl"):
        return None
    pem = ssl.get_server_certificate((host, 443))
    texto = subprocess.run(["openssl", "x509", "-noout", "-text"], input=pem, capture_output=True, text=True).stdout
    m = re.search(r"CA Issuers - URI:(\S+)", texto)
    if not m:
        return None
    crudo = urllib.request.urlopen(urllib.request.Request(m.group(1), headers={"User-Agent": UA}), timeout=60).read()
    inter = crudo.decode() if crudo.lstrip().startswith(b"-----BEGIN") else ssl.DER_cert_to_PEM_cert(crudo)
    ctx = ssl.create_default_context()
    ctx.load_verify_locations(cadata=inter)
    _CONTEXTOS[host] = ctx
    print(f"  · {host}: cadena completada con el intermedio de {m.group(1)}")
    return ctx


def abrir(url: str, datos: bytes | None = None, intentos=3, tiempo=90):
    host = urllib.parse.urlparse(url).hostname or ""
    ctx = _CONTEXTOS.get(host) or ssl.create_default_context()
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, data=datos, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=tiempo, context=ctx) as r:
                return r.read()
        except (ssl.SSLCertVerificationError, urllib.error.URLError) as e:
            causa = getattr(e, "reason", e)
            if not isinstance(causa, ssl.SSLCertVerificationError):
                if i == intentos - 1:
                    raise
                time.sleep(5 * (i + 1))
                continue
            nuevo = _contexto_con_intermedio(host)
            if nuevo is None or nuevo is ctx:
                raise RuntimeError(f"certificado TLS inválido en {url}: {causa}") from e
            ctx = nuevo
        except Exception as e:  # noqa: BLE001
            if i == intentos - 1:
                raise
            time.sleep(5 * (i + 1))


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
            registro[f"{clave}:{servicio}"] = {"estado": "error", "detalle": str(e)}
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
                                                     "archivo": str(destino.relative_to(RAIZ)), "servicio": servicio}
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
                registro[f"osm:{nombre}"] = {"estado": "ok", "elementos": len(feats), "servidor": ep,
                                             "archivo": str(destino.relative_to(RAIZ)), "licencia": "ODbL"}
                print(f"  ✓ {nombre}: {len(feats)} elementos")
                break
            except Exception as e:  # noqa: BLE001
                registro[f"osm:{nombre}"] = {"estado": "error", "detalle": f"{ep}: {e}"}
                print(f"  ✗ {nombre} en {ep}: {e}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo", nargs="*", choices=[*ARCGIS, "osm"], help="fuentes a descargar")
    a = ap.parse_args(argv)
    fuentes = a.solo or [*ARCGIS, "osm"]
    SALIDA.mkdir(parents=True, exist_ok=True)
    ruta_reg = SALIDA / "registro.json"
    registro = json.loads(ruta_reg.read_text(encoding="utf-8")) if ruta_reg.exists() else {}
    for f in fuentes:
        print(f"== {f}")
        fuente_osm(registro) if f == "osm" else fuente_arcgis(f, registro)
    registro["_fecha"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    ruta_reg.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for k, v in registro.items() if isinstance(v, dict) and v.get("estado") == "ok")
    print(f"listo: {ok} capas descargadas → {SALIDA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
