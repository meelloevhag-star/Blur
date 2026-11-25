"""Registro común de las fuentes que recoge Blur: biocrete_neat/datos/territorio/registro.json.

Cada fuente se guarda bajo una clave ("clima", "relieve", "poblacion", "geo", "gis:osm", …) con su
estado. Una corrida **reemplaza** la entrada completa de su fuente, así no quedan errores viejos
mezclados con capas que después sí se descargaron.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]          # raíz del repo Blur
DIR = RAIZ / "biocrete_neat" / "datos" / "territorio"
RUTA = DIR / "registro.json"


def ahora() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def huella(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


class Registro:
    def __init__(self, ruta: Path = RUTA):
        self.ruta = ruta
        self.datos: dict = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}

    def reemplazar(self, fuente: str, entrada: dict) -> None:
        """Sustituye todo lo que había de `fuente` por `entrada`. La fecha solo cambia si cambió el contenido,
        así una corrida sin novedades no dispara un re-cálculo del Atlas."""
        previo = self.datos.get(fuente, {})
        sin_fecha = {k: v for k, v in previo.items() if k != "_fecha"}
        fecha = previo.get("_fecha") if sin_fecha == entrada and "_fecha" in previo else ahora()
        self.datos[fuente] = entrada | {"_fecha": fecha}

    def guardar(self) -> None:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.ruta.write_text(json.dumps(dict(sorted(self.datos.items())), ensure_ascii=False, indent=2), encoding="utf-8")

    def resumen(self) -> list[str]:
        out = []
        for f, e in sorted(self.datos.items()):
            capas = {k: v for k, v in e.items() if isinstance(v, dict)} if f.startswith("gis:") else {}
            if capas:
                ok = sum(1 for v in capas.values() if v.get("estado") == "ok")
                out.append(f"{f}: {ok}/{len(capas)} capas ok")
            else:
                out.append(f"{f}: {e.get('estado', '?')} {e.get('detalle', '')}".rstrip())
        return out
