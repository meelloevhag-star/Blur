"""
F5 · Versión larga para revista indexada, en español e inglés, generada desde los resultados.

- EN: formato tipo Elsevier (Highlights, Data availability, CRediT, Declaration of interests).
- ES: formato de revista Scopus en español (resumen, palabras clave, disponibilidad de datos).
Una sola fuente de cifras (JSON de resultados) para ambos idiomas.

Uso:
    python articulo/generar_revista.py
Salidas:
    articulo/revista/BioCrete-NEAT_revista_ES.docx
    articulo/revista/BioCrete-NEAT_revista_EN.docx
"""

import json
import re
from pathlib import Path

import docx
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

RAIZ = Path(__file__).resolve().parents[1]
RES = RAIZ / "biocrete_neat" / "resultados"
FIGS = RES / "f3"
ORIGINAL = RAIZ / "articulo" / "original" / "BioCrete-NEAT_v1_original.docx"
SALIDA = RAIZ / "articulo" / "revista"
REPO_URL = "https://github.com/meelloevhag-star/Blur"


def _j(ruta: Path) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


def cifras() -> dict:
    zen = _j(RES / "resumen_datasets_reales_zenodo.json")
    neat = _j(RES / "resumen_neat.json")
    f3 = _j(RES / "f3" / "resumen_f3.json")
    flujo = _j(RAIZ / "biocrete_neat" / "modelos" / "demo_flujo" / "registro_versiones.json")
    rep, meta = f3["replicas"], f3["meta"]
    return {
        "zen": zen, "neat": neat, "f3": f3, "rep": rep, "meta": meta,
        "R": rep["modelos"], "M": meta["modelos"],
        "mr": max(rep["modelos"], key=lambda m: rep["modelos"][m]["R2"]),
        "mm": max(meta["modelos"], key=lambda m: meta["modelos"][m]["R2"]),
        "flujo": {e["version"]: e for e in flujo},
        "n_agno3": sum(r["n_mediciones"] for r in zen["cappellesso2024_agno3_marino"]),
        "kf": neat["cv_5fold_alpha_por_lambda"],
        "cm": neat["cv_5fold_cierre_pct"],
    }


def referencias_originales() -> list[str]:
    d = docx.Document(str(ORIGINAL))
    from correcciones_referencias import corregir

    return [corregir(re.sub(r"^\[\d+\]\s*", "", p.text).strip())
            for p in d.paragraphs if re.match(r"^\[\d+\]", p.text)]


REF_NUEVAS = [
    "T. Chen and C. Guestrin, “XGBoost: A scalable tree boosting system,” in Proc. 22nd ACM SIGKDD Int. Conf. "
    "Knowl. Discov. Data Min., 2016, pp. 785–794, doi: 10.1145/2939672.2939785.",
    "S. M. Lundberg and S.-I. Lee, “A unified approach to interpreting model predictions,” in Adv. Neural Inf. "
    "Process. Syst., vol. 30, 2017, pp. 4765–4774.",
    "G. I. Parisi, R. Kemker, J. L. Part, C. Kanan, and S. Wermter, “Continual lifelong learning with neural "
    "networks: A review,” Neural Netw., vol. 113, pp. 54–71, 2019, doi: 10.1016/j.neunet.2019.01.012.",
    "S. Kapoor and A. Narayanan, “Leakage and the reproducibility crisis in machine-learning-based science,” "
    "Patterns, vol. 4, no. 9, Art. no. 100804, 2023, doi: 10.1016/j.patter.2023.100804.",
    "S. Varma and R. Simon, “Bias in error estimation when using cross-validation for model selection,” BMC "
    "Bioinformatics, vol. 7, Art. no. 91, 2006, doi: 10.1186/1471-2105-7-91.",
]


def L(es: bool, txt_es: str, txt_en: str) -> str:
    return txt_es if es else txt_en


def contenido(c: dict, lang: str) -> dict:
    es = lang == "es"
    R, M, mr, mm, rep, meta = c["R"], c["M"], c["mr"], c["mm"], c["rep"], c["meta"]

    def n(x, d=3):
        s = f"{x:.{d}f}"
        return s.replace(".", ",") if es else s

    def ic(m):
        a, b = n(m["R2_IC95"][0], 2), n(m["R2_IC95"][1], 2)
        return f"[{a}; {b}]" if es else f"[{a}, {b}]"

    n_rep, g_rep = rep["n_registros"], rep["n_grupos"]
    n_mousa, n_capm = rep["fuentes"]["Mousa2022"], rep["fuentes"]["Cappellesso2024"]
    n_meta, e_meta = meta["n_registros"], meta["n_estudios"]
    nr, nm = R["NEAT λ=0.0008"], M["NEAT (λ anidado)"]
    p2, p3 = c["flujo"][2]["r2_prospectivo"], c["flujo"][3]["r2_prospectivo"]
    nr2, nr3 = c["flujo"][2]["n_registros_nuevos"], c["flujo"][3]["n_registros_nuevos"]
    cu = c["f3"]["curva_aprendizaje"]
    sr, sm = c["f3"]["shap"]["replicas"], c["f3"]["shap"]["meta"]
    lam = meta["lambdas_elegidos_cv_anidada"]
    n_alta = sum(1 for l in lam if abs(l - 8e-4) < 1e-9)
    pa = c["f3"]["paita"]
    kf, cm = c["kf"], c["cm"]
    top = c["neat"]["topologia_final_alpha"]
    ratio = c["zen"]["dryad_razon_mediana_life365_vs_exp"]
    T = {}

    T["titulo"] = L(es,
        "BioCrete-NEAT: neuroevolución explicable con aprendizaje continuo para predecir la autorreparación del "
        "concreto bacteriano en ambientes marinos a partir de datos abiertos y colaborativos",
        "BioCrete-NEAT: explainable neuroevolution with continual learning to predict bacterial concrete "
        "self-healing in marine environments from open and collaborative data")
    T["highlights"] = [
        L(es, f"{n_rep} registros de cierre de fisuras extraídos con trazabilidad desde repositorios con DOI",
              f"{n_rep} crack-closure records extracted with full traceability from DOI repositories"),
        L(es, "La validación agrupada sin fuga corrige a la baja métricas infladas por particiones por fila",
              "Leakage-free grouped validation corrects metrics inflated by row-wise splitting"),
        L(es, "NEAT logra precisión competitiva con redes de casi cero neuronas ocultas",
              "NEAT reaches competitive accuracy with nearly zero hidden neurons"),
        L(es, "Un modelo congelado falla ante datos marinos nuevos; la actualización continua lo recupera",
              "A frozen model fails on new marine data; continual updating recovers it"),
        L(es, "Plantilla validada y cosecha mensual permiten que tesis y laboratorios mejoren el modelo",
              "A validated template and monthly harvest let theses and labs improve the model"),
    ]
    T["resumen"] = L(es,
        "El concreto autocurativo bacteriano (CAB) promete prolongar la vida útil de la infraestructura costera, "
        "pero evaluarlo en exposición marina exige programas experimentales de 28 a 365 días. Los modelos de "
        "aprendizaje automático propuestos para acortar ese ciclo suelen entrenarse con pocos promedios de "
        "literatura, validarse con particiones por fila que permiten fuga entre réplicas de un mismo estudio y "
        "quedar congelados tras su publicación. Este trabajo presenta BioCrete-NEAT, un marco abierto que combina "
        "neuroevolución de topologías crecientes (NEAT) con un esquema de aprendizaje continuo. Se extrajeron "
        f"{n_rep} registros individuales de cierre de fisuras de {g_rep} fisuras y probetas de dos repositorios con "
        f"DOI ({n_capm} de ellos en agua de mar ASTM D1141) y se usó un meta-dataset de {n_meta} condiciones de "
        f"{e_meta} estudios para la reducción de transporte de cloruros (α). Con validación cruzada agrupada, "
        f"selección anidada de hiperparámetros e intervalos de confianza bootstrap, {mr} alcanzó "
        f"R² = {n(R[mr]['R2'])} {ic(R[mr])} en cierre y {mm} R² = {n(M[mm]['R2'])} {ic(M[mm])} en α. NEAT obtuvo "
        f"R² = {n(nr['R2'])} y {n(nm['R2'])} con redes de casi cero neuronas ocultas, superó a la regresión lineal "
        "en cierre y coincidió con SHAP en que el nivel de protección biológica gobierna α. La validación agrupada "
        f"redujo el R² de NEAT en α de 0,540 (particiones por fila) a {n(nm['R2'])}. En una simulación de llegada "
        f"de datos por lotes, un modelo congelado cayó a R² = {n(p3['campeon_vigente'])} ante datos marinos nuevos, "
        "mientras que la actualización con control campeón/candidato se recuperó a "
        f"R² = {n(p3['candidato_caliente'])}. El marco incluye una plantilla validada de aportes, una cosecha "
        "mensual de literatura y tesis, un registro de versiones y predicciones con incertidumbre para el programa "
        "experimental de Paita-Piura (Perú).",
        "Bacterial self-healing concrete (BSHC) promises to extend the service life of coastal infrastructure, but "
        "its evaluation under marine exposure requires 28- to 365-day test programs. Machine learning models "
        "proposed to shorten this cycle are typically trained on a few literature averages, validated with "
        "row-wise splits that leak information between replicates of the same study, and frozen after publication. "
        "This work presents BioCrete-NEAT, an open framework coupling NeuroEvolution of Augmenting Topologies (NEAT) "
        f"with a continual-learning scheme. We extracted {n_rep} individual crack-closure records from {g_rep} "
        f"cracks and specimens in two DOI repositories ({n_capm} of them in ASTM D1141 seawater) and used a "
        f"{n_meta}-condition, {e_meta}-study meta-dataset for chloride transport reduction (α). Under grouped "
        f"cross-validation, nested hyperparameter selection and bootstrap confidence intervals, {mr} reached "
        f"R² = {n(R[mr]['R2'])} {ic(R[mr])} for closure and {mm} R² = {n(M[mm]['R2'])} {ic(M[mm])} for α. NEAT "
        f"achieved R² = {n(nr['R2'])} and {n(nm['R2'])} with nearly zero hidden neurons, outperformed linear "
        "regression on closure, and agreed with SHAP that biological protection governs α. Grouped validation "
        f"lowered NEAT's α R² from 0.540 (row-wise splits) to {n(nm['R2'])}. In a batch-arrival simulation, a "
        f"frozen model dropped to R² = {n(p3['campeon_vigente'])} on new marine data, whereas champion/challenger "
        f"updating recovered R² = {n(p3['candidato_caliente'])}. The framework provides a validated contribution "
        "template, a monthly literature and thesis harvest, a version registry, and predictions with uncertainty "
        "for the Paita-Piura (Peru) experimental program.")
    T["claves"] = L(es,
        "concreto autocurativo bacteriano; neuroevolución; NEAT; aprendizaje continuo; aprendizaje automático "
        "explicable; fuga de datos; ambiente marino; datos abiertos",
        "bacterial self-healing concrete; neuroevolution; NEAT; continual learning; explainable machine learning; "
        "data leakage; marine environment; open data")

    S = []
    S.append((1, L(es, "1. Introducción", "1. Introduction"), [
        L(es,
          "El diseño de concreto autocurativo bacteriano (CAB) para infraestructura costera enfrenta un cuello de "
          "botella experimental: cuantificar el cierre de fisuras y la reducción del transporte de cloruros exige "
          "programas de 28, 56, 90 o hasta 365 días bajo inmersión o ciclos marinos [1], [2]. En un estudio paralelo "
          "a escala estructural (BioCrete-Markov) [3] se mostró que extender la vida útil del litoral de Paita-Colán "
          "exige umbrales precisos de reducción de transporte (α) según la relación agua/cemento, el recubrimiento "
          "y la vida media biológica de las esporas. Un modelo estructural responde cuánta autorreparación se "
          "requiere, pero no predice cuánta entregará una formulación antes de ensayarla.",
          "Designing bacterial self-healing concrete (BSHC) for coastal infrastructure faces an experimental "
          "bottleneck: quantifying crack closure and chloride transport reduction requires 28-, 56-, 90- or even "
          "365-day programs under immersion or marine cycles [1], [2]. A companion structural-scale study "
          "(BioCrete-Markov) [3] showed that extending the service life of the Paita-Colán coastline requires precise "
          "transport-reduction thresholds (α) as a function of the water/cement ratio, cover depth and the "
          "biological half-life of spores. A structural model answers how much self-healing is required, but cannot "
          "predict how much a given formulation will deliver before testing it."),
        L(es,
          "La literatura reciente recurre al aprendizaje automático para predecir propiedades del concreto y su "
          "autorreparación [4], [5], y a modelos cinéticos de primer orden para el cierre de fisuras [6], [7]. "
          "Persisten tres problemas metodológicos. Primero, las redes neuronales suelen tener arquitecturas fijadas "
          "por ensayo y error, opacas y propensas al sobreajuste con pocos datos. Segundo, la validación por filas "
          "permite que réplicas de un mismo estudio o probeta estén a la vez en entrenamiento y prueba; esta fuga de "
          "información es una causa documentada de resultados irreproducibles en ciencia basada en aprendizaje "
          "automático [22]. Tercero, los modelos publicados quedan congelados y no incorporan los ensayos que siguen "
          "produciendo tesis y laboratorios.",
          "Recent studies use machine learning to predict concrete properties and self-healing [4], [5], and "
          "first-order kinetic models for crack closure [6], [7]. Three methodological problems persist. First, "
          "neural networks usually have hand-tuned architectures that are opaque and prone to overfitting small "
          "datasets. Second, row-wise validation lets replicates of the same study or specimen appear in both "
          "training and test sets; this leakage is a documented cause of irreproducible machine-learning-based "
          "science [22]. Third, published models are frozen and do not incorporate the tests that theses and "
          "laboratories keep producing."),
        L(es,
          "La neuroevolución de topologías crecientes (NEAT) [8] evoluciona a la vez los pesos y la estructura de "
          "la red partiendo de redes mínimas, y solo añade neuronas o conexiones cuando mejoran la aptitud. Esto "
          "produce redes pequeñas e inspeccionables y, además, una población que puede reanudarse cuando llegan "
          "datos nuevos, lo que la hace natural para el aprendizaje continuo [21]. Como referentes de precisión se "
          "usan bosques aleatorios [9] y árboles con gradiente (XGBoost) [19], interpretados con valores SHAP [20].",
          "NeuroEvolution of Augmenting Topologies (NEAT) [8] evolves both weights and network structure from "
          "minimal networks, adding neurons or connections only when they improve fitness. This yields small, "
          "inspectable networks and a population that can be resumed when new data arrive, which makes NEAT a "
          "natural fit for continual learning [21]. Random forests [9] and gradient-boosted trees (XGBoost) [19], "
          "interpreted with SHAP values [20], serve as accuracy baselines."),
        L(es,
          "Este artículo aporta: (1) la extracción trazable de registros individuales de cierre de fisuras desde "
          "repositorios abiertos, corrigiendo errores de etiquetado de una versión previa; (2) una comparación de "
          "NEAT, XGBoost, Random Forest y Ridge con validación agrupada sin fuga, selección anidada e intervalos de "
          "confianza; (3) un esquema de aprendizaje continuo con entrada validada de datos de terceros, cosecha "
          "periódica de literatura y tesis, neuroevolución incremental y control campeón/candidato; y (4) "
          "predicciones con incertidumbre para el programa experimental de Paita-Piura.",
          "This article contributes: (1) traceable extraction of individual crack-closure records from open "
          "repositories, correcting labelling errors of a previous version; (2) a comparison of NEAT, XGBoost, "
          "Random Forest and Ridge under leakage-free grouped validation, nested selection and confidence intervals; "
          "(3) a continual-learning scheme with validated third-party data intake, periodic literature and thesis "
          "harvesting, incremental neuroevolution and champion/challenger control; and (4) predictions with "
          "uncertainty for the Paita-Piura experimental program."),
    ]))

    S.append((1, L(es, "2. Materiales y métodos", "2. Materials and methods"), []))
    S.append((2, L(es, "2.1. Fuentes de datos", "2.1. Data sources"), [
        L(es,
          "Se descargaron conjuntos crudos con DOI desde Zenodo y Dryad (Tabla 1). Mousa et al. [12] reportan "
          "morteros con Bacillus pseudofirmus encapsulado en perlas de hidrogel, agregado liviano (LWA) o "
          "nanocristales de celulosa (CNC), con acetato de magnesio, lactato de calcio o lactato de sodio como "
          "precursores, sometidos a 28 días de ciclos de humedecimiento y secado. Cappellesso et al. [11] reportan "
          "concreto con un agente bacteriano comercial (BAS) o un aditivo cristalino (CA) frente a una referencia "
          "(REF), con fisuras de 100 y 300 µm, con o sin curado previo, expuesto a agua de mar ASTM D1141. Se usaron "
          f"además 239 ensayos de migración de cloruros de Dryad [10] y un meta-dataset de {n_meta} condiciones de "
          f"{e_meta} estudios revisados por pares [1], [2], [14]–[18].",
          "Raw datasets with DOIs were downloaded from Zenodo and Dryad (Table 1). Mousa et al. [12] report mortars "
          "with Bacillus pseudofirmus encapsulated in hydrogel beads, lightweight aggregate (LWA) or cellulose "
          "nanocrystals (CNC), with magnesium acetate, calcium lactate or sodium lactate precursors, subjected to "
          "28 days of wet/dry cycles. Cappellesso et al. [11] report concrete with a commercial bacterial agent (BAS) "
          "or a crystalline admixture (CA) versus a reference (REF), with 100 and 300 µm cracks, with or without "
          "pre-curing, exposed to ASTM D1141 seawater. In addition, 239 chloride migration tests from Dryad [10] and "
          f"a {n_meta}-condition meta-dataset from {e_meta} peer-reviewed studies [1], [2], [14]–[18] were used."),
        ("tabla", "t1"),
    ]))
    S.append((2, L(es, "2.2. Extracción y control de calidad", "2.2. Extraction and quality control"), [
        L(es,
          "En Mousa et al. se extrajo una fila por fisura (anchos a 0, 3, 7, 14 y 28 días) desde las pestañas de "
          "réplicas, deduplicando por la tupla de anchos porque las pestañas se solapan; una fisura con ancho "
          f"inicial nulo se excluyó, quedando {n_mousa} registros de {n_mousa // 4} fisuras. Al revisar la versión "
          "previa del extractor se detectó que dos muestras sin bacterias se habían etiquetado como bacterianas; el "
          "nuevo clasificador se verificó con pruebas automáticas, incluida la coincidencia del cierre calculado con "
          "la razón almacenada en el propio archivo. En Cappellesso et al. se promediaron las mediciones de ancho "
          "por probeta y zona en cada fecha, y el cierre se calculó respecto de la medición inicial, resultando "
          f"{n_capm} registros. Cada registro conserva DOI, hoja de origen e identificadores de condición y de "
          "probeta. Un script de auditoría compara automáticamente las cifras reportadas con los resultados del "
          "código.",
          "For Mousa et al., one row per crack (widths at 0, 3, 7, 14 and 28 days) was extracted from the replicate "
          "sheets, de-duplicating by the width tuple because sheets overlap; one crack with zero initial width was "
          f"excluded, leaving {n_mousa} records from {n_mousa // 4} cracks. Reviewing the previous extractor revealed "
          "that two bacteria-free samples had been labelled as bacterial; the new classifier was verified with "
          "automated tests, including agreement between the computed closure and the ratio stored in the source "
          "file. For Cappellesso et al., width measurements were averaged per specimen and zone at each date and "
          f"closure was computed relative to the initial measurement, yielding {n_capm} records. Every record keeps "
          "its DOI, source sheet and condition and specimen identifiers. An audit script automatically compares the "
          "reported figures against the code results."),
    ]))
    S.append((2, L(es, "2.3. Variables y normalización", "2.3. Variables and normalization"), [
        L(es,
          "El cierre de fisuras se modeló con seis entradas: ancho inicial w0 (mm), edad desde la fisuración (d), "
          "nivel de protección biológica (0 = sin bacterias; 1 = adición directa o agente comercial; 2 = portador "
          "poroso; 3 = encapsulación), ambiente marino, lactato de calcio y curado previo (binarias). La reducción "
          "α del meta-dataset usó a/c, w0, edad, protección, ambiente y lactato. Todas las entradas se normalizaron "
          "a [0, 1] con límites físicos fijos, lo que evita fuga entre particiones y permite que una red procese "
          "datos futuros sin re-escalar.",
          "Crack closure was modelled with six inputs: initial width w0 (mm), age since cracking (d), biological "
          "protection level (0 = no bacteria; 1 = direct addition or commercial agent; 2 = porous carrier; "
          "3 = encapsulation), marine environment, calcium lactate and pre-curing (binary). The meta-dataset "
          "reduction α used w/c, w0, age, protection, environment and lactate. All inputs were normalized to "
          "[0, 1] with fixed physical bounds, which prevents leakage between folds and allows a network to process "
          "future data without rescaling."),
    ]))
    S.append((2, L(es, "2.4. Modelos", "2.4. Models"), [
        L(es,
          "NEAT se implementó con neat-python 2.0.0 (población 60, 75 generaciones, red feed-forward, activación "
          "sigmoide, cero neuronas ocultas iniciales) con la aptitud F(g) = −MSE(g) − λ_p·(N_ocultas + "
          "0,15·N_conex), donde λ_p penaliza la complejidad. Como referentes se usaron XGBoost (400 árboles, "
          "profundidad 4, η = 0,04), Random Forest (300 árboles, profundidad 8) y regresión Ridge (L2 = 1,0) "
          "(Tabla 2).",
          "NEAT was implemented with neat-python 2.0.0 (population 60, 75 generations, feed-forward network, "
          "sigmoid activation, zero initial hidden neurons) with fitness F(g) = −MSE(g) − λ_p·(N_hidden + "
          "0.15·N_conn), where λ_p penalizes complexity. Baselines were XGBoost (400 trees, depth 4, η = 0.04), "
          "Random Forest (300 trees, depth 8) and Ridge regression (L2 = 1.0) (Table 2)."),
        ("tabla", "t2"),
    ]))
    S.append((2, L(es, "2.5. Protocolo de validación", "2.5. Validation protocol"), [
        L(es,
          "Se usó GroupKFold de 5 particiones agrupando por fisura o probeta (réplicas) y por estudio "
          "(meta-dataset), de modo que ninguna unidad experimental aparezca en entrenamiento y prueba [22]. λ_p se "
          "eligió entre 8×10⁻⁴ y 1,2×10⁻⁴ por validación cruzada anidada [23]. Los intervalos de confianza del "
          "95 % se obtuvieron remuestreando grupos completos (1000 réplicas bootstrap). La importancia de variables "
          "se cuantificó con SHAP sobre XGBoost y por permutación sobre NEAT, y la curva de aprendizaje se "
          "construyó con submuestras del 10 % al 100 % de los grupos.",
          "Five-fold GroupKFold was used, grouping by crack or specimen (replicates) and by study (meta-dataset), so "
          "that no experimental unit appears in both training and test sets [22]. λ_p was chosen between 8×10⁻⁴ and "
          "1.2×10⁻⁴ by nested cross-validation [23]. 95% confidence intervals were obtained by resampling whole "
          "groups (1000 bootstrap replicates). Feature importance was quantified with SHAP on XGBoost and by "
          "permutation on NEAT, and the learning curve was built from 10% to 100% subsamples of the groups."),
    ]))
    S.append((2, L(es, "2.6. Aprendizaje continuo", "2.6. Continual learning"), [
        L(es,
          "El esquema de actualización tiene cuatro componentes. (i) Entrada de datos: una plantilla CSV y un "
          "validador que exige DOI o enlace, norma de ensayo, autoría, rangos físicos y coherencia entre anchos y "
          "cierre, y que rechaza —sin imputar— las filas inválidas. (ii) Cosecha mensual automatizada de "
          "artículos, datasets y tesis (OpenAlex, Zenodo, RENATI, ALICIA) con el mismo protocolo, que propone los "
          "cambios como una solicitud revisable. (iii) Neuroevolución incremental: el candidato reanuda la población "
          "NEAT guardada de la versión vigente, restaurando el rastreador de innovaciones para que la numeración "
          "genética continúe. (iv) Control campeón/candidato: el candidato solo reemplaza al campeón si iguala o "
          "supera su R² prospectivo en los grupos nuevos, evaluado con GroupKFold sobre ellos; como referencia se "
          "entrena también desde cero con las mismas generaciones. Cada versión se registra con la huella de sus "
          "datos, métricas y fecha. El esquema se evaluó simulando la llegada secuencial de tres lotes: Mousa et "
          "al., Cappellesso et al. con curado previo y Cappellesso et al. con exposición directa.",
          "The updating scheme has four components. (i) Data intake: a CSV template and a validator that requires a "
          "DOI or link, test standard, authorship, physical ranges and consistency between widths and closure, and "
          "rejects —without imputing— invalid rows. (ii) An automated monthly harvest of articles, datasets and "
          "theses (OpenAlex, Zenodo, RENATI, ALICIA) under the same protocol, which proposes changes as a reviewable "
          "request. (iii) Incremental neuroevolution: the challenger resumes the saved NEAT population of the "
          "current version, restoring the innovation tracker so that genetic numbering continues. (iv) Champion/"
          "challenger control: the challenger replaces the champion only if it matches or exceeds its prospective "
          "R² on the new groups, evaluated with GroupKFold on them; a from-scratch model with the same generations "
          "is trained as a reference. Each version is logged with its data fingerprint, metrics and date. The "
          "scheme was evaluated by simulating the sequential arrival of three batches: Mousa et al., Cappellesso "
          "et al. with pre-curing, and Cappellesso et al. with direct exposure."),
    ]))

    S.append((1, L(es, "3. Resultados", "3. Results"), []))
    S.append((2, L(es, "3.1. Difusión de laboratorio y penetración marina de cloruros",
                   "3.1. Laboratory diffusion and marine chloride penetration"), [
        L(es,
          "La ecuación base de Life-365 (D28 = 10^(−12,06 + 2,40·a/c)) frente a 239 ensayos de Dryad dio una razón "
          f"mediana Life-365/experimental de {n(ratio, 2)}×, por lo que su subestimación de la vida útil en Colán "
          f"[3] se atribuye a las condiciones de frontera locales. En las {c['n_agno3']} mediciones de penetración "
          "de cloruros de Cappellesso et al. (Tabla 3), el agente bacteriano redujo la profundidad entre 15,4 % y "
          "30,0 % en probetas sin fisurar y en series sin pre-curado, muy por debajo del techo de 68 % citado con "
          "frecuencia.",
          "Life-365's base equation (D28 = 10^(−12.06 + 2.40·w/c)) against 239 Dryad tests gave a median "
          f"Life-365/experimental ratio of {n(ratio, 2)}×, so its underestimation of service life in Colán [3] is "
          f"attributed to local boundary conditions. Across the {c['n_agno3']} chloride penetration measurements of "
          "Cappellesso et al. (Table 3), the bacterial agent reduced depth by 15.4–30.0% in uncracked specimens and "
          "non-pre-cured series, well below the frequently cited 68% ceiling."),
        ("tabla", "t3"),
    ]))
    S.append((2, L(es, "3.2. Comparación de modelos", "3.2. Model comparison"), [
        L(es,
          f"La Tabla 4 y la Fig. 1 resumen el desempeño fuera de muestra. En cierre, {mr} lideró con "
          f"R² = {n(R[mr]['R2'])} {ic(R[mr])}, seguido de XGBoost ({n(R['XGBoost']['R2'])}); NEAT obtuvo "
          f"{n(nr['R2'])} {ic(nr)} con {n(nr['neuronas_ocultas_prom'], 1)} neuronas ocultas en promedio y superó a "
          f"Ridge ({n(R['Ridge']['R2'])}). En α, {mm} lideró con R² = {n(M[mm]['R2'])} {ic(M[mm])}; NEAT con λ_p "
          f"anidado alcanzó {n(nm['R2'])} {ic(nm)}, y la validación anidada eligió la parsimonia alta en {n_alta} "
          f"de {len(lam)} particiones.",
          f"Table 4 and Fig. 1 summarize out-of-sample performance. For closure, {mr} led with "
          f"R² = {n(R[mr]['R2'])} {ic(R[mr])}, followed by XGBoost ({n(R['XGBoost']['R2'])}); NEAT obtained "
          f"{n(nr['R2'])} {ic(nr)} with {n(nr['neuronas_ocultas_prom'], 1)} hidden neurons on average and "
          f"outperformed Ridge ({n(R['Ridge']['R2'])}). For α, {mm} led with R² = {n(M[mm]['R2'])} {ic(M[mm])}; "
          f"NEAT with nested λ_p reached {n(nm['R2'])} {ic(nm)}, and nested validation chose high parsimony in "
          f"{n_alta} of {len(lam)} folds."),
        ("tabla", "t4"),
        ("figura", "fig4_comparacion_modelos_ic95.png",
         L(es, "Fig. 1. R² fuera de muestra con IC 95 % (bootstrap por grupos): réplicas de cierre (izquierda) y "
               "meta-dataset α (derecha).",
               "Fig. 1. Out-of-sample R² with 95% CI (group bootstrap): crack-closure replicates (left) and α "
               "meta-dataset (right).")),
    ]))
    S.append((2, L(es, "3.3. Sensibilidad al protocolo de validación y a la parsimonia",
                   "3.3. Sensitivity to the validation protocol and parsimony"), [
        L(es,
          f"Con particiones por fila (KFold) sobre el meta-dataset, NEAT obtuvo R² = {n(kf['0.0008']['NEAT']['R2'])} "
          f"con λ_p = 8×10⁻⁴ y {n(kf['0.00012']['NEAT']['R2'])} con 1,2×10⁻⁴ "
          f"({n(kf['0.00012']['neat_neuronas_ocultas_promedio'], 1)} neuronas ocultas), frente a "
          f"{n(M['NEAT λ=0.0008']['R2'])} y {n(M['NEAT λ=0.00012']['R2'])} con agrupación por estudio. La "
          "diferencia cuantifica el optimismo de la validación por filas. Con KFold, el cierre del meta-dataset "
          f"fue prácticamente impredecible (R² = {n(cm['NEAT']['R2'])} NEAT, {n(cm['RandomForest']['R2'])} RF, "
          f"{n(cm['Ridge']['R2'])} Ridge), lo que motivó el uso de réplicas individuales para ese objetivo. En las "
          f"réplicas, ambos λ_p dieron resultados similares ({n(R['NEAT λ=0.0008']['R2'])} y "
          f"{n(R['NEAT λ=0.00012']['R2'])}), lo que indica que con más datos la parsimonia deja de ser crítica.",
          f"With row-wise splits (KFold) on the meta-dataset, NEAT obtained R² = {n(kf['0.0008']['NEAT']['R2'])} "
          f"with λ_p = 8×10⁻⁴ and {n(kf['0.00012']['NEAT']['R2'])} with 1.2×10⁻⁴ "
          f"({n(kf['0.00012']['neat_neuronas_ocultas_promedio'], 1)} hidden neurons), versus "
          f"{n(M['NEAT λ=0.0008']['R2'])} and {n(M['NEAT λ=0.00012']['R2'])} when grouping by study. The "
          "difference quantifies the optimism of row-wise validation. With KFold, meta-dataset closure was "
          f"practically unpredictable (R² = {n(cm['NEAT']['R2'])} NEAT, {n(cm['RandomForest']['R2'])} RF, "
          f"{n(cm['Ridge']['R2'])} Ridge), which motivated using individual replicates for that target. On the "
          f"replicates, both λ_p values gave similar results ({n(R['NEAT λ=0.0008']['R2'])} and "
          f"{n(R['NEAT λ=0.00012']['R2'])}), indicating that parsimony becomes less critical as data grow."),
    ]))
    S.append((2, L(es, "3.4. Explicabilidad", "3.4. Explainability"), [
        L(es,
          f"Sobre el meta-dataset completo, NEAT convergió a {top['neuronas_ocultas']} neuronas ocultas y "
          f"{top['conexiones_activas']} conexiones activas. SHAP (Fig. 2) coincide con la permutación sobre NEAT: "
          f"la protección biológica domina α (|SHAP| medio = {n(sm[0]['shap_medio_abs'])}), coherente con la "
          "degradación de esporas sin protección [14] y con el límite práctico de cierre sobre 0,5 mm [15]. En el "
          f"cierre de las réplicas (Fig. 3) domina la edad ({n(sr[0]['shap_medio_abs'])}), seguida del ancho "
          f"inicial ({n(sr[1]['shap_medio_abs'])}).",
          f"On the full meta-dataset, NEAT converged to {top['neuronas_ocultas']} hidden neurons and "
          f"{top['conexiones_activas']} active connections. SHAP (Fig. 2) agrees with permutation on NEAT: "
          f"biological protection dominates α (mean |SHAP| = {n(sm[0]['shap_medio_abs'])}), consistent with the "
          "degradation of unprotected spores [14] and the practical closure limit above 0.5 mm [15]. For replicate "
          f"closure (Fig. 3), age dominates ({n(sr[0]['shap_medio_abs'])}), followed by initial width "
          f"({n(sr[1]['shap_medio_abs'])})."),
        ("figura", "fig5b_shap_meta.png", L(es, "Fig. 2. Valores SHAP de XGBoost para α (meta-dataset).",
                                            "Fig. 2. XGBoost SHAP values for α (meta-dataset).")),
        ("figura", "fig5a_shap_replicas.png",
         L(es, "Fig. 3. Valores SHAP de XGBoost para el cierre de fisuras (réplicas).",
               "Fig. 3. XGBoost SHAP values for crack closure (replicates).")),
    ]))
    S.append((2, L(es, "3.5. Curva de aprendizaje y aprendizaje continuo",
                   "3.5. Learning curve and continual learning"), [
        L(es,
          f"Todos los modelos mejoraron con más datos (Fig. 4): Random Forest pasó de R² = {n(cu['RandomForest'][0])} "
          f"con {cu['n_registros'][0]} registros a {n(cu['RandomForest'][-1])} con {cu['n_registros'][-1]}, y NEAT "
          f"de {n(cu['NEAT λ=0.0008'][0])} a {n(max(cu['NEAT λ=0.0008']))}. En la simulación por lotes (Fig. 5), el "
          f"modelo congelado cayó a R² = {n(p2['campeon_vigente'])} con el lote marino con curado previo "
          f"(+{nr2} registros) y a {n(p3['campeon_vigente'])} con el de exposición directa (+{nr3}), mientras que "
          f"el candidato actualizado alcanzó {n(p2['candidato_caliente'])} y {n(p3['candidato_caliente'])} y fue "
          "aceptado en todos los lotes. El arranque en caliente superó al arranque desde cero en el segundo lote "
          f"({n(p2['candidato_caliente'])} frente a {n(p2['referencia_frio'])}) y quedó por debajo en el tercero "
          f"({n(p3['candidato_caliente'])} frente a {n(p3['referencia_frio'])}).",
          f"All models improved with more data (Fig. 4): Random Forest went from R² = {n(cu['RandomForest'][0])} "
          f"with {cu['n_registros'][0]} records to {n(cu['RandomForest'][-1])} with {cu['n_registros'][-1]}, and "
          f"NEAT from {n(cu['NEAT λ=0.0008'][0])} to {n(max(cu['NEAT λ=0.0008']))}. In the batch simulation "
          f"(Fig. 5), the frozen model dropped to R² = {n(p2['campeon_vigente'])} on the pre-cured marine batch "
          f"(+{nr2} records) and to {n(p3['campeon_vigente'])} on the direct-exposure batch (+{nr3}), whereas the "
          f"updated challenger reached {n(p2['candidato_caliente'])} and {n(p3['candidato_caliente'])} and was "
          "accepted in every batch. Warm start beat training from scratch in the second batch "
          f"({n(p2['candidato_caliente'])} vs {n(p2['referencia_frio'])}) and fell short in the third "
          f"({n(p3['candidato_caliente'])} vs {n(p3['referencia_frio'])})."),
        ("figura", "fig6_curva_aprendizaje.png", L(es, "Fig. 4. Curva de aprendizaje (GroupKFold por fisura).",
                                                   "Fig. 4. Learning curve (GroupKFold by crack).")),
        ("figura", "fig7_aprendizaje_continuo.png",
         L(es, "Fig. 5. Validación prospectiva por lote: campeón congelado, candidato NEAT incremental y NEAT desde "
               "cero.",
               "Fig. 5. Prospective validation per batch: frozen champion, incremental NEAT challenger and NEAT "
               "from scratch.")),
    ]))
    S.append((2, L(es, "3.6. Predicciones para Paita-Piura", "3.6. Predictions for Paita-Piura"), [
        L(es,
          "Un ensamble bootstrap de 100 modelos XGBoost con restricciones monótonas (más ancho, menos cierre; más "
          "edad, más cierre) predijo para 90 días en agua de mar con lactato de calcio un cierre de "
          f"{n(pa[0]['cierre_medio_pct'], 1)} % en fisuras de 0,2 mm y {n(pa[1]['cierre_medio_pct'], 1)} % en 0,5 mm "
          "con adición directa (Tabla 5). Todas las predicciones son extrapolaciones parciales y se marcan como "
          "tales.",
          "A bootstrap ensemble of 100 XGBoost models with monotonic constraints (wider crack, less closure; older, "
          "more closure) predicted 90-day seawater closure with calcium lactate of "
          f"{n(pa[0]['cierre_medio_pct'], 1)}% for 0.2 mm cracks and {n(pa[1]['cierre_medio_pct'], 1)}% for 0.5 mm "
          "with direct addition (Table 5). All predictions are partial extrapolations and are flagged as such."),
        ("tabla", "t5"),
    ]))

    S.append((1, L(es, "4. Discusión", "4. Discussion"), [
        L(es,
          "La principal lección metodológica es que el protocolo de validación cambia la conclusión. Con "
          "particiones por fila, NEAT parecía superar a los referentes en α; con agrupación por estudio, los "
          "árboles con gradiente marcan el techo y la ventaja de NEAT desaparece. Este resultado coincide con la "
          "literatura sobre fuga en ciencia basada en aprendizaje automático [22] y debería ser práctica estándar "
          "en modelos de materiales construidos a partir de meta-datasets.",
          "The main methodological lesson is that the validation protocol changes the conclusion. With row-wise "
          "splits, NEAT seemed to beat the baselines on α; with grouping by study, gradient-boosted trees set the "
          "ceiling and NEAT's advantage vanishes. This agrees with the literature on leakage in "
          "machine-learning-based science [22] and should become standard practice for materials models built "
          "from meta-datasets."),
        L(es,
          "El valor de NEAT no está en superar a XGBoost, sino en ofrecer, con precisión competitiva, una red tan "
          "pequeña que puede dibujarse, auditarse y defenderse ante un comité técnico, y cuya población puede "
          "reanudarse cuando llegan datos nuevos. La concordancia entre la topología evolucionada y SHAP refuerza "
          "la plausibilidad física: la protección de las esporas domina la reducción de transporte, y la edad y el "
          "ancho inicial dominan el cierre.",
          "NEAT's value lies not in beating XGBoost, but in providing, at competitive accuracy, a network small "
          "enough to be drawn, audited and defended before a technical committee, and whose population can be "
          "resumed when new data arrive. The agreement between the evolved topology and SHAP strengthens physical "
          "plausibility: spore protection dominates transport reduction, while age and initial width dominate "
          "closure."),
        L(es,
          "El experimento de llegada por lotes muestra el riesgo de los modelos congelados: un modelo entrenado "
          "solo con datos subtropicales falló por completo en agua de mar. En la práctica, un modelo publicado una "
          "vez queda obsoleto en cuanto cambian las condiciones de exposición, y la comunidad necesita mecanismos "
          "para alimentar y verificar los modelos de forma continua. La ventaja del arranque en caliente frente al "
          "entrenamiento desde cero no fue concluyente y requiere más lotes reales.",
          "The batch-arrival experiment shows the risk of frozen models: a model trained only on subtropical data "
          "failed completely in seawater. In practice, a model published once becomes obsolete as soon as exposure "
          "conditions change, and the community needs mechanisms to feed and verify models continuously. The "
          "advantage of warm start over training from scratch was inconclusive and requires more real batches."),
        L(es,
          "Limitaciones: el meta-dataset de α es pequeño, lo que se refleja en intervalos amplios; las réplicas "
          "provienen de dos laboratorios con agentes y regímenes distintos; ningún dato combina agua de mar con "
          "lactato de calcio, condición central del programa de Paita; y la simulación de aprendizaje continuo usa "
          "lotes históricos y no aportes prospectivos reales. El trabajo futuro incluye incorporar los ensayos de "
          "Paita a 28, 56 y 90 días como validación externa y explorar aprendizaje federado para laboratorios que "
          "no puedan compartir datos crudos.",
          "Limitations: the α meta-dataset is small, reflected in wide intervals; replicates come from two "
          "laboratories with different agents and regimes; no data combine seawater with calcium lactate, the "
          "central condition of the Paita program; and the continual-learning simulation uses historical batches "
          "rather than real prospective contributions. Future work includes adding the Paita 28-, 56- and 90-day "
          "tests as external validation and exploring federated learning for laboratories that cannot share raw "
          "data."),
    ]))
    S.append((1, L(es, "5. Conclusiones", "5. Conclusions"), [
        L(es,
          f"(1) Se construyó un conjunto trazable de {n_rep} registros de cierre de fisuras a partir de repositorios "
          "abiertos, corrigiendo errores de etiquetado de una versión previa. (2) Con validación agrupada sin "
          f"fuga, {mr} y {mm} marcan el techo de precisión (R² = {n(R[mr]['R2'])} en cierre y {n(M[mm]['R2'])} en "
          f"α), y NEAT alcanza R² = {n(nr['R2'])} y {n(nm['R2'])} con redes mínimas. (3) La validación por filas "
          "sobrestimó el desempeño de NEAT en α. (4) La protección biológica gobierna α; la edad y el ancho inicial "
          "gobiernan el cierre. (5) Un modelo congelado falla ante condiciones nuevas, y el esquema de aprendizaje "
          "continuo con control campeón/candidato lo corrige; BioCrete-NEAT queda listo para incorporar tesis, "
          "datos de laboratorio y los ensayos de Paita-Piura.",
          f"(1) A traceable set of {n_rep} crack-closure records was built from open repositories, correcting "
          f"labelling errors of a previous version. (2) Under leakage-free grouped validation, {mr} and {mm} set the "
          f"accuracy ceiling (R² = {n(R[mr]['R2'])} for closure and {n(M[mm]['R2'])} for α), and NEAT reaches "
          f"R² = {n(nr['R2'])} and {n(nm['R2'])} with minimal networks. (3) Row-wise validation overestimated "
          "NEAT's performance on α. (4) Biological protection governs α; age and initial width govern closure. "
          "(5) A frozen model fails under new conditions, and the continual-learning scheme with champion/"
          "challenger control corrects this; BioCrete-NEAT is ready to incorporate theses, laboratory data and the "
          "Paita-Piura tests."),
    ]))
    T["secciones"] = S
    T["finales"] = [
        L(es,
          f"Disponibilidad de datos y código: el código, los datos procesados, los resultados y el registro de "
          f"versiones están en {REPO_URL}. Los datos crudos proceden de los repositorios citados con DOI [10]–[13]. "
          "La plantilla para aportar datos está en biocrete_neat/aportes/plantilla_aportes.csv.",
          f"Data and code availability: code, processed data, results and the version registry are available at "
          f"{REPO_URL}. Raw data come from the cited DOI repositories [10]–[13]. The data contribution template is "
          "at biocrete_neat/aportes/plantilla_aportes.csv."),
        L(es,
          "Contribución de los autores (CRediT): M. A. Guardamino Capcha: conceptualización, metodología, software, "
          "curación de datos, redacción del borrador. C. A. Eyzaguirre Acosta: supervisión, revisión y edición. "
          "[Los autores deben confirmar estos roles.]",
          "CRediT authorship contribution statement: M. A. Guardamino Capcha: conceptualization, methodology, "
          "software, data curation, writing – original draft. C. A. Eyzaguirre Acosta: supervision, writing – "
          "review and editing. [Authors must confirm these roles.]"),
        L(es, "Conflicto de intereses: los autores declaran no tener conflictos de intereses. [Confirmar.]",
              "Declaration of competing interest: the authors declare no competing interests. [Confirm.]"),
        L(es,
          "Declaración de uso de IA: se utilizaron herramientas de IA generativa como asistencia en la programación "
          "y la redacción; los autores revisaron y asumen la responsabilidad del contenido. [Ajustar a la política "
          "de la revista.]",
          "Declaration of generative AI use: generative AI tools assisted with programming and writing; the authors "
          "reviewed the content and take full responsibility for it. [Adapt to the journal policy.]"),
    ]
    return T


def tablas(c: dict, lang: str) -> dict:
    es = lang == "es"
    R, M, rep, meta = c["R"], c["M"], c["rep"], c["meta"]

    def n(x, d=3):
        s = f"{x:.{d}f}"
        return s.replace(".", ",") if es else s

    def ic(m):
        sep = "; " if es else ", "
        return f"[{n(m['R2_IC95'][0], 2)}{sep}{n(m['R2_IC95'][1], 2)}]"

    n_mousa, n_capm = rep["fuentes"]["Mousa2022"], rep["fuentes"]["Cappellesso2024"]
    cap = {(r["condicion"], r["grupo"]): r for r in c["zen"]["cappellesso2024_agno3_marino"]}
    cond = [("Uncracked H", L(es, "Sin fisurar (H)", "Uncracked (H)")),
            ("Uncracked U", L(es, "Sin fisurar (U)", "Uncracked (U)")),
            ("Crack 100 U", L(es, "Fisura 0,1 mm (U)", "Crack 0.1 mm (U)")),
            ("Crack 300 U", L(es, "Fisura 0,3 mm (U)", "Crack 0.3 mm (U)")),
            ("Crack 300 H", L(es, "Fisura 0,3 mm (H)", "Crack 0.3 mm (H)")),
            ("Crack 100 H", L(es, "Fisura 0,1 mm (H)", "Crack 0.1 mm (H)"))]
    avisos = {"fuera del rango": "c", "este nivel de protección": "b", "lactato de calcio": "a"}
    escenarios = [L(es, "Directa · 0,2 mm", "Direct · 0.2 mm"), L(es, "Directa · 0,5 mm", "Direct · 0.5 mm"),
                  L(es, "Directa · 1,0 mm", "Direct · 1.0 mm"), L(es, "Portador · 0,3 mm", "Carrier · 0.3 mm"),
                  L(es, "Encapsulación · 0,3 mm", "Encapsulation · 0.3 mm")]
    pct = " %" if es else "%"
    return {
        "t1": (L(es, "Tabla 1. Fuentes de datos abiertas y su uso.", "Table 1. Open data sources and their use."),
               [[L(es, "Fuente", "Source"), "DOI", L(es, "Registros", "Records"), L(es, "Uso", "Use")],
                ["Mousa et al. [12]", "10.5281/zenodo.6469122", f"{n_mousa}", L(es, "Cierre, 3–28 d", "Closure, 3–28 d")],
                ["Cappellesso et al. [11]", "10.5281/zenodo.11305154", f"{n_capm}",
                 L(es, "Cierre en agua de mar", "Closure in seawater")],
                ["Cappellesso et al. [11]", "10.5281/zenodo.11305154", f"{c['n_agno3']}",
                 L(es, "Penetración de cloruros", "Chloride penetration")],
                ["Dryad [10]", "10.5061/dryad.66t1g1k6j", "239", L(es, "Contraste de Life-365", "Life-365 check")],
                ["Meta-dataset", f"{meta['n_estudios']} " + L(es, "estudios", "studies"), f"{meta['n_registros']}",
                 L(es, "Reducción α", "α reduction")]], None),
        "t2": (L(es, "Tabla 2. Modelos y parámetros.", "Table 2. Models and parameters."),
               [[L(es, "Modelo", "Model"), L(es, "Parámetros", "Parameters")],
                ["BioCrete-NEAT [8]", L(es, "pop. 60; 75 gen.; 0 ocultas iniciales; sigmoide; λ_p anidado",
                                        "pop. 60; 75 gen.; 0 initial hidden; sigmoid; nested λ_p")],
                ["XGBoost [19]", L(es, "400 árboles; prof. 4; η 0,04; submuestreo 0,8",
                                   "400 trees; depth 4; η 0.04; subsample 0.8")],
                ["Random Forest [9]", L(es, "300 árboles; prof. 8; hoja mín. 3", "300 trees; depth 8; min. leaf 3")],
                ["Ridge", L(es, "L2 = 1,0", "L2 = 1.0")]], None),
        "t3": (L(es, "Tabla 3. Penetración de cloruros (AgNO3, mm) en agua de mar, Cappellesso et al. [11].",
                     "Table 3. Chloride penetration (AgNO3, mm) in seawater, Cappellesso et al. [11]."),
               [[L(es, "Condición", "Condition"), "REF", "BAS", L(es, "Reducción BAS", "BAS reduction")]] +
               [[nom, f"{n(cap[(k, 'REF')]['penetracion_cl_media_mm'], 2)} ± {n(cap[(k, 'REF')]['desv_est_mm'], 2)}",
                 f"{n(cap[(k, 'BAS')]['penetracion_cl_media_mm'], 2)} ± {n(cap[(k, 'BAS')]['desv_est_mm'], 2)}",
                 f"{n(cap[(k, 'BAS')]['reduccion_vs_REF_pct'], 1)}{pct}"] for k, nom in cond],
               L(es, "H: pre-curado; U: exposición directa.", "H: pre-cured; U: direct exposure.")),
        "t4": (L(es, "Tabla 4. Desempeño fuera de muestra con GroupKFold e IC 95 % por bootstrap de grupos.",
                     "Table 4. Out-of-sample performance with GroupKFold and 95% group-bootstrap CI."),
               [[L(es, "Objetivo", "Target"), L(es, "Modelo", "Model"), L(es, "R² [IC 95 %]", "R² [95% CI]"),
                 "MAE", "RMSE"]] +
               [[L(es, "Cierre (%)", "Closure (%)"), nom, f"{n(R[k]['R2'])} {ic(R[k])}", n(R[k]["MAE"], 1),
                 n(R[k]["RMSE"], 1)]
                for nom, k in [("Random Forest", "RandomForest"), ("XGBoost", "XGBoost"),
                               ("NEAT (λ_p 8×10⁻⁴)", "NEAT λ=0.0008"),
                               (L(es, "NEAT (λ_p 1,2×10⁻⁴)", "NEAT (λ_p 1.2×10⁻⁴)"), "NEAT λ=0.00012"),
                               ("Ridge", "Ridge")]] +
               [["α", nom, f"{n(M[k]['R2'])} {ic(M[k])}", n(M[k]["MAE"]), n(M[k]["RMSE"])]
                for nom, k in [("XGBoost", "XGBoost"), ("Ridge", "Ridge"), ("Random Forest", "RandomForest"),
                               (L(es, "NEAT (λ_p anidado)", "NEAT (nested λ_p)"), "NEAT (λ anidado)"),
                               ("NEAT (λ_p 8×10⁻⁴)", "NEAT λ=0.0008")]],
               L(es, f"Cierre: n = {rep['n_registros']}, {rep['n_grupos']} grupos (fisura/probeta). α: n = "
                     f"{meta['n_registros']}, {meta['n_estudios']} grupos (estudio).",
                     f"Closure: n = {rep['n_registros']}, {rep['n_grupos']} groups (crack/specimen). α: n = "
                     f"{meta['n_registros']}, {meta['n_estudios']} groups (study).")),
        "t5": (L(es, "Tabla 5. Cierre previsto a 90 d en agua de mar con lactato de calcio (Paita-Piura).",
                     "Table 5. Predicted 90-day closure in seawater with calcium lactate (Paita-Piura)."),
               [[L(es, "Escenario", "Scenario"), L(es, "Cierre medio", "Mean closure"), L(es, "IC 95 %", "95% CI"),
                 L(es, "Aviso", "Flag")]] +
               [[esc, f"{n(f['cierre_medio_pct'], 1)}{pct}",
                 f"{n(f['cierre_IC95_pct'][0], 1)}–{n(f['cierre_IC95_pct'][1], 1)}{pct}",
                 ", ".join(sorted(v for k, v in avisos.items() if k in f["extrapolacion"])) or "—"]
                for esc, f in zip(escenarios, c["f3"]["paita"])],
               L(es, "a: sin datos que combinen agua de mar y lactato de calcio; b: sin datos marinos con esta "
                     "protección; c: ancho fuera del rango entrenado.",
                     "a: no data combining seawater and calcium lactate; b: no marine data at this protection "
                     "level; c: width outside the trained range.")),
    }


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
    c = cifras()
    T, TB = contenido(c, lang), tablas(c, lang)
    es = lang == "es"
    doc = docx.Document()
    st = doc.styles["Normal"]
    st.font.name = "Times New Roman"
    st.font.size = Pt(11)
    st.paragraph_format.line_spacing = 1.5
    st.paragraph_format.space_after = Pt(6)
    for s in doc.sections:
        s.left_margin = s.right_margin = s.top_margin = s.bottom_margin = Inches(1)

    _par(doc, T["titulo"], bold=True, size=16, align=WD_ALIGN_PARAGRAPH.CENTER)
    _par(doc, "Miguel Angelo Guardamino Capcha ᵃ,*, Carlos Augusto Eyzaguirre Acosta ᵃ",
         align=WD_ALIGN_PARAGRAPH.CENTER, after=0)
    _par(doc, "ᵃ Facultad de Ingeniería Civil, Universidad Peruana de Ciencias Aplicadas, Lima, Perú",
         italic=True, size=10, align=WD_ALIGN_PARAGRAPH.CENTER, after=0)
    _par(doc, L(es, "* Autor de correspondencia: u20201c640@upc.edu.pe", "* Corresponding author: u20201c640@upc.edu.pe"),
         size=10, align=WD_ALIGN_PARAGRAPH.CENTER)

    if not es:
        _par(doc, "Highlights", bold=True)
        for h in T["highlights"]:
            doc.add_paragraph(h, style="List Bullet")
    _par(doc, L(es, "Resumen", "Abstract"), bold=True)
    _par(doc, T["resumen"], align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    _par(doc, L(es, "Palabras clave: ", "Keywords: ") + T["claves"], italic=True)
    if es:
        _par(doc, "Aspectos destacados", bold=True)
        for h in T["highlights"]:
            doc.add_paragraph(h, style="List Bullet")

    for nivel, titulo, bloques in T["secciones"]:
        _par(doc, titulo, bold=True, italic=nivel == 2, size=12 if nivel == 1 else 11)
        for b in bloques:
            if isinstance(b, str):
                _par(doc, b, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
            elif b[0] == "tabla":
                _tabla(doc, *TB[b[1]])
            elif b[0] == "figura":
                doc.add_picture(str(FIGS / b[1]), width=Inches(6.0))
                doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
                _par(doc, b[2], italic=True, size=10, align=WD_ALIGN_PARAGRAPH.CENTER)

    for texto in T["finales"]:
        _par(doc, texto, size=10, align=WD_ALIGN_PARAGRAPH.JUSTIFY)

    _par(doc, L(es, "Referencias", "References"), bold=True, size=12)
    for i, ref in enumerate(referencias_originales() + REF_NUEVAS, 1):
        p = _par(doc, f"[{i}] {ref}", size=9, after=2)
        p.paragraph_format.line_spacing = 1.0

    SALIDA.mkdir(parents=True, exist_ok=True)
    ruta = SALIDA / f"BioCrete-NEAT_revista_{lang.upper()}.docx"
    doc.save(str(ruta))
    return ruta


if __name__ == "__main__":
    for lang in ("es", "en"):
        print("[OK]", construir(lang))
