"""Línea de comandos del Atlas.

    python -m atlas ingest              # ¿qué fuentes de Blur cambiaron?
    python -m atlas entrenar            # re-entrena el conjunto (campeón/candidato)
    python -m atlas construir           # recetas por zona → atlas/salida/zonas.geojson
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


def construir(pais="PER"):
    from atlas.optimizar import construir as c
    g = c(pais)
    SALIDA.mkdir(parents=True, exist_ok=True)
    ruta = SALIDA / f"zonas_{pais.lower()}.geojson"
    ruta.write_text(json.dumps(g, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
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
    elif a.cmd == "sync":
        if a.aportes:
            nuevos = importar_aportes(a.aportes)
            if nuevos:
                from biocrete_neat.aportes.validar_aportes import main as validar
                todos = sorted((RAIZ / "biocrete_neat" / "aportes" / "recibidos").glob("*.csv"))
                validar([str(p) for p in todos])
        cambios = detectar_cambios(guardar=True)
        print("fuentes cambiadas:", cambios["cambiadas"] or "ninguna")
        if cambios["cambiadas"] or a.forzar:
            from atlas.modelos import entrenar
            r = entrenar(a.gens)
            print(f"modelo v{r['version']}: aceptado={r['aceptado']} · R² conjunto={r['cv']['conjunto']['R2']}")
            construir(a.pais)
    return 0


if __name__ == "__main__":
    sys.exit(main())
