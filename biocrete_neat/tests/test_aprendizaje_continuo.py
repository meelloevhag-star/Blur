"""Tests de la neuroevolución incremental y del registro de versiones."""

import numpy as np

from biocrete_neat import aprendizaje_continuo as ac


def _datos(n_grupos=12, por_grupo=3, semilla=0):
    rng = np.random.default_rng(semilla)
    X = rng.uniform(0, 1, (n_grupos * por_grupo, 6))
    y = np.clip(0.8 - 0.5 * X[:, 0] + 0.2 * X[:, 1], 0, 1)
    g = np.repeat([f"g{i}" for i in range(n_grupos)], por_grupo)
    return X, y, g


def test_arranque_en_caliente_continua_la_generacion():
    X, y, _ = _datos()
    _, _, estado, _ = ac.evolucionar(X, y, gens=3, semilla=1)
    gen_inicial = estado[3]
    _, _, estado2, _ = ac.evolucionar(X, y, gens=3, semilla=2, estado=estado)
    assert estado2[3] > gen_inicial
    assert estado[3] == gen_inicial  # el estado original no se modifica


def test_registro_versiona_y_aplica_control_de_calidad(tmp_path):
    X, y, g = _datos()
    reg = ac.Registro(tmp_path / "reg")
    primero = np.isin(g, [f"g{i}" for i in range(6)])
    idx = np.flatnonzero(primero)
    e1 = ac.actualizar(reg, X[idx], y[idx], g[idx], np.ones(len(idx), bool), "lote 1", gens=3)
    assert e1["aceptado"] and e1["version"] == 1 and e1["r2_prospectivo"]["campeon_vigente"] is None
    assert (tmp_path / "reg" / e1["archivo_estado"]).exists()

    e2 = ac.actualizar(reg, X, y, g, ~primero, "lote 2", gens=3)
    assert e2["version"] == 2
    assert e2["r2_prospectivo"]["campeon_vigente"] is not None
    assert e2["aceptado"] == (e2["r2_prospectivo"]["candidato_caliente"] >= e2["r2_prospectivo"]["campeon_vigente"])

    reg2 = ac.Registro(tmp_path / "reg")
    assert len(reg2.versiones) == 2 and reg2.campeon() is not None
