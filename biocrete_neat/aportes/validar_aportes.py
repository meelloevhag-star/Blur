"""
Componente 1 · Entrada abierta de datos de terceros (tesis, laboratorios, artículos).

Valida los CSV de aportes (formato de plantilla_aportes.csv) y convierte las filas aceptadas al
esquema de réplicas de cierre de fisuras, con trazabilidad completa. Las filas rechazadas se
reportan con su motivo; nunca se corrigen ni imputan valores automáticamente.

Uso:
    python -m biocrete_neat.aportes.validar_aportes aportes/recibidos/*.csv
Salidas:
    datos/aportes_validados.csv   (filas aceptadas, esquema de réplicas)
    aportes/reporte_validacion.md (aceptadas / rechazadas con motivo)
"""

import csv
import sys
from pathlib import Path

RUTA_BASE = Path(__file__).resolve().parents[1]
SALIDA = RUTA_BASE / "datos" / "aportes_validados.csv"
REPORTE = RUTA_BASE / "aportes" / "reporte_validacion.md"

OBLIGATORIOS = ["autor_aporte", "institucion", "tipo_fuente", "doi_o_url", "norma_ensayo", "id_probeta",
                "nivel_proteccion", "ambiente_marino", "w0_mm", "edad_dias"]
TIPOS_FUENTE = {"tesis", "articulo", "laboratorio", "dataset"}
RANGOS = {"w0_mm": (0.0, 2.0), "edad_dias": (0.0, 1000.0), "wt_mm": (0.0, 3.0), "cierre_pct": (0.0, 100.0),
          "a_c": (0.2, 0.9)}
BINARIOS = ["ambiente_marino", "usa_lactato", "curado_previo"]
TOLERANCIA_CIERRE = 2.0  # puntos %, si se dan wt_mm y cierre_pct a la vez

CAMPOS_SALIDA = [
    "fuente", "doi", "hoja", "fila_excel", "etiqueta_original", "grupo_condicion", "grupo_probeta",
    "portador", "nivel_proteccion", "tiene_bacterias", "nutriente", "concentracion_mM", "usa_lactato",
    "ambiente_marino", "regimen", "ubicacion", "w0_mm", "edad_dias", "wt_mm", "cierre_pct",
]


def _num(v):
    try:
        return float(str(v).replace(",", ".")) if str(v).strip() != "" else None
    except ValueError:
        return "error"


def validar_fila(f: dict) -> tuple[dict | None, list[str]]:
    """Devuelve (fila_normalizada | None, motivos_de_rechazo)."""
    motivos = []
    for c in OBLIGATORIOS:
        if not str(f.get(c, "")).strip():
            motivos.append(f"falta '{c}'")
    if str(f.get("tipo_fuente", "")).strip().lower() not in TIPOS_FUENTE:
        motivos.append(f"tipo_fuente debe ser uno de {sorted(TIPOS_FUENTE)}")
    url = str(f.get("doi_o_url", "")).strip()
    if url and not (url.startswith("10.") or url.startswith("http")):
        motivos.append("doi_o_url debe ser un DOI (10.xxx) o un enlace http(s)")
    if "ejemplo" in str(f.get("notas", "")).lower() or "ejemplo" in str(f.get("autor_aporte", "")).lower():
        motivos.append("fila de ejemplo de la plantilla")

    v = {c: _num(f.get(c, "")) for c in ["a_c", "nivel_proteccion", "w0_mm", "edad_dias", "wt_mm", "cierre_pct",
                                         *BINARIOS]}
    for c, val in v.items():
        if val == "error":
            motivos.append(f"'{c}' no es numérico")
    if motivos:
        return None, motivos

    for c, (lo, hi) in RANGOS.items():
        if v[c] is not None and not lo <= v[c] <= hi:
            motivos.append(f"'{c}'={v[c]} fuera de rango [{lo}, {hi}]")
    if v["w0_mm"] is not None and v["w0_mm"] <= 0:
        motivos.append("w0_mm debe ser > 0")
    if v["nivel_proteccion"] not in (0.0, 1.0, 2.0, 3.0):
        motivos.append("nivel_proteccion debe ser 0, 1, 2 o 3")
    for c in BINARIOS:
        if v[c] is not None and v[c] not in (0.0, 1.0):
            motivos.append(f"'{c}' debe ser 0 o 1")
    if v["wt_mm"] is None and v["cierre_pct"] is None:
        motivos.append("se requiere wt_mm o cierre_pct")
    if motivos:
        return None, motivos

    cierre_calc = None
    if v["wt_mm"] is not None:
        cierre_calc = max(0.0, min(100.0, (v["w0_mm"] - v["wt_mm"]) / v["w0_mm"] * 100.0))
    if v["cierre_pct"] is not None and cierre_calc is not None and abs(cierre_calc - v["cierre_pct"]) > TOLERANCIA_CIERRE:
        return None, [f"cierre_pct={v['cierre_pct']} no coincide con w0/wt ({cierre_calc:.1f})"]
    cierre = v["cierre_pct"] if v["cierre_pct"] is not None else cierre_calc

    autor = str(f["autor_aporte"]).strip()
    nivel = int(v["nivel_proteccion"])
    fila = {
        "fuente": f"aporte:{autor}", "doi": url, "hoja": str(f.get("tipo_fuente", "")).strip().lower(),
        "fila_excel": "", "etiqueta_original": str(f.get("notas", "")).strip()[:120],
        "grupo_condicion": f"aporte:{autor}|n{nivel}|m{int(v['ambiente_marino'])}",
        "grupo_probeta": f"aporte:{autor}|{str(f['id_probeta']).strip()}",
        "portador": "", "nivel_proteccion": nivel, "tiene_bacterias": int(nivel > 0), "nutriente": "",
        "concentracion_mM": "", "usa_lactato": int(v["usa_lactato"] or 0),
        "ambiente_marino": int(v["ambiente_marino"]),
        "regimen": "curado_previo" if v["curado_previo"] == 1.0 else "",
        "ubicacion": str(f.get("norma_ensayo", "")).strip(),
        "w0_mm": v["w0_mm"], "edad_dias": v["edad_dias"],
        "wt_mm": v["wt_mm"] if v["wt_mm"] is not None else "", "cierre_pct": round(cierre, 2),
    }
    return fila, []


def validar_archivos(rutas: list[Path]) -> tuple[list[dict], list[dict]]:
    aceptadas, rechazadas, vistas = [], [], set()
    for ruta in rutas:
        with open(ruta, encoding="utf-8-sig", newline="") as fh:
            for i, f in enumerate(csv.DictReader(fh), 2):
                fila, motivos = validar_fila(f)
                if fila:
                    clave = (fila["grupo_probeta"], fila["edad_dias"])
                    if clave in vistas:
                        fila, motivos = None, ["duplicado (misma probeta y edad)"]
                    else:
                        vistas.add(clave)
                if fila:
                    aceptadas.append(fila)
                else:
                    rechazadas.append({"archivo": ruta.name, "linea": i, "motivos": "; ".join(motivos)})
    return aceptadas, rechazadas


def main(argv: list[str]) -> int:
    rutas = [Path(a) for a in argv]
    aceptadas, rechazadas = validar_archivos(rutas)
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(SALIDA, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS_SALIDA)
        w.writeheader()
        w.writerows(aceptadas)
    lineas = ["# Reporte de validación de aportes", "",
              f"Archivos: {', '.join(r.name for r in rutas) or '—'}", "",
              f"Aceptadas: **{len(aceptadas)}** · Rechazadas: **{len(rechazadas)}**", ""]
    if rechazadas:
        lineas += ["| Archivo | Línea | Motivos |", "|---|---|---|"]
        lineas += [f"| {r['archivo']} | {r['linea']} | {r['motivos']} |" for r in rechazadas]
    REPORTE.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"Aceptadas {len(aceptadas)} · Rechazadas {len(rechazadas)} -> {SALIDA}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
