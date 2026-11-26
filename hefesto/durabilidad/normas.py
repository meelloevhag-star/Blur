"""
Reglas normativas usadas por el cálculo de vida útil.

1. Exposición (datos/durabilidad/normas_exposicion.csv): a/c máxima, cemento mínimo, f'c y
   recubrimiento por régimen. Fuente: E.060 cap. 4, ACI 318-19 19.3 y EN 206 F.1; se toma el valor
   más exigente.
2. Vida útil de diseño por uso. Fuentes: EN 1990 tabla 2.1 (categorías 1-5), BS 6349-1 para obras
   marítimas y la práctica peruana con E.060, que no fija una cifra (se usa 50 años).
   Ninguna norma exige más de 100 años. Valores mayores solo aparecen en contratos de megaproyectos
   (120 años), no en normas. Por eso un objetivo superior a 100 años se rechaza.
"""

import csv
from functools import lru_cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
RUTA_EXPOSICION = RAIZ / "datos" / "durabilidad" / "normas_exposicion.csv"
MAX_OBJETIVO_NORMA = 100

VIDA_DISENO = {  # uso: (años, categoría, fuente)
    "temporal": (10, "EN 1990 cat. 1", "EN 1990 tabla 2.1"),
    "pavimento": (25, "EN 1990 cat. 2", "EN 1990 tabla 2.1 (partes reemplazables)"),
    "agricola": (30, "EN 1990 cat. 3", "EN 1990 tabla 2.1"),
    "vivienda": (50, "EN 1990 cat. 4", "EN 1990 tabla 2.1; práctica E.060"),
    "edificio": (50, "EN 1990 cat. 4", "EN 1990 tabla 2.1; práctica E.060"),
    "tanque": (50, "EN 1990 cat. 4", "EN 1990 tabla 2.1"),
    "puerto": (50, "BS 6349-1", "BS 6349-1-1 (obras marítimas)"),
    "puente": (100, "EN 1990 cat. 5", "EN 1990 tabla 2.1"),
    "tunel": (100, "EN 1990 cat. 5", "EN 1990 tabla 2.1"),
    "obra_hidraulica": (100, "EN 1990 cat. 5", "EN 1990 tabla 2.1"),
}


@lru_cache
def cargar_normas() -> dict:
    with open(RUTA_EXPOSICION, encoding="utf-8") as fh:
        return {r["regimen"]: {"clase": r["clase"], "a_c_max": float(r["a_c_max"]),
                               "cemento_min_kg": float(r["cemento_min_kg"]), "fc_min_mpa": float(r["fc_min_mpa"]),
                               "recubrimiento_mm": float(r["recubrimiento_mm"]),
                               "cementos_permitidos": r["cementos_permitidos"].split(";"), "fuente": r["fuente"]}
                for r in csv.DictReader(fh)}


def reglas(regimen: str) -> dict:
    return cargar_normas()[regimen]


def vida_diseno(uso: str) -> dict:
    anios, cat, fuente = VIDA_DISENO[uso]
    return {"uso": uso, "vida_diseno_anios": anios, "categoria": cat, "fuente": fuente}


def validar_objetivo(objetivo_anios: float) -> None:
    if objetivo_anios > MAX_OBJETIVO_NORMA:
        raise ValueError(f"objetivo de {objetivo_anios:g} años: ninguna norma lo exige "
                         f"(máximo normativo {MAX_OBJETIVO_NORMA} años, EN 1990 cat. 5)")
    if objetivo_anios <= 0:
        raise ValueError("el objetivo debe ser positivo")
