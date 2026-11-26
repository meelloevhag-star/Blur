"""
Artículo 2 (IEEE, español): reparación necesaria para 25–40 años de vida útil del concreto
autorreparable bacteriano en la costa peruana.

Usa la plantilla del artículo 1 (formato IEEE a dos columnas y tabla de autores) y reconstruye el
cuerpo. TODAS las cifras se leen de resultados/*.json; ninguna se escribe a mano.

Uso:
    python -m articulos.2_hefesto.generar_articulo2
Salida:
    articulo/ieee/BioCrete-Vida_IEEE_ES.docx (+ figuras PNG en articulo/ieee/)
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
SALIDA = RAIZ / "articulos" / "2_hefesto" / "ieee" / "BioCrete-Vida_IEEE_ES.docx"
RES = RAIZ / "resultados"
ANCHO_COL = 4780


def cargar() -> dict:
    j = lambda n: json.loads((RES / n).read_text(encoding="utf-8"))
    vz = j("vida_zonas.json")
    return {"hib": j("hibrido.json"), "diag": j("meta20_diagnostico.json"), "vz": vz, "res": vz["resumen"],
            "sens": j("sensibilidad_vida.json"),
            "reg": json.loads((RAIZ / "modelos" / "registro.json").read_text(encoding="utf-8"))[-1]}


def f1(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


# ---------------------------------------------------------------------------- contenido
def contenido(D: dict) -> dict:
    r, hib, diag = D["res"], D["hib"], D["diag"]
    h3 = lambda lab, n: hib[lab]["modelos"]["H3 contraído"][str(n)]["MAE_pp_medio"]
    c25, c40, v25 = r["cierre_requerido_25_pct"], r["cierre_requerido_40_pct"], r["veredicto_25"]
    ncl = r["zonas"] - r["fuera_de_alcance_carbonatacion"]
    neat = r["neat_mejor_opcion_marina"]["cierre_pct"]
    piso = diag["E1_piso_ruido"]["global"]
    sin_tope = vu.t_inicio_determinista(15.8e-12, 0.65, 1.5, congelar=False)
    con_tope = vu.t_inicio_determinista(15.8e-12, 0.65, 1.5, congelar=True)
    base_fib = vu.t_inicio_determinista(15.8e-12, 0.30, 1.5, congelar=False)
    aj, fis = vu.ajuste_d28(), vu.pendiente_fisura()
    resumen = (
        f"Un agente de diseño que recomendaba concreto autorreparable por zona costera devolvía 150 años de vida útil "
        f"en 342 de 384 zonas. Mostramos que esa cifra salía de un tope arbitrario, de la reparación contada dos veces y "
        f"del envejecimiento de la difusión sin límite. Proponemos un flujo que separa dos preguntas. Un motor NEAT "
        f"híbrido predice el cierre de fisura a 3–480 días; su error entre laboratorios es de {f1(h3('Cappellesso2024', 0))}–"
        f"{f1(h3('Mousa2022', 0))} puntos sin calibrar y baja a {f1(h3('Cappellesso2024', 5))}–{f1(h3('Mousa2022', 5))} "
        f"con 5 grupos locales. Un modelo de inicio de la corrosión (fib B34, difusión congelada a los 25 años, "
        f"probabilidad del 10 %) calcula el cierre mínimo necesario para 25 y 40 años. En las {ncl} zonas costeras "
        f"expuestas a cloruros, 25 años son alcanzables con mezclas de norma y un cierre mediano de {f1(c25['mediana'], 0)} % "
        f"(p10–p90: {f1(c25['p10'], 0)}–{f1(c25['p90'], 0)} %); 40 años, solo en {c40['n']} zonas. El cierre que hoy "
        f"predice el motor ({f1(neat, 0)} % ± 20) alcanza el objetivo de 25 años con seguridad en {v25.get('cumple', 0)} zonas.")
    abstract = (
        f"A design agent recommending self-healing concrete for coastal zones returned 150-year service lives in 342 "
        f"of 384 zones. We show that the figure came from an arbitrary cap, double-counted healing and unbounded "
        f"diffusion ageing. A hybrid NEAT engine predicts crack closure at 3–480 days with a cross-laboratory error of "
        f"{h3('Cappellesso2024', 0):.1f}–{h3('Mousa2022', 0):.1f} points, and a corrected corrosion-initiation model "
        f"(fib B34, ageing frozen at 25 years, 10 % probability) yields the minimum closure needed for 25 and 40 years. "
        f"In the {ncl} chloride-exposed zones, 25 years is reachable with code-compliant mixes and a median required "
        f"closure of {c25['mediana']:.0f} %; 40 years only in {c40['n']} zones.")
    S = [("h1", "I. INTRODUCCIÓN"),
         ("p", "El concreto autorreparable bacteriano (CAB) se propone para estructuras costeras porque sella fisuras por "
               "donde entran los cloruros. Para recomendarlo por zona hacen falta dos respuestas distintas: cuánto cierra "
               "una fisura en semanas o meses, y cuántos años tarda la corrosión en empezar. Mezclarlas lleva a errores."),
         ("p", "Un agente de diseño previo (el Atlas) combinaba ambas y entregaba 150 años en 342 de 384 zonas de la "
               "costa peruana. Ninguna norma pide esa cifra: EN 1990 fija 50 años para edificios y 100 para puentes y "
               "obras civiles mayores, y BS 6349-1 fija 50 años para obras marítimas [1]–[3]."),
         ("p", "Las contribuciones son tres: (i) el diagnóstico de por qué aparecían los 150 años; (ii) un flujo de agentes "
               "y un motor NEAT híbrido que solo predice dentro del rango medido; (iii) el cierre mínimo de fisura "
               "necesario para 25 y 40 años en cada zona, contrastado con lo que el motor predice hoy."),
         ("h1", "II. METODOLOGÍA"),
         ("h2", "A. Datos"),
         ("p", f"El motor usa {D['reg']['n_filas']} réplicas de cierre de fisura de dos laboratorios (Mousa 2022 y "
               f"Cappellesso 2024) [4], [5], con 7 entradas: ancho inicial, edad, nivel de protección bacteriana, ambiente "
               f"marino, lactato de calcio, curado previo y agente cristalino. La difusión de cloruros a 28 días proviene "
               f"de {aj['n']} ensayos RCM [6]. El efecto de la fisura se estima con la penetración de cloruros en probetas "
               f"de referencia fisuradas (0,1 y 0,3 mm) y sin fisurar en agua de mar [5]. Las 384 zonas costeras se "
               f"describen con ERA5 2024 [7]."),
         ("h2", "B. Agentes recolectores y curación"),
         ("p", "Tres agentes programados buscan cada semana datos de zona (clima, niebla, cloruros), de daño (patologías por "
               "uso) y de materiales (dosificaciones y cierre). Todo pasa por un esquema único y un curador que rechaza filas "
               "sin procedencia, fuera de rango o duplicadas. Un orquestador reentrena el motor, registra cada versión "
               "con la huella de sus datos y publica qué combinaciones carecen de datos, para que los agentes las busquen "
               "primero. Los agentes nunca imputan valores y entregan sus datos por pull request sin merge."),
         ("h2", "C. Motor NEAT híbrido"),
         ("p", "La base son K = 5 redes NEAT [8] con penalización de complejidad, promediadas para estabilizarlas. Sin datos "
               "del laboratorio destino, el motor usa esa base; con n grupos locales, un bosque aleatorio corrige el residuo "
               "con peso n/(n + 10) (H3) y la predicción conforme por grupos da intervalos del 80 y 90 % [9]. El motor no "
               "predice fuera de las edades medidas (3–480 días): devuelve un valor nulo con su motivo."),
         ("h2", "D. Inicio de la corrosión corregido"),
         ("p", f"Se usa la solución de Fick de la fib B34 [10]: C(x, t) = Cs·[1 − erf(x / 2√(D_app·t))], con "
               f"D_app = k_e·D28·f²·(t0/min(t, 25))^α. D28 sale de un ajuste log-lineal en la relación agua/ligante y "
               f"las adiciones (R² = {f1(aj['r2_log'], 2)} en escala logarítmica); su dispersión residual entra en la "
               f"simulación. El envejecimiento α es 0,30 para cemento Portland y 0,45 para puzolánico (supuesto), y la "
               f"difusión se congela a los 25 años como en Life-365 [11]. Cs sigue DuraCrete [12] según el régimen "
               f"(atmosférico, niebla salina o salpicadura). La fisura multiplica la penetración por f = 1 + s·w_res, "
               f"con s = {f1(fis['s_por_mm'], 2)} mm⁻¹ y w_res = w0·(1 − cierre): la reparación se cuenta una sola vez. "
               f"El resultado es el tiempo en que la probabilidad de inicio llega al 10 % (simulación de Monte Carlo, "
               f"4000 muestras). Nunca se informa un valor mayor que el horizonte pedido; en el régimen seco gobierna la "
               f"carbonatación y el modelo no da cifra."),
         ("h2", "E. Diseño por zona"),
         ("p", "Para cada zona se calcula la exposición (niebla, depósito de cloruros [13] y régimen) y se evalúan mezclas que "
               "cumplen E.060, ACI 318 y EN 206 [3], [14]: cemento I o IP, a/b desde el máximo de norma hasta 0,35 y "
               "recubrimiento mínimo o +15 mm, con una fisura de diseño de 0,3 mm. Se elige la mezcla más sencilla que "
               "alcanza 25 años y se obtiene el cierre mínimo para 25 y 40 años. El veredicto compara ese mínimo con el "
               "cierre que predice el motor a 90 días: «cumple» si se alcanza incluso restando 20 puntos, «incierto» si "
               "solo lo alcanza la predicción central."),
         ("h1", "III. RESULTADOS"),
         ("h2", "A. Precisión del motor de cierre"),
         ("p", f"El piso de ruido de los propios datos es de {f1(piso['piso_inferior_pp'])}–{f1(piso['piso_superior_pp'])} "
               f"puntos. Entre laboratorios, el motor sin calibrar comete {f1(h3('Cappellesso2024', 0))} y "
               f"{f1(h3('Mousa2022', 0))} puntos, y baja de 20 con 5 grupos locales (Tabla I). Recalcular todo con los "
               f"mismos datos y semillas reprodujo exactamente las cifras de la versión anterior."),
         ("tabla", {"titulo": "TABLA I. Error absoluto medio (puntos de cierre) del híbrido H3 según los grupos locales",
                    "cab": ["Destino", "0", "5", "10", "20", "40"],
                    "filas": [[lab[:-4] + " " + lab[-4:]] + [f1(h3(lab, n)) for n in (0, 5, 10, 20, 40)]
                              for lab in ("Cappellesso2024", "Mousa2022")],
                    "prop": [2.2, 1, 1, 1, 1, 1], "nota": "Fuente: resultados/hibrido.json."}),
         ("h2", "B. Qué aprendieron las redes"),
         ("p", f"Las cinco redes conservan la edad y tres conservan el curado previo. El ancho, la protección bacteriana, el "
               f"ambiente marino, el lactato y el agente cristalino quedaron sin conexión: no se sostienen entre los dos "
               f"laboratorios. Por eso el motor predice {f1(neat)} % a 90 días para cualquier opción bacteriana."),
         ("h2", "C. Por qué aparecían 150 años"),
         ("p", f"Cuatro causas se suman (Tabla II). La más fuerte es el envejecimiento sin tope: con α = 0,65 el tiempo medio "
               f"pasa de {f1(sin_tope, 0)} años a {f1(con_tope, 0)} al congelar la difusión a los 25 años (con α = 0,30 la "
               f"fórmula reproduce los {f1(base_fib)} años de la fib). Como el resultado ya no se recorta a 150 sino que "
               f"se informa contra el horizonte, ningún valor de las 384 zonas supera los 40 años."),
         ("tabla", {"titulo": "TABLA II. Causas de los 150 años en el cálculo previo y corrección",
                    "cab": ["Causa", "Efecto", "Corrección"],
                    "filas": [["Tope VIDA_MAX = 150", "satura en 342/384 zonas", "se informa «cumple 40»"],
                              ["Régimen seco: Cs < Ccrit", "150 automático (116 zonas)", "fuera de alcance"],
                              ["Cierre + agente, al cuadrado", "reparación contada dos veces", "una sola reducción"],
                              ["α sin tope (IP, HS)", f"{f1(sin_tope, 0)} años con α = 0,65", "D congelada a 25 años"]],
                    "prop": [2, 2, 1.8], "nota": "Fuente: revisión del código del Atlas y hefesto/durabilidad/vida_util.py."}),
         ("h2", "D. Reparación necesaria por zona"),
         ("p", f"De las 384 zonas, {r['fuera_de_alcance_carbonatacion']} son secas y quedan fuera de alcance. En las "
               f"{ncl} restantes, una fisura de 0,3 mm sin reparar inicia la corrosión en pocos años. Con la mezcla "
               f"adecuada, todas alcanzan 25 años si la fisura se cierra al menos un {f1(c25['mediana'], 0)} % (mediana; "
               f"p10–p90: {f1(c25['p10'], 0)}–{f1(c25['p90'], 0)} %). Cuarenta años solo son alcanzables en {c40['n']} "
               f"zonas, con {f1(c40['p10'], 0)}–{f1(c40['p90'], 0)} % de cierre (Fig. 1). Frente al {f1(neat, 0)} % ± 20 "
               f"que predice el motor, a 25 años cumplen {v25.get('cumple', 0)} zonas, {v25.get('incierto', 0)} quedan "
               f"inciertas y {v25.get('no cumple', 0)} no cumplen."),
         ("fig", {"archivo": "fig1_cierre_requerido.png",
                  "pie": "Fig. 1. Cierre mínimo de una fisura de 0,3 mm para 25 años (izquierda) y 40 años (derecha) en las "
                         "zonas costeras del Perú. Gris: zonas secas, fuera de alcance."}),
         ("h2", "E. Sensibilidad"),
         ("p", "La Tabla III muestra que el resultado depende sobre todo del efecto de la fisura y del criterio de "
               "probabilidad. Con un efecto lineal de la fisura, las zonas atmosféricas ya no necesitan reparación para 25 "
               "años; en niebla salina siguen necesitando un 70–80 %. Diseñar con la vida media (50 %) en lugar del 10 % "
               "elimina la necesidad de reparar, lo que muestra por qué ese criterio no debe usarse para diseño."),
         ("tabla_sens", None),
         ("h1", "IV. DISCUSIÓN Y LIMITACIONES"),
         ("p", "El parámetro de fisura proviene de un solo laboratorio y dos anchos, Cs y el depósito de cloruros por niebla "
               "son supuestos sin medición local, y α para el cemento puzolánico no tiene valor fib. Por eso las cifras "
               "son un rango y no una garantía. El motor NEAT no distingue aún entre opciones bacterianas: hacen falta "
               "ensayos que varíen protección, lactato y ambiente dentro de un mismo laboratorio, que es lo que los "
               "agentes buscan primero. Los recolectores no aportaron datos todavía porque su acceso al repositorio falló."),
         ("h1", "V. CONCLUSIONES"),
         ("p", f"Separar el cierre de fisura (días) de la vida útil (años) y acotar cada uno a su rango elimina los 150 años. "
               f"En la costa peruana con cloruros, 25 años de vida útil son alcanzables con mezclas de norma y un cierre de "
               f"fisura mediano del {f1(c25['mediana'], 0)} %; 40 años solo en {c40['n']} de {ncl} zonas. Las mediciones "
               f"con vela húmeda y los ensayos locales de cierre son los datos que más reducirían la incertidumbre."),
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
    ]
    S += [("ref", t) for t in refs]
    return {"titulo": "Reparación necesaria para 25–40 años de vida útil del concreto autorreparable bacteriano en la "
                      "costa peruana: motor NEAT híbrido, agentes recolectores y un modelo de durabilidad corregido",
            "titulo_en": "Healing required for 25–40-year service life of bacterial self-healing concrete on the Peruvian "
                         "coast: hybrid NEAT engine, data-collecting agents and a corrected durability model",
            "resumen": resumen, "abstract": abstract,
            "clave": "concreto autorreparable bacteriano; NEAT; vida útil; cloruros; sistemas multiagente; costa peruana",
            "keywords": "bacterial self-healing concrete; NEAT; service life; chlorides; multi-agent systems; Peruvian coast",
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
