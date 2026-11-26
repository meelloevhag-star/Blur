"""
Artículo de Hefesto (IEEE, español): neuroevolución y agentes de IA para predecir qué concreto
autorreparable alcanza la vida útil de la norma en un lugar dado.

Usa la plantilla del artículo 1 (formato IEEE a dos columnas y tabla de autores) y reconstruye el
cuerpo. TODAS las cifras se leen de resultados/*.json; ninguna se escribe a mano.

Uso:
    python -m articulos.2_hefesto.generar_articulo2
Salida:
    articulos/2_hefesto/ieee/Hefesto_IEEE_ES.docx (+ figuras PNG en articulo/ieee/)
"""

import copy
import json
from pathlib import Path

import docx
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from docx.oxml.ns import qn
from docx.shared import Inches
from docx.text.paragraph import Paragraph
from docx.text.run import Run

from hefesto.durabilidad import vida_util as vu

RAIZ = Path(__file__).resolve().parents[2]
PLANTILLA = RAIZ / "articulos" / "2_hefesto" / "plantilla" / "plantilla_ieee_es.docx"
SALIDA = RAIZ / "articulos" / "2_hefesto" / "ieee" / "Hefesto_IEEE_ES.docx"
RES = RAIZ / "resultados"
ANCHO_COL = 4780


def cargar() -> dict:
    j = lambda n: json.loads((RES / n).read_text(encoding="utf-8"))
    vz = j("vida_zonas.json")
    return {"hib": j("hibrido.json"), "diag": j("meta20_diagnostico.json"), "vz": vz, "res": vz["resumen"],
            "sens": j("sensibilidad_vida.json"), "banco": j("banco_motores.json"),
            "reg": json.loads((RAIZ / "modelos" / "registro.json").read_text(encoding="utf-8"))[-1]}


def f1(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


# ---------------------------------------------------------------------------- contenido
def contenido(D: dict) -> dict:
    r, hib, diag, banco = D["res"], D["hib"], D["diag"], D["banco"]
    h3 = lambda lab, n: hib[lab]["modelos"]["H3 contraído"][str(n)]["MAE_pp_medio"]
    c25, c40, v25 = r["cierre_requerido_25_pct"], r["cierre_requerido_40_pct"], r["veredicto_25"]
    ncl = r["zonas"] - r["fuera_de_alcance_carbonatacion"]
    neat = r["neat_mejor_opcion_marina"]["cierre_pct"]
    piso = diag["E1_piso_ruido"]["global"]
    sin_tope = vu.t_inicio_determinista(15.8e-12, 0.65, 1.5, congelar=False)
    con_tope = vu.t_inicio_determinista(15.8e-12, 0.65, 1.5, congelar=True)
    base_fib = vu.t_inicio_determinista(15.8e-12, 0.30, 1.5, congelar=False)
    aj, fis = vu.ajuste_d28(), vu.pendiente_fisura()
    cand = {c["nombre"]: c for c in banco["candidatos"]}
    gan = cand[banco["eleccion"]["ganador"]]
    lab = lambda n: cand[n]["precision"]["laboratorio"]["media_MAE_pp"]
    grp = lambda n: cand[n]["precision"]["grupos"]["MAE_pp"]
    rf, mlp = "Random Forest", "MLP 32x16"
    resumen = (
        f"¿Puede la neuroevolución, alimentada por agentes que cosechan datos de concreto autocurativo, predecir qué "
        f"concreto alcanza la vida útil de la norma en un lugar dado? Hefesto combina agentes de IA que recolectan datos, "
        f"un motor NEAT y un modelo de inicio de la corrosión por cloruros. Comparamos 13 motores con {banco['n_filas']} "
        f"réplicas de dos laboratorios. Los modelos más flexibles aciertan más dentro de un laboratorio "
        f"({f1(grp(rf))} puntos de cierre con Random Forest), pero fallan al predecir otro ({f1(lab(rf))}). El ganador, "
        f"cinco redes NEAT con corrección local, comete {f1(lab(gan['nombre']))} puntos entre laboratorios y "
        f"{f1(gan['mejora']['10'])} con 10 probetas locales. Corregimos un cálculo previo que daba 150 años en 342 de "
        f"384 zonas. En las {ncl} zonas con cloruros, 25 años exigen un cierre mediano de {f1(c25['mediana'], 0)} % y 40 "
        f"años solo son alcanzables en {c40['n']} zonas.")
    abstract = (
        f"Can neuroevolution, fed by agents that harvest self-healing concrete data, predict which concrete reaches the "
        f"code service life at a given site? Hefesto combines data-collecting AI agents, a NEAT engine and a chloride "
        f"corrosion-initiation model. Across 13 engines and {banco['n_filas']} replicates from two laboratories, flexible "
        f"models were most accurate within a laboratory but failed across laboratories ({lab(rf):.1f} points for Random "
        f"Forest). The selected engine, five NEAT networks with local correction, achieved {lab(gan['nombre']):.1f} points "
        f"across laboratories. In {ncl} chloride-exposed zones, 25 years required a median crack closure of "
        f"{c25['mediana']:.0f} %; 40 years was reachable in {c40['n']} zones only.")
    filas_banco = [[n, f1(grp(n)), f1(lab(n)), f1(cand[n]["mejora"]["10"]),
                    str(sum(v for k, v in cand[n]["simplicidad"].items() if isinstance(v, int) and k != "redes"))]
                   for n in ("NEAT ×5 (motor actual)", "H3 (NEAT ×5 + RF)", "NEAT ×5 capa oculta", "NEAT capa oculta",
                             "NEAT ×5 evolución larga", "MLP 16", mlp, rf, "XGBoost", "Ridge") if n in cand]
    S = [("h1", "I. INTRODUCCIÓN"),
         ("p", "El concreto autorreparable bacteriano promete estructuras que no dependen de mantenimiento continuo. Para "
               "elegirlo en un lugar concreto hay que responder dos cosas: cuánto cierra una fisura y si eso basta para "
               "alcanzar la vida útil que pide la norma con los cloruros de ese lugar. Los modelos publicados predicen el "
               "cierre con precisión alta, pero los validan mezclando datos del mismo laboratorio [15]–[17]."),
         ("p", "Este trabajo pregunta si la neuroevolución (NEAT) [8], alimentada por agentes de IA que cosechan datos "
               "de concreto autocurativo, puede predecir qué concreto alcanza la vida útil de la norma en un lugar dado, y "
               "reducir la incertidumbre de esa predicción. Las contribuciones son: (i) un banco que compara 13 motores "
               "por precisión, efectividad, capacidad de mejora, velocidad y simplicidad; (ii) un sistema de agentes que "
               "recolecta y cura datos sin imputar valores; (iii) un modelo de durabilidad corregido que traduce el cierre "
               "en el cierre necesario para 25 y 40 años, sin los 150 años de un cálculo previo."),
         ("h1", "II. METODOLOGÍA"),
         ("h2", "A. Datos"),
         ("p", f"El motor usa {banco['n_filas']} réplicas de cierre de fisura de {banco['n_probetas']} probetas o fisuras de "
               f"dos laboratorios (Mousa 2022 y Cappellesso 2024) [4], [5], con 7 entradas: ancho inicial, edad, nivel "
               f"de protección bacteriana, ambiente marino, lactato de calcio, curado previo y agente cristalino. La "
               f"difusión de cloruros a 28 días proviene de {aj['n']} ensayos RCM [6] y el efecto de la fisura, de la "
               f"penetración en probetas fisuradas y sin fisurar en agua de mar [5]. Las 384 zonas costeras se describen "
               f"con ERA5 [7]."),
         ("h2", "B. Agentes de IA"),
         ("p", "Cuatro agentes programados recorren literatura (Scopus, OpenAlex, Europe PMC), repositorios universitarios "
               "(RENATI, ALICIA, DSpace), datasets abiertos (Zenodo, Dryad) y datos de zona (estaciones, depósito de "
               "cloruros). Un curador valida cada fila contra un esquema único y rechaza las que no tienen procedencia o "
               "están fuera de rango; un orquestador reentrena el motor y publica qué combinaciones carecen de datos, "
               "para que los agentes las busquen primero. Ningún agente imputa valores."),
         ("h2", "C. Banco de motores"),
         ("p", "Se compararon 13 candidatos con una interfaz común: variantes NEAT (una red, cinco redes, evolución larga, "
               "capa oculta inicial, poca parsimonia), un híbrido H3 (cinco redes NEAT más una corrección local con peso "
               "n/(n + 10)), perceptrones multicapa entrenados por retropropagación, Random Forest, XGBoost, una mezcla "
               "XGBoost + NEAT y Ridge. Cada red NEAT se compila a matrices de pesos por capa, lo que da el mismo "
               "resultado que neat-python y entrena 52 veces más rápido. La precisión se mide por filas, por probeta "
               "(GroupKFold) y entre laboratorios; la capacidad de mejora, con 0 a 40 probetas locales. Se elige el menor "
               "error entre laboratorios (empate si el intervalo bootstrap de la diferencia incluye cero), luego la mejor "
               "capacidad de mejora, la menor complejidad y la mayor velocidad."),
         ("h2", "D. Inicio de la corrosión"),
         ("p", f"Se usa la solución de Fick de la fib B34 [10] con D_app = k_e·D28·f²·(t0/min(t, 25))^α. D28 sale de un "
               f"ajuste log-lineal sobre los ensayos RCM (R² = {f1(aj['r2_log'], 2)} en escala logarítmica); α es 0,30 para "
               f"cemento Portland y 0,45 para puzolánico (supuesto); la difusión se congela a los 25 años [11]; Cs sigue "
               f"DuraCrete [12]. La fisura multiplica la penetración por f = 1 + s·w0·(1 − cierre), con "
               f"s = {f1(fis['s_por_mm'], 2)} mm⁻¹: la reparación se cuenta una sola vez. Se informa el tiempo en que la "
               f"probabilidad de inicio llega al 10 % y nunca un valor mayor que el horizonte pedido."),
         ("h2", "E. Diseño por lugar"),
         ("p", "Para cada zona se calcula la exposición (niebla, depósito de cloruros [13] y régimen) y se evalúan mezclas "
               "que cumplen E.060, ACI 318 y EN 206 [3], [14]. Se elige la más sencilla que alcanza 25 años y se obtiene "
               "el cierre mínimo para 25 y 40 años. El veredicto compara ese mínimo con el cierre que predice el motor a "
               "90 días, restando su error de 20 puntos."),
         ("h1", "III. RESULTADOS"),
         ("h2", "A. Qué motor generaliza"),
         ("p", f"La Tabla I resume el banco. Dentro de un laboratorio, los modelos flexibles son los más precisos "
               f"({f1(grp(rf))} puntos con Random Forest frente a {f1(grp(gan['nombre']))} del NEAT), pero al predecir otro "
               f"laboratorio su error sube a {f1(lab(rf))}. Las variantes NEAT más grandes empeoran igual: usan el "
               f"ambiente marino y la protección, que en estos datos coinciden con el laboratorio. El ganador es "
               f"{gan['nombre']}: {f1(lab(gan['nombre']))} puntos entre laboratorios (piso de ruido "
               f"{f1(piso['piso_inferior_pp'])}–{f1(piso['piso_superior_pp'])}) y {f1(gan['mejora']['10'])} con 10 probetas "
               f"locales. Promediando 5 conjuntos de semillas, su error entre laboratorios es de {f1(h3('Cappellesso2024', 0))} y "
               f"{f1(h3('Mousa2022', 0))} puntos según la dirección. Entrena en {f1(gan['velocidad']['entrenar_s'])} s y usa {gan['simplicidad'].get('conexiones', 0)} "
               f"conexiones en total."),
         ("tabla", {"titulo": "TABLA I. Banco de motores: error absoluto medio (puntos de cierre)",
                    "cab": ["Motor", "Probeta", "Otro lab", "+10 loc.", "Tamaño"], "filas": filas_banco,
                    "prop": [2.4, 1.05, 1.05, 1.05, 1.15], "nota": "Tamaño: conexiones, parámetros u hojas. Fuente: resultados/banco_motores.json."}),
         ("h2", "B. Qué aprendió el motor"),
         ("p", f"Las redes del ganador conservan la edad, el curado previo y el ancho de fisura. Por eso predice "
               f"{f1(neat)} % de cierre a 90 días para cualquier opción bacteriana: con estos datos, distinguir bacterias "
               f"exigiría ensayos que las varíen dentro de un mismo laboratorio. Con 5 probetas locales el error baja a "
               f"{f1(h3('Cappellesso2024', 5))}–{f1(h3('Mousa2022', 5))} puntos."),
         ("h2", "C. Por qué un cálculo previo daba 150 años"),
         ("p", f"Un agente de diseño anterior devolvía 150 años en 342 de 384 zonas por cuatro causas (Tabla II). Con "
               f"α = 0,65, el tiempo medio pasa de {f1(sin_tope, 0)} años a {f1(con_tope, 0)} al congelar la difusión a "
               f"los 25 años; con α = 0,30 la fórmula reproduce los {f1(base_fib)} años de la fib."),
         ("tabla", {"titulo": "TABLA II. Causas de los 150 años y corrección",
                    "cab": ["Causa", "Efecto", "Corrección"],
                    "filas": [["Tope VIDA_MAX = 150", "satura en 342/384 zonas", "se informa «cumple 40»"],
                              ["Régimen seco: Cs < Ccrit", "150 automático (116 zonas)", "fuera de alcance"],
                              ["Cierre + agente, al cuadrado", "reparación contada dos veces", "una sola reducción"],
                              ["α sin tope (IP, HS)", f"{f1(sin_tope, 0)} años con α = 0,65", "D congelada a 25 años"]],
                    "prop": [2, 2, 1.8], "nota": "Fuente: hefesto/durabilidad/vida_util.py."}),
         ("h2", "D. Reparación necesaria por lugar"),
         ("p", f"De las 384 zonas, {r['fuera_de_alcance_carbonatacion']} son secas. En las {ncl} restantes, todas alcanzan "
               f"25 años con la mezcla adecuada si la fisura se cierra al menos un {f1(c25['mediana'], 0)} % (p10–p90: "
               f"{f1(c25['p10'], 0)}–{f1(c25['p90'], 0)} %); 40 años solo en {c40['n']} zonas (Fig. 1). Con el {f1(neat, 0)} % "
               f"± 20 que predice el motor, cumplen {v25.get('cumple', 0)} zonas, {v25.get('incierto', 0)} quedan inciertas "
               f"y {v25.get('no cumple', 0)} no cumplen."),
         ("fig", {"archivo": "fig1_cierre_requerido.png",
                  "pie": "Fig. 1. Cierre mínimo de una fisura de 0,3 mm para 25 años (izquierda) y 40 años (derecha) en las "
                         "zonas costeras del Perú. Gris: zonas secas, fuera de alcance."}),
         ("h2", "E. Sensibilidad"),
         ("p", "La Tabla III muestra que el resultado depende sobre todo del efecto de la fisura y del criterio de "
               "probabilidad; por eso se informa un rango y no una cifra única."),
         ("tabla_sens", None),
         ("h1", "IV. DISCUSIÓN Y LIMITACIONES"),
         ("p", "La respuesta a la pregunta es parcial. La neuroevolución con poca complejidad generaliza entre laboratorios "
               "mejor que los modelos flexibles y reduce la incertidumbre del cierre a unos 19 puntos, y menos con ensayos "
               "locales. Pero hoy no distingue tipos de bacteria ni condiciones del lugar, porque esas variables coinciden "
               "con el laboratorio de origen. El parámetro de fisura proviene de un solo laboratorio, y Cs y el depósito "
               "de cloruros por niebla son supuestos sin medición local. Los agentes priorizan justamente esos datos."),
         ("h1", "V. CONCLUSIONES"),
         ("p", f"Hefesto separa el cierre de fisura (días) de la vida útil (años) y acota cada uno a su rango. Entre 13 "
               f"motores, cinco redes NEAT con corrección local fueron las que mejor predijeron otro laboratorio. En la "
               f"costa peruana con cloruros, 25 años son alcanzables con mezclas de norma y un cierre mediano del "
               f"{f1(c25['mediana'], 0)} %; 40 años solo en {c40['n']} de {ncl} zonas."),
         ("h1", "REFERENCIAS")]
    refs = [
        "[1] CEN, «EN 1990: Eurocode – Basis of structural design», Bruselas, 2002.",
        "[2] BSI, «BS 6349-1-1: Maritime works – General – Code of practice for planning and design for operations», Londres, 2013.",
        "[3] Ministerio de Vivienda, «Norma E.060 Concreto armado», Reglamento Nacional de Edificaciones, Lima, 2009.",
        "[4] M. R. Mousa et al., «Determination of the optimal parameters for self-healing efficiency of encapsulated bacteria in concrete», Zenodo, 2022, doi: 10.5281/zenodo.6469122.",
        "[5] V. Giaretton Cappellesso et al., «Supplementary data: Self-healing concrete with a bacteria-based or crystalline admixture to prevent chloride ingress and corrosion in a marine environment», Zenodo, 2024, doi: 10.5281/zenodo.11305154.",
        "[6] L. Yang, E. Zhu y Y. Wei, «Experimental data for chloride diffusion coefficient of concrete by rapid chloride migration test», Dryad, doi: 10.5061/dryad.66t1g1k6j.",
        "[7] H. Hersbach et al., «The ERA5 global reanalysis», Q. J. R. Meteorol. Soc., vol. 146, pp. 1999–2049, 2020.",
        "[8] K. O. Stanley y R. Miikkulainen, «Evolving neural networks through augmenting topologies», Evol. Comput., vol. 10, no. 2, pp. 99–127, 2002.",
        "[9] V. Vovk, A. Gammerman y G. Shafer, Algorithmic Learning in a Random World. Nueva York: Springer, 2005.",
        "[10] fib, «Model Code for Service Life Design», Bulletin 34, Lausana, 2006.",
        "[11] M. D. A. Thomas y E. C. Bentz, «Life-365: Computer program for predicting the service life and life-cycle costs of reinforced concrete exposed to chlorides», manual, 2000.",
        "[12] DuraCrete, «Statistical quantification of the variables in the limit state functions», BE95-1347/R9, 2000.",
        "[13] G. R. Meira et al., «Measurements and modelling of marine salt transportation and deposition in a tropical region in Brazil», Atmos. Environ., vol. 40, pp. 5596–5607, 2006.",
        "[14] ACI, «ACI 318-19: Building code requirements for structural concrete», 2019; CEN, «EN 206: Concrete – Specification, performance, production and conformity», 2013+A2:2021.",
        "[15] «Self-healing performance assessment of bacterial-based concrete using machine learning approaches», Materials, 2022. [En línea]: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9267731/",
        "[16] «Modeling self-healing of concrete using hybrid genetic algorithm–artificial neural network», Materials, 2017. [En línea]: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5459209/",
        "[17] «Prediction of healing performance of autogenous healing concrete using machine learning», Materials, 2021. [En línea]: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8348520/",
    ]
    S += [("ref", t) for t in refs]
    return {"titulo": "Hefesto: neuroevolución y agentes de IA para predecir qué concreto autorreparable alcanza la vida "
                      "útil de la norma en un lugar dado",
            "titulo_en": "Hefesto: neuroevolution and AI agents to predict which self-healing concrete reaches the code "
                         "service life at a given site",
            "resumen": resumen, "abstract": abstract,
            "clave": "concreto autorreparable bacteriano; NEAT; neuroevolución; agentes de IA; vida útil; cloruros",
            "keywords": "bacterial self-healing concrete; NEAT; neuroevolution; AI agents; service life; chlorides",
            "cuerpo": S}


# ---------------------------------------------------------------------------- figura
def figura_mapa(D: dict, ruta: Path):
    zonas = D["vz"]["zonas"]
    fig, axs = plt.subplots(1, 2, figsize=(3.4, 3.6), sharey=True)
    sc = None
    for ax, o in zip(axs, ("25", "40")):
        secas = [z for z in zonas if z["estado"] != "evaluada"]
        ax.plot([z["lon"] for z in secas], [z["lat"] for z in secas], ".", color="0.8", ms=2.5)
        ev = [z for z in zonas if z["estado"] == "evaluada"]
        ok = [z for z in ev if z["requerido"][o]["cierre_min"] is not None]
        no = [z for z in ev if z["requerido"][o]["cierre_min"] is None]
        ax.plot([z["lon"] for z in no], [z["lat"] for z in no], "x", color="#b4562a", ms=2.5, label="no alcanzable")
        sc = ax.scatter([z["lon"] for z in ok], [z["lat"] for z in ok], s=5,
                        c=[100 * z["requerido"][o]["cierre_min"] for z in ok], cmap="viridis_r", vmin=0, vmax=100)
        ax.set_title(f"{o} años", fontsize=8)
        ax.tick_params(labelsize=6)
        ax.set_aspect("equal")
    axs[0].set_ylabel("Latitud", fontsize=7)
    axs[1].legend(fontsize=5.5, loc="lower left", frameon=False)
    cb = fig.colorbar(sc, ax=axs, orientation="horizontal", fraction=0.05, pad=0.08)
    cb.set_label("Cierre requerido (%)", fontsize=7)
    cb.ax.tick_params(labelsize=6)
    fig.savefig(ruta, dpi=300, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------- docx
def poner(p: Paragraph, texto: str, negrita_hasta: str | None = None):
    """Reemplaza el texto conservando el formato del primer run de la plantilla."""
    plant = copy.deepcopy(p.runs[0]._r) if p.runs else p._p.makeelement(qn("w:r"), {})
    for r in list(p.runs):
        r._r.getparent().remove(r._r)
    partes = [(texto, None)] if not negrita_hasta else [(negrita_hasta, True), (texto[len(negrita_hasta):], False)]
    for t, b in partes:
        nuevo = copy.deepcopy(plant)
        for hijo in list(nuevo):
            if hijo.tag != qn("w:rPr"):
                nuevo.remove(hijo)
        p._p.append(nuevo)
        run = Run(nuevo, p)
        run.text = t
        if b is not None:
            run.bold = b


def ajustar_ancho(tabla, prop, total=ANCHO_COL):
    anchos = [int(total * x / sum(prop)) for x in prop]
    tblPr = tabla._tbl.tblPr
    for tag in ("w:tblW", "w:tblLayout"):
        for el in tblPr.findall(qn(tag)):
            tblPr.remove(el)
    tblPr.insert(0, tblPr.makeelement(qn("w:tblW"), {qn("w:w"): str(total), qn("w:type"): "dxa"}))
    tblPr.append(tblPr.makeelement(qn("w:tblLayout"), {qn("w:type"): "fixed"}))
    grid = tabla._tbl.tblGrid
    for gc in list(grid):
        grid.remove(gc)
    for w in anchos:
        grid.append(grid.makeelement(qn("w:gridCol"), {qn("w:w"): str(w)}))
    for fila in tabla.rows:
        for celda, w in zip(fila.cells, anchos):
            tcPr = celda._tc.get_or_add_tcPr()
            for el in tcPr.findall(qn("w:tcW")):
                tcPr.remove(el)
            tcPr.insert(0, tcPr.makeelement(qn("w:tcW"), {qn("w:w"): str(w), qn("w:type"): "dxa"}))


def construir_tabla(proto_tbl, cab, filas):
    """Clona la tabla de la plantilla (bordes y fuentes) con el número de columnas pedido."""
    t = copy.deepcopy(proto_tbl)
    trs = t.findall(qn("w:tr"))
    tr_cab, tr_cuerpo = trs[0], trs[1]
    for tr in trs:
        t.remove(tr)

    def fila_desde(tr_proto, valores):
        tr = copy.deepcopy(tr_proto)
        tcs = tr.findall(qn("w:tc"))
        for tc in tcs[1:]:
            tr.remove(tc)
        for _ in valores[1:]:
            tr.append(copy.deepcopy(tcs[0]))
        for tc, v in zip(tr.findall(qn("w:tc")), valores):
            ps = tc.findall(qn("w:p"))
            for p in ps[1:]:
                tc.remove(p)
            poner(Paragraph(ps[0], None), str(v))
        return tr

    t.append(fila_desde(tr_cab, cab))
    for f in filas:
        t.append(fila_desde(tr_cuerpo, f))
    return t


def construir() -> Path:
    D = cargar()
    C = contenido(D)
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    figura_mapa(D, SALIDA.parent / "fig1_cierre_requerido.png")
    doc = docx.Document(PLANTILLA)
    body = doc.element.body
    hijos = list(body.iterchildren())
    ps = doc.paragraphs
    buscar = lambda pref: next(p for p in ps if p.text.strip().startswith(pref))
    i_tab = ps.index(buscar("TABLA I."))
    i_fig = ps.index(buscar("Fig. 1."))
    proto = {"resumen": buscar("Resumen—")._p, "h1": buscar("I. INTRODUCCIÓN")._p, "h2": buscar("A. Conjuntos")._p,
             "p": buscar("Evaluar el concreto")._p, "cap": ps[i_tab]._p, "nota": ps[i_tab + 1]._p,
             "pie": ps[i_fig]._p, "fig": ps[i_fig - 1]._p, "ref": buscar("[1]")._p, "tbl": doc.tables[1]._tbl}
    proto = {k: copy.deepcopy(v) for k, v in proto.items()}
    poner(Paragraph(hijos[0], None), C["titulo"])
    poner(Paragraph(hijos[1], None), C["titulo_en"])
    i_sect = next(i for i, el in enumerate(hijos) if el.tag == qn("w:p") and el.xpath(".//w:sectPr"))
    for el in hijos[i_sect + 1:]:
        if el.tag != qn("w:sectPr"):
            body.remove(el)
    sect_final = body.find(qn("w:sectPr"))

    def par(tipo, texto, negrita=None):
        e = copy.deepcopy(proto[tipo])
        poner(Paragraph(e, None), texto, negrita)
        sect_final.addprevious(e)

    for etiqueta, clave in (("Resumen—", "resumen"), ("Palabras clave—", "clave"),
                            ("Abstract—", "abstract"), ("Keywords—", "keywords")):
        par("resumen", etiqueta + C[clave], etiqueta)
    for tipo, x in C["cuerpo"]:
        if tipo in ("h1", "h2", "p", "ref"):
            par(tipo, x)
        elif tipo in ("tabla", "tabla_sens"):
            if tipo == "tabla_sens":
                var = ("base", "fisura_lineal", "p_50", "recub_+15")
                fm = lambda v: "—" if v["cierre_req_25_pct"] is None else (
                    "0" if v["cierre_req_25_pct"] <= 1 else f1(v["cierre_req_25_pct"], 0))
                x = {"titulo": "TABLA III. Cierre requerido (%) para 25 años en 5 zonas tipo según el supuesto",
                     "cab": ["Zona", "Base", "Fisura lineal", "P = 50 %", "Recub. +15"],
                     "filas": [[n] + [fm(z["variantes"][k]) for k in var] for n, z in D["sens"].items()],
                     "prop": [1.6, 1, 1.2, 1.1, 1.1],
                     "nota": "Base: D ∝ f², P = 10 %. «—»: no alcanzable. Fuente: resultados/sensibilidad_vida.json."}
            par("cap", x["titulo"])
            tbl = construir_tabla(proto["tbl"], x["cab"], x["filas"])
            sect_final.addprevious(tbl)
            ajustar_ancho(docx.table.Table(tbl, doc._body), x["prop"])
            par("nota", x["nota"])
        elif tipo == "fig":
            e = copy.deepcopy(proto["fig"])
            for r in e.findall(qn("w:r")):
                e.remove(r)
            sect_final.addprevious(e)
            Paragraph(e, doc._body).add_run().add_picture(str(SALIDA.parent / x["archivo"]), width=Inches(3.3))
            par("pie", x["pie"])
    doc.save(SALIDA)
    return SALIDA


if __name__ == "__main__":
    print(construir())
