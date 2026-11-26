"""
Vida útil frente a cloruros (inicio de la corrosión) y reparación necesaria para alcanzarla.

Corrige el cálculo del Atlas (Blur/atlas/durabilidad.py), que daba 150 años en 342 de 384 zonas:
  1. Sin tope arbitrario de 150 años. Si el tiempo pasa de 40 años se informa "cumple 40 años";
     nunca se da una cifra mayor que el horizonte pedido.
  2. Régimen seco (sin cloruros): gobierna la carbonatación. Se marca "fuera de alcance" y no se da
     un número (antes salía 150 años automáticamente).
  3. La reparación se cuenta UNA sola vez: reduce el ancho residual de la fisura, w0·(1 − cierre).
     No se suma además la reducción de penetración del agente, que ya incluye ese cierre.
  4. El envejecimiento de D se congela a los 25 años (Life-365); sin ese tope, los cementos con
     adiciones dan cientos de años.

Modelo (fib Bulletin 34, solución de Fick con D aparente):
    C(x, t) = Cs · [1 − erf( x / (2·√(D_app(t)·t)) )]
    D_app(t) = k_e · D28 · f_fisura² · (t0 / min(t, 25 años))^m
Parámetros:
  D28   ajuste log-lineal sobre la base Dryad RCM (581 ensayos; a/b, ceniza, escoria).
        DOI 10.5061/dryad.66t1g1k6j. La dispersión residual del ajuste entra en el Monte Carlo.
  m     exponente de envejecimiento α de la fib B34 (CEM I 0,30; IP/HS 0,45 supuesto), congelado a
        los 25 años como en Life-365.
  Cs    DuraCrete: Cs = A·(a/b), A = 2,565 (atmosférico) y 7,758 (salpicadura); la niebla salina
        interpola entre ambos según el depósito de cloruros (supuesto a calibrar con vela húmeda).
  Ccrit 0,6 % de la masa de ligante (fib B34, valor medio).
  k_e   exp(4800·(1/293 − 1/T)) (fib B34).
  fisura  f = 1 + s·w_res. La pendiente s se ajusta con la penetración de cloruros en probetas REF
        fisuradas (0,1 y 0,3 mm) frente a no fisuradas de Cappellesso 2024 (DOI 10.5281/zenodo.11305154).
        PARÁMETRO PROVISIONAL: dos anchos y un solo laboratorio.
Resultado: tiempo en que la probabilidad de inicio de la corrosión llega al 10 % (β ≈ 1,3, fib).
"""

import csv
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
import openpyxl
from scipy.special import erf

from hefesto.durabilidad.normas import validar_objetivo

RAIZ = Path(__file__).resolve().parents[2]
DIR = RAIZ / "datos" / "durabilidad"
T0 = 28 / 365.25
T_CONGELA = 25.0
C_CRIT = 0.6
A_CS = {"atmosferico_marino": 2.565, "salpicadura": 7.758}
P_OBJETIVO = 0.10
COV_CS = 0.3       # dispersión log de Cs (supuesto)
EXP_FISURA = 2     # D ∝ f²: penetración ∝ √(D·t) (supuesto conservador; 1 = efecto lineal sobre D)
HORIZONTE = 40.0
REJILLA = np.arange(0.5, 100.01, 0.5)
N_MC = 4000
SEMILLA = 2026
SEG_ANIO = 365.25 * 24 * 3600
# Composición supuesta de los cementos peruanos (fracción del ligante). Los valores de IP y HS son
# supuestos: puzolana natural tratada como ceniza volante, con la proporción central de 15-40 %.
CEMENTOS = {"I": (0.0, 0.0), "GU": (0.0, 0.0), "IP": (0.25, 0.0), "HS": (0.25, 0.0)}


@lru_cache
def ajuste_d28() -> dict:
    wb = openpyxl.load_workbook(RAIZ / "datos" / "zenodo" / "Dryad_RCM_Chloride_Diffusion_Database" / "Experimental_data_for_chloride_diffusion_coefficient_of_concrete_by_rapid_chloride_migration_test.xlsx", read_only=True, data_only=True)
    filas = []
    for ws in wb.worksheets:
        cab = None
        for r in ws.iter_rows(values_only=True):
            if cab is None:
                if any(isinstance(c, str) and "Water-binder" in c for c in r):
                    cab = [c.strip() if isinstance(c, str) else "" for c in r]
                continue
            d = {h: v for h, v in zip(cab, r) if h}
            col_d = next(h for h in cab if h.startswith("Chloride"))
            try:
                filas.append((float(d["Water-binder ratio"]), float(d.get("Amount of fly ash") or 0),
                              float(d.get("Amount of slag") or 0), float(d[col_d])))
            except (TypeError, ValueError):
                continue
    A = np.array(filas)
    X = np.c_[np.ones(len(A)), A[:, :3]]
    y = np.log(A[:, 3])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ b
    return {"coef": b.tolist(), "sd_log": float(res.std(ddof=4)), "n": len(A),
            "r2_log": float(1 - (res ** 2).sum() / ((y - y.mean()) ** 2).sum()),
            "rango_ab": [float(A[:, 0].min()), float(A[:, 0].max())], "fuente": "Dryad 10.5061/dryad.66t1g1k6j"}


@lru_cache
def pendiente_fisura() -> dict:
    with open(DIR / "cappellesso2024_agno3_marino.csv", encoding="utf-8-sig") as fh:
        ref = {r["condicion"]: float(r["penetracion_cl_media_mm"]) for r in csv.DictReader(fh) if r["grupo"] == "REF"}
    pts = []
    for cond, pen in ref.items():
        if cond.startswith("Crack"):
            w = int(cond.split()[1]) / 1000
            pts.append((w, pen / ref[cond.replace(f"Crack {int(w * 1000)}", "Uncracked")] - 1))
    w, e = np.array(pts).T
    return {"s_por_mm": float((w * e).sum() / (w ** 2).sum()), "puntos": pts, "provisional": True,
            "fuente": "Cappellesso 2024, REF fisurado vs no fisurado (10.5281/zenodo.11305154)"}


def d28(a_b: float, cemento: str) -> float:
    fa, sg = CEMENTOS[cemento]
    return float(math.exp(np.dot(ajuste_d28()["coef"], [1, a_b, fa, sg])))  # ×1e-12 m²/s


ALFA = {"I": (0.30, 0.12), "GU": (0.30, 0.12), "IP": (0.45, 0.15), "HS": (0.45, 0.15)}


def exponente_m(cemento: str) -> float:
    """Exponente de envejecimiento α de la fib B34, consistente con D aparente.
    CEM I: media 0,30, sd 0,12. Para IP y HS (puzolana natural, sin dato fib) se usa 0,45 con sd
    0,15: queda entre CEM I (0,30) y ceniza volante (0,60). Es un SUPUESTO."""
    return ALFA[cemento][0]


def cs(regimen: str, a_b: float, deposicion: float = 0.0) -> float:
    if regimen == "niebla_salina":
        f = min(max(math.log10(max(deposicion, 1)) / math.log10(300), 0), 1)
        return (A_CS["atmosferico_marino"] + f * (A_CS["salpicadura"] - A_CS["atmosferico_marino"])) * a_b
    return A_CS[regimen] * a_b


def _muestras(a_b, cemento, regimen, deposicion, t_media_c, recubrimiento_mm, w_res_mm):
    rng = np.random.default_rng(SEMILLA)
    aj = ajuste_d28()
    D = d28(a_b, cemento) * 1e-12 * np.exp(rng.normal(0, aj["sd_log"], N_MC))
    m = np.clip(rng.normal(*ALFA[cemento], N_MC), 0.0, 0.8)
    Cs = cs(regimen, a_b, deposicion) * np.exp(rng.normal(-0.5 * COV_CS ** 2, COV_CS, N_MC))  # supuesto
    Cc = np.clip(rng.normal(C_CRIT, 0.15, N_MC), 0.2, 2.0)                               # fib B34
    x = np.clip(rng.normal(recubrimiento_mm, 8.0, N_MC), 10, None) / 1000                # fib B34
    ke = math.exp(4800 * (1 / 293.0 - 1 / (273.15 + t_media_c)))
    f = 1 + pendiente_fisura()["s_por_mm"] * w_res_mm
    return D * ke * f ** EXP_FISURA, m, Cs, Cc, x


def _t_inicio(a_b, cemento, regimen, deposicion, t_media_c, recubrimiento_mm, w_res_mm, alpha_fijo=None):
    """Tiempo (años) con P(inicio) = 10 %, o inf si no se alcanza en 100 años."""
    D, m, Cs, Cc, x = _muestras(a_b, cemento, regimen, deposicion, t_media_c, recubrimiento_mm, w_res_mm)
    if alpha_fijo is not None:
        m = np.full_like(m, alpha_fijo)
    t = REJILLA[:, None]
    tc = np.minimum(t, T_CONGELA)
    Dapp = D * (T0 / tc) ** m
    C = Cs * (1 - erf(x / (2 * np.sqrt(Dapp * t * SEG_ANIO))))
    p = (C >= Cc).mean(axis=1)
    hit = np.flatnonzero(p >= P_OBJETIVO)
    return float(REJILLA[hit[0]]) if len(hit) else math.inf


def t_inicio_determinista(D0, alfa, Cs, Ccrit=C_CRIT, x_m=0.05, ke=1.0, congelar=True) -> float:
    """Solución cerrada de la fib B34 con valores medios (sin incertidumbre), en años.
    Con congelar=False reproduce la fórmula sin tope que inflaba el Atlas."""
    from scipy.special import erfinv
    if Cs <= Ccrit:
        return math.inf
    z = float(erfinv(1 - Ccrit / Cs))
    Da = ke * D0 * SEG_ANIO
    k = (x_m / (2 * z)) ** 2                        # = D_app(t)·t
    t = (k / (Da * T0 ** alfa)) ** (1 / (1 - alfa))  # sin tope
    if not congelar or t <= T_CONGELA:
        return t
    return k / (Da * (T0 / T_CONGELA) ** alfa)       # D congelada después de 25 años


def vida_util(a_b, cemento, regimen, deposicion=0.0, t_media_c=20.0, recubrimiento_mm=50.0,
              w0_mm=0.3, cierre_frac=0.0, horizonte=HORIZONTE) -> dict:
    validar_objetivo(horizonte)
    base = {"regimen": regimen, "a_b": a_b, "cemento": cemento, "w0_mm": w0_mm, "cierre_frac": cierre_frac,
            "horizonte_anios": horizonte, "criterio": "P(inicio corrosión) = 10 %"}
    if regimen not in A_CS and regimen != "niebla_salina":
        return base | {"estado": "fuera_de_alcance", "anios": None,
                       "reporte": "sin cloruros: gobierna la carbonatación (fuera de alcance de este modelo)"}
    w_res = w0_mm * (1 - min(max(cierre_frac, 0.0), 1.0))
    t = _t_inicio(a_b, cemento, regimen, deposicion, t_media_c, recubrimiento_mm, w_res)
    avisos = []
    if not ajuste_d28()["rango_ab"][0] <= a_b <= ajuste_d28()["rango_ab"][1]:
        avisos.append("a/b fuera del rango de la base Dryad")
    if w_res > 0:
        avisos.append("efecto de la fisura con parámetro provisional (Cappellesso 2024)")
    if t > horizonte:
        return base | {"estado": "cumple", "anios": None, "reporte": f"cumple {horizonte:g} años", "avisos": avisos}
    if t < 1:
        return base | {"estado": "menor_1", "anios": None, "reporte": "menos de 1 año", "avisos": avisos}
    return base | {"estado": "numero", "anios": t, "reporte": f"{t:g} años", "avisos": avisos}


def cierre_requerido(a_b, cemento, regimen, objetivo, deposicion=0.0, t_media_c=20.0,
                     recubrimiento_mm=50.0, w0_mm=0.3, iteraciones=14) -> dict:
    """Cierre mínimo de la fisura (fracción) para que el inicio de la corrosión llegue al objetivo."""
    validar_objetivo(objetivo)
    if regimen not in A_CS and regimen != "niebla_salina":
        return {"estado": "fuera_de_alcance", "cierre_min": None, "objetivo_anios": objetivo}
    args = (a_b, cemento, regimen, deposicion, t_media_c, recubrimiento_mm)
    if _t_inicio(*args, w0_mm) >= objetivo:
        return {"estado": "sin_reparacion_basta", "cierre_min": 0.0, "objetivo_anios": objetivo}
    if _t_inicio(*args, 0.0) < objetivo:
        return {"estado": "no_alcanzable", "cierre_min": None, "objetivo_anios": objetivo,
                "nota": "ni con la fisura cerrada del todo: cambiar a/b, cemento o recubrimiento"}
    lo, hi = 0.0, 1.0
    for _ in range(iteraciones):
        mid = (lo + hi) / 2
        if _t_inicio(*args, w0_mm * (1 - mid)) >= objetivo:
            hi = mid
        else:
            lo = mid
    return {"estado": "requiere_reparacion", "cierre_min": round(hi, 3), "objetivo_anios": objetivo}
