"""Pruebas del Atlas. El fixture de paridad lo usa también la prueba de Go (api/internal/modelo)."""
import json
from pathlib import Path

import numpy as np
import pytest

from atlas import niebla as nb
from atlas.diseno_mezcla import dosificar, fc_estimado
from atlas.durabilidad import vida_util, ajuste_drcm
from atlas.ingesta import NOMBRES_CIERRE, dataset_cierre, vector_cierre
from atlas.normas import reglas
from atlas.rutas import MODELOS, SALIDA
from atlas.viabilidad import catalogo

FIXTURE = Path(__file__).parent / "fixture_paridad.json"


def test_dataset_cierre_lee_blur():
    X, y, g, f = dataset_cierre()
    assert X.shape[1] == len(NOMBRES_CIERRE)
    assert len(y) > 2000 and 0 <= y.min() and y.max() <= 1
    assert {"Mousa2022", "Cappellesso2024"} <= set(f)


def test_reglas_mas_estrictas_en_salpicadura():
    assert reglas("salpicadura")["a_c_max"] < reglas("atmosferico_marino")["a_c_max"] < reglas("seco")["a_c_max"]


def test_dosificacion_suma_un_m3():
    c = catalogo()
    r = dosificar(0.45, 19.0, c["cementos"]["IP"] | {"id": "IP"}, 320,
                  {"arena": c["agregados"]["arena"], "piedra": c["agregados"]["piedra_34"]})
    vol = (r["agua_kg"] / 1000 + r["cemento_kg"] / 2850 + r["piedra_kg"] / 2680 + r["arena_kg"] / 2620
           + r["aire_pct"] / 100)
    assert abs(vol - 1.0) < 1e-3   # cantidades redondeadas a 0,1 kg
    assert fc_estimado(0.40) > fc_estimado(0.50)


def test_vida_util_monotona():
    a = vida_util(0.40, "HS", "salpicadura", 500, 20, 65, 0.45)
    b = vida_util(0.50, "HS", "salpicadura", 500, 20, 65, 0.45)
    assert a >= b
    assert vida_util(0.45, "I", "salpicadura", 500, 20, 65, 0.3, cierre_frac=0.9) >= \
        vida_util(0.45, "I", "salpicadura", 500, 20, 65, 0.3, cierre_frac=0.0)
    assert ajuste_drcm()["b"] > 0      # más a/c → más difusión


def test_deposicion_decae_y_niebla_la_extiende():
    amb = {"viento_medio_ms": 5, "frac_horas_niebla": 0.1, "nubes_bajas_media_pct": 40, "frac_horas_hr85": 0.8}
    seco = {"viento_medio_ms": 5, "frac_horas_niebla": 0.0, "nubes_bajas_media_pct": 0, "frac_horas_hr85": 0.0}
    assert nb.deposicion_cloruros(0.1, amb, 1) > nb.deposicion_cloruros(5, amb, 1)
    assert nb.deposicion_cloruros(10, amb, nb.indice_niebla(amb)) > nb.deposicion_cloruros(10, seco, nb.indice_niebla(seco))


@pytest.mark.skipif(not (MODELOS / "modelo_cierre.json").exists(), reason="sin modelo exportado")
def test_fixture_paridad_go():
    """Genera/actualiza el fixture que la prueba de Go compara con tolerancia 1e-9."""
    from atlas.modelos import ModeloCierre, evaluar_neat_json, evaluar_xgb_json
    m = ModeloCierre()
    rng = np.random.default_rng(0)
    casos = []
    for _ in range(50):
        port = ["ninguno", "cristalino", "Basilisk", "LWA", "hidrogel", "CNC"][rng.integers(6)]
        x = vector_cierre(float(rng.uniform(0.05, 0.8)), float(rng.choice([7, 28, 90, 180])), port,
                          int(rng.integers(2)), ["ninguno", "lactato"][rng.integers(2)], int(rng.integers(2)),
                          int(rng.integers(2)))
        xn = np.clip(np.array(x) / m.max, 0, 1)
        bs = np.clip([evaluar_xgb_json(t, 0.5, xn) for t in m.p["xgb"]["bootstrap"]], 0, 1)
        casos.append({"x": x, "xgb_media": float(bs.mean()), "neat": float(evaluar_neat_json(m.p["neat"], xn))})
    FIXTURE.write_text(json.dumps(casos), encoding="utf-8")
    assert all(0 <= c["xgb_media"] <= 1 for c in casos)


@pytest.mark.skipif(not (SALIDA / "zonas_per.geojson").exists(), reason="sin salida construida")
def test_geojson_recetas_completas():
    g = json.loads((SALIDA / "zonas_per.geojson").read_text(encoding="utf-8"))
    assert len(g["features"]) > 300
    for f in g["features"]:
        p = f["properties"]
        for tipo in ("ideal", "economica", "disponible"):
            r = p["recetas"][tipo]
            assert r["agente"] != "ninguno"
            assert r["dosificacion"]["a_c"] <= p["reglas"]["a_c_max"] + 1e-9
            assert r["viabilidad"]["costo_m3_pen"] > 0
