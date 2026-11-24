"""Niebla, garúa y aerosol salino: exposición tipo "spray" aunque la estructura esté lejos del mar.

Índice de niebla (0-1) a partir de ERA5:
  - fracción de horas con HR ≥ 95 % y T−Td ≤ 1 °C (niebla/garúa en superficie),
  - nubosidad baja media (estratos de la camanchaca),
  - fracción de horas con HR ≥ 85 % (humedad persistente).

Deposición de cloruros (mg Cl⁻/m²·día) con un perfil exponencial doble según la distancia al mar,
del tipo usado para la costa atlántica de Brasil (Meira et al., Atmospheric Environment 2007):
una caída rápida (gotas gruesas, ~0,4 km) y una cola larga que transporta la niebla. La cola se
amplifica con el índice de niebla. Clases ISO 9223: S0 ≤ 3, S1 ≤ 60, S2 ≤ 300, S3 ≤ 1500.
Los coeficientes son SUPUESTOS a calibrar con mediciones de candela húmeda en Perú.
"""
from __future__ import annotations

import math

D0_COSTA = 400.0      # mg/m²·d en la línea de costa con viento de 5 m/s (supuesto)
# Relieve (v2): niebla orográfica y apantallamiento del aerosol por crestas (supuestos a calibrar)
A_OROGRAFICO = 2.0    # con frac_loma ≥ 1/A la zona alcanza el máximo (todo lo que le falta al índice regional)
H_BARRERA_M = 300.0   # escala de atenuación del aerosol salino tras una cresta
UMBRAL_LOMA = 0.15    # fracción mínima de "ladera al mar en el cinturón" para el régimen de loma
L_RAPIDA_KM = 0.4
D0_COLA = 40.0
L_COLA_KM = 8.0


def indice_niebla(amb: dict) -> float:
    # ERA5 (~9-28 km) suaviza la niebla costera: se escala con los percentiles altos de la costa
    # peruana en 2024 (≈10 % de horas de niebla y ≈40 % de nubosidad baja media → índice máximo).
    fn = min(amb.get("frac_horas_niebla", 0.0) / 0.10, 1.0)
    cl = min((amb.get("nubes_bajas_media_pct") or 0.0) / 40.0, 1.0)
    h85 = amb.get("frac_horas_hr85", 0.0)
    return round(max(0.0, min(1.0, 0.45 * fn + 0.35 * cl + 0.2 * h85)), 3)


def indice_niebla_orografica(amb: dict, rel: dict | None) -> float:
    """Índice regional (ERA5) amplificado donde los cerros cortan la capa de estratos a barlovento.
    En el desierto llano no cambia; en las lomas (ladera al mar entre 300 y 1000 m) puede saturar."""
    base = indice_niebla(amb)
    if not rel:
        return base
    # acerca el índice a 1 en proporción a la ladera al mar dentro del cinturón (no satura en llano)
    return round(base + (1 - base) * min(1.0, A_OROGRAFICO * rel.get("frac_loma", 0.0)), 3)


def deposicion_cloruros(dist_km: float, amb: dict, niebla: float, barrera_m: float = 0.0) -> float:
    v = max(amb.get("viento_medio_ms", 4.0), 0.5)
    fv = (v / 5.0) ** 2
    rapida = D0_COSTA * fv * math.exp(-dist_km / L_RAPIDA_KM)
    cola = D0_COLA * fv * (1.0 + 2.0 * niebla) * math.exp(-dist_km / (L_COLA_KM * (1.0 + niebla)))
    return round((rapida + cola) * math.exp(-max(barrera_m, 0.0) / H_BARRERA_M), 1)


def clase_iso9223(dep: float) -> str:
    return "S0" if dep <= 3 else "S1" if dep <= 60 else "S2" if dep <= 300 else "S3"


def regimen(franja: int, dep: float, niebla: float, rel: dict | None = None) -> str:
    """Régimen de exposición ampliado."""
    if franja == 0:
        return "salpicadura"            # mareas / salpicadura directa
    if rel and rel.get("frac_loma", 0) >= UMBRAL_LOMA and niebla >= 0.45:
        return "niebla_orografica"      # cerros/lomas dentro del cinturón de niebla, a barlovento
    if niebla >= 0.45 and dep >= 30:
        return "niebla_salina"          # garúa/camanchaca con aerosol: spray atenuado
    if dep >= 15:
        return "atmosferico_marino"
    return "seco"
