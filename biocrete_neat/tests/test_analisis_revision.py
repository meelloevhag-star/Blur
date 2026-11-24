"""Tests de los análisis de la revisión mayor."""

import csv

import numpy as np

from biocrete_neat import analisis_revision as ar


def test_loso_no_mezcla_fuentes():
    X, y, g, f = ar.cargar_replicas7()
    parts = ar.particiones(X, y, g, "fuente", 1, fuentes=f)
    assert len(parts) == len(np.unique(f))
    for _, _, tr, te in parts:
        assert len(set(f[te])) == 1 and not set(f[tr]) & set(f[te])


def test_grupos_sin_fuga_con_repeticiones():
    X, y, g, _ = ar.cargar_replicas7()
    for _, _, tr, te in ar.particiones(X, y, g, "grupos", 2):
        assert not set(g[tr]) & set(g[te])


def test_confusion_marino_coincide_con_fuente():
    X, y, g, f = ar.cargar_replicas7()
    tabla = ar.tabla_confusion(X, y, f)
    assert tabla["Cappellesso2024"]["ambiente_marino"] == [1]
    assert tabla["Mousa2022"]["ambiente_marino"] == [0]
    assert tabla["Cappellesso2024"]["agente_cristalino"] > 0 and tabla["Mousa2022"]["agente_cristalino"] == 0


def test_nadeau_bengio_detecta_diferencia_y_simetria():
    rng = np.random.default_rng(0)
    a = rng.normal(1.0, 0.05, 25)
    b = a - 0.2
    r = ar.nadeau_bengio(a, b, 100, 400)
    assert r["p"] < 0.05 and r["t"] > 0
    assert ar.nadeau_bengio(b, a, 100, 400)["t"] == -r["t"]


def test_meta_v2_no_imputa_y_respeta_regla_alpha():
    X, y, g, info = ar.cargar_meta_v2("alpha")
    assert info["n_completas"] == len(y) <= info["n_candidatas"]
    assert np.isfinite(X).all() and (0 <= y).all() and (y <= 1).all()
    with open(ar.RUTA_META_V2, encoding="utf-8") as fh:
        filas = list(csv.DictReader(fh))
    usadas = [r for r in filas if r["usar_en_modelo"] == "si" and r["alpha_equiv"].strip()]
    assert all(r["alpha_base"] == "referencia" for r in usadas if r["estudio"] in set(g))


def test_paita_bootstrap_por_grupos_y_rango_marino():
    X, y, g, _ = ar.cargar_replicas7()
    filas = ar.predicciones_paita(X, y, g, B=3)
    por_nombre = {f["escenario"]: f for f in filas}
    assert filas[0]["w0_max_marino_mm"] < 0.5
    assert "c" in por_nombre["Directa · 0,5 mm"]["avisos"] and "c" in por_nombre["Directa · 1,0 mm"]["avisos"]
    assert all("a" in f["avisos"] for f in filas)  # no hay datos marinos con lactato de calcio
