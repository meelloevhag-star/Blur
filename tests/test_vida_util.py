"""Tests del horizonte del motor y del modelo de vida útil corregido (adiós a los 150 años)."""

import inspect
import math

import numpy as np
import pytest

from hefesto.durabilidad import exposicion as ex
from hefesto.durabilidad import vida_util as vu
from hefesto.motor.motor import MotorBioCrete
from hefesto.durabilidad.normas import validar_objetivo


def test_motor_no_predice_150_anios():
    X = np.array([[0.3, 28, 1, 1, 0, 0, 0], [0.3, 0.3, 1, 1, 0, 0, 0]] * 10, float)
    X[:, 1] = np.where(np.arange(len(X)) % 2, 14, 28)
    m = MotorBioCrete(K=2, generaciones=3, workers=1).ajustar(X, np.linspace(0.3, 0.6, len(X)))
    p = m.predecir(np.array([[0.3, 150 * 365, 1, 1, 0, 0, 0], [0.3, 20, 1, 1, 0, 0, 0]]))
    assert p[0]["cierre_pct"] is None and p[0]["modo"] == "fuera de horizonte" and "vida_util" in p[0]["motivo"]
    assert p[1]["cierre_pct"] is not None


def test_objetivo_mayor_a_100_se_rechaza():
    with pytest.raises(ValueError, match="ninguna norma"):
        validar_objetivo(150)
    with pytest.raises(ValueError):
        vu.vida_util(0.4, "I", "atmosferico_marino", horizonte=150)


def test_regimen_seco_fuera_de_alcance():
    r = vu.vida_util(0.5, "I", "seco")
    assert r["estado"] == "fuera_de_alcance" and r["anios"] is None
    assert vu.cierre_requerido(0.5, "I", "seco", 25)["estado"] == "fuera_de_alcance"


def test_mas_cierre_nunca_da_menos_anios():
    args = (0.40, "IP", "atmosferico_marino", 30, 22, 65)
    t = [vu._t_inicio(*args, 0.3 * (1 - c)) for c in np.linspace(0, 1, 6)]
    assert all(a <= b for a, b in zip(t, t[1:]))


def test_reparacion_se_cuenta_una_vez():
    assert "agente" not in inspect.signature(vu.vida_util).parameters
    a = vu.vida_util(0.4, "IP", "atmosferico_marino", 30, 22, 65, w0_mm=0.0, cierre_frac=0.0)
    b = vu.vida_util(0.4, "IP", "atmosferico_marino", 30, 22, 65, w0_mm=0.0, cierre_frac=0.9)
    assert a["reporte"] == b["reporte"]  # sin fisura, el cierre no puede sumar años


@pytest.mark.parametrize("cem,reg,ab,cov", [("I", "salpicadura", 0.40, 65), ("IP", "atmosferico_marino", 0.35, 65),
                                            ("IP", "niebla_salina", 0.40, 50), ("I", "atmosferico_marino", 0.50, 50)])
def test_nunca_informa_mas_del_horizonte_sin_etiqueta(cem, reg, ab, cov):
    for w0 in (0.0, 0.3):
        r = vu.vida_util(ab, cem, reg, 100, 22, cov, w0_mm=w0)
        assert r["anios"] is None or r["anios"] <= r["horizonte_anios"]
        if r["anios"] is None and r["estado"] == "cumple":
            assert r["reporte"].startswith("cumple")


def test_fib_sin_tope_reproduce_y_el_tope_corrige():
    # fib B34, CEM I a/c 0,50 (D_RCM,0 = 15,8e-12 m²/s), recubrimiento 50 mm, Ccrit 0,6 %
    assert vu.t_inicio_determinista(15.8e-12, 0.30, 1.5, congelar=False) == pytest.approx(18.3, abs=0.2)
    sin_tope = vu.t_inicio_determinista(15.8e-12, 0.65, 1.5, congelar=False)
    con_tope = vu.t_inicio_determinista(15.8e-12, 0.65, 1.5, congelar=True)
    assert sin_tope > 4000 and con_tope < sin_tope / 25   # 4 364 → 152 años: el tope quita el ×29
    # y aun así la salida nunca informa ese valor: queda como "cumple 40 años"
    assert vu.vida_util(0.35, "IP", "atmosferico_marino", 15, 22, 65, w0_mm=0.0)["anios"] is None


def test_exposicion_regimenes():
    amb = {"viento_medio_ms": 5.0, "frac_horas_niebla": 0.1, "nubes_bajas_media_pct": 40, "frac_horas_hr85": 0.5}
    n = ex.indice_niebla(amb)
    assert ex.regimen(0, 500, n) == "salpicadura"
    assert ex.regimen(2, ex.deposicion_cloruros(60, amb, 0.0), 0.0) == "seco"
    assert math.isfinite(ex.deposicion_cloruros(1.0, amb, n))
