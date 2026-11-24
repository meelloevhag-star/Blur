"""
Genera la versión larga para revista (español e inglés) del artículo de auditoría.

Usa los mismos bloques de articulo/contenido.py que la versión IEEE (cifras desde
biocrete_neat/resultados/revision/resumen_revision.json) y los maqueta a una columna.

Uso:
    python articulo/generar_revista.py
Salidas:
    articulo/revista/BioCrete-NEAT_revista_ES.docx
    articulo/revista/BioCrete-NEAT_revista_EN.docx
"""

from pathlib import Path

import docx
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

from contenido import bloques, numerar_citas

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "articulo" / "revista"


def _par(doc, texto, bold=False, italic=False, size=None, align=None, after=None):
    p = doc.add_paragraph()
    r = p.add_run(texto)
    r.bold, r.italic = bold, italic
    if size:
        r.font.size = Pt(size)
    if align is not None:
        p.alignment = align
    if after is not None:
        p.paragraph_format.space_after = Pt(after)
    return p


def _tabla(doc, titulo, filas, nota):
    _par(doc, titulo, bold=True, size=10, after=2)
    t = doc.add_table(rows=len(filas), cols=len(filas[0]))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, fila in enumerate(filas):
        for j, v in enumerate(fila):
            celda = t.cell(i, j)
            celda.text = ""
            par = celda.paragraphs[0]
            run = par.add_run(str(v))
            run.font.size = Pt(9)
            run.bold = i == 0
            par.paragraph_format.line_spacing = 1.0
            par.paragraph_format.space_after = Pt(0)
    _par(doc, nota or "", italic=True, size=9)


def construir(lang: str) -> Path:
    es = lang == "es"
    B, _ = bloques(lang, "revista")
    B, refs = numerar_citas(B)
    doc = docx.Document()
    st = doc.styles["Normal"]
    st.font.name = "Times New Roman"
    st.font.size = Pt(11)
    st.paragraph_format.line_spacing = 1.5
    st.paragraph_format.space_after = Pt(6)
    for s in doc.sections:
        s.left_margin = s.right_margin = s.top_margin = s.bottom_margin = Inches(1)

    for b in B:
        tipo = b[0]
        if tipo == "titulo":
            _par(doc, b[1], bold=True, size=16, align=WD_ALIGN_PARAGRAPH.CENTER)
            _par(doc, "Miguel Angelo Guardamino Capcha ᵃ,*, Carlos Augusto Eyzaguirre Acosta ᵃ",
                 align=WD_ALIGN_PARAGRAPH.CENTER, after=0)
            _par(doc, "ᵃ Facultad de Ingeniería Civil, Universidad Peruana de Ciencias Aplicadas, Lima, Perú",
                 italic=True, size=10, align=WD_ALIGN_PARAGRAPH.CENTER, after=0)
            _par(doc, ("* Autor de correspondencia: " if es else "* Corresponding author: ") + "u20201c640@upc.edu.pe",
                 size=10, align=WD_ALIGN_PARAGRAPH.CENTER)
        elif tipo == "resumen":
            _par(doc, b[1], bold=True)
            _par(doc, b[2], align=WD_ALIGN_PARAGRAPH.JUSTIFY)
        elif tipo == "claves":
            _par(doc, f"{b[1]}: {b[2]}", italic=True)
        elif tipo == "destacados":
            _par(doc, "Aspectos destacados" if es else "Highlights", bold=True)
            for h in b[1]:
                doc.add_paragraph(h, style="List Bullet")
        elif tipo == "h1":
            _par(doc, b[1], bold=True, size=12)
        elif tipo == "h2":
            _par(doc, b[1], bold=True, italic=True)
        elif tipo == "p":
            _par(doc, b[1], align=WD_ALIGN_PARAGRAPH.JUSTIFY)
        elif tipo == "tabla":
            _tabla(doc, b[1], b[2], b[3])
        elif tipo == "figura":
            doc.add_picture(str(b[1]), width=Inches(6.0))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            _par(doc, b[2], italic=True, size=10, align=WD_ALIGN_PARAGRAPH.CENTER)
        elif tipo == "declaraciones":
            for texto in b[1]:
                _par(doc, texto, size=10, align=WD_ALIGN_PARAGRAPH.JUSTIFY)

    _par(doc, "Referencias" if es else "References", bold=True, size=12)
    for i, ref in enumerate(refs, 1):
        p = _par(doc, f"[{i}] {ref}", size=9, after=2)
        p.paragraph_format.line_spacing = 1.0

    SALIDA.mkdir(parents=True, exist_ok=True)
    ruta = SALIDA / f"BioCrete-NEAT_revista_{lang.upper()}.docx"
    doc.save(str(ruta))
    return ruta


if __name__ == "__main__":
    for lang in ("es", "en"):
        print("[OK]", construir(lang))
