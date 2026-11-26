"""
Durabilidad orientada a objetos: un lugar, una mezcla y la pregunta de Hefesto.

    lugar = Exposicion.desde_clima(dist_mar_km=0.8, franja=1, clima={...})
    mezcla = Mezcla(cemento="IP", a_b=0.40, recubrimiento_mm=50)
    diseno = Diseno(lugar, uso="puerto")
    diseno.evaluar(mezcla, cierre_predicho_pct=78, error_pp=20)

Responde: ¿esta mezcla, con el cierre de fisura que predice el motor, alcanza la vida útil de diseño
que pide la norma para ese uso en ese lugar? Los cálculos son los de hefesto.durabilidad.vida_util
(Fick fib B34 corregido); aquí solo se ordenan como objetos.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from hefesto.durabilidad import exposicion as ex
from hefesto.durabilidad import vida_util as vu
from hefesto.durabilidad.normas import reglas, vida_diseno

W0_DISENO_MM = 0.3


@dataclass(frozen=True)
class Exposicion:
    """Condiciones de un lugar: régimen de exposición, depósito de cloruros y temperatura."""
    regimen: str
    deposicion_mg_m2_d: float = 0.0
    t_media_c: float = 20.0
    indice_niebla: float = 0.0

    @classmethod
    def desde_clima(cls, dist_mar_km: float, franja: int, clima: dict) -> "Exposicion":
        n = ex.indice_niebla(clima)
        dep = ex.deposicion_cloruros(dist_mar_km, clima, n)
        return cls(ex.regimen(franja, dep, n), dep, clima.get("t_media_c", 20.0), n)

    @property
    def con_cloruros(self) -> bool:
        return self.regimen != "seco"

    @property
    def norma(self) -> dict:
        return reglas(self.regimen)


@dataclass(frozen=True)
class Mezcla:
    cemento: str
    a_b: float
    recubrimiento_mm: float

    def cumple_norma(self, lugar: Exposicion) -> bool:
        r = lugar.norma
        return (self.cemento in r["cementos_permitidos"] and self.a_b <= r["a_c_max"] + 1e-9
                and self.recubrimiento_mm >= r["recubrimiento_mm"])


@dataclass
class ModeloCloruros:
    """Inicio de la corrosión por cloruros con P = 10 % (vida_util). Horizonte máximo informado."""
    horizonte_anios: float = 40.0

    def vida(self, lugar: Exposicion, mezcla: Mezcla, w0_mm: float, cierre_frac: float = 0.0) -> dict:
        return vu.vida_util(mezcla.a_b, mezcla.cemento, lugar.regimen, lugar.deposicion_mg_m2_d, lugar.t_media_c,
                            mezcla.recubrimiento_mm, w0_mm, cierre_frac, horizonte=self.horizonte_anios)

    def cierre_requerido(self, lugar: Exposicion, mezcla: Mezcla, objetivo: float, w0_mm: float) -> dict:
        return vu.cierre_requerido(mezcla.a_b, mezcla.cemento, lugar.regimen, objetivo, lugar.deposicion_mg_m2_d,
                                   lugar.t_media_c, mezcla.recubrimiento_mm, w0_mm)


@dataclass
class Diseno:
    """La pregunta de Hefesto para un lugar y un uso."""
    lugar: Exposicion
    uso: str = "vivienda"
    objetivo_anios: float | None = None        # por defecto: la vida útil de diseño de la norma
    w0_mm: float = W0_DISENO_MM
    modelo: ModeloCloruros = field(default_factory=ModeloCloruros)

    def __post_init__(self):
        if self.objetivo_anios is None:
            self.objetivo_anios = float(vida_diseno(self.uso)["vida_diseno_anios"])
        self.modelo.horizonte_anios = max(self.modelo.horizonte_anios, self.objetivo_anios)

    def evaluar(self, mezcla: Mezcla, cierre_predicho_pct: float | None = None, error_pp: float = 20.0) -> dict:
        if not self.lugar.con_cloruros:
            return {"estado": "fuera_de_alcance", "nota": "sin cloruros: gobierna la carbonatación"}
        req = self.modelo.cierre_requerido(self.lugar, mezcla, self.objetivo_anios, self.w0_mm)
        out = {"uso": self.uso, "objetivo_anios": self.objetivo_anios, "mezcla": mezcla.__dict__,
               "cumple_norma": mezcla.cumple_norma(self.lugar), "requerido": req,
               "sin_reparar": self.modelo.vida(self.lugar, mezcla, self.w0_mm)["reporte"]}
        if cierre_predicho_pct is not None:
            out["veredicto"] = veredicto(req, cierre_predicho_pct, error_pp)
        return out


def veredicto(req: dict, pred_pct: float, error_pp: float = 20.0) -> str:
    """«cumple» si se alcanza aun restando el error; «incierto» si solo con la predicción central."""
    if req["estado"] == "sin_reparacion_basta":
        return "cumple sin reparación"
    if req["estado"] != "requiere_reparacion":
        return "no alcanzable con esta mezcla"
    r = 100 * req["cierre_min"]
    return "cumple" if pred_pct - error_pp >= r else "incierto" if pred_pct >= r else "no cumple"
