"""
Genera la versión IEEE (español) del artículo de auditoría sobre el .docx original.

Conserva título, autores, secciones y formato del original (estilos directos a dos columnas) y
reconstruye el cuerpo con los bloques de articulo/contenido.py. Todas las cifras provienen de
biocrete_neat/resultados/revision/resumen_revision.json.

Uso:
    python articulo/generar_articulo.py
Salida:
    articulo/ieee/BioCrete-NEAT_IEEE_v2.docx
"""

import copy
import json
from pathlib import Path

import docx
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from docx.oxml.ns import qn
from docx.shared import Inches
from docx.text.paragraph import Paragraph
from docx.text.run import Run

from contenido import RES, bloques, numerar_citas

RAIZ = Path(__file__).resolve().parents[1]
ORIGINAL = RAIZ / "articulo" / "original" / "BioCrete-NEAT_v1_original.docx"
SALIDA = RAIZ / "articulo" / "ieee" / "BioCrete-NEAT_IEEE_v2.docx"
ANCHO_COLUMNA_TWIPS = 4780  # (7,14 in − 0,5 in de separación) / 2 columnas ≈ 3,32 in


# ---------------------------------------------------------------------------
# Edición con conservación de formato
# ---------------------------------------------------------------------------

def poner(p: Paragraph, partes):
    """Reemplaza el texto de `p`. `partes` = str o [(texto, índice_de_run_plantilla), ...]."""
    if isinstance(partes, str):
        partes = [(partes, 0)]
    plant = [copy.deepcopy(r._r) for r in p.runs] or [p._p.makeelement(qn("w:r"), {})]
    for r in list(p.runs):
        r._r.getparent().remove(r._r)
    for texto, k in partes:
        nuevo = copy.deepcopy(plant[min(k, len(plant) - 1)])
        for hijo in list(nuevo):
            if hijo.tag != qn("w:rPr"):
                nuevo.remove(hijo)
        p._p.append(nuevo)
        Run(nuevo, p).text = texto


def buscar(doc, prefijo: str) -> Paragraph:
    for p in doc.paragraphs:
        if p.text.strip().startswith(prefijo):
            return p
    raise KeyError(prefijo)


def ajustar_ancho(tabla, proporciones, total=ANCHO_COLUMNA_TWIPS):
    anchos = [int(total * p / sum(proporciones)) for p in proporciones]
    tblPr = tabla._tbl.tblPr
    for tag in ("w:tblW", "w:tblLayout"):
        for el in tblPr.findall(qn(tag)):
            tblPr.remove(el)
    tblPr.insert(0, tblPr.makeelement(qn("w:tblW"), {qn("w:w"): str(total), qn("w:type"): "dxa"}))
    tblPr.append(tblPr.makeelement(qn("w:tblLayout"), {qn("w:type"): "fixed"}))
    for gc, w in zip(tabla._tbl.tblGrid.findall(qn("w:gridCol")), anchos):
        gc.set(qn("w:w"), str(w))
    for fila in tabla.rows:
        for celda, w in zip(fila.cells, anchos):
            tcPr = celda._tc.get_or_add_tcPr()
            for el in tcPr.findall(qn("w:tcW")):
                tcPr.remove(el)
            tcPr.insert(0, tcPr.makeelement(qn("w:tcW"), {qn("w:w"): str(w), qn("w:type"): "dxa"}))


# ---------------------------------------------------------------------------
# Figura vertical para una columna
# ---------------------------------------------------------------------------

def figura_protocolos_vertical(ruta_json: Path, ruta_png: Path):
    res = json.loads(ruta_json.read_text(encoding="utf-8"))
    fig, axes = plt.subplots(3, 1, figsize=(5.2, 8.4))
    paneles = [("replicas", "Cierre (réplicas, 2 laboratorios)"),
               ("literatura_cierre", "Cierre (literatura, multi-estudio)"), ("meta", "α (meta-dataset v2)")]
    for ax, (clave, titulo) in zip(axes, paneles):
        modelos = list(res[clave]["grupos"]["modelos"])
        x = np.arange(len(modelos))
        for desp, prot, color, etiqueta in [(-0.2, "filas", "#d97706", "Por filas (con fuga)"),
                                            (0.2, "grupos", "#0f766e", "Por grupo (sin fuga)")]:
            M = res[clave][prot]["modelos"]
            ax.bar(x + desp, [M[m]["R2_medio"] for m in modelos], 0.4, yerr=[M[m]["R2_de"] for m in modelos],
                   color=color, capsize=3, label=etiqueta)
        ax.set_xticks(x, ["Random Forest" if m == "RandomForest" else m for m in modelos], fontsize=10)
        ax.axhline(0, color="k", lw=0.8)
        ax.set_ylabel("R²", fontsize=10)
        ax.set_title(titulo, fontsize=11)
        ax.tick_params(axis="y", labelsize=9)
    axes[0].legend(fontsize=9, loc="lower right")
    fig.tight_layout()
    fig.savefig(ruta_png, dpi=220)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Construcción
# ---------------------------------------------------------------------------

def construir() -> Path:
    figura_protocolos_vertical(RES / "revision" / "resumen_revision.json", RES / "revision" / "fig8v_protocolos.png")
    B, _ = bloques("es", "ieee")
    B, refs = numerar_citas(B)

    doc = docx.Document(str(ORIGINAL))
    P = {k: copy.deepcopy(buscar(doc, pref)._p) for k, pref in [
        ("p", "El diseño de concreto"), ("h1", "I. INTRODUCCIÓN"), ("h2", "A. Motivación"), ("resumen", "Resumen"),
        ("claves", "Palabras claves"), ("t_titulo", "TABLA I."), ("t_nota", "Fuente: elaboración"),
        ("pie", "Fig. 1."), ("ref_h", "REFERENCIAS"), ("ref", "[1]")]}
    P["figura"] = copy.deepcopy(buscar(doc, "Fig. 1.")._p.getprevious())
    tpl_tabla = doc.tables[4]
    tpl_tblPr = copy.deepcopy(tpl_tabla._tbl.tblPr)
    tpl_celda_cab = copy.deepcopy(tpl_tabla.rows[0].cells[0].paragraphs[0]._p)
    tpl_celda = copy.deepcopy(tpl_tabla.rows[1].cells[1].paragraphs[0]._p)

    # Título (primera sección, una columna)
    titulos = [b[1] for b in B if b[0] in ("titulo", "titulo2")]
    poner(doc.paragraphs[0], titulos[0])
    poner(doc.paragraphs[1], titulos[1])

    # Vaciar el cuerpo tras el salto de sección del encabezado
    body = doc.element.body
    hijos = list(body.iterchildren())
    corte = next(i for i, el in enumerate(hijos) if el.tag == qn("w:p") and el.find(".//" + qn("w:sectPr")) is not None)
    sect_final = body.find(qn("w:sectPr"))
    for el in hijos[corte + 1:]:
        if el is not sect_final:
            body.remove(el)

    def agregar(clave, partes):
        el = copy.deepcopy(P[clave])
        for d in el.findall(".//" + qn("w:drawing")):
            d.getparent().remove(d)
        sect_final.addprevious(el)
        par = Paragraph(el, doc._body)
        poner(par, partes)
        return par

    def agregar_tabla(filas, proporciones):
        t = doc.add_table(rows=len(filas), cols=len(filas[0]))
        t._tbl.remove(t._tbl.tblPr)
        t._tbl.insert(0, copy.deepcopy(tpl_tblPr))
        for i, fila in enumerate(filas):
            for j, v in enumerate(fila):
                celda = t.cell(i, j)
                viejo = celda.paragraphs[0]._p
                nuevo = copy.deepcopy(tpl_celda_cab if i == 0 else tpl_celda)
                viejo.addprevious(nuevo)
                viejo.getparent().remove(viejo)
                poner(Paragraph(nuevo, celda), str(v))
        ajustar_ancho(t, proporciones)

    for b in B:
        tipo = b[0]
        if tipo in ("titulo", "titulo2"):
            continue
        if tipo == "resumen":
            agregar("resumen", [(f"{b[1]}—", 0), (b[2], 1)])
        elif tipo == "claves":
            agregar("claves", [(f"{b[1]}—", 0), (b[2], 1)])
        elif tipo in ("h1", "h2", "p"):
            agregar(tipo, b[1])
        elif tipo == "tabla":
            _, titulo, filas, nota, prop = b
            agregar("t_titulo", titulo)
            agregar_tabla(filas, prop)
            agregar("t_nota", nota or " ")
        elif tipo == "figura":
            _, ruta, pie, ancho = b
            par = agregar("figura", "")
            for r in list(par.runs):
                r._r.getparent().remove(r._r)
            par.add_run().add_picture(str(ruta), width=Inches(ancho))
            agregar("pie", pie)

    agregar("ref_h", "REFERENCIAS")
    for i, ref in enumerate(refs, 1):
        agregar("ref", f"[{i}]\t{ref}")

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(SALIDA))
    return SALIDA


if __name__ == "__main__":
    print("[OK]", construir())
