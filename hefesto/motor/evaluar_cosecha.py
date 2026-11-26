"""
¿Mejora el motor al entrenarlo con la cosecha? Prueba honesta "fuente nueva" (leave-one-source-out).

Para cada fuente S de datos/aceptados (cada estudio o dataset):
  actual   motor entrenado solo con las réplicas de laboratorio (Mousa + Cappellesso), como v003;
           si S es una de ellas, se entrena con la otra.
  cosecha  motor entrenado con TODO lo aceptado salvo S.
Ambos predicen S sin haberla visto. Se reporta el MAE (puntos de % de cierre) por fuente, ponderado
por filas, y aparte para Perú (procedencia_ambito = peru), que es lo que manda.

Salida: resultados/evaluacion_cosecha.json

Uso:
    python -m hefesto.motor.evaluar_cosecha [--workers 4] [--semillas 1]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from hefesto.agentes.orquestador import ACEPTADOS, CAMPOS_MOTOR
from hefesto.motor.modelos import HibridoH3

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "resultados" / "evaluacion_cosecha.json"
REPLICAS = {"Mousa2022", "Cappellesso2024"}


class DatosCosecha:
    """Filas aceptadas con las 7 entradas y cierre medido, con su fuente y ámbito."""

    def __init__(self):
        X, y, fuente, ambito = [], [], [], []
        for ruta in sorted(ACEPTADOS.glob("*.csv")):
            with open(ruta, encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    if any(not (r.get(c) or "").strip() for c in CAMPOS_MOTOR + ["resultado_cierre_pct"]):
                        continue
                    X.append([float(r[c]) for c in CAMPOS_MOTOR])
                    y.append(float(r["resultado_cierre_pct"]) / 100.0)
                    fuente.append(r["fuente"])
                    ambito.append((r.get("procedencia_ambito") or "").strip() or "global")
        self.X, self.y = np.array(X), np.array(y)
        self.fuente, self.ambito = np.array(fuente), np.array(ambito)
        self.fuentes = sorted(set(fuente))


def _ajustar_predecir(args):
    X_tr, y_tr, X_te, semilla = args
    np.random.seed(semilla)
    return HibridoH3().ajustar(X_tr, y_tr).predecir(X_te)


class EvaluacionCosecha:
    def __init__(self, workers: int = 4, semillas: int = 1):
        self.d, self.workers, self.semillas = DatosCosecha(), workers, semillas

    def tareas(self):
        d = self.d
        rep = np.isin(d.fuente, list(REPLICAS))
        for s in d.fuentes:
            te = d.fuente == s
            base = rep & ~te                       # "actual": solo réplicas (sin la fuente evaluada)
            for k in range(self.semillas):
                yield (s, "actual", k), (d.X[base], d.y[base], d.X[te], 1000 + k)
                yield (s, "cosecha", k), (d.X[~te], d.y[~te], d.X[te], 1000 + k)

    def correr(self) -> dict:
        claves, args = zip(*self.tareas())
        with ProcessPoolExecutor(self.workers) as pool:
            preds = list(pool.map(_ajustar_predecir, args))
        d, por = self.d, {}
        for (s, modo, _k), p in zip(claves, preds):
            te = d.fuente == s
            por.setdefault(s, {}).setdefault(modo, []).append(float(np.mean(np.abs(p - d.y[te])) * 100))
        filas = []
        for s in d.fuentes:
            te = d.fuente == s
            filas.append({"fuente": s, "n": int(te.sum()), "ambito": str(d.ambito[te][0]),
                          "MAE_actual": round(float(np.mean(por[s]["actual"])), 2),
                          "MAE_cosecha": round(float(np.mean(por[s]["cosecha"])), 2)})

        def ponderado(sel):
            n = sum(f["n"] for f in sel)
            if not n:
                return None
            return {"n_filas": n, "n_fuentes": len(sel),
                    "MAE_actual": round(sum(f["n"] * f["MAE_actual"] for f in sel) / n, 2),
                    "MAE_cosecha": round(sum(f["n"] * f["MAE_cosecha"] for f in sel) / n, 2),
                    "fuentes_que_mejoran": sum(f["MAE_cosecha"] < f["MAE_actual"] for f in sel)}

        resumen = {
            "protocolo": "fuente nueva (leave-one-source-out); MAE en puntos de % de cierre",
            "filas_totales": int(len(d.y)), "fuentes": len(d.fuentes), "semillas": self.semillas,
            "fuentes_nuevas": ponderado([f for f in filas if f["fuente"] not in REPLICAS]),
            "peru": ponderado([f for f in filas if f["ambito"] == "peru"]),
            "replicas_entre_laboratorios": ponderado([f for f in filas if f["fuente"] in REPLICAS]),
            "todas": ponderado(filas),
            "por_fuente": sorted(filas, key=lambda f: -f["n"]),
        }
        SALIDA.parent.mkdir(parents=True, exist_ok=True)
        SALIDA.write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
        return resumen


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--semillas", type=int, default=1)
    a = ap.parse_args(argv)
    r = EvaluacionCosecha(a.workers, a.semillas).correr()
    print(json.dumps({k: v for k, v in r.items() if k != "por_fuente"}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
