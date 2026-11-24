"""
Componentes 3 y 4 · Neuroevolución incremental con control de calidad y registro de versiones.

Flujo cuando llegan datos nuevos:
  1. El modelo vigente (campeón) predice los grupos nuevos sin haberlos visto (validación prospectiva).
  2. El candidato parte de la POBLACIÓN NEAT guardada de la versión anterior (arranque en caliente)
     y sigue evolucionando con los datos acumulados. Se evalúa con GroupKFold sobre los grupos
     nuevos: cada partición de prueba queda fuera de su entrenamiento.
  3. Como referencia se entrena también desde cero (arranque en frío) con las mismas generaciones.
  4. El candidato se acepta solo si iguala o supera al campeón en los datos nuevos. Si se acepta,
     se re-entrena en caliente con todos los datos y se guarda como nueva versión.

Uso:
    python -m biocrete_neat.aprendizaje_continuo --demo   # simula la llegada por lotes y genera la fig. 7
    python -m biocrete_neat.aprendizaje_continuo          # actualiza con réplicas + aportes validados
"""

import argparse
import datetime as dt
import hashlib
import json
import math
import pickle
import random
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import neat
import numpy as np
from sklearn.metrics import r2_score
from sklearn.model_selection import GroupKFold

from biocrete_neat.entrenar_neat import LAMBDA_PARSIMONIA_ALTA, RUTA_CFG
from biocrete_neat.modelos_ampliados import cargar_replicas, normalizar_replicas

RUTA_BASE = Path(__file__).resolve().parent
DIR_MODELOS = RUTA_BASE / "modelos"
RUTA_APORTES = RUTA_BASE / "datos" / "aportes_validados.csv"


# ---------------------------------------------------------------------------
# NEAT con estado reanudable
# ---------------------------------------------------------------------------

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


def _predecir(red, X):
    return np.array([red.activate(x)[0] for x in X])


# ---------------------------------------------------------------------------
# Registro de versiones
# ---------------------------------------------------------------------------

class Registro:
    def __init__(self, carpeta: Path):
        self.carpeta = carpeta
        self.ruta = carpeta / "registro_versiones.json"
        self.versiones = json.loads(self.ruta.read_text(encoding="utf-8")) if self.ruta.exists() else []

    def campeon(self):
        aceptadas = [v for v in self.versiones if v["aceptado"]]
        if not aceptadas:
            return None
        with open(self.carpeta / aceptadas[-1]["archivo_estado"], "rb") as f:
            return pickle.load(f)

    def guardar(self, entrada: dict, paquete: dict | None):
        self.carpeta.mkdir(parents=True, exist_ok=True)
        if paquete is not None:
            nombre = f"version_{entrada['version']:03d}.pkl"
            with open(self.carpeta / nombre, "wb") as f:
                pickle.dump(paquete, f)
            entrada["archivo_estado"] = nombre
        self.versiones.append(entrada)
        self.ruta.write_text(json.dumps(self.versiones, ensure_ascii=False, indent=2), encoding="utf-8")


def _huella(X, y) -> str:
    return hashlib.sha256(np.ascontiguousarray(np.c_[X, y]).tobytes()).hexdigest()[:16]


def actualizar(registro: Registro, X, y, grupos, es_nuevo, etiqueta: str, gens=40, semilla=2026) -> dict:
    """Ejecuta un ciclo campeón/candidato con los datos acumulados (X, y) y la máscara de filas nuevas."""
    campeon = registro.campeon()
    idx_nuevos = np.flatnonzero(es_nuevo)
    nuevos_g = np.unique(grupos[idx_nuevos])
    n_splits = min(5, len(nuevos_g))
    p_cand = np.zeros(len(idx_nuevos))
    p_frio = np.zeros(len(idx_nuevos))
    estado_previo = campeon["estado"] if campeon else None

    for k, (_, te_rel) in enumerate(GroupKFold(n_splits=n_splits).split(idx_nuevos, groups=grupos[idx_nuevos])):
        te = idx_nuevos[te_rel]
        tr = np.setdiff1d(np.arange(len(y)), te)
        _, red_c, _, _ = evolucionar(X[tr], y[tr], gens, semilla + k, estado=estado_previo)
        _, red_f, _, _ = evolucionar(X[tr], y[tr], gens, semilla + k, estado=None)
        p_cand[te_rel] = _predecir(red_c, X[te])
        p_frio[te_rel] = _predecir(red_f, X[te])

    y_new = y[idx_nuevos]
    r2_cand = float(r2_score(y_new, p_cand))
    r2_frio = float(r2_score(y_new, p_frio))
    r2_camp = float(r2_score(y_new, _predecir(campeon["red"], X[idx_nuevos]))) if campeon else None
    aceptado = r2_camp is None or r2_cand >= r2_camp

    paquete = None
    hist_final = []
    if aceptado:
        ganador, red, estado, hist_final = evolucionar(X, y, gens, semilla, estado=estado_previo)
        paquete = {"estado": estado, "red": red, "genoma": ganador}

    entrada = {
        "version": len(registro.versiones) + 1,
        "fecha": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "lote": etiqueta,
        "n_registros_total": int(len(y)), "n_registros_nuevos": int(len(idx_nuevos)),
        "n_grupos_nuevos": int(len(nuevos_g)), "huella_datos": _huella(X, y),
        "generaciones": gens, "lambda_parsimonia": LAMBDA_PARSIMONIA_ALTA,
        "r2_prospectivo": {"campeon_vigente": None if r2_camp is None else round(r2_camp, 3),
                           "candidato_caliente": round(r2_cand, 3), "referencia_frio": round(r2_frio, 3)},
        "aceptado": bool(aceptado),
        "rmse_final_entrenamiento": round(hist_final[-1], 4) if hist_final else None,
        "archivo_estado": None,
    }
    registro.guardar(entrada, paquete)
    return entrada


# ---------------------------------------------------------------------------
# Datos acumulados
# ---------------------------------------------------------------------------

def cargar_acumulado():
    """Réplicas extraídas + aportes validados (si existen), normalizados con límites físicos fijos."""
    X, y, g, f = cargar_replicas()
    if RUTA_APORTES.exists() and RUTA_APORTES.stat().st_size > 0:
        Xa, ya, ga, fa = cargar_replicas(RUTA_APORTES)
        if len(ya):
            X, y, g, f = np.r_[X, Xa], np.r_[y, ya], np.r_[g, ga], np.r_[f, fa]
    return normalizar_replicas(X), y, g, f


def lotes_demo(fuentes, grupos):
    """Llegada simulada: Mousa → Cappellesso con curado previo → Cappellesso exposición directa."""
    cap = fuentes == "Cappellesso2024"
    curado = np.array(["h100" in s or "h300" in s for s in grupos.astype(str)])
    return [("v1 · Mousa 2022 (subtropical)", fuentes == "Mousa2022"),
            ("v2 · + Cappellesso marino, curado previo", cap & curado),
            ("v3 · + Cappellesso marino, exposición directa", cap & ~curado)]


def demo(gens=40) -> list[dict]:
    X, y, g, f = cargar_acumulado()
    registro = Registro(DIR_MODELOS / "demo_flujo")
    for p in registro.carpeta.glob("*") if registro.carpeta.exists() else []:
        p.unlink()
    registro.versiones = []
    acumulado = np.zeros(len(y), dtype=bool)
    salida = []
    for etiqueta, mascara in lotes_demo(f, g):
        nuevo = mascara & ~acumulado
        acumulado |= mascara
        idx = np.flatnonzero(acumulado)
        e = actualizar(registro, X[idx], y[idx], g[idx], nuevo[idx], etiqueta, gens=gens)
        print(json.dumps(e, ensure_ascii=False), flush=True)
        salida.append(e)
    figura_flujo(salida, RUTA_BASE / "resultados" / "f3" / "fig7_aprendizaje_continuo.png")
    return salida


def figura_flujo(entradas, ruta: Path):
    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(len(entradas))
    camp = [e["r2_prospectivo"]["campeon_vigente"] for e in entradas]
    cand = [e["r2_prospectivo"]["candidato_caliente"] for e in entradas]
    frio = [e["r2_prospectivo"]["referencia_frio"] for e in entradas]
    w = 0.27
    ax.bar(x - w, [c if c is not None else 0 for c in camp], w, label="Campeón vigente (sin re-entrenar)",
           color="#94a3b8")
    ax.bar(x, cand, w, label="Candidato NEAT incremental (caliente)", color="#0f766e")
    ax.bar(x + w, frio, w, label="NEAT desde cero (frío)", color="#d97706")
    for i, e in enumerate(entradas):
        ax.text(i, max(cand[i], frio[i], camp[i] or 0) + 0.02, "aceptado" if e["aceptado"] else "rechazado",
                ha="center", fontsize=8)
    ax.set_xticks(x, [e["lote"].split(" · ")[0] + f"\n(+{e['n_registros_nuevos']})" for e in entradas])
    ax.axhline(0, color="k", lw=0.8)
    ax.set_ylabel("R² prospectivo en los datos nuevos")
    ax.set_title("Aprendizaje continuo: validación prospectiva por lote", fontsize=10)
    ax.legend(fontsize=7)
    fig.tight_layout()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta, dpi=220)
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--generaciones", type=int, default=40)
    args = ap.parse_args(argv)
    if args.demo:
        demo(args.generaciones)
        return 0
    X, y, g, f = cargar_acumulado()
    registro = Registro(DIR_MODELOS / "produccion")
    vistos = set()
    for v in registro.versiones:
        vistos |= set(v.get("grupos", []))
    nuevo = ~np.isin(g, list(vistos))
    if not nuevo.any():
        print("Sin datos nuevos: el campeón vigente se mantiene.")
        return 0
    e = actualizar(registro, X, y, g, nuevo, f"actualización {dt.date.today().isoformat()}", gens=args.generaciones)
    registro.versiones[-1]["grupos"] = sorted(set(g.tolist()))
    registro.ruta.write_text(json.dumps(registro.versiones, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(e, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
