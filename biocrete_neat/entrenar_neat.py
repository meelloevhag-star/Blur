r"""
BioCrete-NEAT (Módulo Micro — Prototipo para Artículo 2)
Neuroevolución de Redes Neuronales Artificiales (NEAT) sobre un meta-dataset
curado de literatura de Concreto Autocurativo Bacteriano (CAB).

Objetivo científico:
  Predecir el cierre de fisuras (%) y la reducción de transporte de cloruros (alpha)
  a partir de 6 variables físicas simples (a/c, ancho de fisura w0, edad de curado,
  nivel de protección biológica, ambiente marino y uso de lactato de calcio),
  empezando desde 0 neuronas ocultas para obtener la red MÍNIMA explicable,
  y conectar esa predicción micro con los umbrales macro de BioCrete-Markov.

Ejecutar con:
  .venv\Scripts\python.exe entrenar_neat.py
"""

import csv
import json
import math
import random
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import neat
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold

RUTA_BASE = Path(__file__).resolve().parent
RUTA_CSV = RUTA_BASE / "datos" / "meta_dataset_cab.csv"
RUTA_CFG = RUTA_BASE / "config_neat.txt"
RUTA_RES = RUTA_BASE / "resultados"

NOMBRES_ENTRADAS = [
    "a/c",
    "Ancho fisura (mm)",
    "Edad curado (d)",
    "Protección bio (0-3)",
    "Ambiente marino",
    "Usa lactato",
]


def cargar_dataset() -> tuple[np.ndarray, np.ndarray, np.ndarray, list[dict]]:
    """Lee el CSV curado y normaliza las 6 variables físicas en [0, 1]."""
    filas = []
    with open(RUTA_CSV, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            filas.append(row)

    X_raw = np.array([
        [
            float(r["a_c"]),
            float(r["ancho_fisura_mm"]),
            float(r["edad_curado_dias"]),
            float(r["nivel_proteccion"]),
            float(r["ambiente_marino"]),
            float(r["usa_lactato"]),
        ]
        for r in filas
    ], dtype=float)

    y_cierre = np.array([float(r["cierre_fisura_pct"]) / 100.0 for r in filas], dtype=float)
    y_alpha = np.array([float(r["alpha_equiv"]) for r in filas], dtype=float)
    return X_raw, y_cierre, y_alpha, filas


def normalizar(X: np.ndarray) -> np.ndarray:
    """Normalización física fija (no depende del split, evita fuga de datos)."""
    # Rangos físicos fijos: a/c [0.30, 0.75], w0 [0, 1.0], edad [0, 120], prot [0, 3], mar [0, 1], lact [0, 1]
    mins = np.array([0.30, 0.00, 0.0, 0.0, 0.0, 0.0])
    maxs = np.array([0.75, 1.00, 120.0, 3.0, 1.0, 1.0])
    return np.clip((X - mins) / (maxs - mins), 0.0, 1.0)


def evolucionar_neat(X_tr: np.ndarray, y_tr: np.ndarray, generaciones: int = 110,
                     semilla: int = 42, penalizar_complejidad: float = 0.00012):
    """
    Entrena una red neuronal mediante NEAT (empezando con 0 neuronas ocultas).
    Incluye una pequeña penalización por número de nodos/conexiones para favorecer
    redes compactas, explicables y sin sobreajuste.
    """
    random.seed(semilla)
    np.random.seed(semilla)
    config = neat.Config(
        neat.DefaultGenome,
        neat.DefaultReproduction,
        neat.DefaultSpeciesSet,
        neat.DefaultStagnation,
        str(RUTA_CFG),
    )
    pop = neat.Population(config)
    historia_rmse = []

    def evaluar_poblacion(genomes, cfg):
        mejor_mse = 1e9
        for _gid, genome in genomes:
            red = neat.nn.FeedForwardNetwork.create(genome, cfg)
            preds = np.array([red.activate(x)[0] for x in X_tr], dtype=float)
            mse = float(np.mean((preds - y_tr) ** 2))
            if mse < mejor_mse:
                mejor_mse = mse
            n_ocultos = len([n for n in genome.nodes if n >= cfg.genome_config.num_outputs])
            n_conex = sum(1 for c in genome.connections.values() if c.enabled)
            # Fitness = negativo del MSE menos penalización suave por complejidad (principio de Occam)
            genome.fitness = -mse - penalizar_complejidad * (n_ocultos + 0.15 * n_conex)
        historia_rmse.append(math.sqrt(mejor_mse))

    ganador = pop.run(evaluar_poblacion, generaciones)
    red_ganadora = neat.nn.FeedForwardNetwork.create(ganador, config)
    return ganador, red_ganadora, config, historia_rmse


LAMBDA_PARSIMONIA_ALTA = 8e-4      # Tabla IV: NEAT parsimonia alta (0 ocultas)
LAMBDA_PARSIMONIA_MODERADA = 1.2e-4  # Tabla IV: NEAT con nodos ocultos permitidos


def evaluar_validacion_cruzada(X_norm: np.ndarray, y: np.ndarray, etiqueta_obj: str, escala: float = 1.0,
                               penalizar_complejidad: float = LAMBDA_PARSIMONIA_MODERADA) -> dict:
    """
    Validación cruzada 5-fold justa: compara NEAT frente a Ridge y Random Forest
    sobre datos NO vistos durante el entrenamiento (out-of-fold).
    """
    kf = KFold(n_splits=5, shuffle=True, random_state=2026)
    pred_neat = np.zeros_like(y)
    pred_ridge = np.zeros_like(y)
    pred_rf = np.zeros_like(y)
    ocultos_por_fold = []

    for fold_idx, (tr, te) in enumerate(kf.split(X_norm)):
        # 1. NEAT
        ganador, red, cfg, _ = evolucionar_neat(X_norm[tr], y[tr], generaciones=75, semilla=100 + fold_idx,
                                                penalizar_complejidad=penalizar_complejidad)
        pred_neat[te] = [red.activate(x)[0] for x in X_norm[te]]
        n_oc = len([n for n in ganador.nodes if n >= cfg.genome_config.num_outputs])
        ocultos_por_fold.append(n_oc)

        # 2. Ridge (regresión lineal regularizada)
        ridge = Ridge(alpha=1.0)
        ridge.fit(X_norm[tr], y[tr])
        pred_ridge[te] = np.clip(ridge.predict(X_norm[te]), 0.0, 1.0)

        # 3. Random Forest
        rf = RandomForestRegressor(n_estimators=120, max_depth=5, random_state=2026)
        rf.fit(X_norm[tr], y[tr])
        pred_rf[te] = np.clip(rf.predict(X_norm[te]), 0.0, 1.0)

    def metricas(y_real, y_hat):
        return {
            "R2": round(float(r2_score(y_real * escala, y_hat * escala)), 3),
            "MAE": round(float(mean_absolute_error(y_real * escala, y_hat * escala)), 3),
            "RMSE": round(float(math.sqrt(mean_squared_error(y_real * escala, y_hat * escala))), 3),
        }

    return {
        "objetivo": etiqueta_obj,
        "lambda_parsimonia": penalizar_complejidad,
        "NEAT": metricas(y, pred_neat),
        "Ridge": metricas(y, pred_ridge),
        "RandomForest": metricas(y, pred_rf),
        "neat_neuronas_ocultas_promedio": round(float(np.mean(ocultos_por_fold)), 2),
        "pred_neat": pred_neat,
        "pred_rf": pred_rf,
        "pred_ridge": pred_ridge,
    }


def importancia_permutacion(red, X_norm: np.ndarray, y: np.ndarray, repeticiones: int = 30) -> list[dict]:
    """Mide cuánto empeora el RMSE al mezclar cada variable (explicabilidad clara sin caja negra)."""
    rng = np.random.default_rng(2026)
    base_preds = np.array([red.activate(x)[0] for x in X_norm])
    rmse_base = math.sqrt(mean_squared_error(y, base_preds))
    res = []
    for j, nombre in enumerate(NOMBRES_ENTRADAS):
        deltas = []
        for _ in range(repeticiones):
            X_perm = X_norm.copy()
            X_perm[:, j] = rng.permutation(X_perm[:, j])
            p_perm = np.array([red.activate(x)[0] for x in X_perm])
            deltas.append(math.sqrt(mean_squared_error(y, p_perm)) - rmse_base)
        res.append({"variable": nombre, "delta_rmse": round(float(np.mean(deltas)), 4)})
    res.sort(key=lambda d: d["delta_rmse"], reverse=True)
    return res


def graficar_resultados(historia_alpha: list[float], cv_alpha: dict, y_alpha: np.ndarray,
                        ganador_alpha, cfg_alpha, imp_alpha: list[dict]) -> None:
    """Genera 2 figuras científicas limpias (300 dpi) para el Artículo 2."""
    # Figura 1: Convergencia evolutiva + Real vs Predicho (5-fold CV)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.6), dpi=220)
    ax1.plot(range(1, len(historia_alpha) + 1), historia_alpha, color="#0f766e", lw=2.2)
    ax1.set_title("Evolución del error (RMSE) por generación — NEAT")
    ax1.set_xlabel("Generación evolutiva")
    ax1.set_ylabel("RMSE sobre α de transporte")
    ax1.grid(True, alpha=0.3)

    ax2.scatter(y_alpha, cv_alpha["pred_neat"], color="#0f766e", s=46, label=f"NEAT (R²={cv_alpha['NEAT']['R2']})", zorder=3)
    ax2.scatter(y_alpha, cv_alpha["pred_rf"], color="#d97706", marker="^", s=38, alpha=0.75, label=f"Random Forest (R²={cv_alpha['RandomForest']['R2']})")
    ax2.scatter(y_alpha, cv_alpha["pred_ridge"], color="#64748b", marker="s", s=30, alpha=0.6, label=f"Ridge lineal (R²={cv_alpha['Ridge']['R2']})")
    ax2.plot([0, 0.8], [0, 0.8], "k--", lw=1.1, label="Identidad (perfecto)")
    ax2.set_title("Validación cruzada 5-fold (datos no vistos)")
    ax2.set_xlabel("α real reportado en literatura")
    ax2.set_ylabel("α predicho (out-of-fold)")
    ax2.legend(fontsize=8.5)
    ax2.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(RUTA_RES / "fig1_neat_convergencia_y_comparacion.png", dpi=220)
    plt.close(fig)

    # Figura 2: Topología mínima evolucionada + Importancia de variables
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.0, 4.8), dpi=220)

    # Dibujar topología de la red NEAT ganadora
    inputs = list(cfg_alpha.genome_config.input_keys)
    outputs = list(cfg_alpha.genome_config.output_keys)
    hiddens = [n for n in ganador_alpha.nodes if n not in outputs]

    pos = {}
    for idx, k in enumerate(inputs):
        pos[k] = (0.12, 0.88 - idx * 0.15)
    for idx, k in enumerate(hiddens):
        y_pos = 0.50 if len(hiddens) == 1 else (0.78 - idx * (0.56 / max(len(hiddens) - 1, 1)))
        pos[k] = (0.52, y_pos)
    pos[outputs[0]] = (0.88, 0.50)

    for (u, v), cg in ganador_alpha.connections.items():
        if cg.enabled and u in pos and v in pos:
            color = "#0f766e" if cg.weight >= 0 else "#b91c1c"
            lw = min(3.2, 0.6 + abs(cg.weight) * 0.45)
            ax1.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]], color=color, lw=lw, alpha=0.75)

    for idx, k in enumerate(inputs):
        x, y = pos[k]
        ax1.scatter([x], [y], s=260, color="#1e293b", zorder=4)
        ax1.text(x - 0.03, y, NOMBRES_ENTRADAS[idx], ha="right", va="center", fontsize=8.5)
    for k in hiddens:
        x, y = pos[k]
        ax1.scatter([x], [y], s=280, color="#0284c7", zorder=4)
        ax1.text(x, y + 0.07, f"H{k}", ha="center", fontsize=8.5, fontweight="bold")
    xo, yo = pos[outputs[0]]
    ax1.scatter([xo], [yo], s=320, color="#0f766e", zorder=4)
    ax1.text(xo + 0.03, yo, "α predicho", ha="left", va="center", fontsize=9, fontweight="bold")

    ax1.set_xlim(-0.35, 1.15)
    ax1.set_ylim(0.0, 1.02)
    ax1.axis("off")
    ax1.set_title(f"Topología mínima evolucionada por NEAT\n({len(hiddens)} neuronas ocultas · {sum(1 for c in ganador_alpha.connections.values() if c.enabled)} conexiones activas)")

    # Importancia por permutación
    vars_ = [d["variable"] for d in imp_alpha][::-1]
    vals_ = [max(0.0, d["delta_rmse"]) for d in imp_alpha][::-1]
    ax2.barh(vars_, vals_, color="#0f766e", alpha=0.88)
    ax2.set_title("Importancia de variables en NEAT (permutación)")
    ax2.set_xlabel("Aumento de RMSE al perturbar la variable")
    ax2.grid(True, axis="x", alpha=0.3)

    fig.tight_layout()
    fig.savefig(RUTA_RES / "fig2_neat_topologia_y_importancia.png", dpi=220)
    plt.close(fig)


def main() -> None:
    RUTA_RES.mkdir(parents=True, exist_ok=True)
    X_raw, y_cierre, y_alpha, _filas = cargar_dataset()
    X_norm = normalizar(X_raw)

    print("=" * 72)
    print(f"BIOCRETE-NEAT · NEUROEVOLUCIÓN EXPLICABLE (n = {len(X_raw)} ensayos reales)")
    print("=" * 72)

    # 1. Validación cruzada 5-fold (honesta, datos fuera de muestra)
    cv_alpha_por_lambda = {
        str(lam): evaluar_validacion_cruzada(X_norm, y_alpha, "Reducción de cloruros/permeabilidad (alpha)",
                                             escala=1.0, penalizar_complejidad=lam)
        for lam in (LAMBDA_PARSIMONIA_ALTA, LAMBDA_PARSIMONIA_MODERADA)
    }
    cv_alpha = cv_alpha_por_lambda[str(LAMBDA_PARSIMONIA_ALTA)]
    cv_cierre = evaluar_validacion_cruzada(X_norm, y_cierre, "Cierre óptico de fisuras (%)", escala=100.0)

    print("\n[1] Comparación justa en Validación Cruzada 5-fold (α de cloruros):")
    for m in ("NEAT", "RandomForest", "Ridge"):
        print(f"    {m:<14} -> R2 = {cv_alpha[m]['R2']:>6} | MAE = {cv_alpha[m]['MAE']:>5} | RMSE = {cv_alpha[m]['RMSE']:>5}")
    print(f"    Neuronas ocultas promedio evolucionadas por NEAT: {cv_alpha['neat_neuronas_ocultas_promedio']}")

    print("\n[2] Comparación justa en Validación Cruzada 5-fold (Cierre de fisuras %):")
    for m in ("NEAT", "RandomForest", "Ridge"):
        print(f"    {m:<14} -> R2 = {cv_cierre[m]['R2']:>6} | MAE = {cv_cierre[m]['MAE']:>5}% | RMSE = {cv_cierre[m]['RMSE']:>5}%")

    # 2. Entrenamiento final sobre todo el meta-dataset para predicción a priori de nuestras mezclas
    gan_alpha, red_alpha, cfg_alpha, hist_alpha = evolucionar_neat(X_norm, y_alpha, generaciones=100, semilla=2026)
    gan_cierre, red_cierre, cfg_cierre, _ = evolucionar_neat(X_norm, y_cierre, generaciones=100, semilla=2026)

    n_oc_a = len([n for n in gan_alpha.nodes if n >= cfg_alpha.genome_config.num_outputs])
    n_cx_a = sum(1 for c in gan_alpha.connections.values() if c.enabled)
    imp_alpha = importancia_permutacion(red_alpha, X_norm, y_alpha)

    print(f"\n[3] Topología final evolucionada por NEAT (α): {n_oc_a} neuronas ocultas, {n_cx_a} conexiones activas")
    print("    Importancia de variables (permutación):")
    for d in imp_alpha:
        print(f"      - {d['variable']:<22}: ΔRMSE = +{d['delta_rmse']}")

    # 3. Predicción a priori para TU programa experimental en Paita-Colán (enfrentada contra umbral Markov)
    # Formato entrada: [a/c, ancho_fisura_mm, edad_curado_dias, nivel_proteccion (1=directa, 2=portador, 3=encap), marino=1, lactato=1]
    escenarios_propios = [
        ("Tu mezcla actual (a/c 0,68 · directa · fisura 0,2 mm · 90d)",  [0.68, 0.20, 90, 1, 1, 1], "No alcanzable (techo τ_bio)"),
        ("Tu mezcla actual (a/c 0,68 · directa · fisura 0,5 mm · 90d)",  [0.68, 0.50, 90, 1, 1, 1], "No alcanzable (techo τ_bio)"),
        ("Tu mezcla actual (a/c 0,68 · directa · fisura 1,0 mm · 90d)",  [0.68, 1.00, 90, 1, 1, 1], "No alcanzable (techo τ_bio)"),
        ("Mezcla futura (a/c 0,45 · directa · rec 50 mm · 0,2 mm · 90d)",[0.45, 0.20, 90, 1, 1, 1], "0,262 (BioCrete-Markov 25a)"),
        ("Mezcla futura (a/c 0,45 · portador · rec 40 mm · 0,3 mm · 90d)",[0.45, 0.30, 90, 2, 1, 1], "0,520 (BioCrete-Markov 25a)"),
        ("Mezcla futura (a/c 0,45 · encapsul. · rec 40 mm · 0,3 mm · 90d)",[0.45, 0.30, 90, 3, 1, 1], "0,331 (BioCrete-Markov 25a)"),
    ]

    pred_filas = []
    print("\n[4] Predicción a priori NEAT para tus ensayos de Paita vs. Umbral BioCrete-Markov:")
    for nombre, vec, umbral_mk in escenarios_propios:
        xn = normalizar(np.array([vec], dtype=float))[0]
        a_hat = round(float(red_alpha.activate(xn)[0]), 3)
        c_hat = round(float(red_cierre.activate(xn)[0]) * 100.0, 1)
        print(f"    - {nombre}")
        print(f"        NEAT predice: cierre = {c_hat:>5.1f}% | α = {a_hat:.3f}   <-->  Umbral Markov (25a): {umbral_mk}")
        pred_filas.append({
            "escenario": nombre,
            "cierre_predicho_neat_pct": c_hat,
            "alpha_predicho_neat": a_hat,
            "umbral_alpha_biocrete_markov_25a": umbral_mk,
        })

    # 4. Guardar resultados y gráficos
    graficar_resultados(hist_alpha, cv_alpha, y_alpha, gan_alpha, cfg_alpha, imp_alpha)

    with open(RUTA_RES / "predicciones_paita_neat_vs_markov.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(pred_filas[0].keys()))
        w.writeheader()
        w.writerows(pred_filas)

    resumen = {
        "n_ensayos_meta_dataset": len(X_raw),
        "cv_5fold_alpha": {k: v for k, v in cv_alpha.items() if not isinstance(v, np.ndarray)},
        "cv_5fold_alpha_por_lambda": {
            lam: {k: v for k, v in cv.items() if not isinstance(v, np.ndarray)}
            for lam, cv in cv_alpha_por_lambda.items()
        },
        "modelo_final_lambda_parsimonia": LAMBDA_PARSIMONIA_MODERADA,
        "cv_5fold_cierre_pct": {k: v for k, v in cv_cierre.items() if not isinstance(v, np.ndarray)},
        "topologia_final_alpha": {"neuronas_ocultas": n_oc_a, "conexiones_activas": n_cx_a},
        "importancia_permutacion_alpha": imp_alpha,
        "puente_micro_macro_paita": pred_filas,
    }
    (RUTA_RES / "resumen_neat.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n[OK] Resultados y 2 figuras PNG guardados en:", RUTA_RES)


if __name__ == "__main__":
    main()
