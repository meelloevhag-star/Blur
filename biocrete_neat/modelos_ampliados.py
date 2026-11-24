"""
F3 · Modelos ampliados para BioCrete-NEAT.

Responde a los pendientes de la revisión (PENDIENTES_CIENTIFICOS.md):
  - Validación cruzada AGRUPADA (GroupKFold): por fisura/probeta en las réplicas y por estudio
    en el meta-dataset, para que ninguna fisura ni estudio aparezca en entrenamiento y prueba.
  - Selección de λ_p de NEAT por CV ANIDADA (sin sesgo de selección).
  - XGBoost + SHAP como referente fuerte e interpretable.
  - IC 95 % por bootstrap de grupos para R² y MAE.
  - Curva de aprendizaje (R² vs. n) para la tesis "NEAT necesita más datos".
  - Predicciones de Paita con incertidumbre y aviso de extrapolación.

Uso:
    python -m biocrete_neat.modelos_ampliados            # completo
    python -m biocrete_neat.modelos_ampliados --rapido   # menos generaciones (pruebas)
"""

import argparse
import csv
import json
import math
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from xgboost import XGBRegressor

from biocrete_neat.entrenar_neat import (
    LAMBDA_PARSIMONIA_ALTA,
    LAMBDA_PARSIMONIA_MODERADA,
    cargar_dataset,
    evolucionar_neat,
    normalizar,
)

RUTA_BASE = Path(__file__).resolve().parent
RUTA_DATOS = RUTA_BASE / "datos"
RUTA_RES = RUTA_BASE / "resultados" / "f3"
SEMILLA = 2026
LAMBDAS = (LAMBDA_PARSIMONIA_ALTA, LAMBDA_PARSIMONIA_MODERADA)

VARS_REPLICAS = ["Ancho fisura w0 (mm)", "Edad (d)", "Protección bio (0-3)", "Ambiente marino",
                 "Lactato de calcio", "Curado previo"]
VARS_META = ["a/c", "Ancho fisura (mm)", "Edad curado (d)", "Protección bio (0-3)", "Ambiente marino", "Usa lactato"]
# Límites físicos fijos (no dependen de los datos → sin fuga entre particiones)
MIN_REPLICAS = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
MAX_REPLICAS = np.array([1.0, 480.0, 3.0, 1.0, 1.0, 1.0])


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------

def normalizar_replicas(X: np.ndarray) -> np.ndarray:
    return np.clip((X - MIN_REPLICAS) / (MAX_REPLICAS - MIN_REPLICAS), 0.0, 1.0)


def cargar_replicas(ruta: Path = RUTA_DATOS / "replicas_cierre_fisuras.csv"):
    with open(ruta, encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))
    X = np.array([[float(r["w0_mm"]), float(r["edad_dias"]), float(r["nivel_proteccion"]),
                   float(r["ambiente_marino"]), float(r["usa_lactato"] or 0),
                   1.0 if r["regimen"] == "curado_previo" else 0.0] for r in filas])
    y = np.array([float(r["cierre_pct"]) / 100.0 for r in filas])
    grupos = np.array([r["grupo_probeta"] for r in filas])
    fuentes = np.array([r["fuente"] for r in filas])
    return X, y, grupos, fuentes


def cargar_meta():
    X_raw, _y_cierre, y_alpha, filas = cargar_dataset()
    grupos = np.array([r["estudio"] for r in filas])
    return X_raw, normalizar(X_raw), y_alpha, grupos


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------

def _ridge():
    return Ridge(alpha=1.0)


def _rf():
    return RandomForestRegressor(n_estimators=300, max_depth=8, min_samples_leaf=3, random_state=SEMILLA, n_jobs=1)


def _xgb():
    return XGBRegressor(n_estimators=400, max_depth=4, learning_rate=0.04, subsample=0.8, colsample_bytree=0.9,
                        min_child_weight=3, reg_lambda=1.0, random_state=SEMILLA, n_jobs=1, verbosity=0)


MODELOS_SKLEARN = {"Ridge": _ridge, "RandomForest": _rf, "XGBoost": _xgb}


def _neat_fold(args):
    """Entrena NEAT en un fold (proceso aparte). Devuelve (índices_prueba, predicciones, n_ocultas)."""
    X_tr, y_tr, X_te, te_idx, lam, gens, semilla = args
    random.seed(semilla)
    np.random.seed(semilla)
    ganador, red, cfg, _ = evolucionar_neat(X_tr, y_tr, generaciones=gens, semilla=semilla,
                                            penalizar_complejidad=lam)
    pred = np.array([red.activate(x)[0] for x in X_te])
    n_oc = len([n for n in ganador.nodes if n >= cfg.genome_config.num_outputs])
    return te_idx, pred, n_oc


def metricas(y, p, escala=1.0) -> dict:
    return {"R2": round(float(r2_score(y * escala, p * escala)), 3),
            "MAE": round(float(mean_absolute_error(y * escala, p * escala)), 3),
            "RMSE": round(float(math.sqrt(mean_squared_error(y * escala, p * escala))), 3)}


def cv_agrupada(X, y, grupos, gens_neat, n_splits=5, lambdas=LAMBDAS, workers=4) -> dict:
    """Predicciones out-of-fold con GroupKFold para todos los modelos."""
    gkf = GroupKFold(n_splits=n_splits)
    splits = list(gkf.split(X, y, grupos))
    oof = {nombre: np.zeros_like(y) for nombre in MODELOS_SKLEARN}
    for tr, te in splits:
        for nombre, fabrica in MODELOS_SKLEARN.items():
            m = fabrica().fit(X[tr], y[tr])
            oof[nombre][te] = np.clip(m.predict(X[te]), 0.0, 1.0)

    ocultas = {}
    tareas = [(X[tr], y[tr], X[te], te, lam, gens_neat, 100 + i)
              for lam in lambdas for i, (tr, te) in enumerate(splits)]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        resultados = list(ex.map(_neat_fold, tareas))
    for k, lam in enumerate(lambdas):
        nombre = f"NEAT λ={lam:g}"
        oof[nombre] = np.zeros_like(y)
        ocultas[nombre] = []
        for te_idx, pred, n_oc in resultados[k * n_splits:(k + 1) * n_splits]:
            oof[nombre][te_idx] = pred
            ocultas[nombre].append(n_oc)
    return {"oof": oof, "ocultas": {k: float(np.mean(v)) for k, v in ocultas.items()}}


def bootstrap_ic(y, pred, grupos, escala=1.0, B=1000, semilla=SEMILLA) -> dict:
    """IC 95 % de R² y MAE remuestreando GRUPOS completos (respeta la dependencia intra-grupo)."""
    rng = np.random.default_rng(semilla)
    ug = np.unique(grupos)
    idx_por_grupo = {g: np.flatnonzero(grupos == g) for g in ug}
    r2s, maes = [], []
    for _ in range(B):
        idx = np.concatenate([idx_por_grupo[g] for g in rng.choice(ug, size=len(ug), replace=True)])
        if np.var(y[idx]) == 0:
            continue
        r2s.append(r2_score(y[idx] * escala, pred[idx] * escala))
        maes.append(mean_absolute_error(y[idx] * escala, pred[idx] * escala))
    q = lambda v: [round(float(np.percentile(v, 2.5)), 3), round(float(np.percentile(v, 97.5)), 3)]
    return {"R2_IC95": q(r2s), "MAE_IC95": q(maes)}


def cv_anidada_lambda(X, y, grupos, gens_neat, lambdas=LAMBDAS, n_ext=5, n_int=4, workers=4) -> dict:
    """CV anidada: el λ_p de NEAT se elige en el interior de cada partición externa."""
    externos = list(GroupKFold(n_splits=n_ext).split(X, y, grupos))
    pred = np.zeros_like(y)
    elegidos = []
    for i, (tr, te) in enumerate(externos):
        internos = list(GroupKFold(n_splits=min(n_int, len(np.unique(grupos[tr])))).split(X[tr], y[tr], grupos[tr]))
        tareas = [(X[tr][a], y[tr][a], X[tr][b], b, lam, gens_neat, 300 + 10 * i + j)
                  for lam in lambdas for j, (a, b) in enumerate(internos)]
        with ProcessPoolExecutor(max_workers=workers) as ex:
            res = list(ex.map(_neat_fold, tareas))
        puntaje = {}
        for k, lam in enumerate(lambdas):
            p_int = np.zeros(len(tr))
            for b, p, _ in res[k * len(internos):(k + 1) * len(internos)]:
                p_int[b] = p
            puntaje[lam] = r2_score(y[tr], p_int)
        mejor = max(puntaje, key=puntaje.get)
        elegidos.append(mejor)
        _, p_te, _ = _neat_fold((X[tr], y[tr], X[te], te, mejor, gens_neat, 500 + i))
        pred[te] = p_te
    return {"pred": pred, "lambdas_elegidos": [float(l) for l in elegidos]}


def curva_aprendizaje(X, y, grupos, gens_neat, fracciones=(0.1, 0.25, 0.5, 0.75, 1.0), workers=4) -> dict:
    rng = np.random.default_rng(SEMILLA)
    ug = np.unique(grupos)
    salida = {"n_registros": [], "n_grupos": []}
    for frac in fracciones:
        sel_g = rng.choice(ug, size=max(10, int(round(frac * len(ug)))), replace=False)
        mask = np.isin(grupos, sel_g)
        cv = cv_agrupada(X[mask], y[mask], grupos[mask], gens_neat, lambdas=(LAMBDA_PARSIMONIA_ALTA,),
                         workers=workers)
        salida["n_registros"].append(int(mask.sum()))
        salida["n_grupos"].append(int(len(sel_g)))
        for nombre, p in cv["oof"].items():
            salida.setdefault(nombre, []).append(round(float(r2_score(y[mask], p)), 3))
    return salida


def importancia_shap(X, y, nombres):
    import shap

    m = _xgb().fit(X, y)
    valores = shap.TreeExplainer(m).shap_values(X)
    imp = np.abs(valores).mean(axis=0)
    orden = np.argsort(imp)[::-1]
    return [{"variable": nombres[j], "shap_medio_abs": round(float(imp[j]), 4)} for j in orden], valores, m


# ---------------------------------------------------------------------------
# Predicciones para Paita
# ---------------------------------------------------------------------------

ESCENARIOS_PAITA = [
    # (nombre, w0_mm, nivel_proteccion)
    ("Directa · fisura 0,2 mm", 0.2, 1), ("Directa · fisura 0,5 mm", 0.5, 1), ("Directa · fisura 1,0 mm", 1.0, 1),
    ("Portador · fisura 0,3 mm", 0.3, 2), ("Encapsulación · fisura 0,3 mm", 0.3, 3),
]


RESTRICCIONES_MONOTONAS = "(-1,1,0,0,0,0)"  # orden de VARS_REPLICAS


def predicciones_paita(X, y, B=100) -> list[dict]:
    """Ensamble bootstrap de XGBoost entrenado en réplicas: media e IC 95 % del cierre a 90 d en mar."""
    rng = np.random.default_rng(SEMILLA)
    Xn = normalizar_replicas(X)
    filas_esc = np.array([[w0, 90.0, nivel, 1.0, 1.0, 0.0] for _, w0, nivel in ESCENARIOS_PAITA])
    Xe = normalizar_replicas(filas_esc)
    preds = []
    for b in range(B):
        idx = rng.integers(0, len(y), len(y))
        # Restricciones físicas: más ancho inicial -> menos cierre; más edad -> más cierre
        m = _xgb().set_params(random_state=SEMILLA + b, monotone_constraints=RESTRICCIONES_MONOTONAS)\
            .fit(Xn[idx], y[idx])
        preds.append(np.clip(m.predict(Xe), 0, 1) * 100)
    preds = np.array(preds)
    w0_max = float(X[:, 0].max())
    salida = []
    for k, (nombre, w0, nivel) in enumerate(ESCENARIOS_PAITA):
        marino_nivel = (X[:, 3] == 1) & (X[:, 2] == nivel)
        avisos = []
        if w0 > w0_max:
            avisos.append(f"w0 fuera del rango entrenado (máx {w0_max:.2f} mm)")
        if not marino_nivel.any():
            avisos.append("sin datos marinos con este nivel de protección")
        if not ((X[:, 3] == 1) & (X[:, 4] == 1)).any():
            avisos.append("sin datos que combinen ambiente marino y lactato de calcio")
        salida.append({"escenario": f"90 d · mar · lactato Ca · {nombre}",
                       "cierre_medio_pct": round(float(preds[:, k].mean()), 1),
                       "cierre_IC95_pct": [round(float(np.percentile(preds[:, k], 2.5)), 1),
                                           round(float(np.percentile(preds[:, k], 97.5)), 1)],
                       "extrapolacion": "; ".join(avisos) or "no"})
    return salida


# ---------------------------------------------------------------------------
# Figuras
# ---------------------------------------------------------------------------

def figura_comparacion(res: dict, ruta: Path):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, clave, titulo in [(axes[0], "replicas", "Réplicas de cierre (GroupKFold por fisura)"),
                              (axes[1], "meta", "Meta-dataset α (GroupKFold por estudio)")]:
        bloque = res[clave]["modelos"]
        nombres = list(bloque)
        r2 = [bloque[n]["R2"] for n in nombres]
        lo = [max(0.0, bloque[n]["R2"] - bloque[n]["R2_IC95"][0]) for n in nombres]
        hi = [max(0.0, bloque[n]["R2_IC95"][1] - bloque[n]["R2"]) for n in nombres]
        ax.barh(nombres, r2, xerr=[lo, hi], color="#0f766e", alpha=0.8, capsize=4)
        ax.axvline(0, color="k", lw=0.8)
        ax.set_xlabel("R² fuera de muestra (IC 95 % bootstrap por grupos)")
        ax.set_title(titulo, fontsize=10)
    fig.tight_layout()
    fig.savefig(ruta, dpi=220)
    plt.close(fig)


def figura_shap(valores, X, nombres, ruta: Path, titulo: str):
    import shap

    plt.figure()
    shap.summary_plot(valores, X, feature_names=nombres, show=False, plot_size=(7, 4))
    plt.title(titulo, fontsize=10)
    plt.tight_layout()
    plt.savefig(ruta, dpi=220)
    plt.close()


def figura_curva(curva: dict, ruta: Path):
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    for nombre in [k for k in curva if k not in ("n_registros", "n_grupos")]:
        ax.plot(curva["n_registros"], curva[nombre], marker="o", label=nombre)
    ax.set_xlabel("Registros usados (réplicas)")
    ax.set_ylabel("R² fuera de muestra")
    ax.set_title("Curva de aprendizaje (GroupKFold por fisura)", fontsize=10)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(ruta, dpi=220)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------

def _bloque_modelos(y, cv, grupos, escala):
    return {n: {**metricas(y, p, escala), **bootstrap_ic(y, p, grupos, escala),
                **({"neuronas_ocultas_prom": round(cv["ocultas"][n], 2)} if n in cv["ocultas"] else {})}
            for n, p in cv["oof"].items()}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true")
    args = ap.parse_args(argv)
    gens = 20 if args.rapido else 75
    RUTA_RES.mkdir(parents=True, exist_ok=True)
    res = {"semilla": SEMILLA, "generaciones_neat": gens}

    # 1. Réplicas de cierre de fisuras
    X_r, y_r, g_r, f_r = cargar_replicas()
    Xn_r = normalizar_replicas(X_r)
    cv_r = cv_agrupada(Xn_r, y_r, g_r, gens)
    res["replicas"] = {"n_registros": int(len(y_r)), "n_grupos": int(len(np.unique(g_r))),
                       "fuentes": {f: int((f_r == f).sum()) for f in np.unique(f_r)},
                       "modelos": _bloque_modelos(y_r, cv_r, g_r, 100.0)}
    print("[réplicas]", json.dumps({k: v["R2"] for k, v in res["replicas"]["modelos"].items()}), flush=True)

    # 2. Meta-dataset α (agrupado por estudio) + CV anidada de λ
    X_raw_m, Xn_m, y_m, g_m = cargar_meta()
    cv_m = cv_agrupada(Xn_m, y_m, g_m, gens)
    anid = cv_anidada_lambda(Xn_m, y_m, g_m, gens)
    cv_m["oof"]["NEAT (λ anidado)"] = anid["pred"]
    res["meta"] = {"n_registros": int(len(y_m)), "n_estudios": int(len(np.unique(g_m))),
                   "modelos": _bloque_modelos(y_m, cv_m, g_m, 1.0),
                   "lambdas_elegidos_cv_anidada": anid["lambdas_elegidos"]}
    print("[meta α]", json.dumps({k: v["R2"] for k, v in res["meta"]["modelos"].items()}), flush=True)

    # 3. SHAP
    imp_r, shap_r, _ = importancia_shap(Xn_r, y_r, VARS_REPLICAS)
    imp_m, shap_m, _ = importancia_shap(Xn_m, y_m, VARS_META)
    res["shap"] = {"replicas": imp_r, "meta": imp_m}

    # 4. Curva de aprendizaje
    res["curva_aprendizaje"] = curva_aprendizaje(Xn_r, y_r, g_r, max(15, gens // 2))
    print("[curva]", json.dumps(res["curva_aprendizaje"]), flush=True)

    # 5. Paita
    res["paita"] = predicciones_paita(X_r, y_r, B=30 if args.rapido else 100)

    # Figuras y salidas
    figura_comparacion(res, RUTA_RES / "fig4_comparacion_modelos_ic95.png")
    figura_shap(shap_r, Xn_r, VARS_REPLICAS, RUTA_RES / "fig5a_shap_replicas.png", "SHAP · XGBoost · cierre (réplicas)")
    figura_shap(shap_m, Xn_m, VARS_META, RUTA_RES / "fig5b_shap_meta.png", "SHAP · XGBoost · α (meta-dataset)")
    figura_curva(res["curva_aprendizaje"], RUTA_RES / "fig6_curva_aprendizaje.png")
    (RUTA_RES / "resumen_f3.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[OK]", RUTA_RES)


if __name__ == "__main__":
    sys.exit(main())
