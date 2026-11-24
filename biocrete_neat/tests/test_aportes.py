"""Tests del validador de aportes de terceros."""

import csv

from biocrete_neat.aportes.validar_aportes import validar_archivos, validar_fila

BASE = {"autor_aporte": "Perez", "institucion": "UPC", "tipo_fuente": "tesis",
        "doi_o_url": "https://repositorio.upc.edu.pe/x", "norma_ensayo": "EN 12390-8", "fecha_ensayo": "2026-05-01",
        "id_probeta": "P1", "a_c": "0.55", "nivel_proteccion": "1", "ambiente_marino": "1", "usa_lactato": "1",
        "curado_previo": "0", "w0_mm": "0.20", "edad_dias": "28", "wt_mm": "0.08", "cierre_pct": "", "notas": ""}


def test_fila_valida_se_acepta_y_calcula_cierre():
    fila, motivos = validar_fila(dict(BASE))
    assert not motivos
    assert fila["cierre_pct"] == 60.0
    assert fila["grupo_probeta"] == "aporte:Perez|P1"
    assert fila["ambiente_marino"] == 1 and fila["usa_lactato"] == 1


def test_fila_de_ejemplo_se_rechaza():
    _, motivos = validar_fila({**BASE, "notas": "Fila de ejemplo: borrar"})
    assert any("ejemplo" in m for m in motivos)


def test_rangos_y_tipos():
    assert validar_fila({**BASE, "w0_mm": "5"})[0] is None
    assert validar_fila({**BASE, "nivel_proteccion": "7"})[0] is None
    assert validar_fila({**BASE, "edad_dias": "abc"})[0] is None
    assert validar_fila({**BASE, "doi_o_url": "sin enlace"})[0] is None
    assert validar_fila({**BASE, "tipo_fuente": "blog"})[0] is None


def test_cierre_inconsistente_se_rechaza():
    _, motivos = validar_fila({**BASE, "cierre_pct": "95"})
    assert motivos and "no coincide" in motivos[0]


def test_duplicados_se_rechazan(tmp_path):
    ruta = tmp_path / "aporte.csv"
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(BASE))
        w.writeheader()
        w.writerow(BASE)
        w.writerow(BASE)
    aceptadas, rechazadas = validar_archivos([ruta])
    assert len(aceptadas) == 1 and len(rechazadas) == 1
