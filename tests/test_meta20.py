"""Tests de los experimentos de la meta de error < 20 puntos."""

import json

import numpy as np

from hefesto.motor import diagnostico as dg
from hefesto.motor import experimentos_neat as ex


def test_piso_menor_que_cualquier_modelo_dentro_de_laboratorio():
    piso = dg.piso_de_ruido()["global"]
    assert piso["piso_inferior_pp"] <= piso["piso_superior_pp"]
    actual = dg.error_actual()["replicas"]["grupos"]
    assert all(piso["piso_inferior_pp"] <= mae for mae in actual.values())


def test_error_actual_reproduce_blur():
    blur = json.loads(dg.RUTA_BLUR.read_text(encoding="utf-8"))
    actual = dg.error_actual()
    for m, v in blur["replicas"]["grupos"]["modelos"].items():
        assert actual["replicas"]["grupos"][m] == round(v["MAE_medio"] * 100, 2)


class _RedFalsa:
    """Red de prueba: devuelve salidas fijas (cierre_max, s)."""

    def __init__(self, cmax, s):
        self.out = [cmax, s]

    def activate(self, _x):
        return self.out


def test_cinetica_monotona_y_acotada():
    unicas = np.zeros((1, 6))
    t = np.array([0.0, 3.0, 7.0, 28.0, 90.0, 480.0])
    inv = np.zeros(len(t), dtype=int)
    pred = ex.predecir_cinetico(_RedFalsa(0.8, 0.5), unicas, inv, t)
    assert pred[0] == 0.0
    assert np.all(np.diff(pred) >= 0)
    assert np.all((pred >= 0) & (pred <= 0.8 + 1e-12))


def test_k_en_rango():
    k = ex.k_desde(np.array([0.0, 0.5, 1.0]))
    assert np.isclose(k[0], ex.K_MIN) and np.isclose(k[-1], ex.K_MAX) and np.all(np.diff(k) > 0)


def test_preparar_agrupa_combinaciones_sin_edad():
    from hefesto.motor.datos import cargar_replicas7, normalizar7

    X, y, g, f = cargar_replicas7()
    unicas, inv, t = ex.preparar(normalizar7(X), X)
    assert unicas.shape[1] == 6 and len(inv) == len(y) and len(unicas) < len(y)
    assert np.array_equal(t, X[:, 1])
