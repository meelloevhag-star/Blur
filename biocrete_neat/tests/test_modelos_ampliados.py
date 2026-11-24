"""Tests de la F3: validación agrupada sin fuga y utilidades estadísticas."""

import numpy as np
from sklearn.model_selection import GroupKFold

from biocrete_neat import modelos_ampliados as ma


def test_groupkfold_sin_fuga_en_replicas():
    X, y, grupos, _ = ma.cargar_replicas()
    for tr, te in GroupKFold(n_splits=5).split(X, y, grupos):
        assert not set(grupos[tr]) & set(grupos[te])


def test_normalizacion_fisica_fija_en_rango():
    X, *_ = ma.cargar_replicas()
    Xn = ma.normalizar_replicas(X)
    assert Xn.min() >= 0.0 and Xn.max() <= 1.0
    # Los límites no dependen de los datos: misma fila → mismo valor normalizado
    assert np.allclose(ma.normalizar_replicas(X[:5]), Xn[:5])


def test_bootstrap_ic_contiene_estimacion_puntual():
    rng = np.random.default_rng(0)
    grupos = np.repeat(np.arange(60), 4)
    y = rng.uniform(0, 1, grupos.size)
    pred = y + rng.normal(0, 0.1, grupos.size)
    ic = ma.bootstrap_ic(y, pred, grupos, B=300)
    r2 = ma.metricas(y, pred)["R2"]
    assert ic["R2_IC95"][0] <= r2 <= ic["R2_IC95"][1]


def test_escenarios_paita_marcan_extrapolacion():
    X, y, *_ = ma.cargar_replicas()
    filas = ma.predicciones_paita(X, y, B=3)
    fisura_1mm = next(f for f in filas if "1,0 mm" in f["escenario"])
    assert "fuera del rango" in fisura_1mm["extrapolacion"]
