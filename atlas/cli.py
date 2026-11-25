"""Línea de comandos del Atlas.

    python -m atlas ingest              # ¿qué fuentes de Blur cambiaron?
    python -m atlas entrenar            # re-entrena el conjunto (campeón/candidato)
    python -m atlas construir           # recetas por zona → atlas/salida/zonas_<pais>.geojson (+ web/)
    python -m atlas territorio          # relieve (DEM) + población/urbano + clima por celda
    python -m atlas sync [--aportes DIR] [--forzar]
        1) importa aportes exportados por la API (CSV en DIR) → validar_aportes de Blur
        2) si alguna fuente cambió (o --forzar): entrenar → construir
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from atlas.rutas import RAIZ, SALIDA, DATOS

COLUMNAS_BASE = ["autor_aporte", "institucion", "tipo_fuente", "doi_o_url", "norma_ensayo", "fecha_ensayo",
                 "id_probeta", "a_c", "nivel_proteccion", "ambiente_marino", "usa_lactato", "curado_previo",
                 "w0_mm", "edad_dias", "wt_mm", "cierre_pct", "notas"]


# propiedades que bastan para pintar el mapa (el detalle de cada zona se pide aparte)
LIGERAS = ["id", "pais", "departamento", "provincia", "distrito", "anillo", "q", "r", "frente_marino", "lat", "lon", "dist_mar_km", "regimen",
           "indice_niebla", "deposicion_cl_mg_m2_d", "clase_iso9223", "elevacion_media_m", "frac_loma",
           "poblacion", "clase_urbana", "severidad", "prioridad", "ideal_cierre_pct", "ideal_vida_anios",
           "ideal_costo_m3", "ideal_disponibilidad", "economica_costo_m3", "ideal_cumple_anios", "comun_cumple_anios",
           "vida_util_concreto_comun_anios", "ideal_agente", "ideal_cemento", "ideal_a_c"]


def _slug(texto: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return "".join(c if c.isalnum() else "-" for c in t).strip("-")


def escribir_web(g: dict, pais="PER"):
    """Salida para la web estática: GeoJSON ligero + detalle por departamento (carga bajo demanda)."""
    import shutil
    web = SALIDA / "web"
    shutil.rmtree(web / "detalle", ignore_errors=True)      # departamentos de una corrida anterior
    (web / "detalle").mkdir(parents=True, exist_ok=True)
    ligero = {"type": "FeatureCollection", "metadata": g["metadata"], "features": []}
    por_depto: dict[str, dict] = {}
    for f in g["features"]:
        p = f["properties"]
        slug = _slug(p["departamento"])
        ide = p["recetas"]["ideal"]
        extra = {"detalle": slug, "ideal_agente": ide["agente"], "ideal_cemento": ide["dosificacion"]["cemento_tipo"],
                 "ideal_a_c": ide["dosificacion"]["a_c"]}
        ligero["features"].append({"type": "Feature", "id": f["id"], "geometry": f["geometry"],
                                   "properties": {k: p.get(k) for k in LIGERAS} | extra})
        por_depto.setdefault(slug, {})[p["id"]] = f
    sep = (",", ":")
    (web / f"zonas_ligero_{pais.lower()}.geojson").write_text(json.dumps(ligero, ensure_ascii=False, separators=sep), encoding="utf-8")
    for slug, zonas in por_depto.items():
        (web / "detalle" / f"{slug}.json").write_text(json.dumps(zonas, ensure_ascii=False, separators=sep), encoding="utf-8")


def construir(pais="PER"):
    from atlas.optimizar import construir as c
    g = c(pais)
    SALIDA.mkdir(parents=True, exist_ok=True)
    ruta = SALIDA / f"zonas_{pais.lower()}.geojson"
    ruta.write_text(json.dumps(g, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    escribir_web(g, pais)
    from atlas import terreno
    terreno.generar(pais)
    print(f"{len(g['features'])} zonas → {ruta.relative_to(RAIZ)} (modelo v{g['metadata']['modelo_version']})")
    return ruta


def importar_aportes(carpeta: Path) -> list[Path]:
    """CSV extendidos (API) → plantilla base de Blur + copia íntegra en atlas/datos/aportes_extendidos.csv."""
    archivos = sorted(carpeta.glob("*.csv"))
    if not archivos:
        return []
    base_dir = RAIZ / "biocrete_neat" / "aportes" / "recibidos"
    base_dir.mkdir(parents=True, exist_ok=True)
    ext = DATOS / "aportes_extendidos.csv"
    salidas = []
    for a in archivos:
        with open(a, encoding="utf-8-sig", newline="") as f:
            filas = list(csv.DictReader(f))
        if not filas:
            continue
        destino = base_dir / f"atlas_{a.name}"
        with open(destino, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNAS_BASE, extrasaction="ignore")
            w.writeheader()
            w.writerows(filas)
        nuevo = not ext.exists()
        with open(ext, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
            if nuevo:
                w.writeheader()
            w.writerows(filas)
        salidas.append(destino)
    return salidas


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="atlas")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ingest")
    e = sub.add_parser("entrenar")
    e.add_argument("--gens", type=int, default=40)
    e.add_argument("--rapido", action="store_true")
    c = sub.add_parser("construir")
    c.add_argument("--pais", default="PER")
    t = sub.add_parser("territorio")
    t.add_argument("--pais", default="PER")
    s = sub.add_parser("sync")
    s.add_argument("--aportes", type=Path)
    s.add_argument("--forzar", action="store_true")
    s.add_argument("--gens", type=int, default=40)
    s.add_argument("--pais", default="PER")
    a = ap.parse_args(argv)

    from atlas.ingesta import detectar_cambios
    if a.cmd == "ingest":
        print(json.dumps(detectar_cambios(guardar=False), indent=2))
    elif a.cmd == "entrenar":
        from atlas.modelos import entrenar
        print(json.dumps(entrenar(a.gens, a.rapido)["cv"], indent=2))
    elif a.cmd == "construir":
        construir(a.pais)
    elif a.cmd == "territorio":
        from atlas import ambiente, relieve, urbano
        relieve.calcular(a.pais)
        urbano.calcular(a.pais)
        ambiente.descargar(a.pais)
    elif a.cmd == "sync":
        if a.aportes:
            nuevos = importar_aportes(a.aportes)
            if nuevos:
                from biocrete_neat.aportes.validar_aportes import main as validar
                todos = sorted((RAIZ / "biocrete_neat" / "aportes" / "recibidos").glob("*.csv"))
                validar([str(p) for p in todos])
        # el estado se guarda solo después de entrenar y construir con éxito: si algo falla,
        # el próximo sync vuelve a ver las fuentes como nuevas
        cambios = detectar_cambios(guardar=False)
        print("fuentes cambiadas:", cambios["cambiadas"] or "ninguna")
        if cambios["cambiadas"] or a.forzar:
            from atlas.modelos import entrenar
            r = entrenar(a.gens)
            print(f"modelo v{r['version']}: aceptado={r['aceptado']} · R² conjunto={r['cv']['conjunto']['R2']}")
            construir(a.pais)
        detectar_cambios(guardar=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
