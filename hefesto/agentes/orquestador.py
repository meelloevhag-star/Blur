"""
Agente orquestador: entrena el motor con lo aceptado y decide qué datos faltan (aprendizaje activo).

1. Lee datos/aceptados/*.csv (esquema unificado) y arma las 7 entradas del motor. Solo usa filas
   con todas las entradas y cierre medido (no imputa); informa cuántas quedan fuera y por qué campo.
2. Entrena MotorBioCrete y lo registra como nueva versión (huella de datos, fecha, n).
3. Mapa de necesidades: recorre combinaciones ambiente × protección × lactato × ancho (a 90 días) y
   puntúa cada una por falta de datos de soporte, avisos de dominio y desacuerdo entre redes.
   Escribe necesidades.json y necesidades.md con lo que conviene buscar o ensayar primero.

Uso:
    python -m hefesto.agentes.orquestador [--rapido]
"""

import argparse
import csv
import datetime as dt
import itertools
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

from hefesto.motor.motor import MotorBioCrete

RAIZ = Path(__file__).resolve().parents[2]
ACEPTADOS = RAIZ / "datos" / "aceptados"
MODELOS = RAIZ / "modelos"
CAMPOS_MOTOR = ["dano_ancho_fisura_mm", "resultado_edad_dias", "mezcla_nivel_proteccion", "zona_ambiente_marino",
                "mezcla_lactato_calcio", "mezcla_curado_previo", "mezcla_agente_cristalino"]
NOMBRES_PROT = {0: "sin bacterias", 1: "directa/comercial", 2: "portador", 3: "encapsulación"}


def cargar_aceptados() -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    X, y, g, faltan, total = [], [], [], Counter(), 0
    for ruta in sorted(ACEPTADOS.glob("*.csv")):
        with open(ruta, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                total += 1
                vacios = [c for c in CAMPOS_MOTOR + ["resultado_cierre_pct"] if not (r.get(c) or "").strip()]
                if vacios:
                    faltan.update(vacios)
                    continue
                X.append([float(r[c]) for c in CAMPOS_MOTOR])
                y.append(float(r["resultado_cierre_pct"]) / 100.0)
                g.append(f"{r['fuente']}|{r['id_grupo']}")
    info = {"filas_aceptadas": total, "filas_usadas": len(y), "campos_que_faltan": dict(faltan.most_common())}
    return np.array(X), np.array(y), np.array(g), info


def registrar(motor: MotorBioCrete, info: dict) -> dict:
    MODELOS.mkdir(parents=True, exist_ok=True)
    ruta_reg = MODELOS / "registro.json"
    registro = json.loads(ruta_reg.read_text(encoding="utf-8")) if ruta_reg.exists() else []
    version = len(registro) + 1
    entrada = {"version": version, "fecha": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               "huella_datos": motor.huella, "n_filas": info["filas_usadas"], "K_redes": motor.K,
               "generaciones": motor.generaciones, "archivo": f"motor_v{version:03d}.pkl"}
    motor.guardar(MODELOS / entrada["archivo"])
    registro.append(entrada)
    ruta_reg.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
    return entrada


def mapa_necesidades(motor: MotorBioCrete, X: np.ndarray, top: int = 12) -> list[dict]:
    candidatos = []
    for marino, prot, lact, w0 in itertools.product((0, 1), (0, 1, 2, 3), (0, 1), (0.1, 0.2, 0.3, 0.5)):
        fila = np.array([[w0, 90.0, prot, marino, lact, 0, 0]])
        soporte = int(np.sum((X[:, 3] == marino) & (X[:, 2] == prot) & (X[:, 4] == lact)))
        avisos = motor.avisos_dominio(fila[0])
        duda = float(motor.desacuerdo(fila)[0])
        puntaje = 3.0 * (soporte == 0) + 1.0 * len(avisos) + duda / 10.0
        candidatos.append({
            "ambiente": "marino" if marino else "no marino", "proteccion": NOMBRES_PROT[prot],
            "lactato_calcio": bool(lact), "ancho_mm": w0, "filas_de_soporte": soporte,
            "avisos": avisos, "desacuerdo_redes_pp": round(duda, 1), "puntaje": round(puntaje, 2),
            "accion": ("buscar datos o ensayar: combinación sin ningún dato" if soporte == 0 else
                       "ampliar rango (ancho/edad) con ensayos" if avisos else "reforzar con más réplicas"),
        })
    return sorted(candidatos, key=lambda c: -c["puntaje"])[:top]


def escribir_necesidades(nec: list[dict], info: dict, entrada: dict):
    (RAIZ / "necesidades.json").write_text(json.dumps({"version_motor": entrada, "datos": info, "necesidades": nec},
                                                      ensure_ascii=False, indent=2), encoding="utf-8")
    lineas = [f"# Mapa de necesidades (motor v{entrada['version']}, {entrada['fecha']})", "",
              f"Filas aceptadas: {info['filas_aceptadas']} · usadas por el motor: {info['filas_usadas']}.",
              "Campos que más faltan para usar el resto: " + (", ".join(f"{k} ({v})" for k, v in
                                                                  list(info["campos_que_faltan"].items())[:5]) or "—"),
              "", "| # | Ambiente | Protección | Lactato Ca | Ancho (mm) | Soporte | Avisos | Acción |",
              "|---|---|---|---|---|---|---|---|"]
    for i, c in enumerate(nec, 1):
        lineas.append(f"| {i} | {c['ambiente']} | {c['proteccion']} | {'sí' if c['lactato_calcio'] else 'no'} | "
                      f"{c['ancho_mm']} | {c['filas_de_soporte']} | {len(c['avisos'])} | {c['accion']} |")
    (RAIZ / "necesidades.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true")
    a = ap.parse_args(argv)
    X, y, g, info = cargar_aceptados()
    motor = MotorBioCrete(K=2, generaciones=5) if a.rapido else MotorBioCrete()
    motor.ajustar(X, y)
    entrada = registrar(motor, info) if not a.rapido else {"version": 0, "fecha": "rápido"}
    nec = mapa_necesidades(motor, X)
    escribir_necesidades(nec, info, entrada)
    print(json.dumps({"datos": info, "motor": entrada, "top3": nec[:3]}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
