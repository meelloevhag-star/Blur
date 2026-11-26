"""Tests del motor orientado a objetos: red matricial, interfaz común y banco de comparación."""

import neat
import numpy as np
import pytest

from hefesto.motor.datos import cargar_replicas7, normalizar7
from hefesto.motor.modelos import (ConfigNEAT, EvolucionNEAT, HibridoH3, Modelo, NEATConjunto, RedMatricial,
                                   candidatos)


@pytest.fixture(scope="module")
def datos():
    X, y, g, f = cargar_replicas7()
    return X, y, g, f


def test_red_matricial_igual_a_neat_python(datos):
    X, y, *_ = datos
    Xn = normalizar7(X[:300])
    ev = EvolucionNEAT(ConfigNEAT(generaciones=6, ocultos_iniciales=2, conexion_inicial="full_nodirect"))
    ev.ejecutar(Xn, y[:300])
    config, poblacion, *_ = ev.estado
    for g in list(poblacion.values())[:15]:
        a = RedMatricial(g, config)(Xn)
        b = np.array([neat.nn.FeedForwardNetwork.create(g, config).activate(x)[0] for x in Xn])
        assert np.allclose(a, b, atol=1e-12)


def test_matrices_tienen_la_forma_de_las_capas(datos):
    X, y, *_ = datos
    red = EvolucionNEAT(ConfigNEAT(generaciones=4, ocultos_iniciales=3, conexion_inicial="full_nodirect")).ejecutar(
        normalizar7(X[:200]), y[:200])
    for capa in red.matrices():
        W = np.array(capa["W"])
        assert W.shape == (len(capa["nodos"]), len(capa["origenes"]))


def test_todos_los_candidatos_cumplen_la_interfaz(datos):
    X, y, g, _ = datos
    idx = np.arange(0, len(y), 7)
    for m in candidatos(rapido=True):
        assert isinstance(m, Modelo)
        p = m.ajustar(X[idx], y[idx], g[idx]).predecir(X[:50])
        assert p.shape == (50,) and np.all((0 <= p) & (p <= 1))
        assert isinstance(m.complejidad(), dict)


def test_h3_sin_calibrar_es_la_base_y_calibrado_cambia(datos):
    X, y, g, f = datos
    A, B = f == "Mousa2022", f == "Cappellesso2024"
    h3 = HibridoH3(NEATConjunto("NEAT ×2", 2, ConfigNEAT(generaciones=5))).ajustar(X[A], y[A])
    antes = h3.predecir(X[B][:100])
    assert np.allclose(antes, h3.base.predecir(X[B][:100]))
    loc = B & np.isin(g, np.unique(g[B])[:10])
    h3.calibrar(X[loc], y[loc], g[loc])
    assert not np.allclose(antes, h3.predecir(X[B][:100]))


def test_regla_de_eleccion_prefiere_el_mejor_entre_laboratorios():
    from hefesto.motor.banco import Banco
    b = Banco(rapido=True)
    y = b.y
    bueno = {"nombre": "bueno", "precision": {"laboratorio": {"media_MAE_pp": 10.0}}, "mejora": {"10": 10.0},
             "simplicidad": {"conexiones": 3}, "velocidad": {"entrenar_s": 1}, "_pred_lab": y.tolist()}
    malo = {"nombre": "malo", "precision": {"laboratorio": {"media_MAE_pp": 30.0}}, "mejora": {"10": 5.0},
            "simplicidad": {"conexiones": 1}, "velocidad": {"entrenar_s": 0.1},
            "_pred_lab": np.clip(y + 0.3, 0, 1).tolist()}
    assert b.elegir([malo, bueno])["ganador"] == "bueno"
