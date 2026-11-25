"""Ingesta incremental de las fuentes de Blur declaradas en fuentes.yaml.

Cada fuente se identifica por la huella SHA-256 de su contenido. `atlas ingest` compara con el
estado guardado (atlas/datos/estado_ingesta.json) y devuelve qué fuentes cambiaron, para que
`atlas sync` re-entrene solo cuando hay datos nuevos.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import yaml

from atlas.rutas import ATLAS, DATOS, RAIZ

RUTA_ESTADO = DATOS / "estado_ingesta.json"
PORTADORES = ["ninguno", "cristalino", "Basilisk", "LWA", "hidrogel", "CNC"]


def cargar_fuentes() -> list[dict]:
    return yaml.safe_load((ATLAS / "fuentes.yaml").read_text(encoding="utf-8"))["fuentes"]


def huella(ruta: Path) -> str | None:
    if not ruta.exists():
        return None
    h = hashlib.sha256()
    archivos = sorted(p for p in ruta.rglob("*") if p.is_file()) if ruta.is_dir() else [ruta]
    for p in archivos:
        h.update(p.relative_to(ruta if ruta.is_dir() else ruta.parent).as_posix().encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def expandir(f: dict) -> list[dict]:
    """Una entrada con comodines (`*`, `**`) se expande en una fuente por archivo, con id `<id>:<ruta>`.
    Así, los CSV que agreguen los agentes de Blur (tras aprobar su PR) entran sin editar este archivo."""
    if not any(c in f["ruta"] for c in "*?["):
        return [f]
    out = []
    for p in sorted(RAIZ.glob(f["ruta"])):
        if p.is_file():
            rel = p.relative_to(RAIZ).as_posix()
            out.append(f | {"id": f"{f['id']}:{rel}", "ruta": rel})
    return out


def fuentes_expandidas() -> list[dict]:
    return [g for f in cargar_fuentes() for g in expandir(f)]


def detectar_cambios(guardar: bool = True) -> dict:
    previo = json.loads(RUTA_ESTADO.read_text(encoding="utf-8")) if RUTA_ESTADO.exists() else {}
    actual, cambios = {}, []
    for f in fuentes_expandidas():
        h = huella(RAIZ / f["ruta"])
        actual[f["id"]] = h
        if h != previo.get(f["id"]):
            cambios.append(f["id"])
    cambios += [k for k in previo if k not in actual]      # fuentes que desaparecieron
    if guardar:
        DATOS.mkdir(parents=True, exist_ok=True)
        RUTA_ESTADO.write_text(json.dumps(actual, indent=2), encoding="utf-8")
    return {"huellas": actual, "cambiadas": cambios}


def _leer(f: dict) -> list[dict]:
    ruta = RAIZ / f["ruta"]
    if not ruta.exists() or ruta.stat().st_size == 0:
        return []
    with open(ruta, encoding="utf-8-sig", newline="") as fh:
        filas = list(csv.DictReader(fh))
    m = f.get("columnas", {})
    return [{k: r.get(v, "") for k, v in m.items()} | {"_fuente_atlas": f["id"]} for r in filas]


def filas_por_tipo(tipo: str) -> list[dict]:
    out = []
    for f in fuentes_expandidas():
        if f["tipo"] == tipo and f.get("entrena"):
            out += _leer(f)
    return out


def _num(x, defecto=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return defecto


def vector_cierre(w0, edad, portador, bacterias, nutriente, marino, curado) -> list[float]:
    """Esquema de entrada del modelo de cierre (orden fijo; ver NOMBRES_CIERRE)."""
    onehot = [1.0 if portador == p else 0.0 for p in PORTADORES]
    return [w0, edad, *onehot, float(bacterias), 0.0 if nutriente in ("", "ninguno") else 1.0,
            float(marino), float(curado)]


NOMBRES_CIERRE = ["w0_mm", "edad_dias", *[f"portador_{p}" for p in PORTADORES],
                  "tiene_bacterias", "tiene_nutriente", "ambiente_marino", "curado_previo"]
# límites físicos fijos para normalizar (sin fuga entre particiones)
MAX_CIERRE = np.array([1.0, 480.0] + [1.0] * (len(NOMBRES_CIERRE) - 2))


def dataset_cierre():
    """X (crudo), y (0-1), grupos, fuentes a partir de todas las fuentes 'replicas_cierre'."""
    X, y, g, fu = [], [], [], []
    for r in filas_por_tipo("replicas_cierre"):
        if r["cierre_pct"] in ("", None) or r["w0_mm"] in ("", None):
            continue
        port = r["portador"] if r["portador"] in PORTADORES else "ninguno"
        X.append(vector_cierre(_num(r["w0_mm"]), _num(r["edad_dias"]), port, _num(r["tiene_bacterias"]),
                               r["nutriente"] or "ninguno", _num(r["ambiente_marino"]),
                               1.0 if r["regimen"] == "curado_previo" else 0.0))
        y.append(max(0.0, min(1.0, _num(r["cierre_pct"]) / 100.0)))
        g.append(r["grupo"] or f"{r['_fuente_atlas']}|{len(g)}")
        fu.append(r["fuente"] or r["_fuente_atlas"])
    return np.array(X), np.array(y), np.array(g), np.array(fu)


def normalizar_cierre(X: np.ndarray) -> np.ndarray:
    return np.clip(X / MAX_CIERRE, 0.0, 1.0)


if __name__ == "__main__":
    print(json.dumps(detectar_cambios(), indent=2))
