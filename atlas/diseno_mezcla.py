"""Dosificación por m³ con el método de volumen absoluto de ACI 211.1.

Asentamiento de 75-100 mm, concreto sin aire incorporado, módulo de finura de la arena 2,8.
Si la relación a/c ≤ 0,45 se añade superplastificante (reducción de agua del 15 %).
"""
from __future__ import annotations

import numpy as np

# ACI 211.1 tabla 6.3.3 (asentamiento 75-100 mm, sin aire): agua kg/m³ y aire atrapado %
AGUA_TMN = {12.5: (216, 2.5), 19.0: (205, 2.0), 25.0: (193, 1.5)}
# ACI 211.1 tabla 6.3.6: volumen de grava compactada por m³ para MF = 2,8
VOL_GRAVA = {12.5: 0.55, 19.0: 0.62, 25.0: 0.67}
# ACI 211.1 tabla 6.3.4(a): resistencia media a 28 d (MPa) vs a/c (sin aire)
TABLA_FC = ([0.42, 0.47, 0.54, 0.61, 0.69, 0.79], [40, 35, 30, 25, 20, 15])


def fc_estimado(a_c: float) -> float:
    x, y = TABLA_FC
    return float(np.interp(a_c, x, y, left=y[0] + (x[0] - a_c) * 100, right=y[-1]))


def dosificar(a_c: float, tmn: float, cemento: dict, cem_min: float, agregados: dict,
              agente_kg: float = 0.0, cristalino_kg: float = 0.0) -> dict:
    agua, aire = AGUA_TMN[tmn]
    sp_pct = 0.0
    if a_c <= 0.45:
        agua *= 0.85
        sp_pct = 1.0
    cem = max(agua / a_c, cem_min)
    a_c_real = agua / cem
    grava = VOL_GRAVA[tmn] * agregados["piedra"]["peso_unitario_kg_m3"]
    v = (agua / 1000 + cem / (cemento["densidad"] * 1000) + grava / (agregados["piedra"]["densidad_sss"] * 1000)
         + aire / 100 + agente_kg / 1800 + cristalino_kg / 2500)
    arena = (1.0 - v) * agregados["arena"]["densidad_sss"] * 1000
    return {
        "cemento_tipo": cemento["id"], "cemento_kg": round(cem, 1), "agua_kg": round(agua, 1),
        "a_c": round(a_c_real, 3), "arena_kg": round(arena, 1), "piedra_kg": round(grava, 1),
        "tmn_mm": tmn, "aire_pct": aire, "superplastificante_kg": round(cem * sp_pct / 100, 2),
        "cristalino_kg": round(cristalino_kg, 2), "agente_kg": round(agente_kg, 2),
        "fc_estimado_mpa": round(fc_estimado(a_c_real), 1),
        "metodo": "ACI 211.1 volumen absoluto (asentamiento 75-100 mm, MF arena 2,8)",
    }
