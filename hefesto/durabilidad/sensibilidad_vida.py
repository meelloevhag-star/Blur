"""
Sensibilidad del cálculo de vida útil a los supuestos más débiles, en 5 zonas tipo.

Variantes (una a la vez sobre el caso base):
  base           D ∝ f², CoV(Cs) 0,3, P(inicio) 10 %, recubrimiento de la mezcla elegida
  fisura_lineal  D ∝ f (efecto de la fisura menos severo)
  cs_cov_0.5     más dispersión en los cloruros de superficie
  p_50           vida media (P = 50 %) en lugar del criterio de diseño (P = 10 %)
  recub_+15      recubrimiento 15 mm mayor
Salida: resultados/sensibilidad_vida.json

Uso:
    python -m hefesto.durabilidad.sensibilidad_vida
"""

import json
import sys
from pathlib import Path

from hefesto.durabilidad import vida_util as vu

RAIZ = Path(__file__).resolve().parents[2]
PUNTOS = {"Talara": (-4.58, -81.27), "Paita": (-5.09, -81.11), "Piura": (-5.19, -80.63),
          "Callao": (-12.05, -77.15), "Chimbote": (-9.08, -78.59)}
VARIANTES = {"base": {}, "fisura_lineal": {"EXP_FISURA": 1}, "cs_cov_0.5": {"COV_CS": 0.5},
             "p_50": {"P_OBJETIVO": 0.5}, "recub_+15": {"_recub": 15}}


def zona_cercana(zonas, lat, lon, evaluada=True):
    cand = [z for z in zonas if (z["estado"] == "evaluada") == evaluada]
    return min(cand, key=lambda z: (z["lat"] - lat) ** 2 + (z["lon"] - lon) ** 2)


def evaluar(z: dict, extra_recub: float = 0.0) -> dict:
    mz = z["mezcla"]
    kw = dict(deposicion=z["deposicion_mg_m2_d"], t_media_c=z["t_media_c"],
              recubrimiento_mm=mz["recubrimiento_mm"] + extra_recub)
    out = {"sin_fisura": vu.vida_util(mz["a_b"], mz["cemento"], z["regimen"], w0_mm=0.0, **kw)["reporte"],
           "fisura_sin_reparar": vu.vida_util(mz["a_b"], mz["cemento"], z["regimen"], w0_mm=0.3, **kw)["reporte"]}
    for o in (25, 40):
        r = vu.cierre_requerido(mz["a_b"], mz["cemento"], z["regimen"], o, w0_mm=0.3, **kw)
        out[f"cierre_req_{o}_pct"] = None if r["cierre_min"] is None else round(100 * r["cierre_min"], 1)
        out[f"estado_{o}"] = r["estado"]
    return out


def main() -> int:
    zonas = json.loads((RAIZ / "resultados" / "vida_zonas.json").read_text(encoding="utf-8"))["zonas"]
    sal, orig = {}, {k: getattr(vu, k) for k in ("EXP_FISURA", "COV_CS", "P_OBJETIVO")}
    for nombre, (lat, lon) in PUNTOS.items():
        z = zona_cercana(zonas, lat, lon)
        sal[nombre] = {"zona": z["id"], "regimen": z["regimen"], "deposicion_mg_m2_d": z["deposicion_mg_m2_d"],
                       "mezcla": z["mezcla"], "variantes": {}}
        for var, cambios in VARIANTES.items():
            for k, v in cambios.items():
                if not k.startswith("_"):
                    setattr(vu, k, v)
            try:
                sal[nombre]["variantes"][var] = evaluar(z, cambios.get("_recub", 0.0))
            finally:
                for k, v in orig.items():
                    setattr(vu, k, v)
        print(nombre, json.dumps(sal[nombre], ensure_ascii=False), flush=True)
    (RAIZ / "resultados" / "sensibilidad_vida.json").write_text(json.dumps(sal, ensure_ascii=False, indent=1),
                                                                 encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
