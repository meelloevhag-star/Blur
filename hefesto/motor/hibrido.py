"""
Híbrido NEAT → árboles con predicción conforme agrupada (siguiente paso del INFORME_META20).

Escenario (igual que E5): el modelo conoce un laboratorio A y llega a un laboratorio nuevo B del
que se miden n grupos (probetas o fisuras) locales; se evalúa en los grupos restantes de B.

Modelos comparados sobre los MISMOS grupos de prueba:
  NEAT           NEAT directo entrenado solo en A (sin datos locales).
  RF             Random Forest entrenado en A + n grupos locales.
  H1 residual    NEAT(A) + RF que aprende el residuo de NEAT solo con los n grupos locales.
  H2 apilado     RF entrenado en A + locales con la predicción de NEAT(A) como entrada extra.
  H3 contraído   Como H1, pero la corrección se pondera por n / (n + 10): con pocos datos manda NEAT.
Margen de error: predicción conforme sobre H1 dejando fuera un grupo local a la vez
(puntuaciones |y − ŷ| de grupos no vistos); cobertura y ancho medidos en los grupos de prueba.

Uso:
    python -m hefesto.motor.hibrido [--rapido]
"""

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

from hefesto.motor.datos import cargar_replicas7, normalizar7
from hefesto.motor.modelos import ConfigNEAT, EvolucionNEAT

RAIZ = Path(__file__).resolve().parents[2]
RUTA_RES = RAIZ / "resultados"
SEMILLA = 2026
LAMBDA = 8e-4
K_BASE = 5  # redes NEAT promediadas como predicción base
K_CONTRACCION = 10  # nº de grupos locales con el que la corrección pesa la mitad


def _rf(semilla=SEMILLA):
    return RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=semilla, n_jobs=1)


def _neat_en_A(args):
    """Entrena NEAT directo en A y devuelve sus predicciones para todas las filas."""
    Xn, y, A, gens, semilla = args
    red = EvolucionNEAT(ConfigNEAT(generaciones=gens, lam=LAMBDA), semilla).ejecutar(Xn[A], y[A])
    return red(Xn)


def conforme_residual(Xn, y, g, cal, base, alfas=(0.2, 0.1)) -> dict:
    """Cuantiles conformes de |y − ŷ_H1| dejando fuera un grupo local a la vez."""
    grupos = np.unique(g[cal])
    if len(grupos) < 3:
        return {}
    puntuaciones = []
    for gg in grupos:
        fuera = cal[g[cal] == gg]
        dentro = cal[g[cal] != gg]
        rf = _rf().fit(Xn[dentro], y[dentro] - base[dentro])
        puntuaciones += list(np.abs(y[fuera] - np.clip(base[fuera] + rf.predict(Xn[fuera]), 0, 1)))
    s = np.sort(np.array(puntuaciones))
    m = len(s)
    return {a: float(s[min(m - 1, int(np.ceil((1 - a) * (m + 1))) - 1)]) for a in alfas}


def evaluar_sentido(Xn, y, g, f, fte, base_por_semilla, ns) -> dict:
    A, B = np.flatnonzero(f != fte), np.flatnonzero(f == fte)
    gB = np.unique(g[B])
    filas = {}
    for s, base in enumerate(base_por_semilla):
        orden = np.random.default_rng(SEMILLA + s).permutation(gB)
        te = B[np.isin(g[B], orden[max(ns):])]
        for n in ns:
            cal = B[np.isin(g[B], orden[:n])]
            res = {"NEAT": np.clip(base[te], 0, 1)}
            tr = np.r_[A, cal]
            res["RF"] = np.clip(_rf(SEMILLA + s).fit(Xn[tr], y[tr]).predict(Xn[te]), 0, 1)
            if n > 0:
                rf_res = _rf(SEMILLA + s).fit(Xn[cal], y[cal] - base[cal])
                corr = rf_res.predict(Xn[te])
                res["H1 residual"] = np.clip(base[te] + corr, 0, 1)
                # H3: corrección contraída según cuántos grupos locales hay (peso n / (n + K_CONTRACCION))
                res["H3 contraído"] = np.clip(base[te] + n / (n + K_CONTRACCION) * corr, 0, 1)
            else:
                res["H1 residual"] = res["NEAT"]
                res["H3 contraído"] = res["NEAT"]
            Xs = np.c_[Xn, base]
            res["H2 apilado"] = np.clip(_rf(SEMILLA + s).fit(Xs[tr], y[tr]).predict(Xs[te]), 0, 1)
            for nombre, pred in res.items():
                filas.setdefault(nombre, {}).setdefault(n, []).append(mean_absolute_error(y[te], pred) * 100)
            q = conforme_residual(Xn, y, g, cal, base) if n >= 5 else {}
            for a, qa in q.items():
                err = np.abs(y[te] - res["H1 residual"])
                filas.setdefault("conforme", {}).setdefault(n, []).append((a, float(np.mean(err <= qa)), qa * 100))
    salida = {"entrenado_en": str(np.unique(f[A])[0]), "n_grupos_B": int(len(gB)), "modelos": {}}
    for nombre, por_n in filas.items():
        if nombre == "conforme":
            continue
        salida["modelos"][nombre] = {str(n): {"MAE_pp_medio": round(float(np.mean(v)), 2),
                                              "MAE_pp_de": round(float(np.std(v, ddof=1)), 2) if len(v) > 1 else 0.0}
                                     for n, v in sorted(por_n.items())}
        for meta in (20, 15):
            ok = [n for n, v in sorted(por_n.items()) if np.mean(v) < meta]
            salida["modelos"][nombre][f"n_min_para_<{meta}pp"] = ok[0] if ok else None
    conf = {}
    for n, lista in filas.get("conforme", {}).items():
        for a in sorted({x[0] for x in lista}):
            sel = [x for x in lista if x[0] == a]
            conf.setdefault(str(n), {})[f"{int(round((1 - a) * 100))}%"] = {
                "cobertura_real": round(float(np.mean([x[1] for x in sel])), 3),
                "semiancho_pp": round(float(np.mean([x[2] for x in sel])), 1)}
    salida["conforme_H1"] = conf
    return salida


def figura(res, ruta):
    fig, axes = plt.subplots(1, len(res), figsize=(6 * len(res), 4.4))
    estilos = {"NEAT": ("#0f766e", "o", "NEAT (solo otro laboratorio)"), "RF": ("#64748b", "s", "Random Forest"),
               "H1 residual": ("#7c3aed", "D", "Híbrido H1: NEAT + corrección local"),
               "H2 apilado": ("#d97706", "^", "Híbrido H2: apilado"),
               "H3 contraído": ("#db2777", "v", "Híbrido H3: corrección gradual")}
    for ax, (fte, b) in zip(np.atleast_1d(axes), res.items()):
        for nombre, (color, mk, et) in estilos.items():
            c = {int(k): v for k, v in b["modelos"][nombre].items() if k.isdigit()}
            ns = sorted(c)
            ax.errorbar(ns, [c[n]["MAE_pp_medio"] for n in ns], yerr=[c[n]["MAE_pp_de"] for n in ns], marker=mk,
                        color=color, label=et, capsize=3)
        ax.axhline(20, color="crimson", ls="--", lw=1, label="Meta 20 pp")
        ax.axhline(15, color="crimson", ls=":", lw=1)
        ax.set_title(f"{b['entrenado_en']} → {fte}", fontsize=11)
        ax.set_xlabel("Probetas/fisuras locales medidas")
        ax.set_ylabel("Error medio (puntos de cierre)")
        ax.set_ylim(0, 42)
        ax.grid(alpha=0.3)
    np.atleast_1d(axes)[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(ruta, dpi=200)
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true")
    a = ap.parse_args(argv)
    gens, sem, ns = (8, 1, (0, 5, 10)) if a.rapido else (50, 5, (0, 2, 5, 10, 20, 40))
    X, y, g, f = cargar_replicas7()
    Xn = normalizar7(X)
    res = {}
    for fte in np.unique(f):
        A = np.flatnonzero(f != fte)
        # Base estable: promedio de K_BASE redes NEAT (semillas distintas) por cada repetición
        with ProcessPoolExecutor(max_workers=4) as ex:
            individuales = list(ex.map(_neat_en_A, [(Xn, y, A, gens, SEMILLA + 100 * s + k)
                                                    for s in range(sem) for k in range(K_BASE)]))
        bases = [np.mean(individuales[s * K_BASE:(s + 1) * K_BASE], axis=0) for s in range(sem)]
        B = np.flatnonzero(f == fte)
        var_individual = [mean_absolute_error(y[B], np.clip(p_[B], 0, 1)) * 100 for p_ in individuales]
        var_promedio = [mean_absolute_error(y[B], np.clip(p_[B], 0, 1)) * 100 for p_ in bases]
        res[str(fte)] = evaluar_sentido(Xn, y, g, f, fte, bases, ns)
        res[str(fte)]["estabilidad_base"] = {
            "K_redes": K_BASE,
            "MAE_pp_una_red": [round(float(np.mean(var_individual)), 2), round(float(np.std(var_individual, ddof=1)), 2)],
            "MAE_pp_promedio_K": [round(float(np.mean(var_promedio)), 2), round(float(np.std(var_promedio, ddof=1)), 2)
                                  if len(var_promedio) > 1 else 0.0]}
        print(f"[{fte}]", json.dumps(res[str(fte)], ensure_ascii=False)[:1500], flush=True)
    sufijo = "_rapido" if a.rapido else ""
    (RUTA_RES / f"hibrido{sufijo}.json").write_text(json.dumps({"generaciones": gens, "semillas": sem, **res},
                                                               ensure_ascii=False, indent=2), encoding="utf-8")
    figura(res, RUTA_RES / f"fig_hibrido{sufijo}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
