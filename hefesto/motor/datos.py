"""Carga y normalización de las réplicas de cierre de fisuras (7 entradas, límites físicos fijos).

Copiado de meelloevhag-star/Blur (commit bf6000d), biocrete_neat/analisis_revision.py. No editar sin actualizar la procedencia.
"""

import csv
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
RUTA_REPLICAS = RAIZ / "datos" / "replicas_cierre_fisuras.csv"
VARS_R = ['Ancho fisura w0 (mm)', 'Edad (d)', 'Protección bio (0-3)', 'Ambiente marino', 'Lactato de calcio', 'Curado previo', 'Agente cristalino']
MIN_R = np.zeros(7)
MAX_R = np.array([1.0, 480.0, 3.0, 1.0, 1.0, 1.0, 1.0])


def cargar_replicas7(ruta: Path = RUTA_REPLICAS):
    with open(ruta, encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))
    X = np.array([[float(r["w0_mm"]), float(r["edad_dias"]), float(r["nivel_proteccion"]), float(r["ambiente_marino"]),
                   float(r["usa_lactato"] or 0), 1.0 if r["regimen"] == "curado_previo" else 0.0,
                   1.0 if r["portador"] == "cristalino" else 0.0] for r in filas])
    y = np.array([float(r["cierre_pct"]) / 100.0 for r in filas])
    return X, y, np.array([r["grupo_probeta"] for r in filas]), np.array([r["fuente"] for r in filas])


def normalizar7(X):
    return np.clip((X - MIN_R) / (MAX_R - MIN_R), 0.0, 1.0)
