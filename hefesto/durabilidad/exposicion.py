"""
Exposición por zona: índice de niebla, depósito de cloruros y régimen.

Portado de Blur/atlas/niebla.py (commit 200cb3a) sin cambios de fórmula. TODOS los coeficientes son
SUPUESTOS a calibrar con vela húmeda (ISO 9225) en la costa peruana: depósito en costa, distancias de
caída y efecto de la niebla.
Perfil doble exponencial con la distancia al mar, del tipo de Meira et al. (Atmos. Environ. 2007).
Clases ISO 9223: S0 ≤ 3, S1 ≤ 60, S2 ≤ 300, S3 ≤ 1500 mg/m²·d.
"""

import math

D0_COSTA, L_RAPIDA_KM, D0_COLA, L_COLA_KM = 400.0, 0.4, 40.0, 8.0


def indice_niebla(amb: dict) -> float:
    fn = min(amb.get("frac_horas_niebla", 0.0) / 0.10, 1.0)
    cl = min((amb.get("nubes_bajas_media_pct") or 0.0) / 40.0, 1.0)
    h85 = amb.get("frac_horas_hr85", 0.0)
    return round(max(0.0, min(1.0, 0.45 * fn + 0.35 * cl + 0.2 * h85)), 3)


def deposicion_cloruros(dist_km: float, amb: dict, niebla: float) -> float:
    fv = (max(amb.get("viento_medio_ms", 4.0), 0.5) / 5.0) ** 2
    rapida = D0_COSTA * fv * math.exp(-dist_km / L_RAPIDA_KM)
    cola = D0_COLA * fv * (1.0 + 2.0 * niebla) * math.exp(-dist_km / (L_COLA_KM * (1.0 + niebla)))
    return round(rapida + cola, 1)


def clase_iso9223(dep: float) -> str:
    return "S0" if dep <= 3 else "S1" if dep <= 60 else "S2" if dep <= 300 else "S3"


def regimen(franja: int, dep: float, niebla: float) -> str:
    if franja == 0:
        return "salpicadura"
    if niebla >= 0.45 and dep >= 30:
        return "niebla_salina"
    if dep >= 15:
        return "atmosferico_marino"
    return "seco"
