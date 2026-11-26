"""
Motor único de Hefesto: el ganador del banco de comparación (resultados/banco_motores.json).

H3 = promedio de K = 5 redes NEAT (hefesto.motor.modelos, RedMatricial) + corrección local con
peso n/(n + 10) + márgenes conformes. Ganó por menor error entre laboratorios (19,3 pp, empatado
con el NEAT ×5 sin corrección) y por aprender más rápido con ensayos locales (18,7 pp con 10).

    motor = Motor().ajustar(X, y)                  # K redes NEAT (base global estable)
    motor.calibrar(X_loc, y_loc, g_loc)             # corrección H3 + márgenes conformes con ensayos locales
    motor.predecir(X_nuevo)                         # cierre %, intervalos 80/90 %, modo y avisos de dominio
    motor.guardar(ruta) / Motor.cargar(ruta)

X usa las 7 entradas de hefesto.motor.datos.VARS_R en unidades físicas (sin normalizar).
Horizonte: solo hay predicción entre las edades medidas (3–480 días). Fuera de ese rango
cierre_pct = None con su motivo. El motor da cierre de fisura, nunca años de vida útil; esos los
calcula hefesto.durabilidad.vida_util. Contrato de salida: esquema/contrato_salida.json.
Respaldo empírico (resultados/hibrido.json): sin calibrar ≈ 20 pp; con 5 grupos locales < 20 pp;
con 20–40 grupos ≈ 13–17 pp; cobertura conforme 76–94 %.
"""

import hashlib
import pickle
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestRegressor

from hefesto.motor.datos import VARS_R, normalizar7
from hefesto.motor.modelos import ConfigNEAT, NEATConjunto

SEMILLA = 2026
ERROR_SIN_CALIBRAR_PP = 20.0  # validación entre laboratorios (INFORME_META20 / hibrido.json)


def _rf(semilla=SEMILLA):
    return RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=semilla, n_jobs=1)


class Motor:
    def __init__(self, K=5, generaciones=50, lam=8e-4, k_contraccion=10, workers=4):
        self.K, self.generaciones, self.lam = K, generaciones, lam
        self.k_contraccion, self.workers = k_contraccion, workers
        self.redes, self.correccion, self.n_grupos_locales, self.cuantiles = [], None, 0, {}
        self.dominio, self.huella = {}, None

    # ------------------------------------------------------------------ ajuste global
    def ajustar(self, X, y):
        X = np.asarray(X, float)
        Xn = normalizar7(X)
        self._neat = NEATConjunto("NEAT ×5", self.K, ConfigNEAT(generaciones=self.generaciones, lam=self.lam))
        self._neat.ajustar(X, np.asarray(y, float))
        self.redes = self._neat.redes
        self._X_dominio = X
        self.dominio = self._calcular_dominio(X)
        self.huella = hashlib.sha256(np.c_[X, y].tobytes()).hexdigest()[:16]
        self.correccion, self.n_grupos_locales, self.cuantiles = None, 0, {}
        return self

    @staticmethod
    def _calcular_dominio(X) -> dict:
        marino = X[:, 3] == 1
        return {"w0_max_global": float(X[:, 0].max()),
                "w0_max_marino": float(X[marino, 0].max()) if marino.any() else None,
                "edad_rango": [float(X[:, 1].min()), float(X[:, 1].max())],
                "combinaciones": sorted({(int(m), int(p), int(l)) for m, p, l in X[:, [3, 2, 4]]})}

    def _base(self, Xn):
        return np.mean([red(Xn) for red in self.redes], axis=0)

    def desacuerdo(self, X):
        """Desviación típica entre las K redes (pp). Útil para priorizar, no como margen de error."""
        Xn = normalizar7(np.asarray(X, float))
        return np.std([red(Xn) for red in self.redes], axis=0) * 100

    # ------------------------------------------------------------------ calibración local (H3 + conforme)
    def _peso(self, n):
        return n / (n + self.k_contraccion)

    def calibrar(self, X_loc, y_loc, grupos_loc, alfas=(0.2, 0.1)):
        Xn, y, g = normalizar7(np.asarray(X_loc, float)), np.asarray(y_loc, float), np.asarray(grupos_loc)
        # Lo medido localmente pasa a formar parte del dominio conocido
        self.dominio = self._calcular_dominio(np.r_[self._X_dominio, np.asarray(X_loc, float)])
        base = self._base(Xn)
        ug = np.unique(g)
        self.n_grupos_locales = len(ug)
        self.correccion = _rf().fit(Xn, y - base)
        self.cuantiles = {}
        if len(ug) >= 3:
            w = self._peso(len(ug) - 1)
            puntuaciones = []
            for gg in ug:
                fuera, dentro = g == gg, g != gg
                rf = _rf().fit(Xn[dentro], y[dentro] - base[dentro])
                pred = np.clip(base[fuera] + w * rf.predict(Xn[fuera]), 0, 1)
                puntuaciones += list(np.abs(y[fuera] - pred))
            s = np.sort(puntuaciones)
            m = len(s)
            self.cuantiles = {a: float(s[min(m - 1, int(np.ceil((1 - a) * (m + 1))) - 1)]) for a in alfas}
        return self

    # ------------------------------------------------------------------ predicción
    def avisos_dominio(self, fila) -> list[str]:
        w0, edad, prot, marino, lact = fila[0], fila[1], int(fila[2]), int(fila[3]), int(fila[4])
        avisos = []
        if w0 > self.dominio["w0_max_global"]:
            avisos.append("ancho fuera del rango entrenado")
        if marino and self.dominio["w0_max_marino"] is not None and w0 > self.dominio["w0_max_marino"]:
            avisos.append("ancho fuera del rango marino entrenado")
        if not self.dominio["edad_rango"][0] <= edad <= self.dominio["edad_rango"][1]:
            avisos.append("edad fuera del rango entrenado")
        if (marino, prot, lact) not in {tuple(c) for c in self.dominio["combinaciones"]}:
            avisos.append("combinación ambiente/protección/lactato sin datos")
        return avisos

    def predecir(self, X) -> list[dict]:
        X = np.asarray(X, float)
        Xn = normalizar7(X)
        base = self._base(Xn)
        if self.correccion is not None:
            pred = np.clip(base + self._peso(self.n_grupos_locales) * self.correccion.predict(Xn), 0, 1)
            modo = f"H3 (NEAT + corrección local, {self.n_grupos_locales} grupos)"
        else:
            pred, modo = np.clip(base, 0, 1), "NEAT global (sin calibrar)"
        salida = []
        e_min, e_max = self.dominio["edad_rango"]
        for i, fila in enumerate(X):
            avisos = self.avisos_dominio(fila)
            d = {"cierre_pct": round(float(pred[i] * 100), 1), "modo": modo, "avisos": avisos,
                 "confiable": not avisos, "entradas": dict(zip(VARS_R, map(float, fila))),
                 "horizonte_valido": {"edad_dias": [e_min, e_max], "w0_max_mm": self.dominio["w0_max_global"],
                                      "unidad": "cierre de fisura (%) a la edad indicada; NO es vida útil"}}
            if not e_min <= fila[1] <= e_max:
                # Sin recorte silencioso: fuera del rango de edades medidas no hay predicción.
                d.update(cierre_pct=None, modo="fuera de horizonte", confiable=False,
                         motivo=f"edad {fila[1]:g} d fuera de {e_min:g}–{e_max:g} d medidos; "
                                "para años de servicio use hefesto.durabilidad.vida_util")
                salida.append(d)
                continue
            if self.cuantiles:
                for a, q in self.cuantiles.items():
                    d[f"intervalo_{int(round((1 - a) * 100))}"] = [round(max(0.0, pred[i] - q) * 100, 1),
                                                                   round(min(1.0, pred[i] + q) * 100, 1)]
            else:
                d["error_esperado_pp"] = ERROR_SIN_CALIBRAR_PP
            salida.append(d)
        return salida

    # ------------------------------------------------------------------ persistencia
    def guardar(self, ruta: Path) -> Path:
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with open(ruta, "wb") as fh:
            pickle.dump(self, fh)
        return ruta

    @staticmethod
    def cargar(ruta: Path) -> "Motor":
        with open(ruta, "rb") as fh:
            return pickle.load(fh)

    def matrices(self) -> list[list[dict]]:
        """Matrices de pesos por capa de cada red (para inspeccionar qué aprendió)."""
        return [r.matrices() for r in self.redes]


MotorBioCrete = Motor  # nombre anterior, usado por agentes y pruebas
