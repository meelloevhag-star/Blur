"""Reglas normativas de durabilidad por clase de exposición (simplificación documentada).

Fuentes: E.060 Concreto Armado (Perú, cap. 4, tablas de exposición a cloruros/sulfatos, alineadas
con ACI 318), ACI 318-19 tabla 19.3.2.1 (clases C1/C2, S1), EN 206 tabla F.1 (XS1-XS3, cemento
mínimo). Se toma el valor más exigente cuando difieren. La niebla salina se trata como XS2 en lugar
de XS1 porque humedece y aporta sal a la vez (criterio del proyecto, por validar con ensayos).
"""
CLASES = {
    #  régimen            clase   a/c_max  cem_min  fc_min_MPa  recubrimiento_mm  cementos_permitidos
    "salpicadura":        ("XS3", 0.40, 340, 35, 65, ("HS", "IP")),
    "niebla_salina":      ("XS2", 0.45, 320, 32, 50, ("HS", "IP", "I", "GU")),
    # lomas/cerros con niebla orográfica: humedad casi permanente + aerosol salino atenuado
    "niebla_orografica":  ("XS2", 0.45, 320, 32, 50, ("HS", "IP", "I", "GU")),
    "atmosferico_marino": ("XS1", 0.50, 300, 28, 50, ("HS", "IP", "I", "GU")),
    "seco":               ("XC",  0.55, 280, 21, 40, ("HS", "IP", "I", "GU")),
}


def reglas(regimen: str) -> dict:
    c, ac, cem, fc, rec, tipos = CLASES[regimen]
    return {"clase": c, "a_c_max": ac, "cemento_min_kg": cem, "fc_min_mpa": fc,
            "recubrimiento_mm": rec, "cementos_permitidos": list(tipos),
            "fuente": "E.060 cap. 4 / ACI 318-19 19.3 / EN 206 F.1 (simplificado)"}
