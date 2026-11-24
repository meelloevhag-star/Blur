"""Recetas por zona: candidatas que cumplen la norma → modelos → frente de Pareto → 3 recetas.

Para cada zona se evalúan todas las combinaciones de cemento permitido × a/c × agente × curado ×
tamaño máximo de agregado. Se entregan:
  - ideal:      mejor desempeño (vida útil + cierre) con datos que la respalden en ese ambiente,
  - económica:  la más barata que llega a ≥ 50 años,
  - disponible: la de mayor disponibilidad que llega a ≥ 50 años.
"""
from __future__ import annotations

import itertools
import json
import math

from atlas import ambiente as amb_mod
from atlas import niebla as nb
from atlas import relieve as rel_mod
from atlas import urbano as urb_mod
from atlas.diseno_mezcla import dosificar
from atlas.durabilidad import VIDA_MAX, vida_util, ajuste_drcm, efecto_agentes_cloruros
from atlas.ingesta import vector_cierre
from atlas.modelos import ModeloCierre
from atlas.normas import reglas
from atlas.viabilidad import catalogo, costo_y_disponibilidad
from atlas.zonas import cargar_zonas
from atlas.rutas import DATOS

W0_DISENO = 0.3       # mm, fisura de diseño (límite usual de servicio)
EDAD_DISENO = 90      # días
A_C_GRID = (0.35, 0.40, 0.45, 0.50, 0.55)
TMN_GRID = (12.5, 19.0)
VIDA_OBJ = 50


def evaluar_zona(z, amb, modelo: ModeloCierre, rel: dict | None = None, urb: dict | None = None) -> dict:
    cat = catalogo()
    idx_n = nb.indice_niebla_orografica(amb, rel)
    dep = nb.deposicion_cloruros(z.dist_mar_km, amb, idx_n, (rel or {}).get("barrera_m", 0.0))
    reg = nb.regimen(z.franja, dep, idx_n, rel)
    acceso_km = (urb or {}).get("dist_via_principal_km", 0.0)
    rg = reglas(reg)
    marino = 1 if reg != "seco" else 0
    agregados = {"arena": cat["agregados"]["arena"]}
    candidatas = []
    for tipo, ac, agente_id, curado, tmn in itertools.product(
            rg["cementos_permitidos"], A_C_GRID, cat["agentes"], (0, 1), TMN_GRID):
        if ac > rg["a_c_max"] + 1e-9:
            continue
        ag = cat["agentes"][agente_id]
        cem = cat["cementos"][tipo] | {"id": tipo}
        agregados["piedra"] = cat["agregados"]["piedra_12" if tmn <= 12.5 else "piedra_34"]
        cris = 4.5 if agente_id == "cristalino" else 0.0
        receta = dosificar(ac, tmn, cem, rg["cemento_min_kg"], agregados,
                           agente_kg=float(ag["dosis_kg_m3"]) if agente_id not in ("ninguno", "cristalino") else 0.0,
                           cristalino_kg=cris)
        if receta["fc_estimado_mpa"] < rg["fc_min_mpa"]:
            continue
        x = vector_cierre(W0_DISENO, EDAD_DISENO, ag["portador_blur"], int(ag["tiene_bacterias"]),
                          "lactato" if ag["nutriente"] else "ninguno", marino, curado)
        pred = modelo.predecir(x)
        # temperatura: la actividad bacteriana cae por debajo de ~10 °C (supuesto documentado)
        if int(ag["tiene_bacterias"]):
            f_t = min(max((amb["t_media_c"] - 5) / 10, 0.3), 1.0)
            pred["cierre_pct"] = round(pred["cierre_pct"] * f_t, 1)
            pred["factor_temperatura"] = round(f_t, 2)
        vida = vida_util(receta["a_c"], tipo, reg, dep, amb["t_media_c"], rg["recubrimiento_mm"],
                         cem["n"], pred["cierre_pct"] / 100, agente_id)
        vida_sin = vida_util(receta["a_c"], tipo, reg, dep, amb["t_media_c"], rg["recubrimiento_mm"],
                             cem["n"], 0.0, "ninguno")
        econ = costo_y_disponibilidad(receta, agente_id, z.lat, z.lon, acceso_km)
        en_dominio = pred["n_datos_combinacion"] > 0
        avisos = []
        if not en_dominio:
            avisos.append("combinación sin datos en Blur para este ambiente: predicción extrapolada")
        if not (ajuste_drcm()["rango_a_c"][0] <= receta["a_c"] <= ajuste_drcm()["rango_a_c"][1]):
            avisos.append("a/c fuera del rango de la base de cloruros")
        desempeno = 0.6 * min(vida / 100, 1) + 0.4 * pred["cierre_pct"] / 100
        candidatas.append({
            "agente": agente_id, "agente_nombre": ag["nombre"], "cepa": ag["cepa"] or "—",
            "portador": ag["portador_blur"], "nutriente": ag["nutriente"] or "—", "dosis_agente": ag["dosis_texto"],
            "curado_humedo_previo": bool(curado), "dosificacion": receta,
            "prediccion": pred, "vida_util_anios": vida, "vida_util_sin_reparacion_anios": vida_sin,
            "viabilidad": econ, "en_dominio": en_dominio, "avisos": avisos,
            "puntaje_desempeno": round(desempeno, 3),
            "origen": {"cierre": "modelo (XGBoost+NEAT, datos Blur)" if en_dominio else "modelo extrapolado",
                       "dosificacion": "regla ACI 211.1 + E.060", "vida_util": "Fick/fib B34 + datos Blur",
                       "costo": "catálogo con fuentes (atlas/catalogo)"}})
    # la referencia sin agente se reporta pero no se recomienda: el Atlas busca concreto autorreparable
    referencia = max((c for c in candidatas if c["agente"] == "ninguno"),
                     key=lambda c: (c["puntaje_desempeno"], -c["viabilidad"]["costo_m3_pen"]))
    autorrep = [c for c in candidatas if c["agente"] != "ninguno"]
    validas = [c for c in autorrep if c["en_dominio"]] or autorrep
    ideal = max(validas, key=lambda c: (c["puntaje_desempeno"], -c["viabilidad"]["costo_m3_pen"]))
    ok = [c for c in validas if c["vida_util_anios"] >= VIDA_OBJ] or validas
    economica = min(ok, key=lambda c: (c["viabilidad"]["costo_m3_pen"], -c["puntaje_desempeno"]))
    disponible = max(ok, key=lambda c: (c["viabilidad"]["disponibilidad"], c["puntaje_desempeno"]))
    pareto = _pareto(validas)
    # concreto común de la zona (Tipo I, a/c 0,55, recubrimiento de obra 40 mm, sin fisurar, sin agente):
    # mide qué tan agresivo es el ambiente para lo que hoy se construye → severidad para la prioridad
    vida_comun = vida_util(0.55, "I", reg, dep, amb["t_media_c"], 40,
                           cat["cementos"]["I"]["n"], 0.0, "ninguno", fisurado=False)
    return {"regimen": reg, "vida_util_concreto_comun_anios": vida_comun, "reglas": rg, "indice_niebla": idx_n, "deposicion_cl_mg_m2_d": dep,
            "clase_iso9223": nb.clase_iso9223(dep), "ambiente_marino_modelo": marino,
            "recetas": {"ideal": ideal, "economica": economica, "disponible": disponible},
            "referencia_sin_agente": referencia,
            "n_candidatas": len(candidatas), "n_pareto": len(pareto)}


def _pareto(c):
    def domina(a, b):
        fa = (a["puntaje_desempeno"], -a["viabilidad"]["costo_m3_pen"], a["viabilidad"]["disponibilidad"])
        fb = (b["puntaje_desempeno"], -b["viabilidad"]["costo_m3_pen"], b["viabilidad"]["disponibilidad"])
        return all(x >= y for x, y in zip(fa, fb)) and fa != fb
    return [a for a in c if not any(domina(b, a) for b in c)]


def construir(pais="PER") -> dict:
    zonas = cargar_zonas(pais)
    celdas = amb_mod.cargar(pais)
    if not celdas:
        raise RuntimeError("no hay datos climáticos: ejecute python -m atlas.ambiente")
    relieve = rel_mod.cargar(pais)
    urbano = urb_mod.cargar(pais)
    modelo = ModeloCierre()
    feats = []
    for z in zonas:
        rel = relieve.get(z.id)
        urb = urbano.get(z.id)
        amb = amb_mod.clima_zona(z, celdas, rel["elev_media_m"] if rel else None)
        r = evaluar_zona(z, amb, modelo, rel, urb)
        # escala logarítmica: 1 año → 1; 10 años → 0,54; 50 → 0,22; ≥ 150 → 0
        sev = max(0.0, min(1.0, 1 - math.log(max(r["vida_util_concreto_comun_anios"], 1)) / math.log(VIDA_MAX)))
        pob = (urb or {}).get("poblacion", 0)
        ideal = r["recetas"]["ideal"]
        feats.append({"type": "Feature", "id": z.id,
                      "geometry": {"type": "Polygon", "coordinates": [z.poligono]},
                      "properties": {
                          "id": z.id, "pais": z.pais, "departamento": z.departamento, "franja": z.franja,
                          "provincia": z.provincia, "distrito": z.distrito, "ubigeo": z.ubigeo, "tramo": z.tramo,
                          "dist_mar_km": z.dist_mar_km, "lat": z.lat, "lon": z.lon,
                          "ambiente": amb, "relieve": rel, "urbano": urb,
                          "elevacion_media_m": (rel or {}).get("elev_media_m"),
                          "frac_loma": (rel or {}).get("frac_loma", 0.0),
                          "poblacion": pob, "clase_urbana": (urb or {}).get("clase_urbana", "sin dato"),
                          "severidad": round(sev, 3),
                          # población que vive donde el concreto común dura menos: dónde rinde más el autorreparable
                          "prioridad": round(pob * sev),
                          **{k: v for k, v in r.items() if k not in ("recetas", "referencia_sin_agente")},
                          "referencia_sin_agente": r["referencia_sin_agente"],
                          "recetas": r["recetas"],
                          # atajos para colorear el mapa
                          "ideal_cierre_pct": ideal["prediccion"]["cierre_pct"],
                          "ideal_vida_anios": ideal["vida_util_anios"],
                          "ideal_vida_sin_reparacion_anios": ideal["vida_util_sin_reparacion_anios"],
                          "ganancia_autorreparacion_anios": ideal["vida_util_anios"] - ideal["vida_util_sin_reparacion_anios"],
                          "ideal_costo_m3": ideal["viabilidad"]["costo_m3_pen"],
                          "ideal_disponibilidad": ideal["viabilidad"]["disponibilidad"],
                          "economica_costo_m3": r["recetas"]["economica"]["viabilidad"]["costo_m3_pen"],
                      }})
    meta = {"modelo_version": modelo.p["version"], "cv_modelo": modelo.p["cv"],
            "durabilidad": {"drcm": ajuste_drcm(), "agentes": efecto_agentes_cloruros()},
            "w0_diseno_mm": W0_DISENO, "edad_diseno_dias": EDAD_DISENO, "vida_objetivo": VIDA_OBJ,
            "zonas_con_clima_propio": sum(1 for f in feats if f["properties"]["ambiente"]["celda_propia"]),
            "zonas": len(zonas), "celdas_era5": len(celdas),
            "malla": {"paso_km": 10, "franjas_km": [list(f) for f in __import__("atlas.zonas", fromlist=["x"]).FRANJAS_KM]},
            "poblacion_total_zonas": sum(f["properties"]["poblacion"] for f in feats),
            "fuentes_territorio": {"relieve": relieve.get("_meta"), "urbano": urbano.get("_meta")}}
    return {"type": "FeatureCollection", "metadata": meta, "features": feats}
