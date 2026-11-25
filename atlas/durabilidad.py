"""Vida útil frente a cloruros (Fick, modelo de fib Bulletin 34) alimentada con datos de Blur.

  - D_RCM,0 de concreto OPC vs a/c: ajuste log-lineal sobre la base de datos de Dryad (RCM) de Blur.
  - Factor por tipo de cemento: relaciones aproximadas de fib B34 (cementos con adiciones difunden menos).
  - Cs (superficie, % de masa de cemento) por régimen: DuraCrete, Cs = A·(a/c), con A = 7,758
    (mareas/salpicadura) y 2,565 (atmosférico). La niebla salina interpola entre ambos según la deposición.
  - Efecto de la temperatura: k_e = exp(b_e (1/293 − 1/T)), b_e = 4800 K.
  - Fisura de diseño de 0,3 mm: aumenta la penetración (Cappellesso 2024, Blur: ×2,1 de media en
    probetas REF fisuradas frente a no fisuradas) y la reparación predicha reduce ese aumento.
  - Agentes con datos de cloruros en mar (Cappellesso 2024): reducción media de la penetración.
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
from scipy.special import erf

from atlas.ingesta import filas_por_tipo

C_CRIT = 0.6          # % masa de cemento (fib B34, valor medio)
T0_ANIOS = 28 / 365
VIDA_MAX = 150.0
FACTOR_CEMENTO = {"I": 1.0, "GU": 1.0, "IP": 0.55, "HS": 0.40}   # aprox. fib B34 (por verificar)
A_CS = {"salpicadura": 7.758, "atmosferico_marino": 2.565, "seco": 0.5}


@lru_cache
def ajuste_drcm() -> dict:
    filas = [r for r in filas_por_tipo("cloruros_rcm") if r["a_c"] and r["d_rcm_1e12"]]
    x = np.array([float(r["a_c"]) for r in filas])
    y = np.log(np.array([float(r["d_rcm_1e12"]) for r in filas]))
    b, a = np.polyfit(x, y, 1)
    pred = a + b * x
    r2 = 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    return {"a": float(a), "b": float(b), "r2_log": round(float(r2), 3), "n": int(len(x)),
            "rango_a_c": [float(x.min()), float(x.max())]}


@lru_cache
def efecto_agentes_cloruros() -> dict:
    """Reducción media de la penetración de cloruros por agente (grupos BAS/CA de Cappellesso)."""
    filas = filas_por_tipo("cloruros_agno3")
    ref = {r["condicion"]: float(r["penetracion_mm"]) for r in filas if r["grupo"] == "REF"}
    out = {}
    for g, agente in (("BAS", "basilisk"), ("CA", "cristalino")):
        red = [1 - float(r["penetracion_mm"]) / ref[r["condicion"]] for r in filas
               if r["grupo"] == g and r["condicion"] in ref]
        if red:
            out[agente] = {"reduccion_media": round(float(np.mean(red)), 3),
                           "min": round(float(np.min(red)), 3), "max": round(float(np.max(red)), 3), "n": len(red)}
    fis = [ref[c] / ref[c.replace("Crack 300", "Uncracked")] for c in ref if c.startswith("Crack 300")]
    out["_factor_fisura_0p3"] = round(float(np.mean(fis)), 2) if fis else 2.0
    return out


def drcm0(a_c: float, cemento: str) -> float:
    aj = ajuste_drcm()
    return math.exp(aj["a"] + aj["b"] * a_c) * FACTOR_CEMENTO.get(cemento, 1.0)   # ×1e-12 m²/s


# A de DuraCrete en función de la deposición de cloruros (mg/m²·d, escala log): 3 → 0,5 (seco);
# 60 → 2,565 (atmosférico marino, límite ISO S1/S2); 300 → 5,0; ≥ 1500 → 7,758 (equivalente a salpicadura).
_DEP = [3.0, 60.0, 300.0, 1500.0]
_A = [0.5, A_CS["atmosferico_marino"], 5.0, A_CS["salpicadura"]]
HUMECTACION_NIEBLA = 1.25   # la superficie mojada por niebla mantiene el cloruro móvil (supuesto)


def cs(regimen: str, a_c: float, dep: float) -> float:
    if regimen == "salpicadura":
        A = A_CS["salpicadura"]
    else:
        A = float(np.interp(math.log10(max(dep, 0.1)), np.log10(_DEP), _A))
        if regimen in ("niebla_salina", "niebla_orografica"):
            A = min(A * HUMECTACION_NIEBLA, A_CS["salpicadura"])
    return A * a_c


def parametros_fick(a_c, cemento, regimen, dep, t_media_c, recubrimiento_mm, n_env,
                    cierre_frac=0.0, agente="ninguno", fisurado=True) -> dict:
    """Parámetros del perfil de cloruros C(x, t) = Cs·(1 − erf(x / (2·√(D·(t0/t)^n·t)))) para el visor web."""
    D = drcm0(a_c, cemento) * 1e-12 * math.exp(4800 * (1 / 293.0 - 1 / (273.15 + t_media_c)))
    pen = 1.0
    ef = efecto_agentes_cloruros()
    if fisurado:
        pen *= 1 + (ef["_factor_fisura_0p3"] - 1) * (1 - cierre_frac)
    if agente in ef:
        pen *= 1 - max(ef[agente]["reduccion_media"], 0.0)
    return {"cs": round(cs(regimen, a_c, dep), 4), "d_m2_s": float(f"{D * pen ** 2:.4e}"), "n": n_env,
            "t0_anios": round(T0_ANIOS, 5), "c_crit": C_CRIT, "recubrimiento_mm": recubrimiento_mm}


def vida_util(a_c, cemento, regimen, dep, t_media_c, recubrimiento_mm, n_env,
              cierre_frac=0.0, agente="ninguno", fisurado=True) -> float:
    """Años hasta que el cloruro en el acero alcanza C_crit (iniciación de la corrosión)."""
    D = drcm0(a_c, cemento) * 1e-12 * math.exp(4800 * (1 / 293.0 - 1 / (273.15 + t_media_c)))
    pen = 1.0
    ef = efecto_agentes_cloruros()
    if fisurado:
        pen *= 1 + (ef["_factor_fisura_0p3"] - 1) * (1 - cierre_frac)
    if agente in ef:
        pen *= 1 - max(ef[agente]["reduccion_media"], 0.0)
    D *= pen ** 2                      # penetración ∝ √(D t)
    Cs = cs(regimen, a_c, dep)
    if Cs <= C_CRIT:
        return VIDA_MAX
    x = recubrimiento_mm / 1000
    seg = 365.25 * 24 * 3600
    t = np.arange(1, VIDA_MAX + 1, 1.0)
    c = Cs * (1 - erf(x / (2 * np.sqrt(D * (T0_ANIOS / t) ** n_env * t * seg))))
    hit = np.flatnonzero(c >= C_CRIT)
    return float(t[hit[0]]) if len(hit) else VIDA_MAX
