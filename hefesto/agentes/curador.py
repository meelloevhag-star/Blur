"""
Agente curador: valida los CSV entrantes contra esquema/esquema_datos.json y reglas de coherencia.

    datos/entrantes/*.csv  →  datos/aceptados/<archivo>  +  datos/rechazados/<archivo> (con motivo)
                              + datos/reporte_curador.md

Reglas además del esquema: duplicados (fuente, grupo, edad, ancho, cierre, α, protección) y
coherencia entre nivel de protección y bacteria declarada. Nunca corrige ni imputa valores.

Uso:
    python -m hefesto.agentes.curador
"""

import csv
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

RAIZ = Path(__file__).resolve().parents[2]
ESQUEMA = json.loads((RAIZ / "hefesto" / "esquema" / "esquema_datos.json").read_text(encoding="utf-8"))
VALIDADOR = Draft202012Validator(ESQUEMA)
TIPOS = {k: v.get("type") for k, v in ESQUEMA["properties"].items()}
ENTRANTES, ACEPTADOS, RECHAZADOS = (RAIZ / "datos" / d for d in ("entrantes", "aceptados", "rechazados"))


def tipar(fila: dict) -> tuple[dict, list[str]]:
    """Convierte texto a los tipos del esquema; los vacíos se omiten (no reportado)."""
    salida, errores = {}, []
    for k, v in fila.items():
        v = (v or "").strip()
        if v == "" or k.startswith("_"):
            continue
        if k not in TIPOS:
            errores.append(f"campo desconocido '{k}'")
            continue
        try:
            if TIPOS[k] == "number":
                salida[k] = float(v.replace(",", "."))
            elif TIPOS[k] == "integer":
                salida[k] = int(float(v))
            else:
                salida[k] = v
        except ValueError:
            errores.append(f"'{k}' no es {TIPOS[k]}: {v!r}")
    return salida, errores


def validar_fila(fila: dict) -> tuple[dict | None, list[str]]:
    registro, errores = tipar(fila)
    errores += [f"{'/'.join(map(str, e.path)) or 'fila'}: {e.message}" for e in VALIDADOR.iter_errors(registro)]
    if not errores and registro.get("mezcla_nivel_proteccion", 0) == 0 and registro.get("mezcla_bacteria_especie"):
        errores.append("nivel de protección 0 (sin bacterias) pero se declara una especie bacteriana")
    return (None, errores) if errores else (registro, [])


def curar_archivo(ruta: Path, vistos: set) -> tuple[list[dict], list[dict]]:
    aceptadas, rechazadas = [], []
    with open(ruta, encoding="utf-8-sig", newline="") as fh:
        for i, fila in enumerate(csv.DictReader(fh), 2):
            reg, errores = validar_fila(fila)
            if reg is not None:
                clave = tuple(reg.get(k) for k in ("fuente", "id_grupo", "resultado_edad_dias", "dano_ancho_fisura_mm",
                                                   "resultado_cierre_pct", "resultado_alpha", "mezcla_nivel_proteccion"))
                if clave in vistos:
                    reg, errores = None, ["duplicado"]
                else:
                    vistos.add(clave)
            if reg is not None:
                aceptadas.append(fila)
            else:
                rechazadas.append({**fila, "_linea": i, "_motivos": "; ".join(errores)})
    return aceptadas, rechazadas


def _guardar(carpeta: Path, nombre: str, filas: list[dict]):
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / nombre
    if filas:
        with open(destino, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(filas[0]))
            w.writeheader()
            w.writerows(filas)
    elif destino.exists():
        destino.unlink()


def main() -> int:
    vistos: set = set()
    lineas = ["# Reporte del agente curador", "", "| Archivo | Aceptadas | Rechazadas | Motivo más frecuente |",
              "|---|---|---|---|"]
    for ruta in sorted(ENTRANTES.glob("*.csv")):
        acep, rech = curar_archivo(ruta, vistos)
        _guardar(ACEPTADOS, ruta.name, acep)
        _guardar(RECHAZADOS, ruta.name, rech)
        motivos: dict = {}
        for r in rech:
            for m in r["_motivos"].split("; "):
                motivos[m.split(":")[0]] = motivos.get(m.split(":")[0], 0) + 1
        top = max(motivos, key=motivos.get) if motivos else "—"
        lineas.append(f"| {ruta.name} | {len(acep)} | {len(rech)} | {top} |")
        print(f"{ruta.name}: aceptadas {len(acep)} · rechazadas {len(rech)} · {top}")
    (RAIZ / "datos" / "reporte_curador.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
