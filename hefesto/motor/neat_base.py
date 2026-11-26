"""NEAT reanudable (arranque en caliente) con penalización de parsimonia.

Copiado de meelloevhag-star/Blur (commit bf6000d), biocrete_neat/aprendizaje_continuo.py. No editar sin actualizar la procedencia.
"""

import math
import pickle
import random
import re
from pathlib import Path

import neat
import numpy as np

RUTA_CFG = Path(__file__).resolve().parent / "config_neat.txt"
LAMBDA_PARSIMONIA_ALTA = 8e-4


def evolucionar(X, y, gens, semilla, estado=None, lam=LAMBDA_PARSIMONIA_ALTA, ruta_cfg=RUTA_CFG):
    """Evoluciona NEAT; si `estado` = (config, población, especies, generación) continúa desde ahí."""
    random.seed(semilla)
    np.random.seed(semilla)
    if estado is None:
        config = neat.Config(neat.DefaultGenome, neat.DefaultReproduction, neat.DefaultSpeciesSet,
                             neat.DefaultStagnation, str(ruta_cfg))
        pop = neat.Population(config, seed=semilla)
    else:
        config, poblacion, especies, generacion = pickle.loads(pickle.dumps(estado))  # copia independiente
        rastreador = getattr(config.genome_config, "innovation_tracker", None)
        pop = neat.Population(config, initial_state=(poblacion, especies, generacion), seed=semilla)
        if rastreador is not None:
            # DefaultReproduction crea un rastreador nuevo; se restaura el guardado para que los
            # números de innovación continúen (igual que neat.Checkpointer.restore_checkpoint).
            pop.reproduction.innovation_tracker = rastreador
            config.genome_config.innovation_tracker = rastreador
    historia = []

    def evaluar(genomas, cfg):
        mejor = 1e9
        for _gid, g in genomas:
            red = neat.nn.FeedForwardNetwork.create(g, cfg)
            p = np.array([red.activate(x)[0] for x in X])
            mse = float(np.mean((p - y) ** 2))
            mejor = min(mejor, mse)
            n_oc = len([n for n in g.nodes if n >= cfg.genome_config.num_outputs])
            n_cx = sum(1 for c in g.connections.values() if c.enabled)
            g.fitness = -mse - lam * (n_oc + 0.15 * n_cx)
        historia.append(math.sqrt(mejor))

    ganador = pop.run(evaluar, gens)
    red = neat.nn.FeedForwardNetwork.create(ganador, config)
    return ganador, red, (config, pop.population, pop.species, pop.generation), historia


def ruta_config(n_entradas: int) -> Path:
    """Config NEAT idéntica a la base salvo el número de entradas."""
    if n_entradas == 6:
        return RUTA_CFG
    destino = RUTA_CFG.parent / f"config_neat_{n_entradas}.txt"
    texto = re.sub(r"num_inputs\s*=\s*\d+", f"num_inputs              = {n_entradas}",
                   RUTA_CFG.read_text(encoding="utf-8"))
    if not destino.exists() or destino.read_text(encoding="utf-8") != texto:
        destino.write_text(texto, encoding="utf-8")
    return destino
