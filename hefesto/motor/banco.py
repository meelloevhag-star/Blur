"""
Banco de comparación: elige UN solo motor para Hefesto.

Cada candidato de hefesto.motor.modelos se mide con los mismos datos (2 166 réplicas de cierre de
fisura de dos laboratorios) y las mismas particiones, en cinco criterios:

  precisión         MAE (puntos de cierre) y R² con tres protocolos:
                      filas (con fuga: réplicas de una probeta a ambos lados; solo referencia),
                      grupos (GroupKFold por probeta o fisura),
                      laboratorio (entrena en uno y predice el otro, en ambos sentidos).
  efectividad       ¿baja de 20 puntos entre laboratorios? Distancia al piso de ruido de los datos.
  capacidad de      MAE al predecir el laboratorio nuevo cuando se suman 0, 5, 10, 20 y 40 probetas
  mejora            locales al entrenamiento (3 sorteos).
  velocidad         segundos para entrenar con todo y para predecir 1 000 filas.
  simplicidad       nodos, conexiones o parámetros, y qué variables usa.

Regla de elección (en orden):
  1. menor MAE entre laboratorios. Se consideran empatados los modelos cuya diferencia con el
     mejor no es distinta de cero (intervalo bootstrap 95 % por probetas, pareado);
  2. entre empatados, menor MAE con 10 probetas locales (aprende mejor con datos nuevos);
  3. luego, menor complejidad;
  4. luego, más rápido.

Uso:
    python -m hefesto.motor.banco [--rapido] [--workers 4]
Salida:
    resultados/banco_motores.json, resultados/fig_banco_motores.png
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold, KFold

from hefesto.motor.datos import VARS_R, cargar_replicas7
from hefesto.motor.modelos import HibridoH3, candidatos, cronometrar

RAIZ = Path(__file__).resolve().parents[2]
SEMILLA = 2026
N_LOCALES = (0, 5, 10, 20, 40)
SORTEOS = 3


def _mae(y, p):
    return float(mean_absolute_error(y, p) * 100)


class Banco:
    def __init__(self, rapido: bool = False):
        self.rapido = rapido
        self.X, self.y, self.g, self.f = cargar_replicas7()
        self.labs = sorted(np.unique(self.f))

    # ------------------------------------------------------------------ protocolos
    def protocolo_filas(self, idx):
        p = np.zeros(len(self.y))
        for tr, te in KFold(5, shuffle=True, random_state=SEMILLA).split(self.X):
            p[te] = candidatos(self.rapido)[idx].ajustar(self.X[tr], self.y[tr]).predecir(self.X[te])
        return p

    def protocolo_grupos(self, idx):
        p = np.zeros(len(self.y))
        for tr, te in GroupKFold(5).split(self.X, groups=self.g):
            p[te] = candidatos(self.rapido)[idx].ajustar(self.X[tr], self.y[tr], self.g[tr]).predecir(self.X[te])
        return p

    def protocolo_laboratorio(self, idx):
        p = np.zeros(len(self.y))
        for lab in self.labs:
            A, B = self.f != lab, self.f == lab
            p[B] = candidatos(self.rapido)[idx].ajustar(self.X[A], self.y[A], self.g[A]).predecir(self.X[B])
        return p

    def curva_mejora(self, idx):
        """MAE en el laboratorio nuevo con n probetas locales sumadas (o calibradas, en H3)."""
        res = {}
        for lab in self.labs:
            A, B = np.flatnonzero(self.f != lab), np.flatnonzero(self.f == lab)
            gB = np.unique(self.g[B])
            base_h3 = None
            for s in range(SORTEOS):
                orden = np.random.default_rng(SEMILLA + s).permutation(gB)
                te = B[np.isin(self.g[B], orden[max(N_LOCALES):])]
                for n in N_LOCALES:
                    loc = B[np.isin(self.g[B], orden[:n])]
                    m = candidatos(self.rapido)[idx]
                    if isinstance(m, HibridoH3):          # el híbrido no se reentrena: se calibra
                        if base_h3 is None:
                            base_h3 = m.ajustar(self.X[A], self.y[A])
                        m = base_h3
                        m.rf, m.n_local = None, 0
                        if n:
                            m.calibrar(self.X[loc], self.y[loc], self.g[loc])
                    else:
                        tr = np.r_[A, loc]
                        m.ajustar(self.X[tr], self.y[tr], self.g[tr])
                    res.setdefault(n, []).append(_mae(self.y[te], m.predecir(self.X[te])))
        return {str(n): round(float(np.mean(v)), 2) for n, v in sorted(res.items())}

    # ------------------------------------------------------------------ un candidato completo
    def evaluar(self, idx) -> dict:
        m = candidatos(self.rapido)[idx]
        out = {"nombre": m.nombre, "familia": m.familia}
        t0 = time.perf_counter()
        pf, pg, pl = self.protocolo_filas(idx), self.protocolo_grupos(idx), self.protocolo_laboratorio(idx)
        out["precision"] = {
            "filas": {"MAE_pp": round(_mae(self.y, pf), 2), "R2": round(float(r2_score(self.y, pf)), 3)},
            "grupos": {"MAE_pp": round(_mae(self.y, pg), 2), "R2": round(float(r2_score(self.y, pg)), 3)},
            "laboratorio": {lab: {"MAE_pp": round(_mae(self.y[self.f == lab], pl[self.f == lab]), 2),
                                  "R2": round(float(r2_score(self.y[self.f == lab], pl[self.f == lab])), 3)}
                            for lab in self.labs}}
        out["precision"]["laboratorio"]["media_MAE_pp"] = round(float(np.mean(
            [out["precision"]["laboratorio"][l]["MAE_pp"] for l in self.labs])), 2)
        out["mejora"] = self.curva_mejora(idx)
        mt, t_fit = cronometrar(candidatos(self.rapido)[idx].ajustar, self.X, self.y, self.g)
        _, t_pred = cronometrar(mt.predecir, np.repeat(self.X[:100], 10, axis=0))
        out["velocidad"] = {"entrenar_s": round(t_fit, 2), "predecir_1000_ms": round(1000 * t_pred, 2),
                            "banco_total_s": round(time.perf_counter() - t0, 1)}
        out["simplicidad"] = {**mt.complejidad(), "variables_usadas": mt.variables_usadas()}
        out["importancia_pp"] = self.importancia(mt)
        out["_pred_lab"] = pl.tolist()
        out["_pred_grupos"] = pg.tolist()
        return out

    def importancia(self, m) -> dict:
        """Aumento del MAE (pp) al barajar cada variable: qué usa realmente el modelo."""
        rng = np.random.default_rng(SEMILLA)
        base = _mae(self.y, m.predecir(self.X))
        imp = {}
        for j, v in enumerate(VARS_R):
            Xp = self.X.copy()
            Xp[:, j] = rng.permutation(Xp[:, j])
            imp[v] = round(_mae(self.y, m.predecir(Xp)) - base, 2)
        return imp

    # ------------------------------------------------------------------ elección
    def bootstrap_diferencia(self, pa, pb, mascara_lab=None, B=2000) -> tuple[float, float]:
        """IC 95 % de MAE(a) − MAE(b) entre laboratorios, remuestreando probetas (pareado)."""
        rng = np.random.default_rng(SEMILLA)
        grupos = np.unique(self.g)
        ea, eb = np.abs(self.y - pa), np.abs(self.y - pb)
        por_g = {gg: np.flatnonzero(self.g == gg) for gg in grupos}
        da = np.array([ea[por_g[gg]].sum() for gg in grupos])
        db = np.array([eb[por_g[gg]].sum() for gg in grupos])
        nn = np.array([len(por_g[gg]) for gg in grupos])
        dif = []
        for _ in range(B):
            k = rng.integers(0, len(grupos), len(grupos))
            dif.append(100 * (da[k].sum() - db[k].sum()) / nn[k].sum())
        return float(np.percentile(dif, 2.5)), float(np.percentile(dif, 97.5))

    def elegir(self, res: list[dict]) -> dict:
        lab = lambda r: r["precision"]["laboratorio"]["media_MAE_pp"]
        mejor = min(res, key=lab)
        empatados = []
        for r in res:
            lo, hi = self.bootstrap_diferencia(np.array(r["_pred_lab"]), np.array(mejor["_pred_lab"]))
            r["dif_vs_mejor_IC95_pp"] = [round(lo, 2), round(hi, 2)]
            if lo <= 0 <= hi or r is mejor:
                empatados.append(r)

        def tamano(r):
            s = r["simplicidad"]
            return s.get("conexiones", 0) + s.get("parametros", 0) + s.get("hojas", 0) + 10 * s.get("arboles", 0)

        ganador = min(empatados, key=lambda r: (r["mejora"]["10"], tamano(r), r["velocidad"]["entrenar_s"]))
        return {"ganador": ganador["nombre"], "mejor_precision": mejor["nombre"],
                "empatados_en_precision": [r["nombre"] for r in empatados],
                "regla": "1) MAE entre laboratorios (empate si el IC 95 % bootstrap de la diferencia incluye 0); "
                         "2) MAE con 10 probetas locales; 3) complejidad; 4) tiempo de entrenamiento"}

    # ------------------------------------------------------------------ ejecutar
    def correr(self, workers=4) -> dict:
        n = len(candidatos(self.rapido))
        with ProcessPoolExecutor(max_workers=workers) as pool:
            res = list(pool.map(self.evaluar, range(n)))
        eleccion = self.elegir(res)
        diag = RAIZ / "resultados" / "meta20_diagnostico.json"
        piso = json.loads(diag.read_text(encoding="utf-8"))["E1_piso_ruido"]["global"] if diag.exists() else None
        # matriz de predicción del ganador: real vs predicho medio por laboratorio y condición
        gan = next(r for r in res if r["nombre"] == eleccion["ganador"])
        matriz = self.matriz_prediccion(np.array(gan["_pred_lab"]))
        for r in res:
            r.pop("_pred_lab"), r.pop("_pred_grupos")
        return {"n_filas": int(len(self.y)), "n_probetas": int(len(np.unique(self.g))), "laboratorios": self.labs,
                "rapido": self.rapido, "piso_ruido_pp": piso, "eleccion": eleccion,
                "matriz_prediccion_ganador": matriz, "candidatos": res}

    def matriz_prediccion(self, p) -> list[dict]:
        claves = np.array([f"{f}|w0={x[0]:.2f}|prot={int(x[2])}|marino={int(x[3])}|lact={int(x[4])}|curado={int(x[5])}"
                           f"|crist={int(x[6])}" for f, x in zip(self.f, self.X)])
        out = []
        for k in np.unique(claves):
            m = claves == k
            out.append({"condicion": k, "n": int(m.sum()), "real_pct": round(100 * float(self.y[m].mean()), 1),
                        "predicho_pct": round(100 * float(p[m].mean()), 1)})
        return sorted(out, key=lambda d: -abs(d["real_pct"] - d["predicho_pct"]))


def figura(res: dict, ruta: Path):
    c = res["candidatos"]
    nombres = [r["nombre"] for r in c]
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.8))
    y = np.arange(len(c))
    for k, (prot, col) in enumerate((("grupos", "#64748b"), ("laboratorio", "#0f766e"))):
        vals = [r["precision"][prot]["MAE_pp"] if prot == "grupos" else r["precision"][prot]["media_MAE_pp"] for r in c]
        axs[0].barh(y + 0.2 * (1 - 2 * k), vals, 0.4, color=col, label=f"por {prot}")
    if res.get("piso_ruido_pp"):
        axs[0].axvline(res["piso_ruido_pp"]["piso_superior_pp"], color="k", ls=":", label="piso de ruido")
    axs[0].axvline(20, color="crimson", ls="--", label="meta 20 pp")
    axs[0].set_yticks(y, nombres, fontsize=8)
    axs[0].invert_yaxis()
    axs[0].set_xlabel("MAE (puntos de cierre)")
    axs[0].legend(fontsize=7)
    axs[0].set_title("Precisión")
    for r in c:
        ns = sorted(int(n) for n in r["mejora"])
        axs[1].plot(ns, [r["mejora"][str(n)] for n in ns], marker="o", lw=2.5 if r["nombre"] == res["eleccion"]["ganador"] else 1,
                    label=r["nombre"])
    axs[1].axhline(20, color="crimson", ls="--")
    axs[1].set_xlabel("Probetas locales sumadas")
    axs[1].set_ylabel("MAE en el laboratorio nuevo (pp)")
    axs[1].set_title("Capacidad de mejora")
    axs[1].legend(fontsize=6)
    tam = [max(1, sum(v for k, v in r["simplicidad"].items() if isinstance(v, int))) for r in c]
    axs[2].scatter(tam, [r["precision"]["laboratorio"]["media_MAE_pp"] for r in c],
                   s=[20 + 30 * r["velocidad"]["entrenar_s"] ** 0.5 for r in c], color="#0f766e")
    for t, r in zip(tam, c):
        axs[2].annotate(r["nombre"], (t, r["precision"]["laboratorio"]["media_MAE_pp"]), fontsize=6)
    axs[2].set_xscale("log")
    axs[2].set_xlabel("Tamaño (conexiones, parámetros u hojas; log)")
    axs[2].set_ylabel("MAE entre laboratorios (pp)")
    axs[2].set_title("Simplicidad vs precisión (área = tiempo)")
    fig.tight_layout()
    fig.savefig(ruta, dpi=170)
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    res = Banco(a.rapido).correr(a.workers)
    sal = RAIZ / "resultados"
    nombre = "banco_motores_rapido" if a.rapido else "banco_motores"
    (sal / f"{nombre}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    figura(res, sal / f"fig_{nombre}.png")
    for r in res["candidatos"]:
        print(f"{r['nombre']:28s} grupos {r['precision']['grupos']['MAE_pp']:6.2f}  lab {r['precision']['laboratorio']['media_MAE_pp']:6.2f}"
              f"  mejora10 {r['mejora']['10']:6.2f}  fit {r['velocidad']['entrenar_s']:7.2f}s  {r['simplicidad']}", flush=True)
    print(json.dumps(res["eleccion"], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
