"""
Mapea al esquema unificado los datasets abiertos de cierre de fisuras que se sumaron en la cosecha de
datasets (Zenodo, CC BY 4.0). Solo entra lo que trae las 7 entradas del motor y el cierre medido.

  cristalino_jact     Hermawan, Wiktor, Serna y Gruyaert, "Modification of concrete mix design with crystalline
                      admixture for self-healing improvement", J. Adv. Concr. Technol. 22 (2024) 237,
                      doi 10.3151/jact.22.237; datos 10.5281/zenodo.11064970. Hoja "Permeability": ancho de fisura
                      por disco (promedio de todas las superficies) a 0, 21 y 121 días; mezclas M1–M7.
                      M1 sin aditivo cristalino; M2–M7 con Penetron (hoja "Mix design").

Reglas (las mismas de mapear.py y de las réplicas de Cappellesso):
  · cierre = (w0 − wt)/w0 · 100 por zona o disco, acotado a [0, 100] como en las réplicas existentes;
  · Penetron = agente cristalino 1, protección 0;
  · JACT: sin exposición agresiva → marino 0 y curado previo 0; sin bacterias ni lactato;
  · solo filas de discos ("Disc n"): la hoja trae además un ejemplo de ensayo que no es una probeta.
No se estima ningún valor: lo que la hoja no trae queda fuera.

Descartados (revisados el 27-11-2026):
  · frost salt scaling (10.5281/zenodo.7388208): la hoja no dice cuánto duró el régimen de cicatrización,
    así que no hay edad;
  · ataque por sulfatos (10.5281/zenodo.18277063): las series "healed" son las MISMAS probetas que Cappellesso
    2024 con curado previo a 90 días (380 de 380 zonas con w0 y cierre idénticos): duplicarían datos;
  · footbridge de Jakubovskis y Boris y A465 (Al-Tabbaa et al.): el cierre solo está en figuras, sin w0 numérico.

Uso:
    python -m hefesto.esquema.mapear_datasets_extra
Salida:
    datos/entrantes/datasets_zenodo_2026-11-27.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

import openpyxl

from hefesto.esquema.mapear import CAMPOS, _escribir

RAIZ = Path(__file__).resolve().parents[2]
ZEN = RAIZ / "datos" / "zenodo"
SALIDA = RAIZ / "datos" / "entrantes" / "datasets_zenodo_2026-11-27.csv"


def _cierre(w0: float, wt: float) -> float:
    return round(min(100.0, max(0.0, (w0 - wt) / w0 * 100)), 2)


def _fila(**k) -> dict:
    base = {"dano_tipo": "fisura", "dano_uso": "laboratorio", "procedencia_tipo": "dataset",
            "procedencia_verificado": "si", "procedencia_ambito": "global", "mezcla_familia": "autorreparable",
            "resultado_protocolo": "microscopía óptica superficial (ancho de fisura)"}
    return {**base, **k}


def jact() -> list[dict]:
    wb = openpyxl.load_workbook(ZEN / "cristalino_jact" / "Data paper JACT.xlsx", data_only=True)
    mix = wb["Mix design"]
    nombres = [mix.cell(5, c).value for c in range(4, 11)]                       # M1..M7
    ac = {n: mix.cell(13, c).value for n, c in zip(nombres, range(4, 11))}      # a/c efectiva
    ca = {n: mix.cell(16, c).value for n, c in zip(nombres, range(4, 11))}      # Penetron kg/m3 ('-' = sin)
    filas, mezcla = [], None
    for r in wb["Permeability"].iter_rows(min_row=6, max_row=80, values_only=True):
        if r[1]:
            mezcla = r[1]
        if not (mezcla and str(r[2] or "").startswith("Disc") and isinstance(r[3], (int, float)) and r[3] > 0):
            continue
        w0 = float(r[3]) / 1000
        cristal = 0 if ca[mezcla] in ("-", None, 0) else 1
        for edad, wt in ((21, r[6]), (121, r[9])):
            if not isinstance(wt, (int, float)):
                continue
            filas.append(_fila(
                fuente="Hermawan2024_JACT", id_grupo=f"{mezcla}|{r[2]}", dano_ancho_fisura_mm=f"{w0:.4f}",
                mezcla_a_c=str(ac[mezcla]), mezcla_cemento="CEM III/A 42.5N",
                mezcla_nivel_proteccion="0", mezcla_lactato_calcio="0", mezcla_curado_previo="0",
                mezcla_agente_cristalino=str(cristal), zona_ambiente_marino="0",
                mezcla_aditivos=f"Penetron {ca[mezcla]} kg/m3" if cristal else "",
                resultado_edad_dias=str(edad), resultado_cierre_pct=str(_cierre(w0, float(wt) / 1000)),
                procedencia_doi_o_url="10.5281/zenodo.11064970",
                procedencia_ubicacion=f"Permeability, {mezcla} {r[2]} (todas las superficies)",
                procedencia_notas="Hermawan et al., J. Adv. Concr. Technol. 22 (2024) 237, doi 10.3151/jact.22.237."))
    return filas


def davies_a465() -> list[dict]:
    """Ensayo de campo de la A465 (Davies et al. 2018, datos 10.17035/d.2018.0055749445, CC BY 4.0).
    Solo el panel D (control C40/50 sin aditivos): los A, B y C usan agentes que no son entradas del motor
    (microcápsulas, polímeros con memoria de forma, redes de flujo) y el E quedó bajo carga sostenida.
    Ancho por microscopio (µm) tras descargar y cada mes; el de 2 meses se excluye porque la propia hoja lo
    marca como erróneo. Edades desde la fisuración (Tabla 3 del artículo: 1 mes = 28 días)."""
    ws = openpyxl.load_workbook(ZEN / "davies2018_a465" / "LVDT, Microscope & DEMEC summary.xlsx",
                                data_only=True)["Sheet1"]
    col_d = 7                                                        # columna G: "Panel D" del bloque Microscope
    valores = {ws.cell(f, 1).value or "6-month": ws.cell(f, col_d).value for f in range(20, 27)}
    w0 = float(valores["Unloaded"]) / 1000
    edades = {"1-month": 28, "3-month": 84, "4-month": 112, "5-month": 140, "6-month": 168}
    return [_fila(
        fuente="Davies2018_A465", id_grupo="Panel D (control)", dano_ancho_fisura_mm=f"{w0:.4f}",
        dano_uso="otro", mezcla_a_c="0.43", mezcla_cemento="CEM I", mezcla_nivel_proteccion="0",
        mezcla_lactato_calcio="0", mezcla_curado_previo="0", mezcla_agente_cristalino="0", zona_ambiente_marino="0",
        zona_region="A465 Heads of the Valleys, Gales (Reino Unido)",
        resultado_edad_dias=str(e), resultado_cierre_pct=str(_cierre(w0, float(valores[k]) / 1000)),
        resultado_protocolo="microscopio en campo sobre la fisura del panel",
        procedencia_doi_o_url="10.17035/d.2018.0055749445",
        procedencia_ubicacion=f"ProcessedData/LVDT, Microscope & DEMEC summary.xlsx, Sheet1, Microscope, Panel D, {k}",
        procedencia_notas="Davies et al., Front. Mater. 5:51 (2018). Exposición exterior natural en obra; mezcla "
                          "C40/50 de control (Tabla 1).")
        for k, e in edades.items()]


def main() -> int:
    filas = jact() + davies_a465()
    faltan = [c for f in filas for c in f if c not in CAMPOS]
    if faltan:
        sys.exit(f"campos fuera del esquema: {sorted(set(faltan))}")
    n = _escribir(SALIDA, filas)
    print(f"{SALIDA.relative_to(RAIZ)}: {n} filas (Hermawan 2024 JACT y Davies 2018 A465)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
