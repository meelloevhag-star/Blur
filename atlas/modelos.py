"""Conjunto de modelos de cierre de fisuras entrenado con todos los datos de Blur.

  - XGBoost con bootstrap por grupos (B modelos) → media e IC 95 %; restricciones monótonas físicas
    (más ancho inicial → menos cierre; más edad → más cierre).
  - NEAT (red mínima explicable, reutiliza biocrete_neat.aprendizaje_continuo.evolucionar) con ciclo
    campeón/candidato: la nueva red solo reemplaza a la vigente si iguala o mejora su R² con
    validación cruzada agrupada.
  - Validación: GroupKFold por probeta/fisura (ninguna fisura en entrenamiento y prueba a la vez).

Todo se exporta a JSON (atlas/modelos/) para que la API en Go evalúe sin Python.
"""
from __future__ import annotations

import datetime as dt
import json
import random

import numpy as np
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold
from xgboost import XGBRegressor

from atlas.ingesta import NOMBRES_CIERRE, MAX_CIERRE, dataset_cierre, normalizar_cierre, detectar_cambios
from atlas.rutas import ATLAS, MODELOS

SEMILLA = 2026
B_BOOT = 20
CFG_NEAT = ATLAS / "config_neat_atlas.txt"
MONOTONO = "(" + ",".join(["-1", "1"] + ["0"] * (len(NOMBRES_CIERRE) - 2)) + ")"


def _xgb(semilla=SEMILLA):
    return XGBRegressor(n_estimators=250, max_depth=4, learning_rate=0.06, subsample=0.8, colsample_bytree=0.9,
                        min_child_weight=3, reg_lambda=1.0, random_state=semilla, n_jobs=4, verbosity=0,
                        monotone_constraints=MONOTONO, base_score=0.5)


def _neat(X, y, gens, semilla, estado=None):
    from biocrete_neat.aprendizaje_continuo import evolucionar
    return evolucionar(X, y, gens, semilla, estado=estado, ruta_cfg=CFG_NEAT)


def _pred_red(red, X):
    return np.array([red.activate(list(x))[0] for x in X])


def cv_agrupada(Xn, y, g, gens_neat=30, k=5, estado_neat=None):
    pred = {"xgb": np.zeros(len(y)), "neat": np.zeros(len(y))}
    for i, (tr, te) in enumerate(GroupKFold(n_splits=k).split(Xn, y, g)):
        pred["xgb"][te] = np.clip(_xgb().fit(Xn[tr], y[tr]).predict(Xn[te]), 0, 1)
        _, red, _, _ = _neat(Xn[tr], y[tr], gens_neat, SEMILLA + i, estado=estado_neat)
        pred["neat"][te] = _pred_red(red, Xn[te])
    r2 = {m: max(float(r2_score(y, p)), 0.0) for m, p in pred.items()}
    tot = sum(r2.values()) or 1.0
    pesos = {m: r2[m] / tot for m in pred}           # peso ∝ R² agrupado (un modelo con R² ≤ 0 no vota)
    pred["conjunto"] = pesos["xgb"] * pred["xgb"] + pesos["neat"] * pred["neat"]
    out = {m: {"R2": round(float(r2_score(y, p)), 3), "MAE_pct": round(float(mean_absolute_error(y, p)) * 100, 2)}
           for m, p in pred.items()}
    out["pesos"] = {m: round(w, 3) for m, w in pesos.items()}
    return out


# --------------------------------------------------------------------------- exportación

def exportar_xgb(modelo) -> list:
    """Árboles en formato compacto: cada nodo [feature, umbral, si, no, hoja] (feature = -1 en hojas)."""
    arboles = []
    for t in modelo.get_booster().get_dump(dump_format="json"):
        raiz = json.loads(t)
        nodos = {}

        def visitar(n):
            nodos[n["nodeid"]] = n
            for c in n.get("children", []):
                visitar(c)
        visitar(raiz)
        tam = max(nodos) + 1
        plano = [None] * tam
        for i, n in nodos.items():
            if "leaf" in n:
                plano[i] = [-1, 0.0, 0, 0, n["leaf"]]
            else:
                plano[i] = [int(n["split"][1:]), n["split_condition"], n["yes"], n["no"], 0.0]
        arboles.append(plano)
    return arboles


def evaluar_xgb_json(arboles, base, x) -> float:
    s = base
    for t in arboles:
        i = 0
        while t[i][0] >= 0:
            f, u, si, no, _ = t[i]
            i = si if x[f] < u else no
        s += t[i][4]
    return s


def exportar_neat(red) -> dict:
    """Red feed-forward de neat-python → JSON (activación sigmoide de neat: 1/(1+e^(−5z)))."""
    return {"entradas": list(red.input_nodes), "salidas": list(red.output_nodes),
            "nodos": [{"id": n, "sesgo": b, "respuesta": r, "enlaces": [[i, w] for i, w in links]}
                      for n, _act, _agg, b, r, links in red.node_evals],
            "activacion": "sigmoid_neat (z = clamp(5·x, −60, 60); 1/(1+e^−z))", "agregacion": "suma"}


def evaluar_neat_json(red, x) -> float:
    import math
    v = {k: x[j] for j, k in enumerate(red["entradas"])}
    for n in red["nodos"]:
        s = n["sesgo"] + n["respuesta"] * sum(v[i] * w for i, w in n["enlaces"])
        z = max(-60.0, min(60.0, 5.0 * s))
        v[n["id"]] = 1.0 / (1.0 + math.exp(-z))
    return v[red["salidas"][0]]


# --------------------------------------------------------------------------- entrenamiento

def entrenar(gens_neat=40, rapido=False) -> dict:
    random.seed(SEMILLA)
    np.random.seed(SEMILLA)
    X, y, g, fuentes = dataset_cierre()
    Xn = normalizar_cierre(X)
    MODELOS.mkdir(parents=True, exist_ok=True)
    reg_path = MODELOS / "registro.json"
    registro = json.loads(reg_path.read_text(encoding="utf-8")) if reg_path.exists() else []
    vigente = next((r for r in reversed(registro) if r["aceptado"]), None)

    gcv = 10 if rapido else max(15, gens_neat // 2)
    cv = cv_agrupada(Xn, y, g, gens_neat=gcv)
    aceptado = vigente is None or cv["conjunto"]["R2"] >= vigente["cv"]["conjunto"]["R2"] - 1e-9

    entrada = {"version": len(registro) + 1, "fecha": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               "n_registros": int(len(y)), "n_grupos": int(len(np.unique(g))),
               "fuentes": {str(f): int((fuentes == f).sum()) for f in np.unique(fuentes)},
               "huellas_datos": detectar_cambios(guardar=False)["huellas"], "cv": cv, "aceptado": bool(aceptado)}
    if aceptado:
        rng = np.random.default_rng(SEMILLA)
        grupos_u = np.unique(g)
        idx_por_g = {k: np.flatnonzero(g == k) for k in grupos_u}
        boot = []
        for b in range(4 if rapido else B_BOOT):
            gs = rng.choice(grupos_u, len(grupos_u), replace=True)
            idx = np.concatenate([idx_por_g[k] for k in gs])
            boot.append(exportar_xgb(_xgb(SEMILLA + b).fit(Xn[idx], y[idx])))
        _, red, _, _ = _neat(Xn, y, gens_neat if not rapido else 10, SEMILLA)
        # soporte del dominio: combinaciones observadas (portador, bacterias, marino, curado)
        soporte = {}
        for x in X:
            clave = "|".join(str(int(v)) for v in x[2:])
            soporte[clave] = soporte.get(clave, 0) + 1
        paquete = {"version": entrada["version"], "variables": NOMBRES_CIERRE, "max_normalizacion": MAX_CIERRE.tolist(),
                   "xgb": {"base": 0.5, "bootstrap": boot}, "neat": exportar_neat(red),
                   "rango_w0_mm": [float(X[:, 0].min()), float(X[:, 0].max())],
                   "rango_edad_dias": [float(X[:, 1].min()), float(X[:, 1].max())],
                   "soporte_combinaciones": soporte, "cv": cv}
        (MODELOS / "modelo_cierre.json").write_text(json.dumps(paquete), encoding="utf-8")
        entrada["archivo"] = "modelo_cierre.json"
    registro.append(entrada)
    reg_path.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
    return entrada


class ModeloCierre:
    """Evalúa el paquete exportado (misma lógica que la API en Go)."""

    def __init__(self, ruta=None):
        self.p = json.loads((ruta or MODELOS / "modelo_cierre.json").read_text(encoding="utf-8"))
        self.max = np.array(self.p["max_normalizacion"])
        self.w = self.p["cv"]["pesos"]
        self._cache = {}

    def predecir(self, x_crudo) -> dict:
        clave = tuple(float(v) for v in x_crudo)
        if clave not in self._cache:
            self._cache[clave] = self._predecir(x_crudo)
        return dict(self._cache[clave])

    def _predecir(self, x_crudo) -> dict:
        xn = np.clip(np.asarray(x_crudo, float) / self.max, 0, 1)
        bs = np.clip([evaluar_xgb_json(t, self.p["xgb"]["base"], xn) for t in self.p["xgb"]["bootstrap"]], 0, 1)
        neat = float(evaluar_neat_json(self.p["neat"], xn))
        clave = "|".join(str(int(v)) for v in x_crudo[2:])
        return {"cierre_xgb_pct": round(float(bs.mean()) * 100, 1),
                "cierre_ic95_pct": [round(float(np.percentile(bs, 2.5)) * 100, 1),
                                    round(float(np.percentile(bs, 97.5)) * 100, 1)],
                "cierre_neat_pct": round(neat * 100, 1),
                "cierre_pct": round(float(self.w["xgb"] * bs.mean() + self.w["neat"] * neat) * 100, 1),
                "n_datos_combinacion": int(self.p["soporte_combinaciones"].get(clave, 0))}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true")
    ap.add_argument("--gens", type=int, default=40)
    a = ap.parse_args()
    print(json.dumps(entrenar(a.gens, a.rapido), ensure_ascii=False, indent=2))
