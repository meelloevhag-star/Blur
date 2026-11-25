"""Reglas normativas de durabilidad por régimen de exposición (gobierna la más exigente).

Fuentes:
  - E.060 Concreto Armado (Perú; propuesta SENCICO 2019, tablas 4.2.1 y 4.3.1): C2 = "expuesto a
    cloruros de agua de mar o salpicaduras": a/mc ≤ 0,40 y f′c ≥ 35 MPa; agua de mar = S2 (sulfatos).
  - ACI 318-19 tabla 19.3.2.1 (C1/C2) y 20.5.1.3 (recubrimiento).
  - EN 206 tabla F.1 (XS1: 0,50 / C30/37 / 300 kg; XS3: 0,45 / C35/45 / 340 kg) y EN 1992-1-1
    tabla 4.4N (c_min,dur para clase estructural S4, 50 años) + Δc_dev = 10 mm.
  - La niebla salina es aerosol marino (XS1 en EN 206, que no tiene una clase "niebla"); por mojar
    con sal casi a diario se diseña como C2 de la E.060/ACI. XS2 (sumergido) no aplica en la costa
    emergida.
Recubrimiento nominal para 50 años de vida de diseño; el optimizador prueba también +10 y +20 mm.
"""
CLASES = {
    #  régimen              clase          a/c_max cem_min fc_min rec_mm  cementos              agentes autorreparadores
    "salpicadura":        ("XS3 / C2",     0.40, 340, 35, 65, ("IP", "HS"),        ("cristalino",)),
    "niebla_salina":      ("XS1 / C2",     0.40, 340, 35, 55, ("IP", "HS"),        ("cristalino", "basilisk")),
    "niebla_orografica":  ("XS1 / C2",     0.40, 340, 35, 55, ("IP", "HS", "GU"),  ("cristalino", "basilisk")),
    "atmosferico_marino": ("XS1 / C1",     0.45, 300, 30, 50, ("IP", "HS", "GU"),  ("cristalino", "basilisk")),
    "seco":               ("XC4 / C1",     0.55, 280, 21, 40, ("IP", "HS", "GU", "I"),
                           ("cristalino", "basilisk", "lwa_bacterias", "hidrogel_bacterias")),
}
CEMENTO_MAX_KG = 450      # criterio: más cemento = más calor y retracción (más fisuras)


def reglas(regimen: str, dep: float | None = None) -> dict:
    """dep: deposición de cloruros (mg/m²·d). En lomas o brisa con ≥ 60 (ISO 9223 S2) rige C2."""
    c, ac, cem, fc, rec, tipos, agentes = CLASES[regimen]
    if dep is not None and dep < 60 and regimen == "niebla_orografica":
        c, ac, cem, fc = "XS1 / C1", 0.45, 320, 32
    if dep is not None and dep >= 60 and regimen == "atmosferico_marino":
        c, ac, cem, fc = "XS1 / C2", 0.40, 340, 35
    return {"clase": c, "a_c_max": ac, "cemento_min_kg": cem, "cemento_max_kg": CEMENTO_MAX_KG, "fc_min_mpa": fc,
            "recubrimiento_mm": rec, "cementos_permitidos": list(tipos), "agentes_permitidos": list(agentes),
            "fuente": "E.060 (2019) tablas 4.2.1/4.3.1 · ACI 318-19 19.3.2.1 · EN 206 F.1 · EN 1992-1-1 4.4N"}
