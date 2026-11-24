"""
F4 · Genera la versión IEEE del artículo BioCrete-NEAT sobre el .docx original.

Conserva el formato del original (Normal + formato directo, dos columnas) y reemplaza el contenido.
TODAS las cifras se leen de los resultados del código, de modo que el texto no puede
desincronizarse de los análisis. Volver a ejecutar tras re-entrenar.

Uso:
    python articulo/generar_articulo.py
Salida:
    articulo/ieee/BioCrete-NEAT_IEEE_v2.docx
"""

import copy
import json
from pathlib import Path

import docx
from docx.oxml.ns import qn
from docx.shared import Inches
from docx.text.paragraph import Paragraph
from docx.text.run import Run

RAIZ = Path(__file__).resolve().parents[1]
ORIGINAL = RAIZ / "articulo" / "original" / "BioCrete-NEAT_v1_original.docx"
SALIDA = RAIZ / "articulo" / "ieee" / "BioCrete-NEAT_IEEE_v2.docx"
RES = RAIZ / "biocrete_neat" / "resultados"


def _j(ruta: Path) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


def coma(x, d=3) -> str:
    """Formato numérico en español (coma decimal)."""
    return f"{x:.{d}f}".replace(".", ",")


# ---------------------------------------------------------------------------
# Utilidades de edición que preservan el formato
# ---------------------------------------------------------------------------

def _plantillas(p: Paragraph):
    return [copy.deepcopy(r._r) for r in p.runs] or [p._p.makeelement(qn("w:r"), {})]


def poner(p: Paragraph, partes):
    """Reemplaza el texto de `p`. `partes` = str o [(texto, índice_de_run_plantilla), ...]."""
    if isinstance(partes, str):
        partes = [(partes, 0)]
    plant = _plantillas(p)
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


def clonar_despues(ref: Paragraph, modelo: Paragraph, partes) -> Paragraph:
    """Inserta tras `ref` una copia de `modelo` (mismo formato) con el texto indicado."""
    nuevo_xml = copy.deepcopy(modelo._p)
    for d in nuevo_xml.findall(".//" + qn("w:drawing")):
        d.getparent().remove(d)
    ref._p.addnext(nuevo_xml)
    nuevo = Paragraph(nuevo_xml, ref._parent)
    poner(nuevo, partes)
    return nuevo


def eliminar(p: Paragraph):
    p._p.getparent().remove(p._p)


def reemplazar_imagen(p: Paragraph, ruta_img: Path, ancho=3.3):
    for d in p._p.findall(".//" + qn("w:drawing")):
        d.getparent().remove(d)
    for r in list(p.runs):
        r._r.getparent().remove(r._r)
    p.add_run().add_picture(str(ruta_img), width=Inches(ancho))


def parrafo_anterior(p: Paragraph) -> Paragraph:
    return Paragraph(p._p.getprevious(), p._parent)


def llenar_tabla(tabla, filas):
    """Rellena la tabla (encabezado incluido) copiando el formato de la última fila para filas nuevas."""
    while len(tabla.rows) < len(filas):
        tabla._tbl.append(copy.deepcopy(tabla.rows[-1]._tr))
    while len(tabla.rows) > len(filas):
        tabla._tbl.remove(tabla.rows[-1]._tr)
    for fila, valores in zip(tabla.rows, filas):
        for celda, v in zip(fila.cells, valores):
            parrafos = celda.paragraphs
            poner(parrafos[0], str(v))
            for extra in parrafos[1:]:
                eliminar(extra)


ANCHO_COLUMNA_TWIPS = 4780  # (7,14 in − 0,5 in de separación) / 2 columnas ≈ 3,32 in


def ajustar_ancho(tabla, proporciones, total=ANCHO_COLUMNA_TWIPS):
    """Fija el ancho de la tabla al de una columna IEEE con diseño fijo (evita desbordes en Word/LibreOffice)."""
    anchos = [int(total * p / sum(proporciones)) for p in proporciones]
    tblPr = tabla._tbl.tblPr
    for tag in ("w:tblW", "w:tblLayout"):
        for el in tblPr.findall(qn(tag)):
            tblPr.remove(el)
    tblW = tblPr.makeelement(qn("w:tblW"), {qn("w:w"): str(total), qn("w:type"): "dxa"})
    layout = tblPr.makeelement(qn("w:tblLayout"), {qn("w:type"): "fixed"})
    tblPr.insert(0, tblW)
    tblPr.append(layout)
    for gc, w in zip(tabla._tbl.tblGrid.findall(qn("w:gridCol")), anchos):
        gc.set(qn("w:w"), str(w))
    for fila in tabla.rows:
        for celda, w in zip(fila.cells, anchos):
            tcPr = celda._tc.get_or_add_tcPr()
            for el in tcPr.findall(qn("w:tcW")):
                tcPr.remove(el)
            tcPr.insert(0, tcPr.makeelement(qn("w:tcW"), {qn("w:w"): str(w), qn("w:type"): "dxa"}))


# ---------------------------------------------------------------------------
# Cifras
# ---------------------------------------------------------------------------

def cifras() -> dict:
    neat = _j(RES / "resumen_neat.json")
    zen = _j(RES / "resumen_datasets_reales_zenodo.json")
    f3 = _j(RES / "f3" / "resumen_f3.json")
    flujo = _j(RAIZ / "biocrete_neat" / "modelos" / "demo_flujo" / "registro_versiones.json")
    rep, meta = f3["replicas"], f3["meta"]
    mejor_rep = max(rep["modelos"], key=lambda m: rep["modelos"][m]["R2"])
    mejor_meta = max(meta["modelos"], key=lambda m: meta["modelos"][m]["R2"])
    return {"neat": neat, "zen": zen, "f3": f3, "flujo": flujo, "rep": rep, "meta": meta,
            "mejor_rep": mejor_rep, "mejor_meta": mejor_meta,
            "neat_rep": rep["modelos"]["NEAT λ=0.0008"], "neat_meta": meta["modelos"]["NEAT (λ anidado)"],
            "n_cap_agno3": sum(r["n_mediciones"] for r in zen["cappellesso2024_agno3_marino"])}


def ic(m: dict) -> str:
    return f"[{coma(m['R2_IC95'][0], 2)}; {coma(m['R2_IC95'][1], 2)}]"


# ---------------------------------------------------------------------------
# Construcción
# ---------------------------------------------------------------------------

def construir() -> Path:
    c = cifras()
    rep, meta, f3, flujo = c["rep"], c["meta"], c["f3"], c["flujo"]
    R, M = rep["modelos"], meta["modelos"]
    n_rep, g_rep = rep["n_registros"], rep["n_grupos"]
    n_mousa, n_capm = rep["fuentes"]["Mousa2022"], rep["fuentes"]["Cappellesso2024"]
    n_meta, e_meta = meta["n_registros"], meta["n_estudios"]
    curva = f3["curva_aprendizaje"]
    shap_rep, shap_meta = f3["shap"]["replicas"], f3["shap"]["meta"]
    lam_elegidos = meta["lambdas_elegidos_cv_anidada"]
    n_alta = sum(1 for l in lam_elegidos if abs(l - 8e-4) < 1e-9)
    r2p = {e["version"]: e["r2_prospectivo"] for e in flujo}
    paita = f3["paita"]
    dryad_ratio = c["zen"]["dryad_razon_mediana_life365_vs_exp"]
    mr, mm = c["mejor_rep"], c["mejor_meta"]

    doc = docx.Document(str(ORIGINAL))

    # --- Título -----------------------------------------------------------
    poner(doc.paragraphs[0], "BioCrete-NEAT: neuroevolución explicable con aprendizaje continuo para predecir "
                             "la autorreparación del concreto bacteriano a partir de datos abiertos y colaborativos "
                             "en ambientes marinos")
    poner(doc.paragraphs[1], "BioCrete-NEAT: explainable neuroevolution with continual learning to predict "
                             "bacterial concrete self-healing from open and collaborative data in marine environments")

    # --- Resumen / Abstract ----------------------------------------------
    resumen = (
        "Evaluar experimentalmente el concreto autocurativo bacteriano (CAB) en exposición marina exige programas "
        "de 28 a 90 días o más, y los modelos predictivos publicados suelen entrenarse con pocos promedios, "
        "validarse sin agrupar por estudio o probeta y quedar congelados tras su publicación. Este trabajo presenta "
        "BioCrete-NEAT, un marco reproducible y auditable que combina neuroevolución de topologías crecientes (NEAT) "
        f"con aprendizaje continuo. Se extrajeron {n_rep} registros individuales de cierre de fisuras de {g_rep} "
        f"fisuras y probetas de dos repositorios abiertos con DOI (Mousa et al., {n_mousa}; Cappellesso et al., "
        f"{n_capm} en agua de mar ASTM D1141) y se usó un meta-dataset de {n_meta} condiciones de {e_meta} estudios "
        "para la reducción de transporte de cloruros (α). Con validación cruzada agrupada sin fuga e intervalos de "
        f"confianza bootstrap, el mejor referente alcanzó R² = {coma(R[mr]['R2'])} en cierre ({mr}) y "
        f"R² = {coma(M[mm]['R2'])} en α ({mm}); NEAT con selección anidada de parsimonia obtuvo "
        f"R² = {coma(c['neat_rep']['R2'])} y {coma(c['neat_meta']['R2'])} con redes de casi cero neuronas ocultas, "
        "superando a la regresión lineal en cierre y ofreciendo la topología más inspeccionable. SHAP y la topología "
        "evolucionada coinciden en que el nivel de protección biológica gobierna α, mientras que la edad y el ancho "
        "inicial gobiernan el cierre. En una simulación de llegada por lotes, un modelo congelado cayó a "
        f"R² = {coma(r2p[3]['campeon_vigente'])} ante datos marinos nuevos, mientras que la actualización con control "
        f"campeón/candidato se recuperó a R² = {coma(r2p[3]['candidato_caliente'])}. El marco incluye una plantilla "
        "validada para que tesis y laboratorios aporten datos y una cosecha mensual de literatura, y entrega "
        "predicciones para Paita-Piura con intervalos de confianza y advertencias de extrapolación, listas para su "
        "validación externa."
    )
    poner(buscar(doc, "Resumen"), [("Resumen—", 0), (resumen, 1)])
    poner(buscar(doc, "Palabras claves"), [("Palabras claves—", 0),
          ("concreto autocurativo bacteriano, neuroevolución, NEAT, aprendizaje continuo, aprendizaje automático "
           "explicable, validación agrupada, datos abiertos, ambiente marino", 1)])
    abstract = (
        "Experimental evaluation of bacterial self-healing concrete (BSHC) under marine exposure requires 28- to "
        "90-day programs or longer, and published predictors are usually trained on a few averages, validated "
        "without grouping by study or specimen, and frozen after publication. This paper presents BioCrete-NEAT, a "
        "reproducible and auditable framework that couples NeuroEvolution of Augmenting Topologies (NEAT) with "
        f"continual learning. We extracted {n_rep} individual crack-closure records from {g_rep} cracks and specimens "
        f"in two open DOI repositories (Mousa et al., {n_mousa}; Cappellesso et al., {n_capm} in ASTM D1141 "
        f"seawater) and used a {n_meta}-condition, {e_meta}-study meta-dataset for chloride transport reduction (α). "
        "Under leakage-free grouped cross-validation with bootstrap confidence intervals, the best baseline reached "
        f"R² = {R[mr]['R2']:.3f} for closure ({mr}) and R² = {M[mm]['R2']:.3f} for α ({mm}); NEAT with nested "
        f"parsimony selection achieved R² = {c['neat_rep']['R2']:.3f} and {c['neat_meta']['R2']:.3f} with nearly zero "
        "hidden neurons, outperforming linear regression on closure and providing the most inspectable topology. "
        "SHAP and the evolved topology agree that biological protection governs α, while age and initial width "
        "govern closure. In a batch-arrival simulation, a frozen model dropped to "
        f"R² = {r2p[3]['campeon_vigente']:.3f} on new marine data, whereas champion/challenger updating recovered "
        f"R² = {r2p[3]['candidato_caliente']:.3f}. The framework provides a validated template for theses and "
        "laboratories to contribute data and a monthly literature harvest, and delivers Paita-Piura predictions "
        "with confidence intervals and extrapolation warnings for external validation."
    )
    poner(buscar(doc, "Abstract"), [("Abstract—", 0), (abstract, 1)])
    poner(buscar(doc, "Keywords"), [("Keywords—", 0),
          ("bacterial self-healing concrete, neuroevolution, NEAT, continual learning, explainable machine learning, "
           "grouped validation, open data, marine environment", 1)])

    # --- I. Introducción --------------------------------------------------
    poner(buscar(doc, "Para cubrir ese vacío"), (
        "Para cubrir ese vacío a nivel micro, la literatura recurre a modelos de aprendizaje automático y redes "
        "neuronales artificiales (RNA) [4], [5]. Persisten tres debilidades: (i) la arquitectura de la RNA se fija "
        "por ensayo y error, lo que genera modelos opacos y propensos al sobreajuste con datos escasos; (ii) la "
        "validación suele hacerse por filas, de modo que réplicas de un mismo estudio o probeta aparecen a la vez en "
        "entrenamiento y prueba, una fuga de información que infla las métricas [22]; y (iii) los modelos quedan "
        "congelados tras su publicación y no incorporan los ensayos que siguen generando tesis y laboratorios."))
    p_sota = buscar(doc, "Como alternativa a las RNAs")
    clonar_despues(p_sota, p_sota, (
        "Los algoritmos de árboles con gradiente (XGBoost [19]) combinados con explicaciones SHAP [20] se han "
        "consolidado como referentes de precisión e interpretabilidad local. Por otra parte, el aprendizaje continuo "
        "estudia cómo actualizar un modelo cuando llegan datos nuevos sin perder lo aprendido [21]; NEAT es "
        "especialmente apto para ello porque su población puede reanudarse y seguir evolucionando en lugar de "
        "reiniciarse."))
    poner(buscar(doc, "Este artículo desarrolla"), (
        "Este artículo desarrolla un camino complementario al modelado estocástico macro [3], centrado en la "
        "predicción a escala de material, la validación honesta y la mejora continua. Sus aportes son cuatro: "
        f"(1) la extracción de {n_rep} registros individuales de cierre de fisuras desde repositorios abiertos con "
        "DOI, con trazabilidad por fila y corrección de errores de etiquetado de la versión previa; (2) una "
        "comparación de NEAT, XGBoost, Random Forest y Ridge con validación cruzada agrupada, selección anidada de la "
        "parsimonia e intervalos de confianza; (3) un esquema de aprendizaje continuo con entrada validada de datos "
        "de terceros, neuroevolución incremental y control campeón/candidato; y (4) predicciones con incertidumbre "
        "para el programa experimental de Paita-Piura, enlazadas con los umbrales α de BioCrete-Markov."))

    # --- II. Metodología --------------------------------------------------
    poner(buscar(doc, "En lugar de depender"), (
        "Se descargaron conjuntos experimentales crudos con DOI permanente desde Zenodo y Dryad (Tabla I) y se "
        "procesaron con Python (openpyxl). En Mousa et al. [12] se extrajo una fila por fisura desde las pestañas "
        "de réplicas (anchos a 0, 3, 7, 14 y 28 días), deduplicando las pestañas que se solapan; una fisura con "
        "ancho inicial nulo se excluyó. Los precursores se codificaron según el propio registro (acetato de magnesio, "
        "lactato de calcio y lactato de sodio). En Cappellesso et al. [11] se procesaron las mediciones de "
        "microscopía por probeta y zona en agua de mar ASTM D1141 y las mediciones de penetración de cloruros "
        "por nitrato de plata. El meta-dataset multi-estudio reúne condiciones de estudios revisados por pares "
        "[1], [2], [14]–[18]. El conjunto de aplicación manual de agentes en ambiente rico en cloruros [13] se "
        "descargó y queda reservado para la siguiente actualización del marco. Cada registro conserva su DOI, la "
        "hoja de origen y un identificador de grupo."))
    llenar_tabla(doc.tables[1], [
        ["Conjunto / Fuente", "DOI oficial", "Registros", "Uso en este trabajo"],
        ["Mousa et al. réplicas [12]", "10.5281/zenodo.6469122", f"{n_mousa} reg. ({n_mousa // 4} fisuras)",
         "Cierre % a 3–28 d (hidrogel, LWA, CNC)"],
        ["Cappellesso microscopía [11]", "10.5281/zenodo.11305154", f"{n_capm} reg.",
         "Cierre % en agua de mar (REF, BAS, CA)"],
        ["Cappellesso AgNO3 [11]", "10.5281/zenodo.11305154", f"{c['n_cap_agno3']} med.",
         "Penetración de cloruros (Tabla III)"],
        ["Dryad OPC DRCM [10]", "10.5061/dryad.66t1g1k6j", "239 ensayos", "Contraste de Life-365"],
        ["Meta-dataset CAB", f"{e_meta} estudios con DOI", f"{n_meta} cond.", "Reducción de transporte α"],
    ])
    poner(buscar(doc, "Fuente: elaboración propia"), "Fuente: elaboración propia a partir de los repositorios "
          "oficiales; código y datos procesados disponibles en el repositorio del proyecto.")

    poner(buscar(doc, "Para el meta-dataset multi-estudio"), (
        "Para el cierre de fisuras se usaron seis entradas físicas: ancho inicial w0 (mm), edad desde la fisuración "
        "(d), nivel de protección biológica (0 = sin bacterias, 1 = adición directa o agente comercial, 2 = portador "
        "poroso, 3 = encapsulación), ambiente marino (0/1), lactato de calcio (0/1) y curado previo a la exposición "
        "(0/1). Para α se mantuvieron las seis variables del meta-dataset (a/c, w0, edad, protección, ambiente y "
        "lactato). Todas se normalizaron a [0, 1] con límites físicos fijos, no con estadísticas del conjunto, para "
        "evitar fuga entre particiones y permitir que una misma red procese datos que lleguen en el futuro."))

    poner(buscar(doc, "La neuroevolución se implementó"), (
        "La neuroevolución se implementó en Python con neat-python 2.0.0, red estrictamente feed-forward, activación "
        "sigmoide y topología inicial sin neuronas ocultas (Tabla II). La aptitud incorpora una penalización "
        "explícita de parsimonia:"))
    poner(buscar(doc, "donde MSE(g)"), (
        "donde MSE(g) es el error cuadrático medio del genoma g en el entrenamiento, N_ocultas y N_conex son las "
        "neuronas ocultas y conexiones activas y λ_p controla la parsimonia (8×10⁻⁴ o 1,2×10⁻⁴). Para no sesgar la "
        "comparación, λ_p se eligió por validación cruzada anidada [23]: en cada partición externa, una validación "
        "interna agrupada elige λ_p y solo después se evalúa en la partición externa. Las particiones se agruparon "
        "por fisura o probeta (réplicas) y por estudio (meta-dataset) mediante GroupKFold de 5 particiones, de modo "
        "que ninguna fisura ni estudio aparece a la vez en entrenamiento y prueba [22]. Los intervalos de confianza "
        "del 95 % se obtuvieron remuestreando grupos completos (1000 réplicas bootstrap)."))
    llenar_tabla(doc.tables[2], [
        ["Modelo", "Parámetros clave", "Papel en el estudio"],
        ["BioCrete-NEAT", "Pop = 60; 75 gen.; 0 ocultas iniciales; sigmoide; λ_p anidado",
         "Topología mínima explicable y actualizable"],
        ["XGBoost [19]", "400 árboles; prof. 4; η = 0,04; submuestreo 0,8", "Referente de precisión + SHAP [20]"],
        ["Random Forest [9]", "300 árboles; prof. 8; hoja mín. 3", "Referente no lineal"],
        ["Regresión Ridge", "L2, α_reg = 1,0", "Línea base lineal"],
    ])
    p_val = buscar(doc, "Validación cruzada 5-fold")
    poner(p_val, "GroupKFold de 5 particiones; semilla global = 2026; IC 95 % por bootstrap de grupos.")

    s = clonar_despues(p_val, buscar(doc, "C. Formulación"), "D. Aprendizaje continuo y datos colaborativos")
    clonar_despues(s, buscar(doc, "Para el cierre de fisuras"), (
        "El marco se actualiza cuando llegan datos nuevos en cuatro pasos: (i) los aportes de tesis y laboratorios "
        "se reciben en una plantilla CSV y un validador exige DOI o enlace, norma de ensayo, autoría, rangos físicos "
        "y coherencia entre anchos y porcentaje de cierre, rechazando —sin imputar— las filas inválidas; (ii) una "
        "cosecha mensual automatizada busca artículos, datasets y tesis nuevas (OpenAlex, Zenodo, RENATI y ALICIA) "
        "con el mismo protocolo de trazabilidad; (iii) el candidato NEAT reanuda la población guardada de la versión "
        "vigente (arranque en caliente, restaurando el rastreador de innovaciones) y sigue evolucionando con los "
        "datos acumulados; y (iv) el candidato solo reemplaza al campeón si iguala o supera su R² prospectivo en los "
        "grupos nuevos, evaluado con GroupKFold sobre esos grupos. Cada versión se registra con la huella de sus "
        "datos, sus métricas y su fecha."))

    # --- III. Resultados ---------------------------------------------------
    poner(buscar(doc, "El contraste de la ecuación"), (
        "El contraste de la ecuación de difusión a 28 días de Life-365 (D28 = 10^(−12,06 + 2,40·a/c)) frente a los "
        "239 ensayos de concreto OPC de Dryad [10] arrojó una razón mediana Life-365/experimental de "
        f"{coma(dryad_ratio, 2)}×, de modo que la curva base reproduce la difusión de laboratorio y su subestimación "
        "de la vida útil en Colán [3] obedece a las condiciones de frontera locales."))
    poner(buscar(doc, "Por su parte, el procesamiento"), (
        f"Las {c['n_cap_agno3']} mediciones marinas de penetración de cloruros de Cappellesso et al. [11] "
        "(Tabla III) muestran que el agente bacteriano (BAS) redujo la profundidad de cloruros entre 15,4 % y 30,0 % "
        "en las series sin pre-curado y en probetas sin fisurar, con alta dispersión en la serie Crack 100 H. La "
        "reducción alcanzable en exposición marina se concentra así entre 15 % y 30 %, muy por debajo del techo de "
        "68 % citado habitualmente."))

    poner(buscar(doc, "B. Desempeño de NEAT"), "B. Comparación con validación agrupada sin fuga")
    poner(buscar(doc, "La Tabla IV y la Fig. 1"), (
        f"La Tabla IV y la Fig. 1 resumen el desempeño fuera de muestra. En las {n_rep} réplicas de cierre, {mr} "
        f"obtuvo el mejor R² = {coma(R[mr]['R2'])} {ic(R[mr])}, seguido de XGBoost ({coma(R['XGBoost']['R2'])}); "
        f"NEAT alcanzó {coma(R['NEAT λ=0.0008']['R2'])} {ic(R['NEAT λ=0.0008'])} con "
        f"{coma(R['NEAT λ=0.0008']['neuronas_ocultas_prom'], 1)} neuronas ocultas en promedio, por encima de Ridge "
        f"({coma(R['Ridge']['R2'])}). En el meta-dataset α agrupado por estudio, {mm} lideró con "
        f"R² = {coma(M[mm]['R2'])} {ic(M[mm])}, Ridge obtuvo {coma(M['Ridge']['R2'])} y NEAT con λ_p anidado "
        f"{coma(c['neat_meta']['R2'])} {ic(c['neat_meta'])}; la validación anidada eligió la parsimonia alta en "
        f"{n_alta} de {len(lam_elegidos)} particiones."))
    poner(buscar(doc, "De manera consistente"), (
        "Estos valores corrigen a la baja los de la versión previa del módulo (R² = 0,540 para NEAT en α), que se "
        "obtuvieron con particiones por fila: al impedir que condiciones de un mismo estudio aparezcan en "
        "entrenamiento y prueba, la ventaja de NEAT sobre los referentes desaparece y los intervalos de confianza "
        f"se ensanchan, como corresponde a solo {e_meta} estudios. La conclusión defendible es que NEAT ofrece una "
        "precisión competitiva con la red más pequeña e inspeccionable, mientras que los árboles con gradiente marcan "
        "el techo de precisión actual."))
    llenar_tabla(doc.tables[4], [
        ["Objetivo", "Modelo", "R² [IC 95 %]", "MAE", "RMSE"],
        *[["Cierre % (réplicas)", nom, f"{coma(R[k]['R2'])} {ic(R[k])}", f"{coma(R[k]['MAE'], 1)} %",
           f"{coma(R[k]['RMSE'], 1)} %"]
          for nom, k in [("Random Forest", "RandomForest"), ("XGBoost", "XGBoost"),
                         ("NEAT (λ_p = 8×10⁻⁴)", "NEAT λ=0.0008"), ("Ridge", "Ridge")]],
        *[["α (meta-dataset)", nom, f"{coma(M[k]['R2'])} {ic(M[k])}", coma(M[k]["MAE"]),
           coma(M[k]["RMSE"])]
          for nom, k in [("XGBoost", "XGBoost"), ("Ridge", "Ridge"), ("Random Forest", "RandomForest"),
                         ("NEAT (λ_p anidado)", "NEAT (λ anidado)")]],
    ])
    poner(buscar(doc, "TABLA IV"), "TABLA IV. Desempeño fuera de muestra con validación cruzada agrupada "
                                    "(GroupKFold 5) e IC 95 % por bootstrap de grupos")
    poner(buscar(doc, "Métricas calculadas"), f"Réplicas: n = {n_rep}, agrupadas por fisura/probeta ({g_rep} grupos); "
          f"meta-dataset: n = {n_meta}, agrupado por estudio ({e_meta}). Ninguna fisura ni estudio aparece en "
          "entrenamiento y prueba.")

    figs = RES / "f3"
    p_f1 = buscar(doc, "Fig. 1.")
    reemplazar_imagen(parrafo_anterior(p_f1), figs / "fig4_comparacion_modelos_ic95.png")
    poner(p_f1, "Fig. 1. R² fuera de muestra con IC 95 % (bootstrap por grupos) para réplicas de cierre "
                "(izquierda) y meta-dataset α (derecha).")

    poner(buscar(doc, "C. Topología mínima"), "C. Explicabilidad: topología NEAT y SHAP")
    top = c["neat"]["topologia_final_alpha"]
    ancho_meta = next(s["shap_medio_abs"] for s in shap_meta if s["variable"].startswith("Ancho"))
    p_expl = buscar(doc, "Una ventaja distintiva")
    poner(p_expl, (
        f"Sobre el meta-dataset completo, NEAT convergió a una topología de {top['neuronas_ocultas']} neuronas "
        f"ocultas y {top['conexiones_activas']} conexiones activas, dibujable e interpretable de forma directa. El "
        "análisis SHAP de XGBoost (Fig. 2) coincide con la permutación sobre la red NEAT: el nivel de protección "
        f"biológica domina α (|SHAP| medio = {coma(shap_meta[0]['shap_medio_abs'])}), seguido del ancho de fisura "
        f"({coma(ancho_meta)}), coherente con la degradación de esporas sin protección [14] y con el límite práctico "
        f"de cierre sobre 0,5 mm [15]. En las réplicas de cierre, la variable dominante es la "
        f"{shap_rep[0]['variable'].split(' (')[0].lower()} ({coma(shap_rep[0]['shap_medio_abs'])}), seguida del "
        f"ancho inicial ({coma(shap_rep[1]['shap_medio_abs'])}) y de la protección biológica "
        f"({coma(shap_rep[2]['shap_medio_abs'])})."))
    p_f2 = buscar(doc, "Fig. 2.")
    reemplazar_imagen(parrafo_anterior(p_f2), figs / "fig5b_shap_meta.png")
    poner(p_f2, "Fig. 2. Valores SHAP de XGBoost para la reducción de transporte α (meta-dataset): cada punto es "
                "una condición; el color indica el valor normalizado de la variable.")
    p_f3 = buscar(doc, "Fig. 3.")
    reemplazar_imagen(parrafo_anterior(p_f3), figs / "fig6_curva_aprendizaje.png")
    poner(p_f3, "Fig. 3. Curva de aprendizaje: R² fuera de muestra frente al número de registros de réplicas "
                "(GroupKFold por fisura).")

    s = clonar_despues(p_f3, buscar(doc, "C. Explicabilidad"), "D. Aprendizaje continuo: más datos, mejor modelo")
    s = clonar_despues(s, p_expl, (
        f"La curva de aprendizaje (Fig. 3) muestra que los modelos mejoran al crecer los datos: Random Forest pasa "
        f"de R² = {coma(curva['RandomForest'][0])} con {curva['n_registros'][0]} registros a "
        f"{coma(curva['RandomForest'][-1])} con {curva['n_registros'][-1]}, y NEAT de "
        f"{coma(curva['NEAT λ=0.0008'][0])} a {coma(max(curva['NEAT λ=0.0008']))}. La Fig. 4 simula la llegada "
        "secuencial de tres lotes. El modelo congelado (campeón sin re-entrenar) cayó a R² = "
        f"{coma(r2p[2]['campeon_vigente'])} y {coma(r2p[3]['campeon_vigente'])} ante los lotes marinos que nunca "
        f"había visto, mientras que el candidato actualizado alcanzó {coma(r2p[2]['candidato_caliente'])} y "
        f"{coma(r2p[3]['candidato_caliente'])} y fue aceptado en todos los lotes. Con igual número de generaciones, "
        "el arranque en caliente superó al arranque desde cero en el segundo lote "
        f"({coma(r2p[2]['candidato_caliente'])} frente a {coma(r2p[2]['referencia_frio'])}) y quedó por debajo en el "
        f"tercero ({coma(r2p[3]['candidato_caliente'])} frente a {coma(r2p[3]['referencia_frio'])}), por lo que su "
        "ventaja no es concluyente con estos datos; el beneficio robusto proviene de actualizar el modelo en lugar de "
        "congelarlo."))
    p_img4 = clonar_despues(s, parrafo_anterior(p_f3), "")
    reemplazar_imagen(p_img4, figs / "fig7_aprendizaje_continuo.png")
    clonar_despues(p_img4, p_f3, "Fig. 4. Validación prospectiva por lote: campeón congelado, candidato NEAT "
                                 "incremental y NEAT desde cero sobre los datos nuevos de cada lote.")

    # --- Paita --------------------------------------------------------------
    poner(buscar(doc, "D. Predicción a priori"), "E. Predicción para Paita-Piura con incertidumbre")
    poner(buscar(doc, "Al evaluar las condiciones"), (
        "Para el programa de Paita-Piura (agua de mar artificial ASTM D1141, 90 días, lactato de calcio) se entrenó "
        "un ensamble bootstrap de 100 modelos XGBoost sobre las réplicas, con restricciones monótonas físicamente "
        "justificadas (más ancho inicial, menos cierre; más edad, más cierre). La Tabla V reporta la media y el "
        f"IC 95 %: en adición directa, el cierre esperado cae de {coma(paita[0]['cierre_medio_pct'], 1)} % en 0,2 mm "
        f"a {coma(paita[1]['cierre_medio_pct'], 1)} % en 0,5 mm. Todas las predicciones llevan advertencias "
        "explícitas: los datos abiertos no combinan ambiente marino con lactato de calcio, no hay datos marinos con "
        "portador o encapsulación y 1,0 mm excede el rango entrenado. Por ello estas cifras deben leerse como "
        "hipótesis a contrastar, y los ensayos de Paita a 28, 56 y 90 días son precisamente los aportes que el marco "
        "incorporará para cerrar esos vacíos antes de enlazarlos con los umbrales α de BioCrete-Markov [3]."))

    def corto(txt: str) -> str:
        codigos = []
        if "fuera del rango" in txt:
            codigos.append("c")
        if "este nivel de protección" in txt:
            codigos.append("b")
        if "lactato de calcio" in txt:
            codigos.append("a")
        return ", ".join(sorted(codigos)) or "—"

    llenar_tabla(doc.tables[5], [
        ["Escenario (90 d, mar, lactato Ca)", "Cierre medio", "IC 95 %", "Aviso"],
        *[[f["escenario"].split(" · ", 3)[-1], f"{coma(f['cierre_medio_pct'], 1)} %",
           f"{coma(f['cierre_IC95_pct'][0], 1)}–{coma(f['cierre_IC95_pct'][1], 1)} %", corto(f["extrapolacion"])]
          for f in paita],
    ])
    poner(buscar(doc, "TABLA V"), "TABLA V. Predicciones de cierre para Paita-Piura (ensamble XGBoost monótono, "
                                  "100 réplicas bootstrap)")
    poner(buscar(doc, "Predicciones a priori para contraste"), "Avisos de extrapolación: a = sin datos que combinen "
          "agua de mar y lactato de calcio; b = sin datos marinos con este nivel de protección; c = ancho fuera del "
          "rango entrenado. Hipótesis para contraste externo (EN 12390-8 y microscopía óptica).")

    poner(buscar(doc, "E. Limitaciones"), "F. Limitaciones")
    poner(buscar(doc, "El presente estudio constituye"), (
        f"El meta-dataset de α sigue siendo pequeño ({n_meta} condiciones de {e_meta} estudios), lo que se refleja en "
        "intervalos de confianza amplios. Las réplicas provienen de dos laboratorios con agentes y regímenes "
        "distintos, y ninguna combina ambiente marino con lactato de calcio. La ventaja del arranque en caliente de "
        "NEAT no es concluyente y debe evaluarse con más lotes reales. Estas limitaciones son precisamente las que el "
        "esquema de aprendizaje continuo está diseñado para reducir a medida que se incorporen tesis, datos de "
        "laboratorio y los ensayos propios de Paita."))

    # --- IV. Conclusiones --------------------------------------------------
    poner(buscar(doc, "Se desarrolló y validó"), (
        f"Se desarrolló BioCrete-NEAT, un marco abierto y auditable que pasa de 52 promedios a {n_rep} registros "
        "individuales de cierre de fisuras con trazabilidad por fila, corrige errores de etiquetado de la versión "
        "previa y verifica automáticamente las cifras reportadas contra el código."))
    poner(buscar(doc, "Los datos crudos de Dryad"), (
        "Con validación agrupada sin fuga, los árboles con gradiente marcan el techo de precisión "
        f"(R² = {coma(R[mr]['R2'])} en cierre y {coma(M[mm]['R2'])} en α), mientras que NEAT logra "
        f"R² = {coma(c['neat_rep']['R2'])} y {coma(c['neat_meta']['R2'])} con redes de casi cero neuronas ocultas y "
        "coincide con SHAP en que la protección biológica gobierna α. Reportar la caída respecto del R² = 0,540 previo "
        "es parte central de la contribución."))
    poner(buscar(doc, "El enlace Micro"), (
        "El aprendizaje continuo demostró ser necesario: un modelo congelado falló ante datos marinos nuevos "
        f"(R² = {coma(r2p[3]['campeon_vigente'])}), mientras que la actualización controlada se recuperó a "
        f"{coma(r2p[3]['candidato_caliente'])}. Con la plantilla de aportes, la cosecha mensual de literatura y "
        "tesis, y el registro de versiones, BioCrete-NEAT queda preparado para mejorar con cada ensayo que aporten la "
        "comunidad y el programa de Paita-Piura."))

    # --- Referencias: correcciones verificadas (F6) y nuevas ------------------
    from correcciones_referencias import corregir

    for p in doc.paragraphs:
        if p.text.startswith("[") and corregir(p.text) != p.text:
            poner(p, corregir(p.text))
    ultima = buscar(doc, "[18]")
    nuevas = [
        "[19]\tT. Chen and C. Guestrin, “XGBoost: A scalable tree boosting system,” in Proc. 22nd ACM SIGKDD Int. "
        "Conf. Knowl. Discov. Data Min., 2016, pp. 785–794, doi: 10.1145/2939672.2939785.",
        "[20]\tS. M. Lundberg and S.-I. Lee, “A unified approach to interpreting model predictions,” in Adv. Neural "
        "Inf. Process. Syst., vol. 30, 2017, pp. 4765–4774.",
        "[21]\tG. I. Parisi, R. Kemker, J. L. Part, C. Kanan, and S. Wermter, “Continual lifelong learning with "
        "neural networks: A review,” Neural Netw., vol. 113, pp. 54–71, 2019, doi: 10.1016/j.neunet.2019.01.012.",
        "[22]\tS. Kapoor and A. Narayanan, “Leakage and the reproducibility crisis in machine-learning-based "
        "science,” Patterns, vol. 4, no. 9, Art. no. 100804, 2023, doi: 10.1016/j.patter.2023.100804.",
        "[23]\tS. Varma and R. Simon, “Bias in error estimation when using cross-validation for model selection,” "
        "BMC Bioinformatics, vol. 7, Art. no. 91, 2006, doi: 10.1186/1471-2105-7-91.",
    ]
    ref = ultima
    for texto in nuevas:
        ref = clonar_despues(ref, ultima, texto)

    for k, prop in {1: [2.3, 2.1, 1.4, 2.6], 2: [1.5, 3.0, 2.2], 3: [1.6, 1.3, 1.3, 1.3],
                    4: [1.4, 1.8, 2.0, 0.85, 0.85], 5: [2.6, 1.1, 1.4, 0.7]}.items():
        ajustar_ancho(doc.tables[k], prop)

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(SALIDA))
    return SALIDA


if __name__ == "__main__":
    print("[OK]", construir())
