r"""
Extractor y Validador de Bases de Datos Oficiales (Zenodo + Dryad):
  1. Dryad (DOI: 10.5061/dryad.66t1g1k6j) -> ~250 ensayos reales D_RCM de OPC vs. Life-365.
  2. Zenodo 6469122 (Mousa et al., LSU)   -> cientos de mediciones reales de cierre de fisuras
     con bacterias encapsuladas vs. control a 3, 7, 14 y 28 días -> entrena NEAT vs. RF vs. Ridge!
  3. Zenodo 11305154 (Cappellesso et al., 2024, Ghent Univ.) -> penetración real de cloruros
     (nitrato de plata AgNO3, mm) en ambiente marino: REF vs. BAS (bacterias) vs. CA (cristalino).
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
import openpyxl
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold

RUTA_NEAT = Path(__file__).resolve().parent
BASE_ZENODO = RUTA_NEAT.parent / "datasets_reales_zenodo"
RUTA_DATOS = RUTA_NEAT / "datos"
RUTA_RES = RUTA_NEAT / "resultados"


def extraer_dryad_opc_drcm() -> list[dict]:
    """Extrae los ensayos experimentales reales de D_RCM para OPC (table1 y table2 de Dryad)."""
    xlsx = BASE_ZENODO / "Dryad_RCM_Chloride_Diffusion_Database" / "Experimental_data_for_chloride_diffusion_coefficient_of_concrete_by_rapid_chloride_migration_test.xlsx"
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    filas = []
    for hoja in ["table1(OPC)", "table2(OPC)"]:
        ws = wb[hoja]
        ref_actual = ""
        for r_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
            # Las columnas en table1 pueden tener un índice inicial; ubicamos numéricos finales (w/b y D_RCM)
            vals = [v for v in row if v is not None]
            if len(vals) < 2:
                continue
            # Buscar los últimos dos valores numéricos válidos: w/b en [0.20, 0.75] y D_RCM en [0.5, 80]
            nums = [float(v) for v in vals if isinstance(v, (int, float))]
            if len(nums) >= 2:
                wb_val, d_rcm = nums[-2], nums[-1]
                if 0.20 <= wb_val <= 0.75 and 0.5 <= d_rcm <= 80.0:
                    textos = [str(v).strip() for v in vals if isinstance(v, str) and len(str(v).strip()) > 2]
                    if textos and len(textos[0]) > 15:
                        ref_actual = textos[0].replace("\n", " ")[:120]
                    cemento = textos[-1] if textos else "OPC"
                    d_life365 = (10.0 ** (-12.06 + 2.40 * wb_val)) * 1e12  # en 10^-12 m2/s
                    filas.append({
                        "hoja": hoja,
                        "cemento": cemento[:30],
                        "a_c": round(wb_val, 3),
                        "d_rcm_exp_1e12": round(d_rcm, 3),
                        "d28_life365_1e12": round(d_life365, 3),
                        "razon_life365_vs_exp": round(d_life365 / d_rcm, 3),
                        "referencia": ref_actual,
                    })
    wb.close()
    return filas


def extraer_mousa_fisuras() -> list[dict]:
    """Extrae mediciones reales de cierre de fisuras a 3, 7, 14 y 28 días de Zenodo 6469122."""
    xlsx = BASE_ZENODO / "Encapsulated_Bacteria_Optimal_SH" / "extraido" / "All cracks summary combined Hydrogel LWA CNC (version 2).xlsx"
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    ws = wb["Summary"]
    registros = []
    # En Summary: col 2 = descripción muestra, cols 3,5,7,9,11 = AVG (um) a 0, 3, 7, 14, 28 días
    edades = [(4, 3), (6, 7), (8, 14), (10, 28)]  # (indice_0based_en_fila, dias)
    for r_idx, row in enumerate(ws.iter_rows(min_row=4, max_col=14, values_only=True), 4):
        desc = row[1]
        w0 = row[2]
        if not isinstance(desc, str) or not isinstance(w0, (int, float)) or w0 <= 15.0:
            continue
        desc_l = desc.lower()
        tiene_bact = 0 if ("no bact" in desc_l or "control" in desc_l or "only" in desc_l and "with bact" not in desc_l) else 1
        if "hydrogel" in desc_l or "bead" in desc_l:
            prot = 3 if tiene_bact else 0
            metodo = "Hidrogel"
        elif "lwa" in desc_l or "clay" in desc_l:
            prot = 2 if tiene_bact else 0
            metodo = "LWA"
        elif "cnc" in desc_l:
            prot = 2 if tiene_bact else 0
            metodo = "CNC"
        else:
            prot = 1 if tiene_bact else 0
            metodo = "Nutriente/Directa"
        tiene_nutr = 0 if "no nutrients" in desc_l else 1

        for col_idx, dias in edades:
            wt = row[col_idx] if col_idx < len(row) else None
            if isinstance(wt, (int, float)) and wt >= 0.0:
                cierre = max(0.0, min(100.0, (w0 - wt) / w0 * 100.0))
                registros.append({
                    "fila_excel": r_idx,
                    "muestra": desc.strip()[:70],
                    "metodo": metodo,
                    "tiene_bacterias": tiene_bact,
                    "nivel_proteccion": prot,
                    "tiene_nutriente": tiene_nutr,
                    "w0_um": round(float(w0), 1),
                    "w0_mm": round(float(w0) / 1000.0, 4),
                    "edad_dias": dias,
                    "wt_um": round(float(wt), 1),
                    "cierre_pct": round(cierre, 2),
                })
    wb.close()
    return registros


def extraer_cappellesso_agno3() -> list[dict]:
    """Extrae promedios reales de penetración de cloruros (AgNO3, mm) de Zenodo 11305154 (Cappellesso 2024)."""
    xlsx = BASE_ZENODO / "Cappellesso2024_Marine_CAB_Cloruros" / "03_Mar_Silver nitrate measurements.xlsx"
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    resumen = []
    for hoja in ["Uncracked H", "Crack 100 H", "Crack 300 H", "Uncracked U", "Crack 100 U", "Crack 300 U"]:
        if hoja not in wb.sheetnames:
            continue
        ws = wb[hoja]
        por_grupo = {"REF": [], "BAS": [], "CA": []}
        for row in ws.iter_rows(min_row=6, values_only=True):
            for c_idx, val in enumerate(row):
                if isinstance(val, str):
                    s = val.strip().upper()
                    grupo = None
                    if s.startswith("REF"):
                        grupo = "REF"
                    elif s.startswith("BAS"):
                        grupo = "BAS"
                    elif s.startswith("CA"):
                        grupo = "CA"
                    if grupo:
                        # Leer los siguientes valores numéricos de profundidad de cloruros (mm) en esa muestra
                        meds = []
                        for nxt in row[c_idx + 2 : c_idx + 12]:
                            if isinstance(nxt, (int, float)) and 0.5 < float(nxt) < 60.0:
                                meds.append(float(nxt))
                            elif isinstance(nxt, str) and nxt.strip():
                                break
                        if meds:
                            por_grupo[grupo].extend(meds)
        ref_m = float(np.mean(por_grupo["REF"])) if por_grupo["REF"] else None
        for g, vals in por_grupo.items():
            if vals:
                prom = float(np.mean(vals))
                red_vs_ref = round((1.0 - prom / ref_m) * 100.0, 1) if (ref_m and g != "REF") else 0.0
                resumen.append({
                    "condicion": hoja,
                    "grupo": g,
                    "n_mediciones": len(vals),
                    "penetracion_cl_media_mm": round(prom, 2),
                    "desv_est_mm": round(float(np.std(vals)), 2),
                    "reduccion_vs_REF_pct": red_vs_ref,
                })
    wb.close()
    return resumen


def entrenar_neat_sobre_zenodo(registros_mousa: list[dict]) -> dict:
    """Entrena y valida (5-fold CV) NEAT vs. Random Forest vs. Ridge sobre las mediciones REALES de Zenodo 6469122."""
    X_raw = np.array([
        [r["w0_mm"], r["edad_dias"], r["tiene_bacterias"], r["nivel_proteccion"], r["tiene_nutriente"], r["w0_mm"] / (r["edad_dias"] + 1.0)]
        for r in registros_mousa
    ], dtype=float)
    y = np.array([r["cierre_pct"] / 100.0 for r in registros_mousa], dtype=float)

    # Normalización min-max segura
    mins = X_raw.min(axis=0)
    spans = np.where((X_raw.max(axis=0) - mins) > 0, X_raw.max(axis=0) - mins, 1.0)
    X = (X_raw - mins) / spans

    kf = KFold(n_splits=5, shuffle=True, random_state=2026)
    pred_neat = np.zeros_like(y)
    pred_rf = np.zeros_like(y)
    pred_ridge = np.zeros_like(y)
    ocultos = []

    cfg_path = str(RUTA_NEAT / "config_neat.txt")
    for fold, (tr, te) in enumerate(kf.split(X)):
        random.seed(200 + fold)
        np.random.seed(200 + fold)
        cfg = neat.Config(neat.DefaultGenome, neat.DefaultReproduction, neat.DefaultSpeciesSet, neat.DefaultStagnation, cfg_path)
        pop = neat.Population(cfg)

        def eval_pop(genomes, c):
            for _gid, g in genomes:
                net = neat.nn.FeedForwardNetwork.create(g, c)
                p = np.array([net.activate(x)[0] for x in X[tr]])
                mse = float(np.mean((p - y[tr]) ** 2))
                n_oc = len([n for n in g.nodes if n >= c.genome_config.num_outputs])
                g.fitness = -mse - 0.0002 * n_oc

        ganador = pop.run(eval_pop, 65)
        net_g = neat.nn.FeedForwardNetwork.create(ganador, cfg)
        pred_neat[te] = [net_g.activate(x)[0] for x in X[te]]
        ocultos.append(len([n for n in ganador.nodes if n >= cfg.genome_config.num_outputs]))

        rf = RandomForestRegressor(n_estimators=150, max_depth=6, random_state=2026)
        rf.fit(X[tr], y[tr])
        pred_rf[te] = np.clip(rf.predict(X[te]), 0.0, 1.0)

        ridge = Ridge(alpha=1.0)
        ridge.fit(X[tr], y[tr])
        pred_ridge[te] = np.clip(ridge.predict(X[te]), 0.0, 1.0)

    def m(yt, yp):
        return {
            "R2": round(float(r2_score(yt * 100, yp * 100)), 3),
            "MAE_pct": round(float(mean_absolute_error(yt * 100, yp * 100)), 2),
            "RMSE_pct": round(float(math.sqrt(mean_squared_error(yt * 100, yp * 100))), 2),
        }

    return {
        "n_mediciones_reales_zenodo": len(registros_mousa),
        "NEAT": m(y, pred_neat),
        "RandomForest": m(y, pred_rf),
        "Ridge": m(y, pred_ridge),
        "neat_neuronas_ocultas_prom": round(float(np.mean(ocultos)), 2),
        "y_real_pct": y * 100.0,
        "pred_neat_pct": pred_neat * 100.0,
        "pred_rf_pct": pred_rf * 100.0,
    }


def guardar_csv(ruta: Path, filas: list[dict]) -> None:
    if not filas:
        return
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)


def main() -> None:
    RUTA_RES.mkdir(parents=True, exist_ok=True)

    # 1. Dryad D_RCM real vs Life-365
    dryad = extraer_dryad_opc_drcm()
    guardar_csv(RUTA_DATOS / "dryad_opc_drcm_real.csv", dryad)
    acs = np.array([d["a_c"] for d in dryad])
    d_exp = np.array([d["d_rcm_exp_1e12"] for d in dryad])
    d_l365 = np.array([d["d28_life365_1e12"] for d in dryad])
    razon_med = float(np.median(d_l365 / d_exp))

    print("=" * 74)
    print("EXTRACCIÓN Y VALIDACIÓN DE DATASETS REALES (ZENODO + DRYAD)")
    print("=" * 74)
    print(f"\n[1] Dryad OPC D_RCM (DOI 10.5061/dryad.66t1g1k6j): n = {len(dryad)} ensayos reales extraídos")
    print(f"    Rango a/c: {acs.min():.2f} a {acs.max():.2f} | Mediana D_RCM exp: {np.median(d_exp):.2f} x10^-12 m2/s")
    print(f"    Razón mediana Life-365 / D_RCM experimental = {razon_med:.2f}x (RMSE Life-365 = {math.sqrt(mean_squared_error(d_exp, d_l365)):.2f} x10^-12)")

    # 2. Cappellesso 2024 AgNO3 real marino
    cap = extraer_cappellesso_agno3()
    guardar_csv(RUTA_DATOS / "cappellesso2024_agno3_marino.csv", cap)
    print(f"\n[2] Cappellesso et al. 2024 (Zenodo 11305154 — AgNO3 marino): {sum(c['n_mediciones'] for c in cap)} mediciones reales")
    for c in cap:
        if c["grupo"] in ("REF", "BAS"):
            print(f"    {c['condicion']:<12} {c['grupo']}: {c['penetracion_cl_media_mm']:>5.2f} ± {c['desv_est_mm']:.2f} mm (n={c['n_mediciones']:>3}) | red vs REF: {c['reduccion_vs_REF_pct']:>+5.1f}%")

    # 3. Mousa et al. (Zenodo 6469122) fisuras reales + NEAT 5-fold CV
    mousa = extraer_mousa_fisuras()
    guardar_csv(RUTA_DATOS / "mousa2022_fisuras_reales.csv", mousa)
    res_neat = entrenar_neat_sobre_zenodo(mousa)
    print(f"\n[3] Mousa et al. (Zenodo 6469122 — cierre fisuras real): n = {len(mousa)} mediciones reales extraídas")
    print("    Validación cruzada 5-fold sobre datos CRUDOS reales de Zenodo:")
    for mod in ("NEAT", "RandomForest", "Ridge"):
        print(f"      {mod:<14} -> R2 = {res_neat[mod]['R2']:>6} | MAE = {res_neat[mod]['MAE_pct']:>5.2f}% | RMSE = {res_neat[mod]['RMSE_pct']:>5.2f}%")
    print(f"      Neuronas ocultas promedio evolucionadas por NEAT: {res_neat['neat_neuronas_ocultas_prom']}")

    # 4. Figura conjunta de validación real (Dryad D_RCM vs Life-365 + NEAT sobre Zenodo)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.0, 4.7), dpi=220)
    ax1.scatter(acs, d_exp, s=22, alpha=0.65, color="#0284c7", label=f"Dryad OPC real (n={len(dryad)})")
    ac_grid = np.linspace(0.24, 0.68, 100)
    ax1.plot(ac_grid, (10.0 ** (-12.06 + 2.40 * ac_grid)) * 1e12, color="#dc2626", lw=2.3, label="Life-365 v2.2.1 (sin calibrar)")
    ax1.set_title("Validación Life-365 vs. Base de Datos Dryad (D_RCM OPC)")
    ax1.set_xlabel("Relación agua/cemento (a/c)")
    ax1.set_ylabel("Coef. difusión cloruros (×10⁻¹² m²/s)")
    ax1.set_ylim(0, 45)
    ax1.legend(fontsize=8.5)
    ax1.grid(True, alpha=0.3)

    ax2.scatter(res_neat["y_real_pct"], res_neat["pred_neat_pct"], s=20, alpha=0.65, color="#0f766e", label=f"NEAT (R²={res_neat['NEAT']['R2']}, MAE={res_neat['NEAT']['MAE_pct']}%)")
    ax2.scatter(res_neat["y_real_pct"], res_neat["pred_rf_pct"], s=18, alpha=0.45, color="#d97706", marker="^", label=f"Random Forest (R²={res_neat['RandomForest']['R2']})")
    ax2.plot([0, 100], [0, 100], "k--", lw=1.1)
    ax2.set_title(f"NEAT 5-fold CV sobre datos crudos Zenodo 6469122 (n={len(mousa)})")
    ax2.set_xlabel("Cierre de fisura real medido (%)")
    ax2.set_ylabel("Cierre predicho (out-of-fold, %)")
    ax2.legend(fontsize=8.5)
    ax2.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(RUTA_RES / "fig3_validacion_datasets_reales_zenodo_dryad.png", dpi=220)
    plt.close(fig)

    resumen_out = {
        "dryad_n_opc": len(dryad),
        "dryad_razon_mediana_life365_vs_exp": round(razon_med, 3),
        "cappellesso2024_agno3_marino": cap,
        "mousa2022_neat_5fold": {k: v for k, v in res_neat.items() if not isinstance(v, np.ndarray)},
    }
    (RUTA_RES / "resumen_datasets_reales_zenodo.json").write_text(json.dumps(resumen_out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n[OK] CSVs reales y figura guardados en:", RUTA_DATOS, "y", RUTA_RES)


if __name__ == "__main__":
    main()
