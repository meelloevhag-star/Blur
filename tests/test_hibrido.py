"""Tests del híbrido NEAT → árboles y de la predicción conforme."""

import numpy as np
from sklearn.ensemble import RandomForestRegressor

from hefesto.motor import hibrido as hb


def test_conforme_cubre_en_datos_sinteticos():
    rng = np.random.default_rng(0)
    por_grupo = 6
    g = np.repeat([f"g{i}" for i in range(30)], por_grupo)
    X = rng.uniform(0, 1, (len(g), 7))
    y = np.clip(0.5 + 0.3 * X[:, 0] + rng.normal(0, 0.05, len(g)), 0, 1)
    base = np.full(len(g), 0.5)  # predicción base deliberadamente sesgada
    idx = np.arange(len(g))
    cal, te = idx[: 20 * por_grupo], idx[20 * por_grupo:]
    q = hb.conforme_residual(X, y, g, cal, base, alfas=(0.1,))
    rf = RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=hb.SEMILLA)
    rf.fit(X[cal], y[cal] - base[cal])
    pred = np.clip(base[te] + rf.predict(X[te]), 0, 1)
    assert np.mean(np.abs(y[te] - pred) <= q[0.1]) >= 0.8


def test_conforme_requiere_al_menos_tres_grupos():
    g = np.array(["a", "a", "b", "b"])
    assert hb.conforme_residual(np.zeros((4, 7)), np.zeros(4), g, np.arange(4), np.zeros(4)) == {}


def test_peso_de_contraccion_crece_con_n():
    pesos = [n / (n + hb.K_CONTRACCION) for n in (0, 2, 5, 10, 20, 40)]
    assert pesos[0] == 0 and all(np.diff(pesos) > 0) and pesos[-1] < 1
