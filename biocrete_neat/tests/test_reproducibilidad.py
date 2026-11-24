"""Tests de regresión: las cifras del manuscrito deben estar respaldadas por los resultados guardados."""

import json
from pathlib import Path

RES = Path(__file__).resolve().parents[1] / "resultados"


def _resumen() -> dict:
    return json.loads((RES / "resumen_neat.json").read_text(encoding="utf-8"))


def test_corrida_parsimonia_alta_guardada():
    """El artículo (Tabla IV) reporta NEAT con λ_p = 8e-4: R² = 0,540, MAE = 0,104, RMSE = 0,125, 0 ocultas."""
    cv = _resumen()["cv_5fold_alpha_por_lambda"]["0.0008"]
    assert cv["NEAT"] == {"R2": 0.54, "MAE": 0.104, "RMSE": 0.125}
    assert cv["neat_neuronas_ocultas_promedio"] == 0.0


def test_corrida_parsimonia_moderada_guardada():
    """El artículo (Tabla IV) reporta NEAT con λ_p = 1,2e-4: R² = 0,366 con 1,4 ocultas promedio."""
    cv = _resumen()["cv_5fold_alpha_por_lambda"]["0.00012"]
    assert cv["NEAT"]["R2"] == 0.366
    assert cv["neat_neuronas_ocultas_promedio"] == 1.4
    assert cv["Ridge"]["R2"] == 0.523
    assert cv["RandomForest"]["R2"] == 0.514


def test_auditoria_sin_discrepancias():
    """auditar_cifras.py no debe encontrar cifras del manuscrito sin respaldo."""
    from biocrete_neat.auditar_cifras import auditar

    filas = auditar()
    fallos = [f for f in filas if f["estado"] != "OK"]
    assert not fallos, fallos
