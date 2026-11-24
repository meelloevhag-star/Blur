"""
F2 · Extracción de réplicas individuales desde los repositorios crudos ya descargados.

Fuentes:
  - Mousa et al. (Zenodo 10.5281/zenodo.6469122): una fila por fisura (ancho a 0, 3, 7, 14 y 28 días),
    pestañas "Sides/Bottoms no/w bact". Las pestañas se solapan; se deduplica por la tupla de anchos.
  - Cappellesso et al. (Zenodo 10.5281/zenodo.11305154): microscopía de fisuras en ambiente marino
    (ASTM D1141), 15 probetas por serie y hasta 8 zonas por probeta, varias fechas.

Salida: datos/replicas_cierre_fisuras.csv (una fila por fisura/zona y edad), con IDs de grupo
para validación cruzada agrupada (sin fuga entre edades de la misma fisura o probeta).

Uso:
    python -m biocrete_neat.extraccion_replicas
"""

import csv
import re
import statistics
from pathlib import Path

import openpyxl

RUTA_BASE = Path(__file__).resolve().parent
BASE_ZENODO = RUTA_BASE.parent / "datasets_reales_zenodo"
RUTA_SALIDA = RUTA_BASE / "datos" / "replicas_cierre_fisuras.csv"

XLSX_MOUSA = (BASE_ZENODO / "Encapsulated_Bacteria_Optimal_SH" / "extraido"
              / "All cracks summary combined Hydrogel LWA CNC (version 2).xlsx")
XLSX_CAPPELLESSO = BASE_ZENODO / "Cappellesso2024_Marine_CAB_Cloruros" / "02_Mar_Microscope measurements.xlsx"

DOI_MOUSA = "10.5281/zenodo.6469122"
DOI_CAPPELLESSO = "10.5281/zenodo.11305154"

HOJAS_MOUSA = ["Sides no bact", "Sides w bact", "Bottoms no bact", "Bottoms w bact"]
EDADES_MOUSA = [3, 7, 14, 28]  # columnas 2..5 de cada fila (0 días en la columna 1)

CAMPOS = [
    "fuente", "doi", "hoja", "fila_excel", "etiqueta_original", "grupo_condicion", "grupo_probeta",
    "portador", "nivel_proteccion", "tiene_bacterias", "nutriente", "concentracion_mM", "usa_lactato",
    "ambiente_marino", "regimen", "ubicacion", "w0_mm", "edad_dias", "wt_mm", "cierre_pct",
]


# ---------------------------------------------------------------------------
# Mousa et al. (2022)
# ---------------------------------------------------------------------------

def clasificar_etiqueta_mousa(etiqueta: str, hoja: str) -> dict:
    """
    Traduce la etiqueta de muestra de Mousa a variables físicas.

    Reglas (desde las pestañas y la hoja 'ALL' del propio archivo):
      - Bacterias: 'with bact' / 'w bact' / '+ bacteria' / 'and bact' -> 1; el resto -> 0.
      - Portador: 'Hydrogel' -> hidrogel; 'LWA' -> agregado liviano; 'CNC' -> nanocelulosa.
        En la serie sin prefijo, las muestras con bacterias usan hidrogel (mismas fisuras que
        'Hydrogel ... with bact' en 'Sides w bact'); sin bacterias, nutriente directo.
      - Nutriente: 'MA' / 'M. A.' -> MA; 'CL' -> CL; 'SL' -> SL; control -> ninguno.
        Significado (descripción del registro Zenodo 6469122): MA = acetato de magnesio,
        CL = lactato de calcio, SL = lactato de sodio. usa_lactato = 1 solo para lactato de calcio
        (misma definición que el meta-dataset).
    """
    e = " ".join(etiqueta.lower().replace(".", " ").split())
    tiene_bact = int(bool(re.search(r"with bact|w bact|\+ bacteria|and bact", e)))

    if "hydrogel" in e or "hydrogl" in e:
        portador = "hidrogel"
    elif "lwa" in e:
        portador = "LWA"
    elif "cnc" in e:
        portador = "CNC"
    elif tiene_bact:
        portador = "hidrogel"
    else:
        portador = "ninguno"

    if re.search(r"\bm a\b|\bma\b", e):
        nutriente = "MA"
    elif re.search(r"\bcl\b", e):
        nutriente = "CL"
    elif re.search(r"\bsl\b", e):
        nutriente = "SL"
    else:
        nutriente = "ninguno"

    conc = re.search(r"\b(67|75)\b", e)
    if tiene_bact:
        nivel = {"hidrogel": 3, "LWA": 2, "CNC": 2}.get(portador, 1)
    else:
        nivel = 0

    return {
        "portador": portador,
        "nivel_proteccion": nivel,
        "tiene_bacterias": tiene_bact,
        "nutriente": nutriente,
        "concentracion_mM": int(conc.group(1)) if conc else "",
        "usa_lactato": int(nutriente == "CL"),
        "ubicacion": "lateral" if hoja.lower().startswith("sides") else "inferior",
    }


def extraer_mousa_replicas() -> list[dict]:
    wb = openpyxl.load_workbook(XLSX_MOUSA, read_only=True, data_only=True)
    vistos: set[tuple] = set()
    filas: list[dict] = []
    n_fisura = 0
    for hoja in HOJAS_MOUSA:
        for r_idx, row in enumerate(wb[hoja].iter_rows(values_only=True), 1):
            if not (isinstance(row[0], str) and all(isinstance(v, (int, float)) for v in row[1:6])):
                continue
            clave = tuple(round(float(v), 6) for v in row[1:6])
            if clave in vistos:
                continue
            vistos.add(clave)
            n_fisura += 1
            w0_um = float(row[1])
            if w0_um <= 0:
                continue
            etiqueta = " ".join(row[0].split())
            meta = clasificar_etiqueta_mousa(etiqueta, hoja)
            for edad, wt_um in zip(EDADES_MOUSA, row[2:6]):
                filas.append({
                    "fuente": "Mousa2022", "doi": DOI_MOUSA, "hoja": hoja, "fila_excel": r_idx,
                    "etiqueta_original": etiqueta,
                    "grupo_condicion": f"Mousa2022|{meta['portador']}|{meta['nutriente']}|"
                                       f"{meta['concentracion_mM']}|b{meta['tiene_bacterias']}",
                    "grupo_probeta": f"Mousa2022|fisura{n_fisura:03d}",
                    **meta,
                    "ambiente_marino": 0, "regimen": "",
                    "w0_mm": round(w0_um / 1000.0, 4), "edad_dias": edad,
                    "wt_mm": round(float(wt_um) / 1000.0, 4),
                    "cierre_pct": round(max(0.0, min(100.0, (w0_um - float(wt_um)) / w0_um * 100.0)), 2),
                })
    wb.close()
    return filas


# ---------------------------------------------------------------------------
# Cappellesso et al. (2024) · microscopía marina
# ---------------------------------------------------------------------------

AGENTES_CAPPELLESSO = {"REF": (0, 0, "ninguno"), "BAS": (1, 1, "Basilisk"), "CA": (0, 0, "cristalino")}


def _bloques_cappellesso(rows: list[tuple]) -> list[tuple[int, float]]:
    """Devuelve (columna_inicial, edad_meses) de cada bloque temporal (fila 'Age/time:')."""
    fila_edad = next(r for r in rows if any(v == "Age/time:" for v in r if isinstance(v, str)))
    return [(j, float(fila_edad[j + 1])) for j, v in enumerate(fila_edad)
            if v == "Age/time:" and isinstance(fila_edad[j + 1], (int, float))]


def _anchos_por_zona(rows: list[tuple], c0: int) -> dict[tuple[int, int], list[float]]:
    """{(probeta, zona): [anchos mm]} para el bloque que empieza en la columna c0."""
    datos: dict[tuple[int, int], list[float]] = {}
    probeta = None
    for row in rows:
        if c0 < len(row) and isinstance(row[c0], int) and c0 + 1 < len(row) and row[c0 + 1] == "Zone":
            probeta = row[c0]
            continue
        if probeta is None or c0 + 1 >= len(row) or not isinstance(row[c0 + 1], int):
            continue
        for zona in range(1, 9):
            col = c0 + 1 + zona
            v = row[col] if col < len(row) else None
            if isinstance(v, (int, float)):
                datos.setdefault((probeta, zona), []).append(float(v))
    return datos


def extraer_cappellesso_microscopio() -> list[dict]:
    wb = openpyxl.load_workbook(XLSX_CAPPELLESSO, read_only=True, data_only=True)
    filas: list[dict] = []
    for ws in wb.worksheets:
        m = re.fullmatch(r"(REF|BAS|CA)([hu])(100|300)", ws.title)
        if not m:
            continue
        agente, regimen, ancho_nominal = m.group(1), m.group(2), int(m.group(3))
        nivel, bact, portador = AGENTES_CAPPELLESSO[agente]
        rows = list(ws.iter_rows(values_only=True))
        bloques = _bloques_cappellesso(rows)
        (c_ini, edad_ini), resto = bloques[0], bloques[1:]
        iniciales = _anchos_por_zona(rows, c_ini)
        for c0, edad_meses in resto:
            posteriores = _anchos_por_zona(rows, c0)
            for (probeta, zona), anchos0 in sorted(iniciales.items()):
                anchos_t = posteriores.get((probeta, zona))
                w0 = statistics.mean(anchos0)
                if not anchos_t or w0 <= 0:
                    continue
                wt = statistics.mean(anchos_t)
                filas.append({
                    "fuente": "Cappellesso2024", "doi": DOI_CAPPELLESSO, "hoja": ws.title, "fila_excel": "",
                    "etiqueta_original": f"{ws.title} probeta {probeta} zona {zona}",
                    "grupo_condicion": f"Cappellesso2024|{agente}|{regimen}|{ancho_nominal}",
                    "grupo_probeta": f"Cappellesso2024|{ws.title}|{probeta}",
                    "portador": portador, "nivel_proteccion": nivel, "tiene_bacterias": bact,
                    "nutriente": "Basilisk" if bact else "ninguno", "concentracion_mM": "", "usa_lactato": "",
                    "ambiente_marino": 1, "regimen": "curado_previo" if regimen == "h" else "exposicion_directa",
                    "ubicacion": f"zona{zona}",
                    "w0_mm": round(w0, 4), "edad_dias": round((edad_meses - edad_ini) * 30.0, 1),
                    "wt_mm": round(wt, 4),
                    "cierre_pct": round(max(0.0, min(100.0, (w0 - wt) / w0 * 100.0)), 2),
                })
    wb.close()
    return filas


def main() -> None:
    mousa = extraer_mousa_replicas()
    cap = extraer_cappellesso_microscopio()
    filas = mousa + cap
    RUTA_SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(RUTA_SALIDA, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(filas)
    print(f"Mousa2022: {len(mousa)} registros de {len({r['grupo_probeta'] for r in mousa})} fisuras")
    print(f"Cappellesso2024: {len(cap)} registros de {len({r['grupo_probeta'] for r in cap})} probetas")
    print(f"Total: {len(filas)} -> {RUTA_SALIDA}")


if __name__ == "__main__":
    main()
