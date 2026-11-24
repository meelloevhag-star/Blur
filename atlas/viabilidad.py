"""Costo por m³ (S/) e índice de disponibilidad (0-1) de una receta en una zona.

  - Cemento: precio de bolsa (catálogo) + flete desde la planta más cercana que fabrica ese tipo
    (distancia geodésica × sinuosidad × tarifa por t·km).
  - Agregados: precio local de cantera (hay canteras a lo largo de toda la costa).
  - Aditivos y agentes: catálogo; el agente comercial bacteriano se modela como +50 % del costo base.
  - Disponibilidad: producto de la disponibilidad de cada insumo, que decae con la distancia al
    proveedor (cemento desde planta; agentes desde Lima o importados).
"""
from __future__ import annotations

import csv
import math
from functools import lru_cache

from atlas.rutas import CATALOGO

LIMA = (-12.05, -77.04)


def _csv(nombre):
    with open(CATALOGO / nombre, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@lru_cache
def catalogo() -> dict:
    t = {r["parametro"]: float(r["valor"]) for r in _csv("transporte.csv")}
    return {
        "cementos": {r["id"]: r | {"densidad": float(r["densidad"]), "n": float(r["factor_envejecimiento_n"]),
                                   "precio_kg": float(r["precio_bolsa_pen"]) / float(r["bolsa_kg"])}
                     for r in _csv("cementos.csv")},
        "plantas": [r | {"lat": float(r["lat"]), "lon": float(r["lon"]), "tipos": r["cementos"].split(";")}
                    for r in _csv("plantas_cemento.csv")],
        "agregados": {r["id"]: r | {k: float(r[k]) for k in ("precio_pen_m3", "densidad_sss", "peso_unitario_kg_m3")}
                      for r in _csv("agregados.csv")},
        "aditivos": {r["id"]: r for r in _csv("aditivos.csv")},
        "agentes": {r["id"]: r for r in _csv("agentes_autorreparacion.csv")},
        "transporte": t,
    }


def dist_km(a, b) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def planta_cercana(lat, lon, tipo):
    c = catalogo()
    cand = [p for p in c["plantas"] if tipo in p["tipos"]]
    p = min(cand, key=lambda p: dist_km((lat, lon), (p["lat"], p["lon"])))
    return p, dist_km((lat, lon), (p["lat"], p["lon"])) * c["transporte"]["sinuosidad_carretera"]


def costo_y_disponibilidad(receta: dict, agente_id: str, lat: float, lon: float, acceso_km: float = 0.0) -> dict:
    """acceso_km: distancia de la zona a la carretera principal más cercana (último tramo)."""
    c = catalogo()
    t = c["transporte"]
    cem = c["cementos"][receta["cemento_tipo"]]
    planta, d_planta = planta_cercana(lat, lon, receta["cemento_tipo"])
    piedra = c["agregados"]["piedra_12" if receta["tmn_mm"] <= 12.5 else "piedra_34"]
    arena = c["agregados"]["arena"]
    partidas = {
        "cemento": receta["cemento_kg"] * cem["precio_kg"],
        "flete_cemento": receta["cemento_kg"] / 1000 * d_planta * t["tarifa_flete"],
        # último tramo sin vía principal: cemento + agregados (≈ 2,3 t/m³) a tarifa doble (supuesto)
        "acceso_ultimo_tramo": 2.3 * acceso_km * t["sinuosidad_carretera"] * 2 * t["tarifa_flete"],
        "arena": receta["arena_kg"] / arena["peso_unitario_kg_m3"] * arena["precio_pen_m3"],
        "piedra": receta["piedra_kg"] / piedra["peso_unitario_kg_m3"] * piedra["precio_pen_m3"],
        "superplastificante": receta["superplastificante_kg"] * float(c["aditivos"]["superplastificante"]["precio_pen_kg"]),
        "cristalizante": receta["cristalino_kg"] * float(c["aditivos"]["cristalino"]["precio_pen_kg"]),
    }
    base = sum(partidas.values())
    ag = c["agentes"][agente_id]
    if agente_id == "basilisk":
        partidas["agente_autorreparador"] = 0.5 * base           # ENR: +50 % del m³
    elif agente_id in ("lwa_bacterias", "hidrogel_bacterias", "consorcio_agricola"):
        lactato_kg = 0.015 * receta["cemento_kg"]                # ~1,5 % del cemento (supuesto de literatura)
        partidas["agente_autorreparador"] = lactato_kg * 5.2 * t["tipo_cambio"] + (
            60.0 if agente_id == "lwa_bacterias" else 120.0 if agente_id == "hidrogel_bacterias" else 25.0)
    total = sum(partidas.values())

    d_lima = dist_km((lat, lon), LIMA)
    disp_cem = math.exp(-d_planta / 600)
    disp_ag = float(ag["disponibilidad_pe"])
    if agente_id not in ("ninguno",):
        disp_ag *= math.exp(-d_lima / 1500)
    disp_cris = (float(c["aditivos"]["cristalino"]["disponibilidad_pe"].replace("media", "0.7").replace("alta", "0.9"))
                 * math.exp(-d_lima / 1500)) if receta["cristalino_kg"] > 0 else 1.0
    disp_acceso = math.exp(-acceso_km / 40)
    disponibilidad = disp_cem * disp_ag * disp_cris * disp_acceso
    return {"costo_m3_pen": round(total, 0), "partidas_pen": {k: round(v, 1) for k, v in partidas.items()},
            "planta_cemento": f"{planta['empresa']} · {planta['planta']}", "dist_planta_km": round(d_planta, 0),
            "disponibilidad": round(disponibilidad, 3), "dist_via_principal_km": round(acceso_km, 1),
            "proveedor_agente": ag["proveedor_ciudad"] or "—"}
