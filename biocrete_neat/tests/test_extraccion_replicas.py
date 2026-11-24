"""Tests de la extracción de réplicas (F2)."""

import openpyxl
import pytest

from biocrete_neat import extraccion_replicas as ex


@pytest.mark.parametrize("etiqueta,hoja,bact,portador,nutriente,nivel", [
    ("M. A. 67.76 mM/l + 1.74 mM/l Yeast Extract", "Sides no bact", 0, "ninguno", "MA", 0),
    ("M. A. 67.76 mM/l + 1.74 mM/l Yeast Extract + bacteria", "Sides w bact", 1, "hidrogel", "MA", 3),
    ("Control No Nutrients No bacteria", "Sides no bact", 0, "ninguno", "ninguno", 0),
    ("MA 67 with bact", "Bottoms w bact", 1, "hidrogel", "MA", 3),
    ("Hydrogel CL 75 with bact", "Sides w bact", 1, "hidrogel", "CL", 3),
    ("LWA SL 75mM with bacteria", "Sides w bact", 1, "LWA", "SL", 2),
    ("LWA MA 75mM no bacteria", "Sides no bact", 0, "LWA", "MA", 0),
    ("CNC  SL 75 W BACT", "Sides w bact", 1, "CNC", "SL", 2),
    ("CL 75 nutrients and bact", "Sides w bact", 1, "hidrogel", "CL", 3),
    ("SL 75 NUTRIENTS ONLY", "Sides no bact", 0, "ninguno", "SL", 0),
])
def test_clasificacion_etiquetas_mousa(etiqueta, hoja, bact, portador, nutriente, nivel):
    m = ex.clasificar_etiqueta_mousa(etiqueta, hoja)
    assert (m["tiene_bacterias"], m["portador"], m["nutriente"], m["nivel_proteccion"]) == (bact, portador, nutriente, nivel)


@pytest.fixture(scope="module")
def mousa():
    return ex.extraer_mousa_replicas()


def test_mousa_fisuras_unicas_y_edades(mousa):
    fisuras = {r["grupo_probeta"] for r in mousa}
    # 192 fisuras únicas en las 4 pestañas; 1 tiene w0 = 0 ('Sides no bact' fila 25) y se excluye.
    assert len(fisuras) == 191
    assert len(mousa) == 191 * 4
    assert {r["edad_dias"] for r in mousa} == {3, 7, 14, 28}


def test_mousa_cierre_coincide_con_ratio_del_excel(mousa):
    """Las columnas 6–9 del Excel guardan 1 − w_t/w0; el cierre extraído debe coincidir."""
    wb = openpyxl.load_workbook(ex.XLSX_MOUSA, read_only=True, data_only=True)
    filas_hoja = list(wb["Sides no bact"].iter_rows(values_only=True))
    comprobadas = 0
    for r in [x for x in mousa if x["hoja"] == "Sides no bact"][:40]:
        fila = filas_hoja[r["fila_excel"] - 1]
        ratio = fila[6 + ex.EDADES_MOUSA.index(r["edad_dias"])]
        if isinstance(ratio, (int, float)) and 0 <= ratio <= 1:
            assert r["cierre_pct"] == pytest.approx(ratio * 100.0, abs=0.01)
            comprobadas += 1
    assert comprobadas >= 20


@pytest.fixture(scope="module")
def cappellesso():
    return ex.extraer_cappellesso_microscopio()


def test_cappellesso_series_y_ambiente(cappellesso):
    assert cappellesso, "sin registros"
    assert {r["ambiente_marino"] for r in cappellesso} == {1}
    series = {r["hoja"] for r in cappellesso}
    assert series == {f"{a}{h}{w}" for a in ("REF", "BAS", "CA") for h in ("h", "u") for w in ("100", "300")}
    assert all(0.0 <= r["cierre_pct"] <= 100.0 for r in cappellesso)
    assert all(r["edad_dias"] > 0 for r in cappellesso)


def test_cappellesso_ancho_inicial_compatible_con_nominal(cappellesso):
    """El ancho medio inicial por serie debe estar cerca del nominal (100 o 300 µm)."""
    for nominal in (100, 300):
        w0 = [r["w0_mm"] for r in cappellesso if r["hoja"].endswith(str(nominal))]
        media = sum(w0) / len(w0)
        assert 0.5 * nominal / 1000 < media < 1.5 * nominal / 1000


def test_grupos_sin_mezcla_de_fuentes(mousa, cappellesso):
    for r in mousa + cappellesso:
        assert r["grupo_probeta"].startswith(r["fuente"])
