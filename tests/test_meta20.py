"""Tests de los experimentos de la meta de error < 20 puntos."""

import json

import numpy as np

from hefesto.motor import diagnostico as dg


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
