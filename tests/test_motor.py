"""Tests del motor del núcleo."""

import numpy as np
import pytest

from hefesto.motor.datos import cargar_replicas7
from hefesto.motor.motor import MotorBioCrete


@pytest.fixture(scope="module")
def motor_y_datos():
    X, y, g, f = cargar_replicas7()
    A, B = f == "Mousa2022", f == "Cappellesso2024"
    m = MotorBioCrete(K=2, generaciones=5).ajustar(X[A], y[A])
    return m, X, y, g, A, B


def test_sin_calibrar_da_error_esperado_y_avisa_combinacion(motor_y_datos):
    m, X, y, g, A, B = motor_y_datos
    p = m.predecir(np.array([[0.2, 20, 1, 1, 1, 0, 0]]))[0]
    assert p["modo"].startswith("NEAT global") and p["error_esperado_pp"] == 20.0
    assert any("combinación" in a for a in p["avisos"])  # Mousa no tiene datos marinos


def test_calibrado_da_intervalos_que_contienen_la_prediccion(motor_y_datos):
    m, X, y, g, A, B = motor_y_datos
    loc = B & np.isin(g, np.unique(g[B])[:6])
    m.calibrar(X[loc], y[loc], g[loc])
    p = m.predecir(np.array([[0.2, 90, 1, 1, 0, 1, 0]]))[0]
    assert p["intervalo_80"][0] <= p["cierre_pct"] <= p["intervalo_80"][1]
    assert p["intervalo_90"][0] <= p["intervalo_80"][0] and p["intervalo_80"][1] <= p["intervalo_90"][1]


def test_calibracion_amplia_dominio_y_marca_ancho_marino(motor_y_datos):
    m, *_ = motor_y_datos
    assert m.dominio["w0_max_marino"] is not None
    p = m.predecir(np.array([[0.9, 90, 1, 1, 0, 1, 0]]))[0]
    assert "ancho fuera del rango marino entrenado" in p["avisos"]


def test_guardar_y_cargar(motor_y_datos, tmp_path):
    m, X, *_ = motor_y_datos
    ruta = m.guardar(tmp_path / "motor.pkl")
    m2 = MotorBioCrete.cargar(ruta)
    assert m2.predecir(X[:3]) == m.predecir(X[:3])
