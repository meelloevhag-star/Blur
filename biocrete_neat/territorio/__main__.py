"""python -m biocrete_neat.territorio [geo|clima|relieve|poblacion|gis|todo ...] [--solo ingemmet osm] [--forzar]

Solo descarga lo que falta (salvo --forzar) y deja todo anotado en biocrete_neat/datos/territorio/registro.json.
"""
from __future__ import annotations

import argparse
import sys

ORDEN = ["geo", "clima", "relieve", "poblacion", "gis"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m biocrete_neat.territorio")
    ap.add_argument("que", nargs="*", default=["todo"], choices=[*ORDEN, "todo"])
    ap.add_argument("--pais", default="PER")
    ap.add_argument("--solo", nargs="*", help="gis: fuentes a descargar (ingemmet, minam, osm)")
    ap.add_argument("--forzar", action="store_true")
    a = ap.parse_args(argv)
    pedidos = ORDEN if "todo" in a.que else [q for q in ORDEN if q in a.que]
    for q in pedidos:
        print(f"=== {q}", flush=True)
        if q == "geo":
            from biocrete_neat.territorio import geo
            geo.recolectar(a.pais, a.forzar)
        elif q == "clima":
            from biocrete_neat.territorio import clima
            clima.recolectar(a.pais)
        elif q == "relieve":
            from biocrete_neat.territorio import relieve
            relieve.recolectar(a.pais)
        elif q == "poblacion":
            from biocrete_neat.territorio import poblacion
            poblacion.recolectar(a.pais, a.forzar)
        elif q == "gis":
            from biocrete_neat.territorio import gis
            gis.recolectar(a.solo)
    from biocrete_neat.territorio.registro import Registro
    print("\n".join(Registro().resumen()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
