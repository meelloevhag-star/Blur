"""
Contenido compartido del artículo (auditoría de reproducibilidad), en español e inglés.

Produce una lista de bloques independientes del formato:
    ("titulo", txt) ("titulo2", txt) ("resumen", etiqueta, txt) ("claves", etiqueta, txt)
    ("destacados", [txt]) ("h1", txt) ("h2", txt) ("p", txt)
    ("tabla", titulo, filas, nota, proporciones) ("figura", ruta, pie, ancho_ieee)
    ("declaraciones", [txt])
Las citas se escriben como ⟦clave⟧ o ⟦c1,c2⟧ y se numeran por orden de aparición (numerar_citas).
Todas las cifras se leen de los resultados del código.
"""

import csv
import json
import re
from collections import Counter
from pathlib import Path

import docx

from correcciones_referencias import corregir

RAIZ = Path(__file__).resolve().parents[1]
RES = RAIZ / "biocrete_neat" / "resultados"
LIT = RAIZ / "biocrete_neat" / "datos" / "literatura"
ORIGINAL = RAIZ / "articulo" / "original" / "BioCrete-NEAT_v1_original.docx"
REPO_URL = "https://github.com/meelloevhag-star/Blur"

# Claves de las referencias 1–18 del manuscrito original (en su orden).
CLAVES_ORIGINALES = ["cappellesso2024", "doostkami2023", "markov", "hilaloglu2026", "chowdhury2026", "zou2025",
                     "du2026", "stanley2002", "breiman2001", "dryad", "cap_zenodo", "mousa_zenodo", "ghent_zenodo",
                     "jonkers2010", "luo2015", "wiktor2011", "khan2021", "xiao2025"]
REFS_NUEVAS = {
    "chen2016": "T. Chen and C. Guestrin, “XGBoost: A scalable tree boosting system,” in Proc. 22nd ACM SIGKDD Int. "
                "Conf. Knowl. Discov. Data Min., 2016, pp. 785–794, doi: 10.1145/2939672.2939785.",
    "lundberg2017": "S. M. Lundberg and S.-I. Lee, “A unified approach to interpreting model predictions,” in Adv. "
                    "Neural Inf. Process. Syst., vol. 30, 2017, pp. 4765–4774.",
    "parisi2019": "G. I. Parisi, R. Kemker, J. L. Part, C. Kanan, and S. Wermter, “Continual lifelong learning with "
                  "neural networks: A review,” Neural Netw., vol. 113, pp. 54–71, 2019, doi: "
                  "10.1016/j.neunet.2019.01.012.",
    "kapoor2023": "S. Kapoor and A. Narayanan, “Leakage and the reproducibility crisis in machine-learning-based "
                  "science,” Patterns, vol. 4, no. 9, Art. no. 100804, 2023, doi: 10.1016/j.patter.2023.100804.",
    "varma2006": "S. Varma and R. Simon, “Bias in error estimation when using cross-validation for model selection,” "
                 "BMC Bioinformatics, vol. 7, Art. no. 91, 2006, doi: 10.1186/1471-2105-7-91.",
    "nadeau2003": "C. Nadeau and Y. Bengio, “Inference for the generalization error,” Mach. Learn., vol. 52, no. 3, "
                  "pp. 239–281, 2003, doi: 10.1023/A:1024068626366.",
    "palin2017": "D. Palin, V. Wiktor, and H. M. Jonkers, “A bacteria-based self-healing cementitious composite for "
                 "application in low-temperature marine environments,” Biomimetics, vol. 2, no. 3, Art. no. 13, 2017, "
                 "doi: 10.3390/biomimetics2030013.",
    "zhuang2019": "X. Zhuang and S. Zhou, “The prediction of self-healing capacity of bacteria-based concrete using "
                  "machine learning approaches,” Comput. Mater. Contin., vol. 59, no. 1, pp. 57–77, 2019, doi: "
                  "10.32604/cmc.2019.04589.",
    "huang2022": "X. Huang, J. Sresakoolchai, X. Qin, Y. F. Ho, and S. Kaewunruen, “Self-healing performance "
                 "assessment of bacterial-based concrete using machine learning approaches,” Materials, vol. 15, "
                 "no. 13, Art. no. 4436, 2022, doi: 10.3390/ma15134436.",
    "pessoa2023": "C. L. E. Pessoa, V. H. Peres Silva, and R. Stefani, “Prediction of the self-healing properties of "
                  "concrete modified with bacteria and fibers using machine learning,” Asian J. Civ. Eng., vol. 25, "
                  "pp. 1801–1810, 2024, doi: 10.1007/s42107-023-00878-w.",
    "tian2024": "Q. Tian et al., “Exploring the viability of AI-aided genetic algorithms in estimating the crack "
                "repair rate of self-healing concrete,” Rev. Adv. Mater. Sci., vol. 63, Art. no. 20230179, 2024, "
                "doi: 10.1515/rams-2023-0179.",
    "lou2024": "Y. Lou et al., “Predicting the crack repair rate of self-healing concrete using soft-computing tools,” "
               "Mater. Today Commun., vol. 38, Art. no. 108043, 2024, doi: 10.1016/j.mtcomm.2024.108043.",
    "khosravi2025": "H. Khosravi, P. Kiani, M. Bahram, and M. Lezgy-Nazargah, “Prediction of crack repair percentage "
                    "in self-healing concrete using machine learning,” Sci. Rep., vol. 16, Art. no. 533, 2025, doi: "
                    "10.1038/s41598-025-30158-3.",
}


def referencias_base() -> dict:
    d = docx.Document(str(ORIGINAL))
    textos = [corregir(re.sub(r"^\[\d+\]\s*", "", p.text).strip()) for p in d.paragraphs if re.match(r"^\[\d+\]", p.text)]
    return {**dict(zip(CLAVES_ORIGINALES, textos)), **REFS_NUEVAS}


def cifras() -> dict:
    r = json.loads((RES / "revision" / "resumen_revision.json").read_text(encoding="utf-8"))
    zen = json.loads((RES / "resumen_datasets_reales_zenodo.json").read_text(encoding="utf-8"))
    with open(LIT / "verificacion_meta_original.csv", encoding="utf-8") as fh:
        ver = list(csv.DictReader(fh))
    with open(LIT / "catalogo_literatura.csv", encoding="utf-8") as fh:
        cat = list(csv.DictReader(fh))
    return {"r": r, "zen": zen, "estados": Counter(v["estado"] for v in ver), "n_campos": len(ver),
            "filas_verif": len({v["id"] for v in ver if v["estado"] in ("coincide", "corregido", "no_encontrado_en_fuente")}),
            "filas_corr": len({v["id"] for v in ver if v["estado"] == "corregido"}),
            "n_catalogo": len(cat), "n_incluidos": sum(x["incluido"] == "si" for x in cat),
            "n_texto_completo": sum(x.get("evaluado_texto_completo") == "si" for x in cat)}


def bloques(lang: str, formato: str) -> tuple[list, dict]:
    """Devuelve (bloques, cifras). formato ∈ {"ieee", "revista"}."""
    es, ieee = lang == "es", formato == "ieee"
    c = cifras()
    r = c["r"]

    def L(a, b):
        return a if es else b

    def n(x, d=3):
        s = f"{x:.{d}f}".replace("-", "−")
        return s.replace(".", ",") if es else s

    def pm(m):
        return f"{n(m['R2_medio'])} ± {n(m['R2_de'])}"

    def pms(d):
        return f"{n(d['media'])} ± {n(d['de'])}"

    def h1(num, es_t, en_t):
        return ("h1", f"{num}. {es_t.upper()}" if ieee else f"{num}. {L(es_t, en_t)}") if ieee and es else \
               ("h1", f"{num}. {L(es_t, en_t)}")

    rom = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V"}
    letras = "ABCDEF"

    def sec(i, es_t, en_t):
        return ("h1", f"{rom[i]}. {L(es_t, en_t).upper()}") if ieee else ("h1", f"{i}. {L(es_t, en_t)}")

    def sub(i, j, es_t, en_t):
        return ("h2", f"{letras[j - 1]}. {L(es_t, en_t)}") if ieee else ("h2", f"{i}.{j}. {L(es_t, en_t)}")

    def tab(k, es_t, en_t):
        return f"TABLA {rom[k]}. {es_t}" if ieee and es else (f"TABLE {rom[k]}. {en_t}" if ieee else
                                                              f"{L('Tabla', 'Table')} {k}. {L(es_t, en_t)}")

    rep, lit, met = r["replicas"], r["literatura_cierre"], r["meta"]
    RG, RF_, RS = rep["grupos"]["modelos"], rep["filas"]["modelos"], rep["fuente"]["modelos"]
    LG, LF = lit["grupos"]["modelos"], lit["filas"]["modelos"]
    MG, MF = met["grupos"]["modelos"], met["filas"]["modelos"]
    conf = r["confusion_fuente"]
    mo, ca = conf["Mousa2022"], conf["Cappellesso2024"]
    n_rep = mo["n"] + ca["n"]
    li, mi = lit["info"], met["info"]
    nb_rep = rep["grupos"]["nadeau_bengio_vs_mejor"]
    s2, s3 = r["secuencial"]["lotes"]["2"], r["secuencial"]["lotes"]["3"]
    nsem = r["secuencial"]["semillas"]
    exp = r["explicabilidad"]
    nf = exp["neat_final_replicas"]
    loso_vals = [v for d in rep["fuente"]["por_fuente_de_prueba"].values() for v in d.values()]
    mejor = lambda M: max(M, key=lambda k: M[k]["R2_medio"])
    lg_best, lf_best, mg_best = mejor(LG), mejor(LF), mejor(MG)
    est = c["estados"]
    nom = {"RandomForest": "Random Forest", "XGBoost": "XGBoost", "Ridge": "Ridge", "NEAT": "NEAT"}
    with open(RAIZ / "biocrete_neat" / "datos" / "replicas_cierre_fisuras.csv", encoding="utf-8") as fh:
        grupos_fuente = Counter()
        for fila in {(x["fuente"], x["grupo_probeta"]) for x in csv.DictReader(fh)}:
            grupos_fuente[fila[0]] += 1
    g_cap, g_mousa = grupos_fuente["Cappellesso2024"], grupos_fuente["Mousa2022"]
    B = []

    t_es = ("¿Generalizan los modelos de aprendizaje automático para concreto autocurativo bacteriano? Auditoría de "
            "fuga, calidad de datos y transferencia entre laboratorios con el protocolo BioCrete")
    t_en = ("Do machine learning models for bacterial self-healing concrete generalize? An audit of leakage, data "
            "quality and cross-laboratory transfer with the BioCrete protocol")
    B.append(("titulo", L(t_es, t_en)))
    if ieee:
        B.append(("titulo2", t_en if es else t_es))

    def resumen(es_):
        n_ = (lambda x, d=3: (f"{x:.{d}f}".replace("-", "−").replace(".", ",") if es_ else
                              f"{x:.{d}f}".replace("-", "−")))
        pm_ = lambda m: f"{n_(m['R2_medio'])} ± {n_(m['R2_de'])}"
        if es_:
            return (
                "Los modelos de aprendizaje automático (ML) que predicen la autorreparación del concreto bacteriano "
                "reportan coeficientes de determinación altos, pero rara vez se comprueba si generalizan a estudios o "
                "laboratorios no vistos. Este trabajo lo audita con el protocolo abierto BioCrete sobre conjuntos "
                f"trazables: {n_rep} réplicas de cierre de fisuras de dos laboratorios, {li['n_completas']} condiciones "
                f"verificadas de {li['n_estudios']} estudios y un meta-dataset de reducción de transporte (α) de "
                f"{mi['n_completas']} condiciones y {mi['n_estudios']} estudios, reconstruido tras auditar la versión "
                "previa. Se compararon NEAT, XGBoost, Random Forest y Ridge, con ajuste anidado de todos los modelos, "
                "bajo partición por filas, por grupo (fisura, probeta o estudio) y por laboratorio. Dentro de los mismos "
                f"laboratorios, Random Forest y XGBoost alcanzaron R² = {pm_(RG['RandomForest'])} y {pm_(RG['XGBoost'])}, "
                f"y NEAT {pm_(RG['NEAT'])} con una red de {nf['neuronas_ocultas']} neurona oculta. La partición por "
                f"filas elevó el R² del cierre multi-estudio hasta {n_(LF[lf_best]['R2_medio'])}, pero al separar por "
                f"estudio ningún modelo superó a la media (R² ≤ {n_(LG[lg_best]['R2_medio'])}) y al cambiar de "
                f"laboratorio todos fallaron (R² entre {n_(min(loso_vals))} y {n_(max(loso_vals))}). La auditoría del "
                f"meta-dataset previo exigió correcciones en las {c['filas_verif']} filas verificables. En una "
                f"actualización secuencial con {nsem} semillas, el modelo congelado falló ante datos nuevos "
                f"(R² = {n_(s2['campeon']['media'])}) y el re-entrenado se recuperó ({n_(s2['caliente']['media'])}), "
                "sin ventaja del arranque en caliente de NEAT. Los modelos actuales aprenden el contexto de cada "
                "laboratorio más que mecanismos transferibles; se proponen requisitos mínimos de validación, "
                "trazabilidad y calibración local.")
        return (
            "Machine learning (ML) models that predict bacterial concrete self-healing report high coefficients of "
            "determination, but whether they generalize to unseen studies or laboratories is rarely tested. This work "
            f"audits that question with the open BioCrete protocol on traceable datasets: {n_rep} crack-closure "
            f"replicates from two laboratories, {li['n_completas']} verified conditions from {li['n_estudios']} studies, "
            f"and a transport-reduction (α) meta-dataset of {mi['n_completas']} conditions and {mi['n_estudios']} "
            "studies, rebuilt after auditing the previous version. NEAT, XGBoost, Random Forest and Ridge, all with "
            "nested tuning, were compared under row-wise, group-wise (crack, specimen or study) and laboratory-wise "
            f"splitting. Within the same laboratories, Random Forest and XGBoost reached R² = {pm_(RG['RandomForest'])} "
            f"and {pm_(RG['XGBoost'])}, and NEAT {pm_(RG['NEAT'])} with a {nf['neuronas_ocultas']}-hidden-neuron "
            f"network. Row-wise splitting raised multi-study closure R² to {n_(LF[lf_best]['R2_medio'])}, but "
            f"study-wise splitting left every model below the mean (R² ≤ {n_(LG[lg_best]['R2_medio'])}), and every "
            f"model failed across laboratories (R² from {n_(min(loso_vals))} to {n_(max(loso_vals))}). Auditing the "
            f"previous meta-dataset required corrections in all {c['filas_verif']} verifiable rows. In sequential "
            f"updating over {nsem} seeds, the frozen model failed on new data (R² = {n_(s2['campeon']['media'])}) "
            f"and retraining recovered it ({n_(s2['caliente']['media'])}), with no benefit from NEAT warm starts. "
            "Current models learn laboratory context rather than transferable mechanisms; minimum requirements for "
            "validation, traceability and local calibration are proposed.")

    B.append(("resumen", L("Resumen", "Abstract"), resumen(es)))
    claves_es = ("concreto autocurativo bacteriano; aprendizaje automático; fuga de datos; validación agrupada; "
                 "reproducibilidad; transferencia entre laboratorios; NEAT; datos abiertos")
    claves_en = ("bacterial self-healing concrete; machine learning; data leakage; grouped validation; reproducibility; "
                 "cross-laboratory transfer; NEAT; open data")
    B.append(("claves", L("Palabras clave", "Keywords"), L(claves_es, claves_en)))
    if ieee and es:
        B.append(("resumen", "Abstract", resumen(False)))
        B.append(("claves", "Keywords", claves_en))
    if not ieee:
        B.append(("destacados", [
            L("La partición por filas infla el R² de modelos de autorreparación entrenados con varios estudios",
              "Row-wise splitting inflates R² of self-healing models trained on several studies"),
            L("Ningún modelo predice el cierre en estudios o laboratorios no vistos",
              "No model predicts closure in unseen studies or laboratories"),
            L("La auditoría de un meta-dataset previo encontró errores en todas las filas verificables",
              "Auditing a previous meta-dataset found errors in every verifiable row"),
            L("Dentro de un laboratorio, los árboles superan a NEAT; NEAT empata con la regresión lineal",
              "Within a laboratory, trees beat NEAT; NEAT ties with linear regression"),
            L("Se proponen requisitos mínimos de validación, trazabilidad y calibración local",
              "Minimum requirements for validation, traceability and local calibration are proposed"),
        ]))

    # --- 1 Introducción ------------------------------------------------------
    B.append(sec(1, "Introducción", "Introduction"))
    B.append(("p", L(
        "Evaluar el concreto autocurativo bacteriano (CAB) exige ensayos de 28 a 365 días en inmersión o ciclos marinos "
        "⟦cappellesso2024,doostkami2023⟧, y su efecto en la vida útil depende de umbrales de reducción de transporte ya "
        "cuantificados a escala estructural ⟦markov⟧. Para acortar ese ciclo, varios trabajos entrenan modelos de "
        "aprendizaje automático (redes neuronales, árboles con gradiente, programación genética) que reportan "
        "coeficientes de determinación altos ⟦zhuang2019,huang2022,pessoa2023,tian2024,lou2024,khosravi2025,"
        "chowdhury2026⟧.",
        "Evaluating bacterial self-healing concrete (BSHC) requires 28- to 365-day tests under immersion or marine cycles "
        "⟦cappellesso2024,doostkami2023⟧, and its effect on service life depends on transport-reduction thresholds "
        "already quantified at structural scale ⟦markov⟧. To shorten this cycle, several studies train machine learning "
        "models (neural networks, gradient-boosted trees, genetic programming) that report high coefficients of "
        "determination ⟦zhuang2019,huang2022,pessoa2023,tian2024,lou2024,khosravi2025,chowdhury2026⟧.")))
    B.append(("p", L(
        "Esos modelos suelen construirse con tablas que reúnen condiciones de muchos estudios y validarse con "
        "particiones aleatorias por filas. Cuando réplicas de un mismo estudio o probeta caen a la vez en entrenamiento "
        "y prueba, el modelo puede reconocer el contexto en lugar de aprender el mecanismo; esta fuga de información es "
        "una causa documentada de resultados irreproducibles ⟦kapoor2023⟧. A ello se suman dos riesgos propios de los "
        "meta-datasets: errores de transcripción y variables objetivo derivadas sin una regla explícita.",
        "Such models are usually built from tables that pool conditions from many studies and validated with random "
        "row-wise splits. When replicates of the same study or specimen fall in both training and test sets, the model "
        "can recognize the context instead of learning the mechanism; this leakage is a documented cause of "
        "irreproducible results ⟦kapoor2023⟧. Meta-datasets add two further risks: transcription errors and target "
        "variables derived without an explicit rule.")))
    B.append(("p", L(
        "Este trabajo se pregunta si los modelos de autorreparación generalizan más allá del contexto en que se "
        "entrenan, mediante tres preguntas: (P1) ¿cuánto cambia el desempeño entre partición por filas, por grupo y por "
        "laboratorio?; (P2) ¿qué calidad tienen los datos de los meta-datasets?; y (P3) ¿aporta NEAT ⟦stanley2002⟧ —una "
        "red que evoluciona su propia topología y puede reanudarse con datos nuevos— frente a árboles y regresión "
        "lineal? Los aportes son un protocolo abierto y trazable (BioCrete), conjuntos de datos auditados y requisitos "
        "mínimos para futuros modelos.",
        "This work asks whether self-healing models generalize beyond the context in which they are trained, through "
        "three questions: (Q1) how much does performance change between row-wise, group-wise and laboratory-wise "
        "splitting? (Q2) what is the quality of meta-dataset data? and (Q3) does NEAT ⟦stanley2002⟧ —a network that "
        "evolves its own topology and can be resumed with new data— add value over trees and linear regression? The "
        "contributions are an open, traceable protocol (BioCrete), audited datasets and minimum requirements for "
        "future models.")))

    # --- 2 Métodos -------------------------------------------------------------
    B.append(sec(2, "Metodología" if ieee else "Métodos", "Methods"))
    B.append(sub(2, 1, "Conjuntos de datos", "Datasets"))
    B.append(("p", L(
        "Se usaron cinco conjuntos (Tabla I). Las réplicas de cierre provienen de dos repositorios con DOI: Mousa et al. "
        "⟦mousa_zenodo⟧ (morteros con Bacillus pseudofirmus en hidrogel, agregado liviano o nanocelulosa, ciclos de "
        f"humedecimiento y secado, {mo['n']} registros) y Cappellesso et al. ⟦cap_zenodo,cappellesso2024⟧ (concreto con "
        f"agente bacteriano comercial o aditivo cristalino en agua de mar ASTM D1141, {ca['n']} registros), con una fila "
        "por fisura o zona y edad e identificadores de grupo. El cierre multi-estudio procede de una búsqueda "
        f"sistemática (Europe PMC, OpenAlex y Zenodo) que cribó {c['n_catalogo']} registros, evaluó "
        f"{c['n_texto_completo']} a texto completo e incluyó {c['n_incluidos']} fuentes; se usaron solo las "
        f"{li['n_completas']} condiciones verificadas con todas las entradas. El meta-dataset de α se reconstruyó con "
        "una regla explícita (α = 1 − propiedad de transporte de la probeta bacteriana / la de la referencia sin "
        f"bacterias a igual edad y ancho), quedando {mi['n_completas']} condiciones de {mi['n_estudios']} estudios. La "
        "lista completa de fuentes está en el repositorio del proyecto.",
        "Five datasets were used (Table I). Closure replicates come from two DOI repositories: Mousa et al. "
        "⟦mousa_zenodo⟧ (mortars with Bacillus pseudofirmus in hydrogel, lightweight aggregate or nanocellulose, wet/dry "
        f"cycles, {mo['n']} records) and Cappellesso et al. ⟦cap_zenodo,cappellesso2024⟧ (concrete with a commercial "
        f"bacterial agent or crystalline admixture in ASTM D1141 seawater, {ca['n']} records), with one row per crack or "
        "zone and age and group identifiers. Multi-study closure comes from a systematic search (Europe PMC, OpenAlex "
        f"and Zenodo) that screened {c['n_catalogo']} records, assessed {c['n_texto_completo']} in full text and "
        f"included {c['n_incluidos']} sources; only the {li['n_completas']} verified conditions with complete inputs "
        "were used. The α meta-dataset was rebuilt with an explicit rule (α = 1 − transport property of the bacterial "
        "specimen / that of the bacteria-free reference at the same age and width), leaving "
        f"{mi['n_completas']} conditions from {mi['n_estudios']} studies. The full source list is in the project "
        "repository.").replace("Tabla I", "Tabla I" if ieee else "Tabla 1").replace("Table I", "Table I" if ieee else "Table 1")))
    B.append(("tabla", tab(1, "Conjuntos de datos y unidad de agrupación", "Datasets and grouping unit"),
              [[L("Conjunto", "Dataset"), L("Grupo", "Group"), "n", L("Grupos", "Groups"), L("Verificación", "Verification")],
               [L("Réplicas Mousa", "Mousa replicates"), L("fisura", "crack"), mo["n"], g_mousa, L("crudo, DOI", "raw, DOI")],
               [L("Réplicas Cappellesso", "Cappellesso replicates"), L("probeta", "specimen"), ca["n"], g_cap,
                L("crudo, DOI", "raw, DOI")],
               [L("Cierre multi-estudio", "Multi-study closure"), L("estudio", "study"), li["n_completas"],
                li["n_estudios"], L("verificadas", "verified")],
               ["α v2", L("estudio", "study"), mi["n_completas"], mi["n_estudios"], L("regla explícita", "explicit rule")],
               [L("Meta v1 (auditado)", "Meta v1 (audited)"), L("estudio", "study"), 36, 12,
                L(f"{c['filas_verif']} verificables", f"{c['filas_verif']} verifiable")]],
              None, [2.4, 1.2, 0.8, 0.9, 1.7]))

    B.append(sub(2, 2, "Variables, modelos y ajuste", "Variables, models and tuning"))
    B.append(("p", L(
        "Las réplicas usan siete entradas: ancho inicial, edad, nivel de protección biológica (0 = sin bacterias; "
        "1 = adición directa o agente comercial; 2 = portador; 3 = encapsulación), ambiente marino, lactato de calcio, "
        "curado previo y aditivo cristalino. Los conjuntos multi-estudio usan a/c, ancho, edad, protección, ambiente y "
        f"lactato. Todas se normalizaron con límites físicos fijos. Se compararon NEAT (población 60, "
        f"{r['generaciones_neat']} generaciones, sin neuronas ocultas iniciales, penalización de complejidad "
        "λ_p ∈ {2, 8, 16}×10⁻⁴) ⟦stanley2002⟧, XGBoost ⟦chen2016⟧, Random Forest ⟦breiman2001⟧ y Ridge. Los "
        "hiperparámetros de los cuatro modelos se eligieron por validación interna dentro de cada partición externa "
        "(validación anidada) ⟦varma2006⟧.",
        "Replicates use seven inputs: initial width, age, biological protection level (0 = no bacteria; 1 = direct "
        "addition or commercial agent; 2 = carrier; 3 = encapsulation), marine exposure, calcium lactate, pre-curing and "
        "crystalline admixture. Multi-study datasets use w/c, width, age, protection, exposure and lactate. All inputs "
        f"were normalized with fixed physical bounds. NEAT (population 60, {r['generaciones_neat']} generations, no "
        "initial hidden neurons, complexity penalty λ_p ∈ {2, 8, 16}×10⁻⁴) ⟦stanley2002⟧, XGBoost ⟦chen2016⟧, Random "
        "Forest ⟦breiman2001⟧ and Ridge were compared. Hyperparameters of all four models were chosen by inner "
        "validation within each outer fold (nested validation) ⟦varma2006⟧.")))
    B.append(sub(2, 3, "Protocolos de validación", "Validation protocols"))
    B.append(("p", L(
        "Cada modelo se evaluó con el mismo código bajo tres protocolos: (i) por filas, KFold aleatorio de 5 "
        "particiones; (ii) por grupo, GroupKFold de 5 particiones por fisura, probeta o estudio; y (iii) por "
        "laboratorio, entrenando en un laboratorio y probando en el otro. Los protocolos (i) y (ii) se repitieron "
        f"{rep['grupos']['repeticiones']} veces con particiones distintas; se reporta el R² medio ± desviación típica "
        "entre repeticiones y se comparó cada modelo con el mejor mediante la prueba t corregida de Nadeau y Bengio "
        "⟦nadeau2003⟧. La importancia de variables se calculó con SHAP fuera de muestra ⟦lundberg2017⟧ y por "
        "permutación sobre la red NEAT final. Por último, se simuló la llegada secuencial de tres lotes (Mousa; "
        "Cappellesso con curado previo; Cappellesso con exposición directa) y, sobre los mismos grupos retenidos de "
        "cada lote nuevo, se compararon el modelo congelado, NEAT re-entrenado desde cero y NEAT reanudado desde su "
        f"población previa ⟦parisi2019⟧, con {nsem} semillas.",
        "Each model was evaluated with the same code under three protocols: (i) row-wise, random 5-fold KFold; "
        "(ii) group-wise, 5-fold GroupKFold by crack, specimen or study; and (iii) laboratory-wise, training on one "
        f"laboratory and testing on the other. Protocols (i) and (ii) were repeated {rep['grupos']['repeticiones']} "
        "times with different splits; mean R² ± standard deviation across repetitions is reported and each model was "
        "compared with the best one using the Nadeau–Bengio corrected t-test ⟦nadeau2003⟧. Feature importance was "
        "computed with out-of-sample SHAP ⟦lundberg2017⟧ and by permutation on the final NEAT network. Finally, the "
        "sequential arrival of three batches (Mousa; Cappellesso pre-cured; Cappellesso direct exposure) was simulated "
        "and, on the same held-out groups of each new batch, the frozen model, NEAT retrained from scratch and NEAT "
        f"resumed from its previous population ⟦parisi2019⟧ were compared over {nsem} seeds.")))

    # --- 3 Resultados ----------------------------------------------------------
    T = (lambda k: f"Tabla {rom[k]}" if ieee else f"Tabla {k}") if es else \
        (lambda k: f"Table {rom[k]}" if ieee else f"Table {k}")
    B.append(sec(3, "Resultados", "Results"))
    B.append(sub(3, 1, "Variables confundidas con el laboratorio", "Variables confounded with laboratory"))
    B.append(("p", L(
        f"La {T(2)} muestra que, en las réplicas, el ambiente marino coincide por completo con el laboratorio: todas "
        "las probetas marinas son de Cappellesso y ninguna de Mousa. También se separan la edad "
        f"({n(mo['edad_dias'][0], 0)}–{n(mo['edad_dias'][1], 0)} frente a {n(ca['edad_dias'][0], 0)}–"
        f"{n(ca['edad_dias'][1], 0)} días), el lactato de calcio (solo Mousa), los niveles de protección y el ancho "
        f"inicial (máximo marino {n(ca['w0_mm'][1], 3)} mm). En Cappellesso, {n(ca['pct_cierre_100'], 1)} % de los "
        "registros alcanzan el cierre total, lo que satura la variable objetivo. Con estos datos, ningún efecto "
        "atribuido al ambiente marino puede separarse del efecto del laboratorio.",
        f"{T(2)} shows that, in the replicates, marine exposure fully coincides with laboratory: all marine specimens "
        f"are from Cappellesso and none from Mousa. Age ({n(mo['edad_dias'][0], 0)}–{n(mo['edad_dias'][1], 0)} vs "
        f"{n(ca['edad_dias'][0], 0)}–{n(ca['edad_dias'][1], 0)} days), calcium lactate (Mousa only), protection levels "
        f"and initial width (marine maximum {n(ca['w0_mm'][1], 3)} mm) are also separated. In Cappellesso, "
        f"{n(ca['pct_cierre_100'], 1)}% of records reach full closure, saturating the target. With these data, no "
        "effect attributed to marine exposure can be separated from the laboratory effect.")))
    niv = lambda d: ", ".join(f"{k}:{v}" for k, v in d["niveles_proteccion"].items())
    B.append(("tabla", tab(2, "Distribución de variables por laboratorio (réplicas)",
                           "Variable distribution by laboratory (replicates)"),
              [[L("Variable", "Variable"), "Mousa", "Cappellesso"],
               [L("Ambiente marino", "Marine exposure"), "no", L("sí", "yes")],
               [L("Edad (d)", "Age (d)"), f"{n(mo['edad_dias'][0], 0)}–{n(mo['edad_dias'][1], 0)}",
                f"{n(ca['edad_dias'][0], 0)}–{n(ca['edad_dias'][1], 0)}"],
               [L("Ancho inicial (mm)", "Initial width (mm)"), f"{n(mo['w0_mm'][0], 3)}–{n(mo['w0_mm'][1], 3)}",
                f"{n(ca['w0_mm'][0], 3)}–{n(ca['w0_mm'][1], 3)}"],
               [L("Protección (nivel:n)", "Protection (level:n)"), niv(mo), niv(ca)],
               [L("Lactato de calcio (n)", "Calcium lactate (n)"), mo["lactato_calcio"], ca["lactato_calcio"]],
               [L("Curado previo (n)", "Pre-curing (n)"), mo["curado_previo"], ca["curado_previo"]],
               [L("Aditivo cristalino (n)", "Crystalline admixture (n)"), mo["agente_cristalino"], ca["agente_cristalino"]],
               [L("Cierre = 100 % (%)", "Closure = 100% (%)"), n(mo["pct_cierre_100"], 1), n(ca["pct_cierre_100"], 1)]],
              None, [2.4, 1.6, 1.6]))

    B.append(sub(3, 2, "Desempeño según el protocolo", "Performance by protocol"))
    p_xgb = nb_rep.get("XGBoost", {"p": 1.0})["p"]
    B.append(("p", L(
        f"La {T(3)} y la Fig. 1 resumen el desempeño. Dentro de los mismos laboratorios (réplicas, partición por "
        f"grupo), Random Forest ({pm(RG['RandomForest'])}) y XGBoost ({pm(RG['XGBoost'])}) no difieren "
        f"significativamente (p = {n(p_xgb, 2)}), mientras que NEAT ({pm(RG['NEAT'])}) y Ridge ({pm(RG['Ridge'])}) "
        "quedan por debajo (p < 0,001) y empatan entre sí. Al pasar de partición por grupo a partición por filas, los "
        "árboles ganan entre 0,06 y 0,08 de R² en las réplicas; en el cierre multi-estudio la diferencia es mucho mayor: "
        f"{nom[lf_best]} pasa de {n(LG[lf_best]['R2_medio'])} a {n(LF[lf_best]['R2_medio'])}. Con partición por "
        f"estudio ningún modelo supera a la media del conjunto (máximo {n(LG[lg_best]['R2_medio'])}), y en α el mejor "
        f"resultado es {n(MG[mg_best]['R2_medio'])} ({nom[mg_best]}). Al cambiar de laboratorio, todos los modelos "
        f"obtienen R² negativo, entre {n(min(loso_vals))} y {n(max(loso_vals))}.",
        f"{T(3)} and Fig. 1 summarize performance. Within the same laboratories (replicates, group-wise split), Random "
        f"Forest ({pm(RG['RandomForest'])}) and XGBoost ({pm(RG['XGBoost'])}) do not differ significantly "
        f"(p = {n(p_xgb, 2)}), while NEAT ({pm(RG['NEAT'])}) and Ridge ({pm(RG['Ridge'])}) are lower (p < 0.001) and "
        "tie with each other. Moving from group-wise to row-wise splits, the trees gain 0.06–0.08 R² on the "
        f"replicates; on multi-study closure the gap is much larger: {nom[lf_best]} goes from "
        f"{n(LG[lf_best]['R2_medio'])} to {n(LF[lf_best]['R2_medio'])}. With study-wise splits no model beats the "
        f"dataset mean (maximum {n(LG[lg_best]['R2_medio'])}), and for α the best result is "
        f"{n(MG[mg_best]['R2_medio'])} ({nom[mg_best]}). Across laboratories every model obtains negative R², between "
        f"{n(min(loso_vals))} and {n(max(loso_vals))}.")))
    filas_t3 = [[L("Conjunto", "Dataset"), L("Modelo", "Model"), L("Por filas", "Row-wise"),
                 L("Por grupo", "Group-wise"), L("Por lab.", "Lab-wise")]]
    for conj, G, F_, S in [(L("Réplicas", "Replicates"), RG, RF_, RS), (L("Multi-estudio", "Multi-study"), LG, LF, None),
                           ("α v2", MG, MF, None)]:
        for m in ("RandomForest", "XGBoost", "NEAT", "Ridge"):
            filas_t3.append([conj, nom[m], pm(F_[m]), pm(G[m]), n(S[m]["R2_medio"]) if S else "—"])
    B.append(("tabla", tab(3, "R² fuera de muestra (media ± DE entre repeticiones)",
                           "Out-of-sample R² (mean ± SD across repetitions)"), filas_t3,
              L(f"Por filas y por grupo: {rep['grupos']['repeticiones']} repeticiones × 5 particiones (réplicas por "
                f"filas: {rep['filas']['repeticiones']}). Por laboratorio: entrenar en uno y probar en el otro (media de "
                "ambos sentidos). Ajuste anidado de todos los modelos.",
                f"Row- and group-wise: {rep['grupos']['repeticiones']} repetitions × 5 folds (replicates row-wise: "
                f"{rep['filas']['repeticiones']}). Lab-wise: train on one, test on the other (mean of both directions). "
                "Nested tuning for all models."),
              [1.3, 1.3, 1.25, 1.25, 0.9]))
    B.append(("figura", RES / "revision" / ("fig8v_protocolos.png" if ieee else "fig8_protocolos_filas_vs_grupos.png"),
              L("Fig. 1. R² fuera de muestra con partición por filas (con fuga) y por grupo (sin fuga) para las réplicas, "
                "el cierre multi-estudio y α. Barras: media ± DE entre repeticiones.",
                "Fig. 1. Out-of-sample R² with row-wise (leaky) and group-wise (leakage-free) splits for replicates, "
                "multi-study closure and α. Bars: mean ± SD across repetitions."), 3.3))

    B.append(sub(3, 3, "Calidad del meta-dataset previo", "Quality of the previous meta-dataset"))
    B.append(("p", L(
        f"De las 36 filas del meta-dataset usado en la versión previa, solo {c['filas_verif']} pudieron contrastarse con "
        f"su fuente (el resto procede de artículos de acceso cerrado) y las {c['filas_corr']} requirieron al menos una "
        f"corrección ({T(4)}). Entre los errores: reducciones de permeabilidad registradas como cierre óptico "
        "⟦palin2017⟧, una relación a/c de 0,50 registrada como 0,45 ⟦cappellesso2024⟧ y ensayos en agua corriente "
        "codificados como marinos ⟦doostkami2023⟧. La variable α no tenía una regla de cálculo documentada. Por ello, el "
        "resultado de la versión previa de este trabajo (R² = 0,540 para NEAT con partición por filas) no es "
        "reproducible ni defendible y se reemplaza por los análisis aquí descritos.",
        f"Of the 36 rows of the meta-dataset used in the previous version, only {c['filas_verif']} could be checked "
        f"against their source (the rest come from closed-access papers) and all {c['filas_corr']} required at least one "
        f"correction ({T(4)}). Errors include permeability-reduction values recorded as optical closure ⟦palin2017⟧, a "
        "w/c of 0.50 recorded as 0.45 ⟦cappellesso2024⟧, and tap-water tests coded as marine ⟦doostkami2023⟧. The α "
        "variable had no documented derivation rule. Hence the result of the previous version of this work (R² = 0.540 "
        "for NEAT with row-wise splitting) is neither reproducible nor defensible and is replaced by the analyses "
        "described here.")))
    B.append(("tabla", tab(4, "Auditoría campo a campo del meta-dataset previo",
                           "Field-by-field audit of the previous meta-dataset"),
              [[L("Resultado", "Outcome"), L("Campos", "Fields"), L("Ejemplo", "Example")],
               [L("Coincide", "Matches"), est.get("coincide", 0), "—"],
               [L("Corregido", "Corrected"), est.get("corregido", 0),
                L("permeabilidad registrada como cierre", "permeability recorded as closure")],
               [L("No encontrado en la fuente", "Not found in source"), est.get("no_encontrado_en_fuente", 0),
                L("valor solo en una figura", "value only in a figure")],
               [L("Fuente no accesible", "Source not accessible"), est.get("fuente_no_accesible", 0),
                L("acceso cerrado sin copia abierta", "closed access, no open copy")]],
              L(f"{c['n_campos']} comprobaciones sobre 36 filas y 8 campos; {c['filas_verif']} filas verificables.",
                f"{c['n_campos']} checks over 36 rows and 8 fields; {c['filas_verif']} verifiable rows."),
              [2.2, 0.9, 2.9]))

    B.append(sub(3, 4, "Qué aprenden los modelos", "What the models learn"))
    sr, sl = exp["shap_oof_replicas"], exp["shap_oof_literatura_cierre"]
    usadas = ", ".join(v.split(" (")[0].lower() for v in nf["entradas_usadas"])
    B.append(("p", L(
        f"En las réplicas, SHAP fuera de muestra indica que la edad domina ({n(sr[0]['shap_medio_abs'])}), seguida del "
        f"ancho inicial ({n(sr[1]['shap_medio_abs'])}); la red NEAT final ({nf['neuronas_ocultas']} neurona oculta, "
        f"{nf['conexiones_activas']} conexiones) usa solo {usadas}. En el cierre multi-estudio domina el nivel de "
        f"protección ({n(sl[0]['shap_medio_abs'])}), seguido del ancho de fisura ({n(sl[1]['shap_medio_abs'])}). Estas "
        "importancias son coherentes con la física —la protección de las esporas y el ancho de fisura limitan el "
        "cierre ⟦jonkers2010,luo2015⟧—, pero describen correlaciones dentro de los datos de entrenamiento y no bastan "
        "para predecir otros estudios.",
        f"In the replicates, out-of-sample SHAP shows that age dominates ({n(sr[0]['shap_medio_abs'])}), followed by "
        f"initial width ({n(sr[1]['shap_medio_abs'])}); the final NEAT network ({nf['neuronas_ocultas']} hidden neuron, "
        f"{nf['conexiones_activas']} connections) uses only age and protection. In multi-study closure, protection level "
        f"dominates ({n(sl[0]['shap_medio_abs'])}), followed by crack width ({n(sl[1]['shap_medio_abs'])}). These "
        "importances are physically consistent —spore protection and crack width limit closure ⟦jonkers2010,luo2015⟧— "
        "but describe correlations within the training data and are not enough to predict other studies.")))
    fig_sec = 2
    if not ieee:
        B.append(("p", L("La Fig. 2 y la Fig. 3 muestran la distribución de los valores SHAP fuera de muestra en las "
                         "réplicas y en el cierre multi-estudio, respectivamente.",
                         "Fig. 2 and Fig. 3 show the distribution of out-of-sample SHAP values for the replicates and "
                         "for multi-study closure, respectively.")))
        B.append(("figura", RES / "revision" / "fig10a_shap_oof_replicas.png",
                  L("Fig. 2. SHAP fuera de muestra (XGBoost) para el cierre de las réplicas.",
                    "Fig. 2. Out-of-sample SHAP (XGBoost) for replicate closure."), 3.3))
        B.append(("figura", RES / "revision" / "fig10c_shap_oof_literatura.png",
                  L("Fig. 3. SHAP fuera de muestra (XGBoost) para el cierre multi-estudio.",
                    "Fig. 3. Out-of-sample SHAP (XGBoost) for multi-study closure."), 3.3))
        fig_sec = 4

    B.append(sub(3, 5, "Actualización secuencial", "Sequential updating"))
    B.append(("p", L(
        f"En la simulación por lotes (Fig. {fig_sec}), el modelo congelado obtuvo R² = {pms(s2['campeon'])} y "
        f"{pms(s3['campeon'])} en los lotes 2 y 3, mientras que re-entrenar con parte del lote nuevo elevó el R² a "
        f"{pms(s2['caliente'])} y {pms(s3['caliente'])} (arranque en caliente) o {pms(s2['frio'])} y {pms(s3['frio'])} "
        "(desde cero). La diferencia entre arranque en caliente y desde cero no fue significativa "
        f"(p = {n(s2['caliente_menos_frio']['p_wilcoxon'], 2)} y {n(s3['caliente_menos_frio']['p_wilcoxon'], 2)}, "
        "Wilcoxon): lo que importa es actualizar con datos del nuevo contexto, no reanudar la población de NEAT.",
        f"In the batch simulation (Fig. {fig_sec}), the frozen model obtained R² = {pms(s2['campeon'])} and "
        f"{pms(s3['campeon'])} on batches 2 and 3, whereas retraining with part of the new batch raised R² to "
        f"{pms(s2['caliente'])} and {pms(s3['caliente'])} (warm start) or {pms(s2['frio'])} and {pms(s3['frio'])} "
        "(from scratch). Warm versus cold start was not significant "
        f"(p = {n(s2['caliente_menos_frio']['p_wilcoxon'], 2)} and {n(s3['caliente_menos_frio']['p_wilcoxon'], 2)}, "
        "Wilcoxon): what matters is updating with data from the new context, not resuming the NEAT population.")))
    B.append(("figura", RES / "revision" / "fig9_actualizacion_secuencial.png",
              L(f"Fig. {fig_sec}. R² sobre los mismos grupos retenidos de cada lote nuevo: modelo congelado, NEAT "
                f"reanudado y NEAT desde cero (media ± DE, {nsem} semillas).",
                f"Fig. {fig_sec}. R² on the same held-out groups of each new batch: frozen model, resumed NEAT and NEAT "
                f"from scratch (mean ± SD, {nsem} seeds)."), 3.3))

    if not ieee:
        cap = {(x["condicion"], x["grupo"]): x for x in c["zen"]["cappellesso2024_agno3_marino"]}
        reds = [cap[(k, "BAS")]["reduccion_vs_REF_pct"] for k in
                ("Uncracked H", "Uncracked U", "Crack 100 U", "Crack 300 U", "Crack 300 H", "Crack 100 H")]
        B.append(sub(3, 6, "Datos complementarios de cloruros y difusión", "Complementary chloride and diffusion data"))
        B.append(("p", L(
            "En las mediciones de penetración de cloruros por nitrato de plata de Cappellesso et al. ⟦cap_zenodo⟧, el "
            f"efecto del agente bacteriano frente a la referencia osciló entre {n(min(reds), 1)} % y {n(max(reds), 1)} %, "
            "con alta dispersión entre series; no se observa una reducción uniforme. La ecuación de difusión base de "
            "Life-365 frente a 239 ensayos de migración de Dryad ⟦dryad⟧ dio una razón mediana de "
            f"{n(c['zen']['dryad_razon_mediana_life365_vs_exp'], 2)}×, coherente con la difusión de laboratorio del "
            "concreto convencional; estos datos no permiten atribuir causas a discrepancias de campo.",
            "In the silver-nitrate chloride penetration measurements of Cappellesso et al. ⟦cap_zenodo⟧, the effect of "
            f"the bacterial agent versus the reference ranged from {n(min(reds), 1)}% to {n(max(reds), 1)}%, with high "
            "dispersion across series; no uniform reduction is observed. Life-365's base diffusion equation against 239 "
            f"Dryad migration tests ⟦dryad⟧ gave a median ratio of {n(c['zen']['dryad_razon_mediana_life365_vs_exp'], 2)}×, "
            "consistent with laboratory diffusion of conventional concrete; these data do not allow attributing causes "
            "to field discrepancies.")))

    # --- 4 Discusión ------------------------------------------------------------
    B.append(sec(4, "Discusión", "Discussion"))
    B.append(("p", L(
        "Con los datos disponibles, la respuesta a la pregunta del título es negativa: los modelos predicen "
        "razonablemente dentro de un laboratorio, pero no transfieren a estudios ni laboratorios nuevos. La partición "
        "por filas oculta este problema y produce valores de R² comparables a los publicados "
        "⟦zhuang2019,huang2022,khosravi2025⟧, lo que sugiere que parte de esa literatura mide la capacidad de reconocer "
        "el contexto experimental más que la de predecir el cierre de una formulación nueva. NEAT no aportó precisión "
        "frente a los árboles; su red mínima equivale en la práctica a un modelo casi lineal, aunque es fácil de "
        "inspeccionar.",
        "With the available data, the answer to the title question is negative: the models predict reasonably within a "
        "laboratory but do not transfer to new studies or laboratories. Row-wise splitting hides this problem and yields "
        "R² values comparable to published ones ⟦zhuang2019,huang2022,khosravi2025⟧, suggesting that part of that "
        "literature measures the ability to recognize the experimental context rather than to predict the closure of a "
        "new formulation. NEAT added no accuracy over trees; its minimal network is in practice almost linear, although "
        "easy to inspect.")))
    B.append(("p", L(
        "Se proponen cinco requisitos mínimos para futuros modelos: (1) partición por estudio o laboratorio y, si es "
        "posible, prueba en un laboratorio externo; (2) trazabilidad por fila (DOI, tabla o figura de origen y "
        "unidades); (3) reglas explícitas para variables derivadas como α; (4) declarar la confusión entre variables y "
        "fuentes; y (5) calibración local con ensayos propios antes de usar las predicciones en diseño. Limitaciones: "
        "solo dos laboratorios aportan réplicas, el cierre total satura los datos marinos, la mayoría de las fuentes "
        "cerradas no pudo verificarse y la simulación secuencial usa lotes históricos. Los ensayos de Paita-Piura a 28, "
        "56 y 90 días permitirán una calibración local y una prueba externa real.",
        "Five minimum requirements are proposed for future models: (1) study- or laboratory-wise splitting and, where "
        "possible, testing in an external laboratory; (2) row-level traceability (DOI, source table or figure, units); "
        "(3) explicit rules for derived variables such as α; (4) disclosure of confounding between variables and "
        "sources; and (5) local calibration with in-house tests before using predictions in design. Limitations: only "
        "two laboratories contribute replicates, full closure saturates the marine data, most closed sources could not "
        "be verified, and the sequential simulation uses historical batches. The Paita-Piura 28-, 56- and 90-day tests "
        "will enable local calibration and a real external test.")))
    if not ieee:
        pa = r["paita"]
        B.append(("p", L(
            "Como ilustración, un ensamble XGBoost monótono con bootstrap por grupos predice para Paita (90 días, agua de "
            f"mar, lactato de calcio, fisura de 0,2 mm) un cierre de {n(pa[0]['cierre_medio_pct'], 1)} % "
            f"[{n(pa[0]['cierre_IC95_pct'][0], 1)}–{n(pa[0]['cierre_IC95_pct'][1], 1)}]; sin embargo, ninguna fila de "
            "entrenamiento combina agua de mar y lactato de calcio, y los anchos mayores de "
            f"{n(pa[0]['w0_max_marino_mm'], 3)} mm quedan fuera del rango marino, por lo que esta cifra no debe usarse "
            "para diseño.",
            "As an illustration, a monotonic XGBoost ensemble with group bootstrap predicts for Paita (90 days, seawater, "
            f"calcium lactate, 0.2 mm crack) a closure of {n(pa[0]['cierre_medio_pct'], 1)}% "
            f"[{n(pa[0]['cierre_IC95_pct'][0], 1)}–{n(pa[0]['cierre_IC95_pct'][1], 1)}]; however, no training row "
            f"combines seawater and calcium lactate, and widths above {n(pa[0]['w0_max_marino_mm'], 3)} mm are outside "
            "the marine range, so this figure must not be used for design.")))

    # --- 5 Conclusiones -----------------------------------------------------------
    B.append(sec(5, "Conclusiones", "Conclusions"))
    B.append(("p", L(
        "(1) Dentro de los mismos laboratorios, Random Forest y XGBoost explican cerca de dos tercios de la varianza del "
        f"cierre (R² ≈ {n(RG['RandomForest']['R2_medio'], 2)}), y NEAT y Ridge cerca del 40 %. (2) Ningún modelo "
        "generaliza a estudios o laboratorios no vistos (R² ≤ 0). (3) La partición por filas infla el desempeño, sobre "
        "todo en conjuntos multi-estudio. (4) El meta-dataset previo tenía errores en todas las filas verificables, y "
        "los resultados basados en él se retiran. (5) Actualizar el modelo con datos del nuevo contexto es "
        "imprescindible; reanudar la población de NEAT no aporta ventaja. El código, los datos auditados y los "
        f"resultados están disponibles en {REPO_URL}.",
        "(1) Within the same laboratories, Random Forest and XGBoost explain about two thirds of closure variance "
        f"(R² ≈ {n(RG['RandomForest']['R2_medio'], 2)}), and NEAT and Ridge about 40%. (2) No model generalizes to unseen "
        "studies or laboratories (R² ≤ 0). (3) Row-wise splitting inflates performance, especially on multi-study "
        "datasets. (4) The previous meta-dataset had errors in every verifiable row, and results based on it are "
        "withdrawn. (5) Updating the model with data from the new context is essential; resuming the NEAT population "
        f"adds no benefit. Code, audited data and results are available at {REPO_URL}.")))

    if not ieee:
        B.append(("declaraciones", [
            L(f"Disponibilidad de datos y código: {REPO_URL} (código, datos procesados, auditorías, catálogo PRISMA y "
              "registro de versiones). Los datos crudos proceden de los repositorios citados.",
              f"Data and code availability: {REPO_URL} (code, processed data, audits, PRISMA catalogue and version "
              "registry). Raw data come from the cited repositories."),
            L("Contribución de los autores (CRediT): M. A. Guardamino Capcha: conceptualización, metodología, software, "
              "curación de datos, redacción. C. A. Eyzaguirre Acosta: supervisión, revisión. [Confirmar.]",
              "CRediT authorship contribution statement: M. A. Guardamino Capcha: conceptualization, methodology, "
              "software, data curation, writing. C. A. Eyzaguirre Acosta: supervision, review. [Confirm.]"),
            L("Conflicto de intereses: ninguno. [Confirmar.]", "Declaration of competing interest: none. [Confirm.]"),
            L("Uso de IA generativa: se usaron herramientas de IA como apoyo en programación, búsqueda bibliográfica y "
              "redacción; los autores revisaron el contenido y son responsables de él. [Confirmar.]",
              "Use of generative AI: AI tools supported programming, literature search and writing; the authors "
              "reviewed the content and take responsibility for it. [Confirm.]"),
        ]))
    return B, c


def numerar_citas(B: list) -> tuple[list, list]:
    """Sustituye ⟦claves⟧ por [n] en orden de aparición y devuelve la lista de referencias usadas."""
    refs = referencias_base()
    orden: list[str] = []

    def sustituir(m):
        nums = []
        for k in (x.strip() for x in m.group(1).split(",")):
            if k not in refs:
                raise KeyError(f"referencia desconocida: {k}")
            if k not in orden:
                orden.append(k)
            nums.append(orden.index(k) + 1)
        return ", ".join(f"[{x}]" for x in nums)

    salida = [("p", re.sub(r"⟦([^⟧]+)⟧", sustituir, b[1])) if b[0] == "p" else b for b in B]
    return salida, [refs[k] for k in orden]
