"""
Modelos candidatos del motor de Hefesto, con una interfaz común orientada a objetos.

Todos heredan de `Modelo` y exponen:
    ajustar(X, y, grupos=None) -> self
    predecir(X) -> np.ndarray          cierre de fisura en fracción [0, 1]
    complejidad() -> dict              nodos, conexiones o parámetros
    variables_usadas() -> list[str]    (solo NEAT: entradas con alguna conexión)

X siempre va en unidades físicas (7 columnas de hefesto.motor.datos.VARS_R); cada modelo normaliza
con los límites físicos fijos de `normalizar7`, así no hay fuga de información entre entrenamiento
y prueba.

NEAT (Stanley y Miikkulainen, 2002) evoluciona a la vez la topología y los pesos. Aquí cada genoma
se compila a una `RedMatricial`: los nodos se ordenan por capas y la red se evalúa con numpy sobre
todas las filas a la vez, en lugar de fila por fila. Así se puede inspeccionar como matrices de pesos
y se entrena mucho más rápido.
"""

from __future__ import annotations

import math
import random
import re
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from pathlib import Path

import neat
import numpy as np
from neat.graphs import feed_forward_layers
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor

from hefesto.motor.datos import VARS_R, normalizar7

SEMILLA = 2026
PLANTILLA_CFG = Path(__file__).resolve().parent / "config_neat.txt"


# ============================================================================ interfaz común
class Modelo(ABC):
    nombre: str = "modelo"
    familia: str = ""

    @abstractmethod
    def ajustar(self, X: np.ndarray, y: np.ndarray, grupos: np.ndarray | None = None) -> "Modelo": ...

    @abstractmethod
    def _predecir_n(self, Xn: np.ndarray) -> np.ndarray: ...

    def predecir(self, X: np.ndarray) -> np.ndarray:
        return np.clip(self._predecir_n(normalizar7(np.asarray(X, float))), 0.0, 1.0)

    def complejidad(self) -> dict:
        return {}

    def variables_usadas(self) -> list[str] | None:
        return None

    def __repr__(self):
        return f"{type(self).__name__}({self.nombre})"


# ============================================================================ NEAT compilado a matrices
def _sigmoide_neat(z: np.ndarray) -> np.ndarray:
    """Activación sigmoide de neat-python: 1 / (1 + e^(−5z)), con z acotado a ±60/5."""
    return 1.0 / (1.0 + np.exp(-np.clip(5.0 * z, -60.0, 60.0)))


class RedMatricial:
    """Red feed-forward de un genoma NEAT, evaluada por capas sobre todas las filas a la vez.

    Por cada nodo guarda sesgo, respuesta y la lista (origen, peso) de sus conexiones activas.
    `matrices()` devuelve, para cada capa, la matriz de pesos W (nodos de la capa × nodos origen),
    de modo que salida_capa = σ(5·(sesgo + respuesta · W·entrada)).
    """

    def __init__(self, genoma, config):
        gc = config.genome_config
        self.entradas = list(gc.input_keys)
        self.salida = gc.output_keys[0]
        conexiones = [cg.key for cg in genoma.connections.values() if cg.enabled]
        capas, requeridos = feed_forward_layers(self.entradas, gc.output_keys, conexiones)
        validos = set(requeridos) | set(self.entradas)          # igual que FeedForwardNetwork.create
        self.capas = [sorted(c) for c in capas]
        self.nodos = {}
        for capa in self.capas:
            for n in capa:
                ng = genoma.nodes[n]
                ins = [(i, genoma.connections[(i, o)].weight) for (i, o) in conexiones if o == n and i in validos]
                self.nodos[n] = (ng.bias, ng.response, ins)
        if self.salida not in self.nodos:              # salida sin conexiones: queda solo el sesgo
            ng = genoma.nodes[self.salida]
            self.nodos[self.salida] = (ng.bias, ng.response, [])
            self.capas.append([self.salida])

    def __call__(self, Xn: np.ndarray) -> np.ndarray:
        v = {k: Xn[:, j] for j, k in enumerate(self.entradas)}
        cero = np.zeros(len(Xn))
        for capa in self.capas:
            for n in capa:
                sesgo, resp, ins = self.nodos[n]
                s = sum((w * v.get(i, cero) for i, w in ins), cero)
                v[n] = _sigmoide_neat(sesgo + resp * s)
        return v[self.salida]

    def matrices(self) -> list[dict]:
        salida = []
        for capa in self.capas:
            origenes = sorted({i for n in capa for i, _ in self.nodos[n][2]})
            W = np.zeros((len(capa), len(origenes)))
            for r, n in enumerate(capa):
                for i, w in self.nodos[n][2]:
                    W[r, origenes.index(i)] = w
            salida.append({"nodos": capa, "origenes": origenes, "W": W.round(4).tolist(),
                           "sesgos": [round(self.nodos[n][0], 4) for n in capa]})
        return salida

    @property
    def n_conexiones(self) -> int:
        return sum(len(v[2]) for v in self.nodos.values())

    @property
    def n_ocultos(self) -> int:
        return len([n for n in self.nodos if n != self.salida and n not in self.entradas])

    def entradas_usadas(self) -> set[int]:
        usadas, pendientes = set(), [self.salida]
        while pendientes:
            n = pendientes.pop()
            for i, _ in self.nodos.get(n, (0, 0, []))[2]:
                if i in self.entradas:
                    usadas.add(i)
                elif i not in usadas:
                    pendientes.append(i)
        return usadas


@dataclass
class ConfigNEAT:
    """Hiperparámetros de la evolución. Los que no se nombran salen de config_neat.txt."""
    generaciones: int = 50
    poblacion: int = 60
    lam: float = 8e-4                   # penalización por complejidad (parsimonia)
    ocultos_iniciales: int = 0
    conexion_inicial: str = "full_direct"
    prob_agregar_conexion: float = 0.18
    prob_agregar_nodo: float = 0.12
    n_entradas: int = 7
    extra: dict = field(default_factory=dict)

    def archivo(self) -> Path:
        t = PLANTILLA_CFG.read_text(encoding="utf-8")
        cambios = {"num_inputs": self.n_entradas, "num_hidden": self.ocultos_iniciales, "pop_size": self.poblacion,
                   "initial_connection": self.conexion_inicial, "conn_add_prob": self.prob_agregar_conexion,
                   "node_add_prob": self.prob_agregar_nodo,
                   # con ocultos iniciales los genomas difieren más: umbral de especie mayor
                   "compatibility_threshold": 2.5 + 1.0 * self.ocultos_iniciales, **self.extra}
        for k, v in cambios.items():
            t = re.sub(rf"(?m)^{k}\s*=.*$", f"{k} = {v}", t)
        ruta = Path(tempfile.gettempdir()) / f"hefesto_neat_{abs(hash(t)) % 10**10}.txt"
        if not ruta.exists():
            ruta.write_text(t, encoding="utf-8")
        return ruta


class EvolucionNEAT:
    """Evoluciona una red con neat-python, evaluando cada genoma con RedMatricial (vectorizado)."""

    def __init__(self, cfg: ConfigNEAT, semilla: int = SEMILLA):
        self.cfg, self.semilla = cfg, semilla
        self.historia: list[float] = []
        self.estado = None

    def ejecutar(self, Xn: np.ndarray, y: np.ndarray, estado=None):
        random.seed(self.semilla)
        np.random.seed(self.semilla)
        if estado is None:
            config = neat.Config(neat.DefaultGenome, neat.DefaultReproduction, neat.DefaultSpeciesSet,
                                 neat.DefaultStagnation, str(self.cfg.archivo()))
            pop = neat.Population(config, seed=self.semilla)
        else:  # arranque en caliente: continúa la misma población (capacidad de mejora)
            config, poblacion, especies, gen = estado
            pop = neat.Population(config, initial_state=(poblacion, especies, gen), seed=self.semilla)
        lam = self.cfg.lam

        def evaluar(genomas, cfg):
            mejor = math.inf
            for _gid, g in genomas:
                red = RedMatricial(g, cfg)
                mse = float(np.mean((red(Xn) - y) ** 2))
                mejor = min(mejor, mse)
                g.fitness = -mse - lam * (red.n_ocultos + 0.15 * red.n_conexiones)
            self.historia.append(math.sqrt(mejor))

        ganador = pop.run(evaluar, self.cfg.generaciones)
        self.estado = (config, pop.population, pop.species, pop.generation)
        return RedMatricial(ganador, config)


class NEATConjunto(Modelo):
    """K redes NEAT evolucionadas con semillas distintas y promediadas (K = 1: una sola red)."""
    familia = "neuroevolución"

    def __init__(self, nombre="NEAT", K=1, cfg: ConfigNEAT | None = None):
        self.nombre, self.K, self.cfg = nombre, K, cfg or ConfigNEAT()
        self.redes: list[RedMatricial] = []
        self._estados = []

    def ajustar(self, X, y, grupos=None, continuar: bool = False):
        Xn = normalizar7(np.asarray(X, float))
        nuevas, estados = [], []
        for k in range(self.K):
            ev = EvolucionNEAT(self.cfg, SEMILLA + k)
            prev = self._estados[k] if continuar and self._estados else None
            nuevas.append(ev.ejecutar(Xn, np.asarray(y, float), prev))
            estados.append(ev.estado)
        self.redes, self._estados = nuevas, estados
        return self

    def _predecir_n(self, Xn):
        return np.mean([r(Xn) for r in self.redes], axis=0)

    def complejidad(self):
        return {"redes": len(self.redes), "ocultos": int(sum(r.n_ocultos for r in self.redes)),
                "conexiones": int(sum(r.n_conexiones for r in self.redes))}

    def variables_usadas(self):
        usadas = set().union(*(r.entradas_usadas() for r in self.redes)) if self.redes else set()
        return [VARS_R[-k - 1] for k in sorted(usadas, reverse=True)]


# ============================================================================ referencias
class _Sklearn(Modelo):
    def __init__(self, nombre, estimador, familia):
        self.nombre, self.est, self.familia = nombre, estimador, familia

    def ajustar(self, X, y, grupos=None):
        self.est.fit(normalizar7(np.asarray(X, float)), y)
        return self

    def _predecir_n(self, Xn):
        return self.est.predict(Xn)


class PerceptronMLP(_Sklearn):
    """Red neuronal clásica entrenada por retropropagación (Adam), con parada temprana."""

    def __init__(self, capas=(16,)):
        super().__init__(f"MLP {'x'.join(map(str, capas))}",
                         MLPRegressor(hidden_layer_sizes=capas, activation="tanh", alpha=1e-3, max_iter=2000,
                                      early_stopping=True, random_state=SEMILLA), "red neuronal (gradiente)")

    def complejidad(self):
        return {"parametros": int(sum(w.size for w in self.est.coefs_) + sum(b.size for b in self.est.intercepts_))}


class BosqueAleatorio(_Sklearn):
    def __init__(self):
        super().__init__("Random Forest", RandomForestRegressor(n_estimators=300, min_samples_leaf=3,
                                                                random_state=SEMILLA, n_jobs=1), "árboles")

    def complejidad(self):
        return {"hojas": int(sum(e.tree_.n_leaves for e in self.est.estimators_))}


class RegresionRidge(_Sklearn):
    def __init__(self):
        super().__init__("Ridge", Ridge(alpha=1.0), "lineal")

    def complejidad(self):
        return {"parametros": 8}


class XGBoostModelo(_Sklearn):
    def __init__(self):
        from xgboost import XGBRegressor
        super().__init__("XGBoost", XGBRegressor(n_estimators=300, max_depth=4, learning_rate=0.05,
                                                 subsample=0.8, random_state=SEMILLA, n_jobs=1), "árboles")

    def complejidad(self):
        return {"arboles": 300}


class ConjuntoXGBNEAT(Modelo):
    """Mezcla 50/50 de XGBoost y una red NEAT (era el modelo de cierre del Atlas)."""
    nombre, familia = "XGBoost + NEAT", "mixto"

    def __init__(self):
        self.xgb, self.neat = XGBoostModelo(), NEATConjunto("NEAT", 1)

    def ajustar(self, X, y, grupos=None):
        self.xgb.ajustar(X, y)
        self.neat.ajustar(X, y)
        return self

    def _predecir_n(self, Xn):
        return 0.5 * self.xgb._predecir_n(Xn) + 0.5 * self.neat._predecir_n(Xn)

    def complejidad(self):
        return {**self.neat.complejidad(), "arboles": 300}


class HibridoH3(Modelo):
    """Base NEAT (otro laboratorio) + corrección local con peso n/(n + k) (n = grupos locales)."""
    familia = "híbrido"

    def __init__(self, base: NEATConjunto | None = None, k_contraccion: int = 10):
        self.base = base or NEATConjunto("NEAT ×5", K=5)
        self.nombre = f"H3 ({self.base.nombre} + RF)"
        self.k, self.rf, self.n_local = k_contraccion, None, 0

    def ajustar(self, X, y, grupos=None):
        self.base.ajustar(X, y)
        self.rf, self.n_local = None, 0
        return self

    def calibrar(self, X_loc, y_loc, g_loc):
        Xn = normalizar7(np.asarray(X_loc, float))
        self.n_local = len(np.unique(g_loc))
        self.rf = RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=SEMILLA, n_jobs=1).fit(
            Xn, np.asarray(y_loc) - self.base._predecir_n(Xn))
        return self

    def _predecir_n(self, Xn):
        b = self.base._predecir_n(Xn)
        if self.rf is None:
            return b
        return b + self.n_local / (self.n_local + self.k) * self.rf.predict(Xn)

    def complejidad(self):
        return {**self.base.complejidad(), "hojas_correccion": int(sum(e.tree_.n_leaves for e in self.rf.estimators_))
                if self.rf else 0}

    def variables_usadas(self):
        return self.base.variables_usadas()


# ============================================================================ catálogo
def candidatos(rapido: bool = False) -> list[Modelo]:
    """Los modelos que compite el banco. En modo rápido, menos generaciones y redes."""
    base = ConfigNEAT(generaciones=8 if rapido else 50)                       # configuración actual
    larga = replace(base, generaciones=8 if rapido else 200, poblacion=60 if rapido else 150)
    K = 2 if rapido else 5
    return [
        NEATConjunto("NEAT 1 red (clásico)", 1, base),
        NEATConjunto("NEAT ×5 (motor actual)", K, base),
        NEATConjunto("NEAT ×5 evolución larga", K, larga),
        NEATConjunto("NEAT capa oculta", 1, replace(larga, ocultos_iniciales=4, conexion_inicial="full_nodirect",
                                                    lam=1e-4, prob_agregar_conexion=0.3)),
        NEATConjunto("NEAT ×5 capa oculta", K, replace(larga, ocultos_iniciales=4, conexion_inicial="full_nodirect",
                                                       lam=1e-4, prob_agregar_conexion=0.3)),
        NEATConjunto("NEAT poca parsimonia", 1, replace(larga, lam=1e-5, prob_agregar_nodo=0.2)),
        HibridoH3(NEATConjunto("NEAT ×5", K, base)),
        PerceptronMLP((16,)),
        PerceptronMLP((32, 16)),
        BosqueAleatorio(),
        XGBoostModelo(),
        ConjuntoXGBNEAT(),
        RegresionRidge(),
    ]


def cronometrar(f, *a, **k):
    t = time.perf_counter()
    r = f(*a, **k)
    return r, time.perf_counter() - t
