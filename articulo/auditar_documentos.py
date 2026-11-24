"""
F6 · Auditoría de coherencia interna de los artículos generados.

Comprueba en cada .docx:
  - que toda cita [n] (incluidos rangos [a]–[b]) tenga su referencia, y que toda referencia se cite;
  - que las figuras y tablas estén numeradas de forma consecutiva y se mencionen en el texto;
  - que no queden marcadores de la versión anterior (p. ej. "0,540" fuera del contexto de corrección);
  - los avisos pendientes de confirmar por los autores ("[Confirmar" / "[Confirm").

Uso:
    python articulo/auditar_documentos.py
Salida:
    articulo/auditoria_documentos.md (código de salida 1 si hay errores)
"""

import re
import sys
from pathlib import Path

import docx

RAIZ = Path(__file__).resolve().parents[1]
DOCUMENTOS = [
    RAIZ / "articulo" / "ieee" / "BioCrete-NEAT_IEEE_v2.docx",
    RAIZ / "articulo" / "revista" / "BioCrete-NEAT_revista_ES.docx",
    RAIZ / "articulo" / "revista" / "BioCrete-NEAT_revista_EN.docx",
]
PATRON_REF = re.compile(r"^\[(\d+)\][\t ]")
PATRON_CITA = re.compile(r"\[(\d+)\](?:\s*[–-]\s*\[(\d+)\])?")


def _texto(doc) -> tuple[list[str], list[str]]:
    cuerpo, refs = [], []
    for p in doc.paragraphs:
        (refs if PATRON_REF.match(p.text) else cuerpo).append(p.text)
    for t in doc.tables:
        for fila in t.rows:
            for c in fila.cells:
                cuerpo.append(c.text)
    return cuerpo, refs


def auditar(ruta: Path) -> tuple[list[str], list[str]]:
    doc = docx.Document(str(ruta))
    cuerpo, refs = _texto(doc)
    texto = "\n".join(cuerpo)
    errores, avisos = [], []

    numeros_ref = [int(PATRON_REF.match(r).group(1)) for r in refs]
    if numeros_ref != list(range(1, len(numeros_ref) + 1)):
        errores.append(f"referencias no consecutivas: {numeros_ref}")
    citadas = set()
    for a, b in PATRON_CITA.findall(texto):
        ini = int(a)
        fin = int(b) if b else ini
        citadas.update(range(ini, fin + 1))
    faltan = sorted(n for n in citadas if n not in numeros_ref)
    sin_citar = sorted(n for n in numeros_ref if n not in citadas)
    if faltan:
        errores.append(f"citas sin referencia: {faltan}")
    if sin_citar:
        errores.append(f"referencias nunca citadas: {sin_citar}")

    for etiqueta, patron_titulo, patron_mencion in [
        ("figura", r"^Fig\. (\d+)\.", r"Figs?\. (\d+)"),
        ("tabla", r"^(?:TABLA|Tabla|Table) ([IVX\d]+)\.", r"(?:Tabla|Table|TABLA) ([IVX\d]+)"),
    ]:
        titulos = [m.group(1) for p in cuerpo if (m := re.match(patron_titulo, p.strip()))]
        romanos = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8}
        nums = [int(t) if t.isdigit() else romanos.get(t, -1) for t in titulos]
        if nums != list(range(1, len(nums) + 1)):
            errores.append(f"{etiqueta}s no consecutivas: {titulos}")
        menciones = {m for p in cuerpo if not re.match(patron_titulo, p.strip())
                     for m in re.findall(patron_mencion, p)}
        no_mencionadas = [t for t in titulos if t not in menciones]
        if no_mencionadas:
            errores.append(f"{etiqueta}s nunca mencionadas en el texto: {no_mencionadas}")

    for p in cuerpo:
        if ("0,540" in p or "0.540" in p) and not re.search(r"previ|row-wise|por fila|KFold|anterior", p):
            errores.append(f"cifra de la versión anterior fuera de contexto: «{p[:90]}…»")
    pendientes = [p[:80] for p in cuerpo if "[Confirm" in p or "[Ajustar" in p or "[Adapt" in p or "[Los autores" in p
                  or "[Authors" in p]
    if pendientes:
        avisos.append(f"{len(pendientes)} declaraciones pendientes de confirmar por los autores")
    return errores, avisos


def main() -> int:
    lineas = ["# Auditoría de coherencia de los documentos", ""]
    total = 0
    for ruta in DOCUMENTOS:
        errores, avisos = auditar(ruta)
        total += len(errores)
        lineas.append(f"## {ruta.name}")
        lineas += [f"- ERROR: {e}" for e in errores] or ["- Sin errores de coherencia."]
        lineas += [f"- Aviso: {a}" for a in avisos]
        lineas.append("")
        print(ruta.name, "errores:", len(errores), errores, avisos)
    (RAIZ / "articulo" / "auditoria_documentos.md").write_text("\n".join(lineas), encoding="utf-8")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
