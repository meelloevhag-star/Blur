"""
Revisión mayor · análisis que responden al revisor (ver articulo/respuesta_revisor.md).

  A1  Confusión fuente ↔ variables: tabla cruzada y validación leave-one-source-out (LOSO).
  A2  GroupKFold repetido (5 particiones × R repeticiones) con ajuste anidado de TODOS los modelos
      y comparación pareada con la prueba t corregida de Nadeau–Bengio.
  A3  Fuga: KFold por filas vs. GroupKFold con el mismo código, semillas y modelos.
  A4  Explicabilidad: SHAP fuera de muestra y permutación sobre el NEAT final con el λ elegido.
  A5  Aprendizaje continuo: prueba secuencial en la que campeón, candidato en caliente y candidato
      desde cero se evalúan sobre los MISMOS grupos retenidos del lote nuevo, con 10 semillas.
  A6  Paita: bootstrap por grupos y comprobación de rango dentro de los datos marinos.
  A7  Agente cristalino (CA) como variable propia (7 entradas para las réplicas).

Uso:
    python -m biocrete_neat.analisis_revision            # completo (~20 min con 4 núcleos)
    python -m biocrete_neat.analisis_revision --rapido   # prueba rápida
"""

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats
from sklearn.base import clone
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV, GroupKFold, KFold
from xgboost import XGBRegressor

from biocrete_neat.aprendizaje_continuo import evolucionar, lotes_demo
from biocrete_neat.entrenar_neat import RUTA_CFG

RUTA_BASE = Path(__file__).resolve().parent
RUTA_RES = RUTA_BASE / "resultados" / "revision"
RUTA_REPLICAS = RUTA_BASE / "datos" / "replicas_cierre_fisuras.csv"
SEMILLA = 2026
LAMBDAS = (2e-4, 8e-4, 1.6e-3)

VARS_R = ["Ancho fisura w0 (mm)", "Edad (d)", "Protección bio (0-3)", "Ambiente marino", "Lactato de calcio",
          "Curado previo", "Agente cristalino"]
MIN_R = np.zeros(7)
MAX_R = np.array([1.0, 480.0, 3.0, 1.0, 1.0, 1.0, 1.0])
MONOTONIA_R = "(-1,1,0,0,0,0,0)"


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------

def ruta_config(n_entradas: int) -> Path:
    """Config NEAT idéntica a la base salvo el número de entradas."""
    if n_entradas == 6:
        return RUTA_CFG
    destino = RUTA_BASE / f"config_neat_{n_entradas}.txt"
    texto = re.sub(r"num_inputs\s*=\s*\d+", f"num_inputs              = {n_entradas}",
                   RUTA_CFG.read_text(encoding="utf-8"))
    if not destino.exists() or destino.read_text(encoding="utf-8") != texto:
        destino.write_text(texto, encoding="utf-8")
    return destino


def cargar_replicas7(ruta: Path = RUTA_REPLICAS):
    with open(ruta, encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))
    X = np.array([[float(r["w0_mm"]), float(r["edad_dias"]), float(r["nivel_proteccion"]), float(r["ambiente_marino"]),
                   float(r["usa_lactato"] or 0), 1.0 if r["regimen"] == "curado_previo" else 0.0,
                   1.0 if r["portador"] == "cristalino" else 0.0] for r in filas])
    y = np.array([float(r["cierre_pct"]) / 100.0 for r in filas])
    return X, y, np.array([r["grupo_probeta"] for r in filas]), np.array([r["fuente"] for r in filas])


RUTA_META_V2 = RUTA_BASE / "datos" / "literatura" / "meta_dataset_cab_v2.csv"
VARS_M = ["a/c", "Ancho fisura (mm)", "Edad (d)", "Protección bio (0-3)", "Ambiente marino", "Lactato de calcio"]
MIN_M = np.array([0.25, 0.0, 0.0, 0.0, 0.0, 0.0])
MAX_M = np.array([0.75, 1.5, 400.0, 3.0, 1.0, 1.0])


def cargar_meta_v2(objetivo: str, solo_verificadas: bool = False):
    """Meta-dataset v2 (regla de α documentada en datos/literatura/regla_alpha.md).

    objetivo = "alpha": α con base 'referencia'; "cierre": cierre óptico %. Solo filas usar_en_modelo = si
    y con las 6 entradas completas (no se imputa nada). Devuelve X normalizado, y, grupos (estudio), info.
    """
    with open(RUTA_META_V2, encoding="utf-8", newline="") as f:
        filas = [r for r in csv.DictReader(f) if r["usar_en_modelo"].strip() == "si"]
    cols = ["a_c", "ancho_fisura_mm", "edad_curado_dias", "nivel_proteccion", "ambiente_marino", "usa_lactato"]
    if objetivo == "alpha":
        cand = [r for r in filas if r["alpha_equiv"].strip() and r["alpha_base"].strip() == "referencia"]
        col_y, escala = "alpha_equiv", 1.0
    else:
        cand = [r for r in filas if r["cierre_fisura_pct"].strip()]
        col_y, escala = "cierre_fisura_pct", 100.0
    if solo_verificadas:
        cand = [r for r in cand if r["verificado"].strip() == "si"]
    completas = [r for r in cand if all(r[c].strip() for c in cols)]
    X = np.array([[float(r[c]) for c in cols] for r in completas])
    y = np.clip(np.array([float(r[col_y]) / escala for r in completas]), 0.0, 1.0)
    g = np.array([r["estudio"] for r in completas])
    info = {"n_candidatas": len(cand), "n_completas": len(completas), "n_estudios": int(len(np.unique(g))),
            "n_marino": int((X[:, 4] == 1).sum()), "por_estudio": dict(Counter(g.tolist()).most_common())}
    return np.clip((X - MIN_M) / (MAX_M - MIN_M), 0.0, 1.0), y, g, info


def normalizar7(X):
    return np.clip((X - MIN_R) / (MAX_R - MIN_R), 0.0, 1.0)


def tabla_confusion(X, y, fuentes) -> dict:
    """A1: cómo se reparten las variables entre fuentes (para declarar la confusión)."""
    salida = {}
    for f in np.unique(fuentes):
        m = fuentes == f
        salida[str(f)] = {
            "n": int(m.sum()),
            "ambiente_marino": sorted({int(v) for v in X[m, 3]}),
            "edad_dias": [float(X[m, 1].min()), float(X[m, 1].max())],
            "w0_mm": [round(float(X[m, 0].min()), 3), round(float(X[m, 0].max()), 3)],
            "niveles_proteccion": {str(int(k)): int(v) for k, v in sorted(Counter(X[m, 2]).items())},
            "lactato_calcio": int(X[m, 4].sum()), "curado_previo": int(X[m, 5].sum()),
            "agente_cristalino": int(X[m, 6].sum()),
            "pct_cierre_100": round(float((y[m] >= 0.9999).mean() * 100), 1),
            "pct_cierre_0": round(float((y[m] <= 1e-4).mean() * 100), 1),
        }
    return salida


# ---------------------------------------------------------------------------
# Modelos y validación
# ---------------------------------------------------------------------------

def _xgb(**kw):
    base = dict(n_estimators=400, max_depth=4, learning_rate=0.04, subsample=0.8, colsample_bytree=0.9,
                min_child_weight=3, reg_lambda=1.0, random_state=SEMILLA, n_jobs=1, verbosity=0)
    base.update(kw)
    return XGBRegressor(**base)


REJILLAS = {
    "Ridge": (Ridge(), {"alpha": [0.1, 1.0, 10.0]}),
    "RandomForest": (RandomForestRegressor(n_estimators=300, random_state=SEMILLA, n_jobs=1),
                     {"max_depth": [4, 8, None], "min_samples_leaf": [1, 3, 10]}),
    "XGBoost": (_xgb(), {"max_depth": [2, 4, 6], "learning_rate": [0.03, 0.1], "n_estimators": [200, 500]}),
}


def _divisor(protocolo: str, k: int, semilla: int):
    if protocolo == "grupos":
        return GroupKFold(n_splits=k, shuffle=True, random_state=semilla)
    if protocolo == "filas":
        return KFold(n_splits=k, shuffle=True, random_state=semilla)
    raise ValueError(protocolo)


def _neat(args):
    Xtr, ytr, Xte, lam, gens, semilla, cfg = args
    ganador, red, _, _ = evolucionar(Xtr, ytr, gens, semilla, lam=lam, ruta_cfg=cfg)
    pred = np.array([red.activate(x)[0] for x in Xte])
    return pred, len([n for n in ganador.nodes if n >= 1])


def particiones(X, y, grupos, protocolo, repeticiones, k=5, fuentes=None):
    """Lista de (rep, pliegue, tr, te). protocolo ∈ {grupos, filas, fuente}."""
    if protocolo == "fuente":
        return [(0, i, np.flatnonzero(fuentes != f), np.flatnonzero(fuentes == f))
                for i, f in enumerate(np.unique(fuentes))]
    k = min(k, len(np.unique(grupos)))
    return [(r, i, tr, te) for r in range(repeticiones)
            for i, (tr, te) in enumerate(_divisor(protocolo, k, SEMILLA + r).split(X, y, grupos))]


def evaluar(X, y, grupos, protocolo, repeticiones, gens, cfg, fuentes=None, k_int=3, workers=4) -> dict:
    """Validación externa con ajuste anidado de todos los modelos; devuelve métricas por pliegue y repetición."""
    prot_int = "filas" if protocolo == "filas" else "grupos"
    parts = particiones(X, y, grupos, protocolo, repeticiones, fuentes=fuentes)
    preds = {m: {} for m in [*REJILLAS, "NEAT"]}
    elegidos = {m: [] for m in [*REJILLAS, "NEAT"]}
    internos = {}
    for r, i, tr, te in parts:
        kk = min(k_int, len(np.unique(grupos[tr])))
        internos[(r, i)] = list(_divisor(prot_int, kk, SEMILLA + 100 + r).split(X[tr], y[tr], grupos[tr]))
        for nombre, (est, rejilla) in REJILLAS.items():
            gs = GridSearchCV(clone(est), rejilla, cv=internos[(r, i)], scoring="r2", n_jobs=workers).fit(X[tr], y[tr])
            preds[nombre][(r, i)] = np.clip(gs.predict(X[te]), 0.0, 1.0)
            elegidos[nombre].append(dict(gs.best_params_))

    # NEAT: etapa 1 (λ por validación interna), etapa 2 (pliegue externo con el λ elegido)
    tr_de = {(r, i): tr for r, i, tr, _ in parts}
    tareas, claves = [], []
    for r, i, tr, te in parts:
        for lam in LAMBDAS:
            for j, (a, b) in enumerate(internos[(r, i)]):
                tareas.append((X[tr][a], y[tr][a], X[tr][b], lam, gens, SEMILLA + 1000 * r + 10 * i + j, cfg))
                claves.append((r, i, lam, j))
    with ProcessPoolExecutor(max_workers=workers) as ex:
        res1 = list(ex.map(_neat, tareas))
    puntajes = {}
    for (r, i, lam, j), (p, _) in zip(claves, res1):
        b = internos[(r, i)][j][1]
        puntajes.setdefault((r, i, lam), []).append(mean_squared_error(y[tr_de[(r, i)]][b], p))
    tareas2 = []
    for r, i, tr, te in parts:
        lam = min(LAMBDAS, key=lambda l: np.mean(puntajes[(r, i, l)]))
        elegidos["NEAT"].append({"lambda": lam})
        tareas2.append((X[tr], y[tr], X[te], lam, gens, SEMILLA + 7 * r + i, cfg))
    with ProcessPoolExecutor(max_workers=workers) as ex:
        res2 = list(ex.map(_neat, tareas2))
    ocultas = []
    for (r, i, tr, te), (p, n_oc) in zip(parts, res2):
        preds["NEAT"][(r, i)] = p
        ocultas.append(n_oc)

    # Métricas
    salida = {"protocolo": protocolo, "repeticiones": repeticiones, "n": int(len(y)), "modelos": {}}
    pliegues = {}
    for nombre in preds:
        r2_rep, mae_rep = [], []
        for r in sorted({r for r, *_ in parts}):
            idx = [(i, te) for rr, i, _, te in parts if rr == r]
            yt = np.concatenate([y[te] for _, te in idx])
            yp = np.concatenate([preds[nombre][(r, i)] for i, _ in idx])
            r2_rep.append(r2_score(yt, yp))
            mae_rep.append(mean_absolute_error(yt, yp))
        pliegues[nombre] = [mean_squared_error(y[te], preds[nombre][(r, i)]) for r, i, _, te in parts]
        salida["modelos"][nombre] = {
            "R2_medio": round(float(np.mean(r2_rep)), 3),
            "R2_de": round(float(np.std(r2_rep, ddof=1)), 3) if len(r2_rep) > 1 else 0.0,
            "R2_por_repeticion": [round(float(v), 3) for v in r2_rep],
            "MAE_medio": round(float(np.mean(mae_rep)), 4),
            "hiperparametros_elegidos": _frecuencias(elegidos[nombre]),
        }
    salida["modelos"]["NEAT"]["neuronas_ocultas_prom"] = round(float(np.mean(ocultas)), 2)
    if protocolo != "fuente":
        n_te = np.mean([len(te) for *_, te in parts])
        n_tr = np.mean([len(tr) for _, _, tr, _ in parts])
        mejor = max(salida["modelos"], key=lambda m: salida["modelos"][m]["R2_medio"])
        salida["mejor"] = mejor
        salida["nadeau_bengio_vs_mejor"] = {m: nadeau_bengio(pliegues[m], pliegues[mejor], n_te, n_tr)
                                            for m in pliegues if m != mejor}
    else:
        salida["por_fuente_de_prueba"] = {
            str(f): {m: round(float(r2_score(y[te], preds[m][(0, i)])), 3) for m in preds}
            for (_, i, _, te), f in zip(parts, np.unique(fuentes))}
    return salida


def _frecuencias(lista):
    c = Counter(json.dumps(d, sort_keys=True) for d in lista)
    return [{"params": json.loads(k), "veces": v} for k, v in c.most_common(3)]


def nadeau_bengio(mse_a, mse_b, n_test, n_train) -> dict:
    """Prueba t corregida (Nadeau y Bengio, 2003) sobre diferencias pareadas de MSE por pliegue."""
    d = np.asarray(mse_a) - np.asarray(mse_b)
    J = len(d)
    var = np.var(d, ddof=1)
    if var == 0:
        return {"t": 0.0, "p": 1.0, "dif_mse_media": float(d.mean())}
    t = d.mean() / math.sqrt((1.0 / J + n_test / n_train) * var)
    p = 2 * stats.t.sf(abs(t), J - 1)
    return {"t": round(float(t), 3), "p": round(float(p), 4), "dif_mse_media": round(float(d.mean()), 5)}


# ---------------------------------------------------------------------------
# A4 · Explicabilidad
# ---------------------------------------------------------------------------

def shap_fuera_de_muestra(X, y, grupos, nombres, k=5):
    import shap

    valores, Xs = [], []
    kk = min(k, len(np.unique(grupos)))
    for tr, te in GroupKFold(n_splits=kk, shuffle=True, random_state=SEMILLA).split(X, y, grupos):
        m = _xgb().fit(X[tr], y[tr])
        valores.append(shap.TreeExplainer(m).shap_values(X[te]))
        Xs.append(X[te])
    V, XX = np.vstack(valores), np.vstack(Xs)
    imp = np.abs(V).mean(axis=0)
    return [{"variable": nombres[j], "shap_medio_abs": round(float(imp[j]), 4)} for j in np.argsort(imp)[::-1]], V, XX


def neat_final(X, y, lam, gens, cfg, nombres, repeticiones=30) -> dict:
    ganador, red, _, _ = evolucionar(X, y, gens, SEMILLA, lam=lam, ruta_cfg=cfg)
    base = np.array([red.activate(x)[0] for x in X])
    rmse0 = math.sqrt(mean_squared_error(y, base))
    rng = np.random.default_rng(SEMILLA)
    imp = []
    for j, nombre in enumerate(nombres):
        deltas = []
        for _ in range(repeticiones):
            Xp = X.copy()
            Xp[:, j] = rng.permutation(Xp[:, j])
            deltas.append(math.sqrt(mean_squared_error(y, np.array([red.activate(x)[0] for x in Xp]))) - rmse0)
        imp.append({"variable": nombre, "delta_rmse": round(float(np.mean(deltas)), 4)})
    activas = [c for c in ganador.connections.values() if c.enabled]
    usadas = sorted({nombres[-k - 1] for (k, _o) in (c.key for c in activas) if k < 0}, key=nombres.index)
    return {"lambda": lam, "neuronas_ocultas": len([n for n in ganador.nodes if n >= 1]),
            "conexiones_activas": len(activas), "entradas_usadas": usadas,
            "importancia_permutacion": sorted(imp, key=lambda d: -d["delta_rmse"])}


# ---------------------------------------------------------------------------
# A5 · Prueba secuencial de aprendizaje continuo
# ---------------------------------------------------------------------------

def _secuencial_semilla(args):
    X, y, g, f, semilla, gens, cfg = args
    lotes = [m for _, m in lotes_demo(f, g)]
    salida = []
    for k in (1, 2):
        previo = np.flatnonzero(np.any(lotes[:k], axis=0))
        nuevo = np.flatnonzero(lotes[k])
        _, red_c, estado, _ = evolucionar(X[previo], y[previo], gens, semilla, ruta_cfg=cfg)
        pc, pw, pf = (np.zeros(len(nuevo)) for _ in range(3))
        for _, te_rel in GroupKFold(n_splits=5, shuffle=True, random_state=semilla).split(nuevo, groups=g[nuevo]):
            te = nuevo[te_rel]
            tr = np.r_[previo, np.setdiff1d(nuevo, te)]
            _, red_w, _, _ = evolucionar(X[tr], y[tr], gens, semilla + 1, estado=estado, ruta_cfg=cfg)
            _, red_f, _, _ = evolucionar(X[tr], y[tr], gens, semilla + 1, ruta_cfg=cfg)
            pc[te_rel] = [red_c.activate(x)[0] for x in X[te]]
            pw[te_rel] = [red_w.activate(x)[0] for x in X[te]]
            pf[te_rel] = [red_f.activate(x)[0] for x in X[te]]
        yn = y[nuevo]
        salida.append({"lote": k + 1, "campeon": r2_score(yn, pc), "caliente": r2_score(yn, pw),
                       "frio": r2_score(yn, pf)})
    return salida


def prueba_secuencial(X, y, g, f, semillas, gens, cfg, workers=4) -> dict:
    with ProcessPoolExecutor(max_workers=workers) as ex:
        res = list(ex.map(_secuencial_semilla, [(X, y, g, f, SEMILLA + s, gens, cfg) for s in range(semillas)]))
    salida = {"semillas": semillas, "generaciones": gens, "lotes": {}}
    for lote in (2, 3):
        filas = [r for rs in res for r in rs if r["lote"] == lote]
        bloque = {}
        for clave in ("campeon", "caliente", "frio"):
            v = [r[clave] for r in filas]
            bloque[clave] = {"media": round(float(np.mean(v)), 3),
                             "de": round(float(np.std(v, ddof=1)), 3) if len(v) > 1 else 0.0}
        dif = np.array([r["caliente"] - r["frio"] for r in filas])
        bloque["caliente_menos_frio"] = {
            "media": round(float(dif.mean()), 3),
            "de": round(float(dif.std(ddof=1)), 3) if len(dif) > 1 else 0.0,
            "semillas_caliente_mejor": int((dif > 0).sum()),
            "p_wilcoxon": round(float(stats.wilcoxon(dif).pvalue), 4) if len(dif) > 5 and np.any(dif != 0) else None}
        salida["lotes"][str(lote)] = bloque
    return salida


# ---------------------------------------------------------------------------
# A6 · Paita
# ---------------------------------------------------------------------------

ESCENARIOS = [("Directa · 0,2 mm", 0.2, 1), ("Directa · 0,5 mm", 0.5, 1), ("Directa · 1,0 mm", 1.0, 1),
              ("Portador · 0,3 mm", 0.3, 2), ("Encapsulación · 0,3 mm", 0.3, 3)]


def predicciones_paita(X, y, grupos, B=100) -> list[dict]:
    """Ensamble XGBoost monótono con bootstrap POR GRUPOS; avisos de rango dentro de los datos marinos."""
    rng = np.random.default_rng(SEMILLA)
    Xn = normalizar7(X)
    Xe = normalizar7(np.array([[w0, 90.0, nivel, 1.0, 1.0, 0.0, 0.0] for _, w0, nivel in ESCENARIOS]))
    ug = np.unique(grupos)
    por_grupo = {gg: np.flatnonzero(grupos == gg) for gg in ug}
    preds = []
    for b in range(B):
        idx = np.concatenate([por_grupo[gg] for gg in rng.choice(ug, len(ug), replace=True)])
        m = _xgb(random_state=SEMILLA + b, monotone_constraints=MONOTONIA_R).fit(Xn[idx], y[idx])
        preds.append(np.clip(m.predict(Xe), 0, 1) * 100)
    preds = np.array(preds)
    marino = X[:, 3] == 1
    w0_max_marino = float(X[marino, 0].max())
    salida = []
    for k, (nombre, w0, nivel) in enumerate(ESCENARIOS):
        avisos = []
        if not (marino & (X[:, 4] == 1)).any():
            avisos.append("a")
        if not (marino & (X[:, 2] == nivel)).any():
            avisos.append("b")
        if w0 > w0_max_marino:
            avisos.append("c")
        salida.append({"escenario": nombre, "cierre_medio_pct": round(float(preds[:, k].mean()), 1),
                       "cierre_IC95_pct": [round(float(np.percentile(preds[:, k], 2.5)), 1),
                                           round(float(np.percentile(preds[:, k], 97.5)), 1)],
                       "avisos": avisos, "w0_max_marino_mm": round(w0_max_marino, 3)})
    return salida


# ---------------------------------------------------------------------------
# Figuras
# ---------------------------------------------------------------------------

def figura_protocolos(res, ruta):
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    for ax, clave, titulo in [(axes[0], "replicas", "Cierre (réplicas, 2 laboratorios)"),
                              (axes[1], "literatura_cierre", "Cierre (literatura, multi-estudio)"),
                              (axes[2], "meta", "α (meta-dataset v2)")]:
        modelos = list(res[clave]["grupos"]["modelos"])
        x = np.arange(len(modelos))
        for desp, prot, color, etiqueta in [(-0.2, "filas", "#d97706", "KFold por filas"),
                                            (0.2, "grupos", "#0f766e", "GroupKFold (sin fuga)")]:
            M = res[clave][prot]["modelos"]
            ax.bar(x + desp, [M[m]["R2_medio"] for m in modelos], 0.4, yerr=[M[m]["R2_de"] for m in modelos],
                   color=color, capsize=3, label=etiqueta)
        ax.set_xticks(x, modelos, fontsize=9)
        ax.axhline(0, color="k", lw=0.8)
        ax.set_ylabel("R² fuera de muestra (media ± DE)")
        ax.set_title(titulo, fontsize=10)
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(ruta, dpi=220)
    plt.close(fig)


def figura_secuencial(sec, ruta):
    fig, ax = plt.subplots(figsize=(7, 4))
    lotes = ["2", "3"]
    x = np.arange(len(lotes))
    for desp, clave, color, etiqueta in [(-0.27, "campeon", "#94a3b8", "Campeón sin actualizar"),
                                         (0.0, "caliente", "#0f766e", "Actualizado (arranque en caliente)"),
                                         (0.27, "frio", "#d97706", "Actualizado (desde cero)")]:
        ax.bar(x + desp, [sec["lotes"][l][clave]["media"] for l in lotes], 0.27,
               yerr=[sec["lotes"][l][clave]["de"] for l in lotes], color=color, capsize=3, label=etiqueta)
    ax.set_xticks(x, ["Lote 2: marino, curado previo", "Lote 3: marino, exposición directa"], fontsize=9)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_ylabel(f"R² en grupos retenidos (media ± DE, {sec['semillas']} semillas)")
    ax.set_title("Protocolo de actualización simulado (mismos grupos de prueba)", fontsize=10)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(ruta, dpi=220)
    plt.close(fig)


def figura_shap(V, X, nombres, ruta, titulo):
    import shap

    plt.figure()
    shap.summary_plot(V, X, feature_names=nombres, show=False, plot_size=(7, 4))
    plt.title(titulo, fontsize=10)
    plt.tight_layout()
    plt.savefig(ruta, dpi=220)
    plt.close()


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------

def _lambda_modal(bloque) -> float:
    c = Counter()
    for d in bloque["modelos"]["NEAT"]["hiperparametros_elegidos"]:
        c[d["params"]["lambda"]] += d["veces"]
    return c.most_common(1)[0][0]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true")
    a = ap.parse_args(argv)
    R, R_filas, gens, semillas, B = (1, 1, 10, 2, 10) if a.rapido else (5, 3, 50, 10, 100)
    RUTA_RES.mkdir(parents=True, exist_ok=True)
    cfg7, cfg6 = ruta_config(7), ruta_config(6)

    X, y, g, f = cargar_replicas7()
    Xn = normalizar7(X)
    Xm, ym, gm, info_a = cargar_meta_v2("alpha")
    Xl, yl, gl, info_l = cargar_meta_v2("cierre", solo_verificadas=True)
    res = {"semilla": SEMILLA, "generaciones_neat": gens, "lambdas_rejilla": list(LAMBDAS),
           "confusion_fuente": tabla_confusion(X, y, f)}

    res["replicas"] = {"grupos": evaluar(Xn, y, g, "grupos", R, gens, cfg7),
                       "filas": evaluar(Xn, y, g, "filas", R_filas, gens, cfg7),
                       "fuente": evaluar(Xn, y, g, "fuente", 1, gens, cfg7, fuentes=f)}
    print("[réplicas]", {p: {m: v["R2_medio"] for m, v in res["replicas"][p]["modelos"].items()}
                         for p in res["replicas"]}, flush=True)
    res["meta"] = {"info": info_a, "grupos": evaluar(Xm, ym, gm, "grupos", R, gens, cfg6),
                   "filas": evaluar(Xm, ym, gm, "filas", R, gens, cfg6)}
    res["literatura_cierre"] = {"info": info_l, "grupos": evaluar(Xl, yl, gl, "grupos", R, gens, cfg6),
                                "filas": evaluar(Xl, yl, gl, "filas", R, gens, cfg6)}
    for clave in ("meta", "literatura_cierre"):
        print(f"[{clave}]", {p: {m: v["R2_medio"] for m, v in res[clave][p]["modelos"].items()}
                             for p in ("grupos", "filas")}, flush=True)

    imp_r, V_r, X_r = shap_fuera_de_muestra(Xn, y, g, VARS_R)
    imp_m, V_m, X_m = shap_fuera_de_muestra(Xm, ym, gm, VARS_M)
    imp_l, V_l, X_l = shap_fuera_de_muestra(Xl, yl, gl, VARS_M)
    res["explicabilidad"] = {
        "shap_oof_replicas": imp_r, "shap_oof_meta": imp_m, "shap_oof_literatura_cierre": imp_l,
        "neat_final_replicas": neat_final(Xn, y, _lambda_modal(res["replicas"]["grupos"]), gens, cfg7, VARS_R),
        "neat_final_meta": neat_final(Xm, ym, _lambda_modal(res["meta"]["grupos"]), gens, cfg6, VARS_M),
        "neat_final_literatura_cierre": neat_final(Xl, yl, _lambda_modal(res["literatura_cierre"]["grupos"]), gens,
                                                   cfg6, VARS_M)}

    res["secuencial"] = prueba_secuencial(Xn, y, g, f, semillas, max(10, gens - 10), cfg7)
    print("[secuencial]", res["secuencial"]["lotes"], flush=True)
    res["paita"] = predicciones_paita(X, y, g, B=B)

    figura_protocolos(res, RUTA_RES / "fig8_protocolos_filas_vs_grupos.png")
    figura_secuencial(res["secuencial"], RUTA_RES / "fig9_actualizacion_secuencial.png")
    figura_shap(V_r, X_r, VARS_R, RUTA_RES / "fig10a_shap_oof_replicas.png", "SHAP fuera de muestra · cierre")
    figura_shap(V_m, X_m, VARS_M, RUTA_RES / "fig10b_shap_oof_meta.png", "SHAP fuera de muestra · α (v2)")
    figura_shap(V_l, X_l, VARS_M, RUTA_RES / "fig10c_shap_oof_literatura.png", "SHAP fuera de muestra · cierre (literatura)")
    (RUTA_RES / "resumen_revision.json").write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str),
                                                    encoding="utf-8")
    print("[OK]", RUTA_RES)
    return 0


if __name__ == "__main__":
    sys.exit(main())
