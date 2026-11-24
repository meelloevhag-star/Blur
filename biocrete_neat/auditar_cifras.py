"""
Auditoría de cifras: compara las cifras del manuscrito BioCrete-NEAT (resumen, Tablas III–V y texto de
resultados, transcritas a mano en MANUSCRITO/TABLA_III/TABLA_V) contra los resultados
y datos guardados. Si el texto cambia, actualizar también estas transcripciones.

Uso:
    python -m biocrete_neat.auditar_cifras
Genera resultados/auditoria_cifras.md y devuelve código 1 si hay discrepancias.
"""

import csv
import json
import math
import statistics
import sys
from pathlib import Path

from biocrete_neat.entrenar_neat import LAMBDA_PARSIMONIA_ALTA, LAMBDA_PARSIMONIA_MODERADA

RUTA_BASE = Path(__file__).resolve().parent
RUTA_RES = RUTA_BASE / "resultados"
RUTA_DATOS = RUTA_BASE / "datos"

# (sección del manuscrito, descripción, valor en el manuscrito, tolerancia absoluta)
# Los valores se copiaron del borrador ACI0189_CON3_GUARDAMINO_F05_Articulo_Cientifico_2.docx.
MANUSCRITO = {
    "n_dryad": ("Resumen / Tabla I", "Ensayos DRCM OPC de Dryad", 239, 0),
    "n_cappellesso": ("Resumen / Tabla III", "Mediciones AgNO3 marinas de Cappellesso", 642, 0),
    "n_mousa": ("Resumen / Tabla IV", "Registros de cierre de Mousa", 52, 0),
    "n_meta": ("Resumen / Tabla IV", "Condiciones del meta-dataset", 36, 0),
    "dryad_razon": ("Resumen / III-A", "Razón mediana Life-365 / experimental", 1.04, 0.005),
    "dryad_mediana": ("III-A", "Mediana experimental D_RCM (1e-12 m²/s)", 7.95, 0.005),
    "dryad_rmse": ("III-A", "RMSE Life-365 (1e-12 m²/s)", 3.03, 0.005),
    "neat_alta_r2": ("Resumen / Tabla IV", "NEAT λ=8e-4 R²", 0.540, 0.0005),
    "neat_alta_mae": ("Resumen / Tabla IV", "NEAT λ=8e-4 MAE", 0.104, 0.0005),
    "neat_alta_rmse": ("Tabla IV", "NEAT λ=8e-4 RMSE", 0.125, 0.0005),
    "neat_alta_ocultas": ("III-B", "NEAT λ=8e-4 neuronas ocultas promedio", 0.0, 0.0),
    "ridge_r2": ("Resumen / Tabla IV", "Ridge R² (α)", 0.523, 0.0005),
    "ridge_mae": ("Tabla IV", "Ridge MAE (α)", 0.110, 0.0005),
    "ridge_rmse": ("Tabla IV", "Ridge RMSE (α)", 0.127, 0.0005),
    "rf_r2": ("Resumen / Tabla IV", "RF R² (α)", 0.514, 0.0005),
    "rf_mae": ("Tabla IV", "RF MAE (α)", 0.109, 0.0005),
    "rf_rmse": ("Tabla IV", "RF RMSE (α)", 0.128, 0.0005),
    "neat_mod_r2": ("III-B / Tabla IV", "NEAT λ=1,2e-4 R²", 0.366, 0.0005),
    "neat_mod_mae": ("Tabla IV", "NEAT λ=1,2e-4 MAE", 0.123, 0.0005),
    "neat_mod_rmse": ("Tabla IV", "NEAT λ=1,2e-4 RMSE", 0.146, 0.0005),
    "neat_mod_ocultas": ("III-B", "NEAT λ=1,2e-4 neuronas ocultas promedio", 1.4, 0.0),
    "mousa_rf_r2": ("Resumen / Tabla IV", "Mousa RF R²", 0.529, 0.0005),
    "mousa_rf_mae": ("Tabla IV", "Mousa RF MAE %", 10.45, 0.005),
    "mousa_rf_rmse": ("Tabla IV", "Mousa RF RMSE %", 12.60, 0.005),
    "mousa_ridge_r2": ("Tabla IV", "Mousa Ridge R²", 0.356, 0.0005),
    "mousa_ridge_mae": ("Tabla IV", "Mousa Ridge MAE %", 12.11, 0.005),
    "mousa_ridge_rmse": ("Tabla IV", "Mousa Ridge RMSE %", 14.72, 0.005),
    "mousa_neat_r2": ("Resumen / Tabla IV", "Mousa NEAT R²", 0.195, 0.0005),
    "mousa_neat_mae": ("Tabla IV", "Mousa NEAT MAE %", 13.58, 0.005),
    "mousa_neat_rmse": ("Tabla IV", "Mousa NEAT RMSE %", 16.46, 0.005),
    "mousa_neat_ocultas": ("Tabla IV", "Mousa NEAT neuronas ocultas promedio", 0.4, 0.0),
    "topo_ocultas": ("III-C", "Topología final: neuronas ocultas", 0, 0),
    "topo_conex": ("III-C", "Topología final: conexiones activas", 2, 0),
    "imp_proteccion": ("Resumen / III-C", "ΔRMSE protección biológica", 0.1122, 0.00005),
    "imp_fisura": ("Resumen / III-C", "ΔRMSE ancho de fisura", 0.0094, 0.00005),
}

# Tabla III: (condición, REF media, REF desv, BAS media, BAS desv, reducción %)
TABLA_III = [
    ("Uncracked H", 9.07, 3.44, 6.35, 3.71, 30.0),
    ("Uncracked U", 23.10, 8.51, 16.52, 5.14, 28.5),
    ("Crack 100 U", 29.18, 8.38, 24.69, 9.08, 15.4),
    ("Crack 300 U", 34.69, 12.02, 28.11, 12.81, 19.0),
    ("Crack 300 H", 24.44, 10.85, 22.57, 15.34, 7.7),
    ("Crack 100 H", 13.84, 7.00, 18.77, 16.17, -35.6),
]

# Tabla V: (fragmento del escenario, cierre %, α)
TABLA_V = [
    ("a/c 0,68 · directa · fisura 0,2", 79.9, 0.362),
    ("a/c 0,68 · directa · fisura 0,5", 64.3, 0.289),
    ("a/c 0,68 · directa · fisura 1,0", 32.5, 0.189),
    ("a/c 0,45 · directa · rec 50 mm · 0,2", 79.9, 0.362),
    ("a/c 0,45 · portador · rec 40 mm · 0,3", 94.5, 0.466),
    ("a/c 0,45 · encapsul. · rec 40 mm · 0,3", 95.4, 0.601),
]


def _json(nombre: str) -> dict:
    return json.loads((RUTA_RES / nombre).read_text(encoding="utf-8"))


def _valores_calculados() -> dict:
    neat = _json("resumen_neat.json")
    zen = _json("resumen_datasets_reales_zenodo.json")
    por_lambda = neat.get("cv_5fold_alpha_por_lambda", {})
    alta = por_lambda.get(str(LAMBDA_PARSIMONIA_ALTA))
    mod = por_lambda.get(str(LAMBDA_PARSIMONIA_MODERADA))
    mousa = zen["mousa2022_neat_5fold"]
    imp = {d["variable"]: d["delta_rmse"] for d in neat["importancia_permutacion_alpha"]}

    with open(RUTA_DATOS / "dryad_opc_drcm_real.csv", encoding="utf-8-sig", newline="") as f:
        dryad = list(csv.DictReader(f))
    d_exp = [float(r["d_rcm_exp_1e12"]) for r in dryad]
    d_l365 = [float(r["d28_life365_1e12"]) for r in dryad]
    razones = [a / b for a, b in zip(d_l365, d_exp)]

    v = {
        "n_dryad": len(dryad),
        "n_cappellesso": sum(r["n_mediciones"] for r in zen["cappellesso2024_agno3_marino"]),
        "n_mousa": mousa["n_mediciones_reales_zenodo"],
        "n_meta": neat["n_ensayos_meta_dataset"],
        "dryad_razon": round(statistics.median(razones), 2),
        "dryad_mediana": round(statistics.median(d_exp), 2),
        "dryad_rmse": round(math.sqrt(sum((a - b) ** 2 for a, b in zip(d_exp, d_l365)) / len(d_exp)), 2),
        "mousa_rf_r2": mousa["RandomForest"]["R2"], "mousa_rf_mae": mousa["RandomForest"]["MAE_pct"],
        "mousa_rf_rmse": mousa["RandomForest"]["RMSE_pct"],
        "mousa_ridge_r2": mousa["Ridge"]["R2"], "mousa_ridge_mae": mousa["Ridge"]["MAE_pct"],
        "mousa_ridge_rmse": mousa["Ridge"]["RMSE_pct"],
        "mousa_neat_r2": mousa["NEAT"]["R2"], "mousa_neat_mae": mousa["NEAT"]["MAE_pct"],
        "mousa_neat_rmse": mousa["NEAT"]["RMSE_pct"], "mousa_neat_ocultas": mousa["neat_neuronas_ocultas_prom"],
        "topo_ocultas": neat["topologia_final_alpha"]["neuronas_ocultas"],
        "topo_conex": neat["topologia_final_alpha"]["conexiones_activas"],
        "imp_proteccion": imp.get("Protección bio (0-3)"),
        "imp_fisura": imp.get("Ancho fisura (mm)"),
    }
    if alta:
        v.update({"neat_alta_r2": alta["NEAT"]["R2"], "neat_alta_mae": alta["NEAT"]["MAE"],
                  "neat_alta_rmse": alta["NEAT"]["RMSE"], "neat_alta_ocultas": alta["neat_neuronas_ocultas_promedio"]})
    ref = mod or {}
    if ref:
        v.update({"ridge_r2": ref["Ridge"]["R2"], "ridge_mae": ref["Ridge"]["MAE"], "ridge_rmse": ref["Ridge"]["RMSE"],
                  "rf_r2": ref["RandomForest"]["R2"], "rf_mae": ref["RandomForest"]["MAE"], "rf_rmse": ref["RandomForest"]["RMSE"]})
    if mod:
        v.update({"neat_mod_r2": mod["NEAT"]["R2"], "neat_mod_mae": mod["NEAT"]["MAE"],
                  "neat_mod_rmse": mod["NEAT"]["RMSE"], "neat_mod_ocultas": mod["neat_neuronas_ocultas_promedio"]})
    return v


def _fila(seccion, desc, manuscrito, calculado, tol) -> dict:
    if calculado is None:
        estado = "SIN RESPALDO"
    elif abs(float(manuscrito) - float(calculado)) <= tol + 1e-12:
        estado = "OK"
    else:
        estado = "DIFIERE"
    return {"seccion": seccion, "cifra": desc, "manuscrito": manuscrito, "calculado": calculado, "estado": estado}


def auditar() -> list[dict]:
    calc = _valores_calculados()
    filas = [_fila(sec, desc, val, calc.get(clave), tol) for clave, (sec, desc, val, tol) in MANUSCRITO.items()]

    zen = _json("resumen_datasets_reales_zenodo.json")
    cap = {(r["condicion"], r["grupo"]): r for r in zen["cappellesso2024_agno3_marino"]}
    for cond, ref_m, ref_s, bas_m, bas_s, red in TABLA_III:
        ref, bas = cap.get((cond, "REF")), cap.get((cond, "BAS"))
        for desc, val, got in [
            ("REF media", ref_m, ref and ref["penetracion_cl_media_mm"]),
            ("REF desv", ref_s, ref and ref["desv_est_mm"]),
            ("BAS media", bas_m, bas and bas["penetracion_cl_media_mm"]),
            ("BAS desv", bas_s, bas and bas["desv_est_mm"]),
            ("Reducción %", red, bas and bas["reduccion_vs_REF_pct"]),
        ]:
            filas.append(_fila("Tabla III", f"{cond} · {desc}", val, got, 0.005))

    preds = _json("resumen_neat.json")["puente_micro_macro_paita"]
    for frag, cierre, alpha in TABLA_V:
        coincidencias = [x for x in preds if frag in x["escenario"]]
        p = coincidencias[0] if len(coincidencias) == 1 else None
        filas.append(_fila("Tabla V", f"{frag} · cierre %", cierre, p and p["cierre_predicho_neat_pct"], 0.05))
        filas.append(_fila("Tabla V", f"{frag} · α", alpha, p and p["alpha_predicho_neat"], 0.0005))
    return filas


def escribir_reporte(filas: list[dict]) -> Path:
    n_ok = sum(f["estado"] == "OK" for f in filas)
    lineas = [
        "# Auditoría de cifras del manuscrito BioCrete-NEAT",
        "",
        f"{n_ok} de {len(filas)} cifras coinciden con los resultados reproducidos.",
        "",
        "| Sección | Cifra | Manuscrito | Calculado | Estado |",
        "|---|---|---|---|---|",
    ]
    lineas += [f"| {f['seccion']} | {f['cifra']} | {f['manuscrito']} | {f['calculado']} | {f['estado']} |" for f in filas]
    ruta = RUTA_RES / "auditoria_cifras.md"
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return ruta


def main() -> int:
    filas = auditar()
    ruta = escribir_reporte(filas)
    fallos = [f for f in filas if f["estado"] != "OK"]
    print(f"{len(filas) - len(fallos)}/{len(filas)} cifras OK -> {ruta}")
    for f in fallos:
        print(f"  [{f['estado']}] {f['seccion']} · {f['cifra']}: manuscrito={f['manuscrito']} calculado={f['calculado']}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
