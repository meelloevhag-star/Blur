"""
E1 · Piso de ruido y E2 · error actual en puntos de cierre.

E1  ¿Cuánto error es irreducible con las variables disponibles?
    - Cota superior del piso: MAE de predecir cada registro con la media de su condición
      (misma fuente, mezcla/agente, régimen, ubicación y edad).
    - Cota inferior (optimista): dentro de cada condición se ajusta además el ancho inicial w0
      con una recta, dentro de la muestra.
    - Cappellesso: variación entre zonas de una misma probeta y edad (heterogeneidad de medición).
E2  Error actual (MAE en puntos) por modelo y protocolo, leído de la auditoría de Blur.

Uso:
    python -m hefesto.motor.diagnostico
"""

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
RUTA_REPLICAS = RAIZ / "datos" / "replicas_cierre_fisuras.csv"
RUTA_BLUR = RAIZ / "articulos" / "1_auditoria" / "resultados" / "revision" / "resumen_revision.json"
RUTA_SALIDA = RAIZ / "resultados" / "meta20_diagnostico.json"
META = 20.0


def _filas():
    with open(RUTA_REPLICAS, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _clave_condicion(r: dict) -> tuple:
    ubic = r["ubicacion"] if r["fuente"] == "Mousa2022" else "-"
    return (r["fuente"], r["grupo_condicion"], r["regimen"], ubic, float(r["edad_dias"]))


def piso_de_ruido(filas=None) -> dict:
    filas = filas or _filas()
    grupos = defaultdict(list)
    for r in filas:
        grupos[_clave_condicion(r)].append((float(r["w0_mm"]), float(r["cierre_pct"])))

    def resumen(fuente=None):
        err_media, err_w0, n_cond = [], [], 0
        for clave, pares in grupos.items():
            if (fuente and clave[0] != fuente) or len(pares) < 2:
                continue
            n_cond += 1
            w0, y = np.array(pares).T
            err_media += list(np.abs(y - y.mean()))
            if len(pares) >= 3 and np.ptp(w0) > 0:
                a, b = np.polyfit(w0, y, 1)
                pred = np.clip(a * w0 + b, 0, 100)
            else:
                pred = np.full_like(y, y.mean())
            err_w0 += list(np.abs(y - pred))
        return {"n_registros": len(err_media), "n_condiciones": n_cond,
                "piso_superior_pp": round(float(np.mean(err_media)), 2),
                "piso_inferior_pp": round(float(np.mean(err_w0)), 2)}

    salida = {"global": resumen()}
    for f in sorted({r["fuente"] for r in filas}):
        salida[f] = resumen(f)
    zonas = defaultdict(list)
    for r in filas:
        if r["fuente"] == "Cappellesso2024":
            zonas[(r["grupo_probeta"], float(r["edad_dias"]))].append(float(r["cierre_pct"]))
    err = [abs(v - np.mean(vs)) for vs in zonas.values() if len(vs) >= 2 for v in vs]
    salida["Cappellesso2024"]["entre_zonas_misma_probeta_pp"] = round(float(np.mean(err)), 2)
    return salida


def error_actual() -> dict:
    r = json.loads(RUTA_BLUR.read_text(encoding="utf-8"))
    salida = {}
    for conj in ("replicas", "literatura_cierre", "meta"):
        escala = 1.0 if conj == "meta" else 100.0  # α no está en %; se reporta tal cual
        salida[conj] = {prot: {m: round(v["MAE_medio"] * escala, 2) for m, v in r[conj][prot]["modelos"].items()}
                        for prot in ("filas", "grupos") if prot in r[conj]}
    salida["replicas"]["laboratorio"] = {
        f"{d['entrenamiento']}→{d['prueba']}": {
            **{m: round(v["MAE"] * 100, 2) for m, v in d["modelos"].items()},
            "referencia_media": round(d["mae_media_entrenamiento"] * 100, 2)}
        for d in r["replicas"]["fuente_detalle"].values()}
    return salida


def main() -> int:
    res = {"meta_pp": META, "E1_piso_ruido": piso_de_ruido(), "E2_error_actual_pp": error_actual()}
    RUTA_SALIDA.parent.mkdir(parents=True, exist_ok=True)
    RUTA_SALIDA.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
