"""Vida útil frente a cloruros: modelo probabilista de fib Bulletin 34 / Model Code 2010 (iniciación).

Estado límite de despasivación: el acero se despasiva cuando el cloruro a la profundidad del
recubrimiento alcanza C_crit. Se verifica con confiabilidad, no con valores medios: la obra cumple
su vida de diseño si la probabilidad de despasivación a esa edad es ≤ 10 % (β ≥ 1,3; fib B34,
ISO 16204). Se resuelve por Monte Carlo (N_MC muestras, números aleatorios comunes).

Variables (fib B34 salvo indicación):
  - D_RCM,0: ajuste log-lineal sobre la base Dryad (RCM) de Blur, cercano a la tabla B2-1 de fib para
    CEM I; Normal con CoV 0,2. Factor por cemento: I/GU/HS 1,0 (HS/GU de la NTP 334.082 son
    especificaciones por desempeño, sin adición declarada); IP 0,70 [criterio, por verificar con
    NT Build 492 por proveedor].
  - Envejecimiento a: Beta(0,30; 0,12) en OPC; IP (puzolana natural) Beta(0,45; 0,15) [criterio].
  - C_crit: Beta(0,60; 0,15) en [0,2; 2,0] % de masa de cemento.
  - Cs: salpicadura 7,758·a/c (DuraCrete) con Δx ~ Beta(8,9; 5,6) en [0; 50] mm; aerosol marino
    A = 0,5 → 2,565 (tope atmosférico de DuraCrete) entre 3 y 60 mg/m²·d (interpolación log, a
    calibrar con perfiles ASTM C1556 y vela húmeda ISO 9225), Δx = 0. Lognormal con CoV 0,5.
    Con menos de 3 mg/m²·d (ISO 9223 S0) no se diseña por cloruros: gobierna la carbonatación (XC).
  - Temperatura: k_e = exp(b_e (1/293 − 1/T)), b_e ~ Normal(4800; 700) K.
  - Recubrimiento: Normal(nominal; 8 mm) (tolerancia de ejecución, E.060 7.5.2.1).
Concreto sin fisurar (w ≤ 0,3 mm, EN 1992-1-1 tabla 7.1N): la autorreparación se informa como sellado
de fisura y no se convierte en años del elemento. Solo el cristalizante, con datos de cloruros en mar
(Cappellesso 2024), recibe un crédito conservador: D × 0,8.
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
from scipy import stats
from scipy.special import erfinv

from atlas.ingesta import filas_por_tipo

C_CRIT = 0.6          # % masa de cemento: media de fib B34
T0_ANIOS = 28 / 365
HORIZONTE = 100.0     # años: el reporte no pasa de 2 × la vida de diseño de una edificación
VIDA_MAX = HORIZONTE  # compatibilidad
EDADES = (25, 50, 75, 100)
PF_OBJETIVO = 0.10    # β = 1,3
N_MC = 10000
FACTOR_CEMENTO = {"I": 1.0, "GU": 1.0, "HS": 1.0, "MS": 1.0, "V": 1.0, "IP": 0.70}
ENVEJECIMIENTO = {"I": (0.30, 0.12), "GU": (0.30, 0.12), "HS": (0.30, 0.12), "MS": (0.30, 0.12), "V": (0.30, 0.12),
                  "IP": (0.45, 0.15)}
A_SALPICADURA = 7.758
A_AEROSOL = (0.5, 2.565)          # entre 3 y 60 mg/m²·d; < 3 (ISO 9223 S0): sin diseño por cloruros
CREDITO_AGENTE = {"cristalino": 0.8}


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


def coef_cs(regimen: str, dep: float) -> float:
    """A de Cs = A·(a/c), % de masa de cemento."""
    if regimen == "salpicadura":
        return A_SALPICADURA
    f = (math.log10(max(dep, 3.0)) - math.log10(3.0)) / (math.log10(60.0) - math.log10(3.0))
    return A_AEROSOL[0] + (A_AEROSOL[1] - A_AEROSOL[0]) * min(max(f, 0.0), 1.0)


def _beta(u, media, desv, lo=0.0, hi=1.0):
    m, s = (media - lo) / (hi - lo), desv / (hi - lo)
    k = m * (1 - m) / s ** 2 - 1
    return lo + (hi - lo) * stats.beta.ppf(u, m * k, (1 - m) * k)


@lru_cache
def _muestras():
    """Números aleatorios comunes: las recetas se comparan con las mismas muestras."""
    r = np.random.default_rng(20261125)
    return {k: r.standard_normal(N_MC) for k in ("d", "cs", "be", "x")} | {k: r.uniform(1e-6, 1 - 1e-6, N_MC) for k in ("a", "cc", "dx")}


def parametros_fick(a_c, cemento, regimen, dep, t_media_c, recubrimiento_mm, agente="ninguno") -> dict:
    """Valores medios del perfil C(x, t) = Cs·(1 − erf((x − Δx) / (2·√(D·(t0/t)^a·t)))) para el visor web."""
    D = drcm0(a_c, cemento) * 1e-12 * math.exp(4800 * (1 / 293.0 - 1 / (273.15 + t_media_c))) * CREDITO_AGENTE.get(agente, 1.0)
    return {"cs": round(coef_cs(regimen, dep) * a_c, 4), "d_m2_s": float(f"{D:.4e}"),
            "n": ENVEJECIMIENTO.get(cemento, (0.30, 0.12))[0], "t0_anios": round(T0_ANIOS, 5), "c_crit": C_CRIT,
            "recubrimiento_mm": recubrimiento_mm, "dx_mm": 8.9 if regimen == "salpicadura" else 0.0}


def inicio_medio(f: dict, hasta: int = 150) -> float:
    """Año entero en que el perfil medio alcanza C_crit en el acero (para la paridad con web/src/fick.ts)."""
    from scipy.special import erf
    if f["cs"] <= f["c_crit"]:
        return float(hasta)
    seg = 365.25 * 24 * 3600
    x = (f["recubrimiento_mm"] - f["dx_mm"]) / 1000
    for t in range(1, hasta + 1):
        D = f["d_m2_s"] * (f["t0_anios"] / t) ** f["n"]
        if f["cs"] * (1 - erf(x / (2 * math.sqrt(D * t * seg)))) >= f["c_crit"]:
            return float(t)
    return float(hasta)


@lru_cache
def _env(cemento):
    return np.minimum(_beta(_muestras()["a"], *ENVEJECIMIENTO.get(cemento, (0.30, 0.12))), 0.95)


@lru_cache
def _fijas():
    m = _muestras()
    return _beta(m["cc"], C_CRIT, 0.15, 0.2, 2.0), _beta(m["dx"], 8.9, 5.6, 0, 50)


@lru_cache(maxsize=200000)
def _tiempos(a_c, cemento, regimen, dep_r, t_r, rec, agente):
    m = _muestras()
    seg = 365.25 * 24 * 3600
    D = np.maximum(drcm0(a_c, cemento) * 1e-12 * (1 + 0.2 * m["d"]), 1e-14) * CREDITO_AGENTE.get(agente, 1.0)
    a = _env(cemento)
    cc, dx_salp = _fijas()
    csm = coef_cs(regimen, dep_r) * a_c
    sg = math.sqrt(math.log(1 + 0.5 ** 2))
    cs = np.exp(math.log(csm) - sg ** 2 / 2 + sg * m["cs"])
    ke = np.exp((4800 + 700 * m["be"]) * (1 / 293.0 - 1 / (273.15 + t_r)))
    x = np.maximum(rec + 8 * m["x"], 5.0)
    dx = dx_salp if regimen == "salpicadura" else 0.0
    util = (x - dx) / 1000
    with np.errstate(divide="ignore", invalid="ignore"):
        z = util / (2 * erfinv(np.clip(1 - cc / cs, 0, 1)))
        t0 = T0_ANIOS * seg
        t = (z ** 2 / (ke * D * t0 ** a)) ** (1 / (1 - a)) / seg
    t = np.where(cs <= cc, np.inf, t)
    if regimen != "salpicadura" and dep_r < 3:
        t = np.full_like(t, np.inf)
    t = np.where(util <= 0, 0.0, t)
    return np.sort(t)


def confiabilidad(a_c, cemento, regimen, dep, t_media_c, recubrimiento_mm, agente="ninguno") -> dict:
    """Probabilidad de despasivación por edad, t10 (edad con 10 % de probabilidad) y vida de diseño que cumple."""
    t = _tiempos(round(a_c, 3), cemento, regimen, round(dep, 0), round(t_media_c, 1), float(recubrimiento_mm),
                 agente if agente in CREDITO_AGENTE else "ninguno")
    pf = {L: float(np.searchsorted(t, L) / len(t)) for L in EDADES}
    t10 = float(t[int(PF_OBJETIVO * len(t))])
    cumple = max([L for L in EDADES if pf[L] <= PF_OBJETIVO], default=0)
    p50 = min(max(pf[50], 1e-6), 1 - 1e-6)
    return {"pf": {str(L): round(v, 4) for L, v in pf.items()}, "t10_anios": round(min(t10, HORIZONTE + 1), 1),
            "cumple_anios": cumple, "beta_50": round(float(-stats.norm.ppf(p50)), 2)}


def vida_util(a_c, cemento, regimen, dep, t_media_c, recubrimiento_mm, agente="ninguno") -> float:
    """Edad (años) con 10 % de probabilidad de despasivación, con tope HORIZONTE + 1."""
    return confiabilidad(a_c, cemento, regimen, dep, t_media_c, recubrimiento_mm, agente)["t10_anios"]
