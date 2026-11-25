"""Blur · población: WorldPop 2022, 1 km, ajustada a la ONU (CC BY 4.0).

WorldPop distribuye los totales del Censo Nacional 2017 (INEI) y sus proyecciones con covariables
satelitales. El ráster se guarda en biocrete_neat/datos/territorio/worldpop/ (no se versiona) y su
huella en el registro.
"""
from __future__ import annotations

from biocrete_neat.territorio.red import bajar_archivo
from biocrete_neat.territorio.registro import DIR, Registro, huella

WORLDPOP_DIR = DIR / "worldpop"
WORLDPOP = {"PER": "https://data.worldpop.org/GIS/Population/Global_2021_2022_1km_UNadj/unconstrained/2022/PER/"
                   "per_ppp_2022_1km_UNadj.tif"}


def ruta(pais="PER"):
    return WORLDPOP_DIR / WORLDPOP[pais].rsplit("/", 1)[1]


def recolectar(pais="PER", forzar=False) -> dict:
    WORLDPOP_DIR.mkdir(parents=True, exist_ok=True)
    r = ruta(pais)
    error = None
    if forzar or not r.exists():
        try:
            bajar_archivo(WORLDPOP[pais], r)
        except Exception as e:  # noqa: BLE001
            error = str(e)
    entrada = {"estado": "ok" if r.exists() and not error else "error", "url": WORLDPOP[pais],
               "licencia": "CC BY 4.0 (WorldPop, Universidad de Southampton)",
               "archivo": str(r.relative_to(DIR.parents[2]))}
    if r.exists():
        entrada |= {"bytes": r.stat().st_size, "huella": huella(r)}
    if error:
        entrada["detalle"] = error
    reg = Registro()
    reg.reemplazar("poblacion", entrada)
    reg.guardar()
    return entrada
