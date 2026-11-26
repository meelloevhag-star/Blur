"""
E3 · NEAT cinético · E4 · conjunto e incertidumbre · E5 · calibración local.

NEAT cinético: la red recibe las 6 entradas SIN la edad y devuelve 2 salidas (sigmoide):
    cierre_max ∈ [0, 1]   y   k = exp(ln K_MIN + s · (ln K_MAX − ln K_MIN))   [1/día]
    cierre(t) = cierre_max · (1 − e^(−k·t))
Así la predicción es monótona en el tiempo y acotada. Como la red no ve la edad, se evalúa solo en
las combinaciones únicas de entradas (mucho más rápido).

E3  Mismas particiones que la auditoría de Blur (GroupKFold barajado, semillas 2026+r) y laboratorio
    por sentido. Se compara con NEAT directo (cifras del artículo 1 en articulos/1_auditoria/resultados/revision/).
E4  Conjunto de K redes cinéticas (semillas distintas): media, DE, cobertura de intervalos,
    correlación duda–error y error de las predicciones "confiables".
E5  Entre laboratorios: entrenar en A y añadir n grupos de B (arranque en caliente y desde cero);
    probar en los grupos restantes de B. Curva MAE vs. n.

Uso:
    python -m hefesto.motor.experimentos_neat [--rapido]
"""

import argparse
import json
import math
import pickle
import random
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import neat
import numpy as np
from scipy import stats
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupKFold

from hefesto.motor.datos import cargar_replicas7, normalizar7
from hefesto.motor.neat_base import RUTA_CFG

RAIZ = Path(__file__).resolve().parents[2]
RUTA_RES = RAIZ / "resultados"
SEMILLA = 2026
LAMBDA = 8e-4
K_MIN, K_MAX = 1e-3, 1.0
COLS_MEZCLA = [0, 2, 3, 4, 5, 6]  # todas menos la edad (columna 1)


# ---------------------------------------------------------------------------
# Modelo cinético
# ---------------------------------------------------------------------------

def ruta_config_cinetica() -> Path:
    destino = RUTA_CFG.parent / "config_neat_6x2.txt"
    texto = RUTA_CFG.read_text(encoding="utf-8")
    texto = re.sub(r"num_inputs\s*=\s*\d+", "num_inputs              = 6", texto)
    texto = re.sub(r"num_outputs\s*=\s*\d+", "num_outputs             = 2", texto)
    if not destino.exists() or destino.read_text(encoding="utf-8") != texto:
        destino.write_text(texto, encoding="utf-8")
    return destino


def preparar(Xn, X_raw):
    """Separa entradas de mezcla (sin edad) y edad en días; índices de combinaciones únicas."""
    M = Xn[:, COLS_MEZCLA]
    unicas, inv = np.unique(np.round(M, 6), axis=0, return_inverse=True)
    return unicas, inv.ravel(), X_raw[:, 1]


def k_desde(s):
    return np.exp(math.log(K_MIN) + np.asarray(s) * (math.log(K_MAX) - math.log(K_MIN)))


def predecir_cinetico(red, unicas, inv, t):
    salidas = np.array([red.activate(u) for u in unicas])
    cmax, k = salidas[:, 0][inv], k_desde(salidas[:, 1])[inv]
    return cmax * (1.0 - np.exp(-k * t))


def evolucionar_cinetico(unicas, inv, t, y, gens, semilla, estado=None, lam=LAMBDA):
    random.seed(semilla)
    np.random.seed(semilla)
    if estado is None:
        config = neat.Config(neat.DefaultGenome, neat.DefaultReproduction, neat.DefaultSpeciesSet,
                             neat.DefaultStagnation, str(ruta_config_cinetica()))
        pop = neat.Population(config, seed=semilla)
    else:
        config, poblacion, especies, generacion = pickle.loads(pickle.dumps(estado))
        rastreador = getattr(config.genome_config, "innovation_tracker", None)
        pop = neat.Population(config, initial_state=(poblacion, especies, generacion), seed=semilla)
        if rastreador is not None:
            pop.reproduction.innovation_tracker = rastreador
            config.genome_config.innovation_tracker = rastreador

    def evaluar(genomas, cfg):
        for _gid, g in genomas:
            red = neat.nn.FeedForwardNetwork.create(g, cfg)
            mse = float(np.mean((predecir_cinetico(red, unicas, inv, t) - y) ** 2))
            n_oc = len([n for n in g.nodes if n >= cfg.genome_config.num_outputs])
            n_cx = sum(1 for c in g.connections.values() if c.enabled)
            g.fitness = -mse - lam * (n_oc + 0.15 * n_cx)

    ganador = pop.run(evaluar, gens)
    red = neat.nn.FeedForwardNetwork.create(ganador, config)
    return red, (config, pop.population, pop.species, pop.generation), ganador


def _ajustar_y_predecir(args):
    """Proceso aparte: entrena en tr (opcionalmente desde estado) y predice te."""
    Xn, X_raw, y, tr, te, gens, semilla, estado = args
    u_tr, i_tr, t_tr = preparar(Xn[tr], X_raw[tr])
    red, est, gan = evolucionar_cinetico(u_tr, i_tr, t_tr, y[tr], gens, semilla, estado=estado)
    u_te, i_te, t_te = preparar(Xn[te], X_raw[te])
    n_oc = len([n for n in gan.nodes if n >= 2])
    return predecir_cinetico(red, u_te, i_te, t_te), est, n_oc


# ---------------------------------------------------------------------------
# E3 · comparación con las mismas particiones de Blur
# ---------------------------------------------------------------------------

def e3(Xn, X, y, g, f, gens, repeticiones, workers) -> dict:
    tareas, claves = [], []
    for r in range(repeticiones):
        for i, (tr, te) in enumerate(GroupKFold(n_splits=5, shuffle=True, random_state=SEMILLA + r).split(Xn, y, g)):
            tareas.append((Xn, X, y, tr, te, gens, SEMILLA + 7 * r + i, None))
            claves.append(("grupos", r, te))
    for fte in np.unique(f):
        tr, te = np.flatnonzero(f != fte), np.flatnonzero(f == fte)
        tareas.append((Xn, X, y, tr, te, gens, SEMILLA, None))
        claves.append(("laboratorio", str(fte), te))
    with ProcessPoolExecutor(max_workers=workers) as ex:
        res = list(ex.map(_ajustar_y_predecir, tareas))
    salida = {"grupos": {}, "laboratorio": {}}
    mae_rep, ocultas = {}, []
    for (prot, clave, te), (pred, _, n_oc) in zip(claves, res):
        ocultas.append(n_oc)
        if prot == "grupos":
            mae_rep.setdefault(clave, []).append((y[te], pred))
        else:
            salida["laboratorio"][f"→{clave}"] = round(float(mean_absolute_error(y[te], pred) * 100), 2)
    maes = [mean_absolute_error(np.concatenate([a for a, _ in v]), np.concatenate([b for _, b in v])) * 100
            for v in mae_rep.values()]
    salida["grupos"] = {"MAE_pp_medio": round(float(np.mean(maes)), 2),
                        "MAE_pp_de": round(float(np.std(maes, ddof=1)), 2) if len(maes) > 1 else 0.0}
    salida["neuronas_ocultas_prom"] = round(float(np.mean(ocultas)), 2)
    return salida


# ---------------------------------------------------------------------------
# E4 · conjunto e incertidumbre
# ---------------------------------------------------------------------------

def e4(Xn, X, y, g, f, gens, K, workers) -> dict:
    """Conjunto de K redes cinéticas, evaluado fuera de muestra: por grupo y por laboratorio."""
    escenarios = [("grupos", tr, te) for tr, te in
                  GroupKFold(n_splits=5, shuffle=True, random_state=SEMILLA).split(Xn, y, g)]
    escenarios += [(f"→{fte}", np.flatnonzero(f != fte), np.flatnonzero(f == fte)) for fte in np.unique(f)]
    tareas = [(Xn, X, y, tr, te, gens, SEMILLA + 100 * k + j, None)
              for j, (_, tr, te) in enumerate(escenarios) for k in range(K)]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        res = list(ex.map(_ajustar_y_predecir, tareas))
    salida = {}
    for j, (nombre, tr, te) in enumerate(escenarios):
        P = np.array([res[j * K + k][0] for k in range(K)])
        bloque = salida.setdefault(nombre if nombre != "grupos" else "grupos", {"y": [], "media": [], "de": []})
        bloque["y"].append(y[te])
        bloque["media"].append(P.mean(axis=0))
        bloque["de"].append(P.std(axis=0, ddof=1))
    resumen = {}
    for nombre, b in salida.items():
        yt, mu, sd = (np.concatenate(b[k]) for k in ("y", "media", "de"))
        err = np.abs(yt - mu)
        umbral = np.median(sd)
        confiable = sd <= umbral
        cobertura = {f"{int(p * 100)}%": round(float(np.mean(err <= stats.norm.ppf(0.5 + p / 2) * sd)), 3)
                     for p in (0.8, 0.9)}
        resumen[nombre] = {
            "MAE_pp": round(float(err.mean() * 100), 2),
            "DE_media_pp": round(float(sd.mean() * 100), 2),
            "spearman_duda_error": round(float(stats.spearmanr(sd, err).statistic), 3),
            "cobertura_intervalos": cobertura,
            "MAE_pp_mitad_confiable": round(float(err[confiable].mean() * 100), 2),
            "MAE_pp_mitad_dudosa": round(float(err[~confiable].mean() * 100), 2),
        }
    return {"K": K, "escenarios": resumen}


# ---------------------------------------------------------------------------
# E5 · calibración local
# ---------------------------------------------------------------------------

def e5(Xn, X, y, g, f, gens, ns, semillas, workers) -> dict:
    salida = {}
    for fte in np.unique(f):
        A, B = np.flatnonzero(f != fte), np.flatnonzero(f == fte)
        # Población global entrenada en A (punto de partida del arranque en caliente)
        _, estado_A, _ = _ajustar_y_predecir((Xn, X, y, A, B[:1], gens, SEMILLA, None))
        gB = np.unique(g[B])
        tareas, claves = [], []
        for s in range(semillas):
            rng = np.random.default_rng(SEMILLA + s)
            orden = rng.permutation(gB)
            prueba_g = orden[max(ns):]  # mismos grupos de prueba para todos los n
            te = B[np.isin(g[B], prueba_g)]
            for n in ns:
                cal = B[np.isin(g[B], orden[:n])]
                tr = np.r_[A, cal]
                for modo, est in (("caliente", estado_A), ("frio", None)):
                    if n == 0 and modo == "frio":
                        continue
                    tareas.append((Xn, X, y, tr, te, max(10, gens // 2) if modo == "caliente" else gens,
                                   SEMILLA + 31 * s + n, est))
                    claves.append((s, n, modo, te))
                # Referencia: Random Forest con los mismos datos
                rf = RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=SEMILLA, n_jobs=workers)
                rf.fit(X[tr] if False else Xn[tr], y[tr])
                claves_rf = (s, n, "RandomForest", te)
                salida.setdefault(str(fte), {}).setdefault("_rf", []).append(
                    (claves_rf, mean_absolute_error(y[te], np.clip(rf.predict(Xn[te]), 0, 1)) * 100))
        with ProcessPoolExecutor(max_workers=workers) as ex:
            res = list(ex.map(_ajustar_y_predecir, tareas))
        curva = {}
        for (s, n, modo, te), (pred, _, _) in zip(claves, res):
            curva.setdefault(modo, {}).setdefault(n, []).append(mean_absolute_error(y[te], pred) * 100)
        for (s, n, modo, te), mae in salida[str(fte)].pop("_rf"):
            curva.setdefault(modo, {}).setdefault(n, []).append(mae)
        if 0 in curva.get("caliente", {}):
            curva.setdefault("frio", {})[0] = curva["caliente"][0]
        bloque = {}
        for modo, por_n in curva.items():
            bloque[modo] = {str(n): {"MAE_pp_medio": round(float(np.mean(v)), 2),
                                     "MAE_pp_de": round(float(np.std(v, ddof=1)), 2) if len(v) > 1 else 0.0}
                            for n, v in sorted(por_n.items())}
            for meta in (20, 15):
                ok = [n for n, v in sorted(por_n.items()) if np.mean(v) < meta]
                bloque[modo][f"n_min_para_<{meta}pp"] = ok[0] if ok else None
        salida[str(fte)] = {"entrenado_en": str(np.unique(f[A])[0]), "n_grupos_B": int(len(gB)), "curvas": bloque}
    return salida


def _directo(args):
    """NEAT directo (7 entradas, con la edad), opcionalmente reanudado. Devuelve (pred, estado)."""
    from hefesto.motor.neat_base import evolucionar, ruta_config

    Xn, y, tr, te, gens, semilla, estado = args
    _, red, est, _ = evolucionar(Xn[tr], y[tr], gens, semilla, estado=estado, lam=LAMBDA, ruta_cfg=ruta_config(7))
    return np.array([red.activate(x)[0] for x in Xn[te]]), est


def e5_directo(Xn, y, g, f, gens, ns, semillas, workers) -> dict:
    """Misma curva de calibración local de E5, pero con NEAT directo (el que ya extrapola ~20 pp)."""
    salida = {}
    for fte in np.unique(f):
        A, B = np.flatnonzero(f != fte), np.flatnonzero(f == fte)
        _, estado_A = _directo((Xn, y, A, B[:1], gens, SEMILLA, None))
        gB = np.unique(g[B])
        tareas, claves = [], []
        for s in range(semillas):
            orden = np.random.default_rng(SEMILLA + s).permutation(gB)
            te = B[np.isin(g[B], orden[max(ns):])]
            for n in ns:
                tr = np.r_[A, B[np.isin(g[B], orden[:n])]]
                for modo, est in (("caliente", estado_A), ("frio", None)):
                    if n == 0 and modo == "frio":
                        continue
                    tareas.append((Xn, y, tr, te, max(10, gens // 2) if modo == "caliente" else gens,
                                   SEMILLA + 31 * s + n, est))
                    claves.append((n, modo, te))
        with ProcessPoolExecutor(max_workers=workers) as ex:
            res = list(ex.map(_directo, tareas))
        curva = {}
        for (n, modo, te), (pred, _) in zip(claves, res):
            curva.setdefault(modo, {}).setdefault(n, []).append(mean_absolute_error(y[te], pred) * 100)
        curva.setdefault("frio", {})[0] = curva["caliente"][0]
        bloque = {}
        for modo, por_n in curva.items():
            bloque[modo] = {str(n): {"MAE_pp_medio": round(float(np.mean(v)), 2),
                                     "MAE_pp_de": round(float(np.std(v, ddof=1)), 2) if len(v) > 1 else 0.0}
                            for n, v in sorted(por_n.items())}
            for meta in (20, 15):
                ok = [n for n, v in sorted(por_n.items()) if np.mean(v) < meta]
                bloque[modo][f"n_min_para_<{meta}pp"] = ok[0] if ok else None
        salida[str(fte)] = {"entrenado_en": str(np.unique(f[A])[0]), "curvas": bloque}
    return salida


def figura_e5(res, ruta):
    fig, axes = plt.subplots(1, len(res), figsize=(6 * len(res), 4.2))
    axes = np.atleast_1d(axes)
    estilos = {"caliente": ("#0f766e", "NEAT cinético (caliente)"), "frio": ("#d97706", "NEAT cinético (desde cero)"),
               "RandomForest": ("#64748b", "Random Forest")}
    for ax, (fte, b) in zip(axes, res.items()):
        for modo, (color, etiqueta) in estilos.items():
            puntos = {int(k): v for k, v in b["curvas"].get(modo, {}).items() if k.isdigit()}
            ns = sorted(puntos)
            ax.errorbar(ns, [puntos[n]["MAE_pp_medio"] for n in ns], yerr=[puntos[n]["MAE_pp_de"] for n in ns],
                        marker="o", color=color, label=etiqueta, capsize=3)
        ax.axhline(20, color="crimson", ls="--", lw=1, label="Meta 20 pp")
        ax.axhline(15, color="crimson", ls=":", lw=1, label="15 pp")
        ax.set_xlabel(f"Grupos locales añadidos de {fte}")
        ax.set_ylabel("MAE en grupos restantes (pp)")
        ax.set_title(f"{b['entrenado_en']} → {fte}", fontsize=10)
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(ruta, dpi=200)
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true")
    a = ap.parse_args(argv)
    gens, reps, K, ns, sem, w = (8, 1, 3, (0, 5), 1, 4) if a.rapido else (50, 3, 10, (0, 2, 5, 10, 20, 40), 5, 4)
    X, y, g, f = cargar_replicas7()
    Xn = normalizar7(X)
    res = {"generaciones": gens, "lambda": LAMBDA, "k_rango_1_dia": [K_MIN, K_MAX]}
    res["E3_neat_cinetico"] = e3(Xn, X, y, g, f, gens, reps, w)
    print("[E3]", res["E3_neat_cinetico"], flush=True)
    res["E4_conjunto"] = e4(Xn, X, y, g, f, gens, K, w)
    print("[E4]", json.dumps(res["E4_conjunto"], ensure_ascii=False), flush=True)
    res["E5_calibracion_local"] = e5(Xn, X, y, g, f, gens, ns, sem, w)
    print("[E5]", json.dumps(res["E5_calibracion_local"], ensure_ascii=False), flush=True)
    sufijo = "_rapido" if a.rapido else ""
    figura_e5(res["E5_calibracion_local"], RUTA_RES / f"fig_e5_calibracion_local{sufijo}.png")
    (RUTA_RES / f"meta20_neat{sufijo}.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[OK]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
