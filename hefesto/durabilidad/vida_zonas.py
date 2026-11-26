"""
Reparación necesaria por zona para 25 y 40 años de vida útil (inicio de la corrosión por cloruros).

Para cada una de las 384 zonas costeras (datos/durabilidad/zonas):
  1. Exposición: índice de niebla, depósito de cloruros y régimen (hefesto.durabilidad.exposicion, supuestos).
  2. Mezclas que cumplen la norma del régimen (hefesto.durabilidad.normas): cemento I o IP, a/b en {máx, máx−0,05}
     y recubrimiento en {mínimo, mínimo + 15 mm}.
  3. Por mezcla: años sin fisura, años con la fisura de diseño (0,3 mm) sin reparar y cierre mínimo
     requerido para 25 y 40 años (hefesto.durabilidad.vida_util).
  4. Se elige la mezcla más sencilla que alcanza 25 años: el menor recubrimiento, luego el menor
     cierre requerido y luego la mayor a/b.
  5. El motor NEAT (último modelos/motor_vNNN.pkl) predice el cierre a 90 días con cada opción de
     protección × lactato. Veredicto con la mejor opción y el error de ±20 pp: "cumple" si
     predicción − 20 ≥ requerido, "incierto" si solo la predicción central alcanza, y "no cumple"
     en otro caso.
Salidas: resultados/vida_zonas.json (con resumen) y resultados/vida_zonas.csv.

Uso:
    python -m hefesto.durabilidad.vida_zonas [--workers 4]
"""

import argparse
import csv
import itertools
import json
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from hefesto.durabilidad import exposicion as ex
from hefesto.motor.motor import MotorBioCrete
from hefesto.durabilidad.normas import reglas
from hefesto.durabilidad.vida_util import cierre_requerido, vida_util

RAIZ = Path(__file__).resolve().parents[2]
ZONAS = RAIZ / "datos" / "durabilidad" / "zonas"
W0, EDAD, ERROR_PP = 0.3, 90, 20.0
OBJETIVOS = (25, 40)
NOMBRES_PROT = {0: "sin bacterias", 1: "directa/comercial", 2: "portador", 3: "encapsulación"}


def ultimo_motor() -> tuple[MotorBioCrete, str]:
    reg = json.loads((RAIZ / "modelos" / "registro.json").read_text(encoding="utf-8"))
    archivo = reg[-1]["archivo"]
    return MotorBioCrete.cargar(RAIZ / "modelos" / archivo), archivo


def mezclas(regimen: str) -> list[dict]:
    r = reglas(regimen)
    cems = [c for c in ("I", "IP") if c in r["cementos_permitidos"]] or ["IP"]
    abs_ = sorted({r["a_c_max"], round(r["a_c_max"] - 0.05, 2), 0.35}, reverse=True)  # norma o más exigente
    covs = (r["recubrimiento_mm"], r["recubrimiento_mm"] + 15)
    return [{"cemento": c, "a_b": a, "recubrimiento_mm": cv} for c, a, cv in itertools.product(cems, abs_, covs)]


def evaluar_zona(z: dict, amb: dict) -> dict:
    niebla = ex.indice_niebla(amb)
    dep = ex.deposicion_cloruros(z["dist_mar_km"], amb, niebla)
    reg = ex.regimen(z["franja"], dep, niebla)
    base = {"id": z["id"], "departamento": z["departamento"], "lat": z["lat"], "lon": z["lon"],
            "dist_mar_km": z["dist_mar_km"], "regimen": reg, "clase": reglas(reg)["clase"],
            "indice_niebla": niebla, "deposicion_mg_m2_d": dep, "clase_iso9223": ex.clase_iso9223(dep),
            "t_media_c": amb["t_media_c"]}
    if reg == "seco":
        return base | {"estado": "fuera_de_alcance", "nota": "sin cloruros: gobierna la carbonatación"}
    cands = []
    for mz in mezclas(reg):
        kw = dict(deposicion=dep, t_media_c=amb["t_media_c"], recubrimiento_mm=mz["recubrimiento_mm"])
        sano = vida_util(mz["a_b"], mz["cemento"], reg, w0_mm=0.0, **kw)
        fis = vida_util(mz["a_b"], mz["cemento"], reg, w0_mm=W0, **kw)
        req = {o: cierre_requerido(mz["a_b"], mz["cemento"], reg, o, w0_mm=W0, **kw) for o in OBJETIVOS}
        cands.append(mz | {"sin_fisura": sano["reporte"], "fisura_sin_reparar": fis["reporte"],
                           "anios_fisura_sin_reparar": fis["anios"], "req": req,
                           "_t_sano": float("inf") if sano["estado"] == "cumple" else (sano["anios"] or 0.0)})

    alcanzan = [c for c in cands if c["req"][25]["estado"] in ("sin_reparacion_basta", "requiere_reparacion")]
    if alcanzan:   # la más sencilla que llega a 25 años: menor recubrimiento, menor cierre, mayor a/b
        elegida = min(alcanzan, key=lambda c: (c["recubrimiento_mm"], c["req"][25]["cierre_min"], -c["a_b"]))
    else:          # ninguna llega: se informa la más durable para mostrar cuánto falta
        elegida = max(cands, key=lambda c: (c["_t_sano"], -c["recubrimiento_mm"]))
    return base | {"estado": "evaluada", "mezcla": {k: elegida[k] for k in ("cemento", "a_b", "recubrimiento_mm")},
                   "sin_fisura": elegida["sin_fisura"], "fisura_sin_reparar": elegida["fisura_sin_reparar"],
                   "requerido": {str(o): elegida["req"][o] for o in OBJETIVOS}, "n_mezclas_evaluadas": len(cands)}


def veredicto(req: dict, pred_pct: float) -> str:
    if req["estado"] == "sin_reparacion_basta":
        return "cumple sin reparación"
    if req["estado"] != "requiere_reparacion":
        return "no alcanzable con esta mezcla"
    r = 100 * req["cierre_min"]
    return "cumple" if pred_pct - ERROR_PP >= r else "incierto" if pred_pct >= r else "no cumple"


def mejor_opcion(motor: MotorBioCrete, marino: int) -> dict:
    filas = [[W0, EDAD, p, marino, l, 0, 0] for p, l in itertools.product(range(4), (0, 1))]
    preds = motor.predecir(np.array(filas, float))
    ops = [{"proteccion": NOMBRES_PROT[f[2]], "lactato_calcio": bool(f[4]), "cierre_pct": p["cierre_pct"],
            "confiable": p["confiable"]} for f, p in zip(filas, preds)]
    fiables = [o for o in ops if o["confiable"]] or ops
    return {"mejor": max(fiables, key=lambda o: o["cierre_pct"]), "opciones": ops}


def _tarea(args):
    return evaluar_zona(*args)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    zonas = json.loads((ZONAS / "zonas_per.json").read_text(encoding="utf-8"))
    clima = json.loads((ZONAS / "ambiente_per.json").read_text(encoding="utf-8"))
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        res = list(pool.map(_tarea, [(z, clima[z["id"]]) for z in zonas], chunksize=4))
    motor, archivo = ultimo_motor()
    neat = {m: mejor_opcion(motor, m) for m in (0, 1)}
    for r in res:
        if r["estado"] != "evaluada":
            continue
        op = neat[1]
        r["neat"] = {"motor": archivo, "edad_dias": EDAD, "w0_mm": W0, **op["mejor"], "error_pp": ERROR_PP}
        r["veredicto"] = {o: veredicto(r["requerido"][str(o)], op["mejor"]["cierre_pct"]) for o in OBJETIVOS}
    ev = [r for r in res if r["estado"] == "evaluada"]
    resumen = {"zonas": len(res), "fuera_de_alcance_carbonatacion": len(res) - len(ev),
               "regimenes": dict(Counter(r["regimen"] for r in res)),
               "fisura_sin_reparar": dict(Counter(r["fisura_sin_reparar"] for r in ev).most_common(8)),
               "veredicto_25": dict(Counter(r["veredicto"][25] for r in ev)),
               "veredicto_40": dict(Counter(r["veredicto"][40] for r in ev)),
               "cierre_requerido_25_pct": _cuantiles([r["requerido"]["25"]["cierre_min"] for r in ev]),
               "cierre_requerido_40_pct": _cuantiles([r["requerido"]["40"]["cierre_min"] for r in ev]),
               "neat_mejor_opcion_marina": neat[1]["mejor"], "neat_opciones_marinas": neat[1]["opciones"],
               "max_anios_informados": max([r.get("anios_fisura_sin_reparar") or 0 for r in ev], default=0)}
    sal = RAIZ / "resultados"
    (sal / "vida_zonas.json").write_text(json.dumps({"resumen": resumen, "zonas": res}, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    campos = ["id", "departamento", "lat", "lon", "dist_mar_km", "regimen", "clase", "deposicion_mg_m2_d",
              "cemento", "a_b", "recubrimiento_mm", "sin_fisura", "fisura_sin_reparar",
              "cierre_req_25_pct", "cierre_req_40_pct", "neat_cierre_pct", "veredicto_25", "veredicto_40"]
    with open(sal / "vida_zonas.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        for r in res:
            fila = {k: r.get(k, "") for k in campos}
            if r["estado"] == "evaluada":
                fila |= r["mezcla"]
                for o in OBJETIVOS:
                    c = r["requerido"][str(o)]["cierre_min"]
                    fila[f"cierre_req_{o}_pct"] = "" if c is None else round(100 * c, 1)
                    fila[f"veredicto_{o}"] = r["veredicto"][o]
                fila["neat_cierre_pct"] = r["neat"]["cierre_pct"]
            else:
                fila["veredicto_25"] = fila["veredicto_40"] = "fuera de alcance (carbonatación)"
            w.writerow(fila)
    print(json.dumps(resumen, ensure_ascii=False, indent=1))
    return 0


def _cuantiles(vals):
    v = [100 * x for x in vals if x is not None]
    if not v:
        return {"n": 0}
    q = np.percentile(v, [10, 50, 90])
    return {"n": len(v), "p10": round(q[0], 1), "mediana": round(q[1], 1), "p90": round(q[2], 1),
            "sin_dato_no_alcanzable": len(vals) - len(v)}


if __name__ == "__main__":
    sys.exit(main())
