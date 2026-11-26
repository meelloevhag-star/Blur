"""Tests del esquema, el curador y el orquestador."""

import numpy as np

from hefesto.agentes import curador, orquestador
from hefesto.esquema import mapear
from hefesto.motor.motor import MotorBioCrete

BUENA = {"fuente": "Lab Paita", "id_grupo": "P01", "zona_ambiente_marino": "1", "dano_tipo": "fisura",
         "dano_ancho_fisura_mm": "0.2", "mezcla_nivel_proteccion": "1", "mezcla_lactato_calcio": "1",
         "resultado_edad_dias": "28", "resultado_cierre_pct": "61.5", "procedencia_doi_o_url": "https://x.edu.pe/t",
         "procedencia_tipo": "laboratorio", "procedencia_ubicacion": "hoja 1", "procedencia_verificado": "si"}


def test_curador_acepta_fila_buena():
    reg, errores = curador.validar_fila(dict(BUENA))
    assert reg is not None and not errores and reg["resultado_cierre_pct"] == 61.5


def test_curador_rechaza_sin_doi_y_fuera_de_rango():
    assert curador.validar_fila({**BUENA, "procedencia_doi_o_url": "sin enlace"})[0] is None
    assert curador.validar_fila({**BUENA, "resultado_cierre_pct": "140"})[0] is None
    assert curador.validar_fila({**BUENA, "campo_inventado": "1"})[0] is None


def test_curador_rechaza_incoherencia_bacteria():
    _, errores = curador.validar_fila({**BUENA, "mezcla_nivel_proteccion": "0", "mezcla_bacteria_especie": "B. subtilis"})
    assert errores and "sin bacterias" in errores[0]


def test_mapeo_cumple_esquema():
    for fila in mapear.mapear_replicas()[:50] + mapear.mapear_literatura()[:50]:
        texto = {k: ("" if v is None else str(v)) for k, v in fila.items()}
        assert curador.validar_fila(texto)[0] is not None, curador.validar_fila(texto)[1]


def test_orquestador_mapa_de_necesidades_prioriza_sin_soporte():
    X = np.array([[0.2, 28, 1, 0, 1, 0, 0], [0.3, 28, 2, 0, 0, 0, 0], [0.1, 14, 0, 0, 0, 0, 0]] * 10, float)
    y = np.linspace(0.2, 0.8, len(X))
    m = MotorBioCrete(K=2, generaciones=3).ajustar(X, y)
    nec = orquestador.mapa_necesidades(m, X)
    assert nec and nec[0]["filas_de_soporte"] == 0
    assert nec == sorted(nec, key=lambda c: -c["puntaje"])
