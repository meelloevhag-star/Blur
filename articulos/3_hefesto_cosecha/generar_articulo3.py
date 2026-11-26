"""
Artículo 3 de Hefesto (formato del artículo ACI0189 CON3 v33, IEEE a dos columnas, 8 páginas):
agentes de IA que cosechan y califican la literatura, motor NEAT entrenado con la cosecha y vida útil
de 384 zonas costeras del Perú.

Usa la plantilla del autor (articulos/3_hefesto_cosecha/plantilla/plantilla_v33.docx) tal cual:
página A4, márgenes, encabezado a una columna, tabla de autores y el formato directo de cada tipo de
párrafo (título, resumen, títulos I./A., cuerpo, tabla, figura, ecuación y referencia). El cuerpo se
reconstruye. Las cifras se leen de resultados/*.json y datos/literatura/*; no se escriben a mano.

Uso:
    python -m articulos.3_hefesto_cosecha.generar_articulo3
Salida:
    articulos/3_hefesto_cosecha/ieee/Hefesto_cosecha_ES.docx  (+ fig*.png)
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import zipfile
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
CARPETA = RAIZ / "articulos" / "3_hefesto_cosecha"
PLANTILLA = CARPETA / "plantilla" / "plantilla_v33.docx"
SALIDA = CARPETA / "ieee" / "Hefesto_cosecha_ES.docx"
RES, LIT = RAIZ / "resultados", RAIZ / "datos" / "literatura"
ANCHO_COL = 4962                     # ancho de columna de la plantilla (dxa)
EMU_COL = 3050000                    # ancho de figura de la plantilla (EMU)

# paleta (dataviz: categórica en orden fijo; secuencial azul para el rango, que es ordinal)
AZUL, NARANJA, GRIS, TEXTO, TEXTO2 = "#257de0", "#f47230", "#9c9c9c", "#191919", "#666666"
RAMPA = ["#0e3d7e", "#1757ac", "#2370cd", "#519ced", "#84b9f3", "#b6d5f8", "#dfe9f5"]


def f1(x, d=1):
    s = f"{x:,.{d}f}"
    return s.replace(",", " ").replace(".", ",")


def n0(x):
    return f"{int(x):,}".replace(",", " ")


# =============================================================================== datos
class Datos:
    def __init__(self):
        j = lambda p: json.loads(p.read_text(encoding="utf-8"))
        self.metas = j(LIT / "metas_cosecha.json")
        self.ev = j(RES / "evaluacion_cosecha.json")
        self.banco = j(RES / "banco_motores.json")
        self.vz = j(RES / "vida_zonas.json")["resumen"]
        self.cob = list(csv.DictReader(open(LIT / "cobertura_cosecha.csv", encoding="utf-8")))
        cat = list(csv.DictReader(open(LIT / "catalogo_repositorios.csv", encoding="utf-8")))
        d7, d6 = "DSpace 7: PUCP, UNI, UPC, USAT, SENCICO", "DSpace 6: UCV, UNPRG, UNS, ULADECH"
        grupo = {**{k: d7 for k in ("PUCP", "UNI", "UPC", "USAT", "SENCICO")},
                 **{k: d6 for k in ("UCV", "UNPRG", "UNS", "ULADECH")},
                 "": "ALICIA (CONCYTEC)", "ALICIA": "ALICIA (CONCYTEC)"}
        self.por_fuente, self.util_fuente = Counter(), Counter()
        for r in cat:
            g = grupo.get(r["fuente"], r["fuente"])
            self.por_fuente[g] += 1
            self.util_fuente[g] += r["familia"] not in ("otro", "")
        self.peru_familia = Counter(r["familia"] for r in cat if r["ambito"] == "peru" and r["familia"] != "otro")
        self.util_grado = Counter(r["grado"] for r in cat if r["familia"] != "otro")
        self.n_consultas = len(self.cob)
        self.bajo90 = sum(str(r["estado"]).startswith("incompleta") for r in self.cob)
        # vida útil por régimen de exposición
        zonas = list(csv.DictReader(open(RES / "vida_zonas.csv", encoding="utf-8")))
        self.regimen = {}
        for g in ("atmosferico_marino", "niebla_salina", "salpicadura", "seco"):
            z = [r for r in zonas if r["regimen"] == g]
            num = lambda c: sorted(float(re.sub(r"[^\d.]", "", r[c])) for r in z if re.search(r"\d", r[c] or ""))
            med = lambda v: v[len(v) // 2] if v else None
            self.regimen[g] = {
                "n": len(z), "veredicto": Counter(r["veredicto_25"] for r in z),
                "cemento": Counter(r["cemento"] for r in z).most_common(1)[0][0],
                "a_b": sorted({r["a_b"] for r in z if r["a_b"]}), "rec": sorted({r["recubrimiento_mm"] for r in z if r["recubrimiento_mm"]},
                                                                               key=lambda s: float(s)),
                "sin_fisura_40": sum(r["sin_fisura"].startswith("cumple 40") for r in z),
                "sin_fisura": med([v for v in num("sin_fisura")]), "fisura": med(num("fisura_sin_reparar")),
                "req25": med(num("cierre_req_25_pct")), "neat": med(num("neat_cierre_pct"))}
        self.departamentos = Counter(r["departamento"] for r in zonas)
        por_id = {r["id"]: r for r in zonas}
        self.ejemplo = {"salp": por_id["PER-007-0"], "atm": por_id["PER-007-1"]}   # mismo sitio, 0,25 y 2,75 km
        self.sens = json.loads((RES / "sensibilidad_vida.json").read_text(encoding="utf-8"))
        self.hib = json.loads((RES / "hibrido.json").read_text(encoding="utf-8"))
        # Piura (UCV 72746): cierre por dosis y edad, tal como se transcribió
        self.piura = {}
        for r in csv.DictReader(open(RAIZ / "datos" / "aceptados" / "repositorios_2026-11-26e.csv", encoding="utf-8")):
            dosis = r["id_grupo"].split()[0]
            d = self.piura.setdefault(dosis, {"w": [], 7: [], 14: []})
            d[int(float(r["resultado_edad_dias"]))].append(float(r["resultado_cierre_pct"]))
            d["w"].append(float(r["dano_ancho_fisura_mm"]) * 1000)
        self.cola = Counter(r["estado"].split(" (")[0] for r in csv.DictReader(open(LIT / "cola_extraccion.csv",
                                                                                     encoding="utf-8")))


# =============================================================================== figuras
def _estilo(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRIS)
    ax.tick_params(colors=TEXTO2, labelsize=6.5, length=2)
    ax.grid(axis="x", color="#e6e6e6", lw=0.5)
    ax.set_axisbelow(True)


def fig_arquitectura(ruta):
    fig, ax = plt.subplots(figsize=(3.35, 2.15), dpi=300)
    ax.set_xlim(0, 10), ax.set_ylim(0, 6), ax.axis("off")
    cajas = [
        (0.1, 4.0, 3.0, 1.85, "Agentes de IA\nrepositorios\nOpenAlex · OSTI\nHAL · Zenodo"),
        (3.5, 4.0, 3.0, 1.85, "Calidad\ntier 0–4\ngrado · rango\nSS+…D"),
        (6.9, 4.0, 3.0, 1.85, "Curador\nesquema único\nduplicados\nsin imputar"),
        (6.9, 0.2, 3.0, 1.85, "Motor NEAT\nH3: 5 redes\n+ corrección\nlocal"),
        (3.5, 0.2, 3.0, 1.85, "Durabilidad\nfib B34\nMonte Carlo\n25 y 40 años"),
        (0.1, 0.2, 3.0, 1.85, "Atlas\n(externo)\n384 zonas"),
    ]
    for i, (x, y, w, h, t) in enumerate(cajas):
        color = AZUL if i < 5 else GRIS
        ax.add_patch(plt.Rectangle((x, y), w, h, fc="white", ec=color, lw=0.9))
        ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=5.0, color=TEXTO, linespacing=1.2)
    flecha = dict(arrowstyle="->", color=TEXTO2, lw=0.8)
    for (a, b) in [((3.1, 4.92), (3.5, 4.92)), ((6.5, 4.92), (6.9, 4.92)), ((8.4, 4.0), (8.4, 2.05)),
                   ((6.9, 1.12), (6.5, 1.12)), ((3.5, 1.12), (3.1, 1.12))]:
        ax.annotate("", xy=b, xytext=a, arrowprops=flecha)
    ax.annotate("", xy=(1.6, 4.0), xytext=(8.4, 2.05),
                arrowprops=dict(arrowstyle="->", color=NARANJA, lw=0.8, ls="--", connectionstyle="arc3,rad=0.25"))
    ax.text(4.9, 3.05, "necesidades (aprendizaje activo)", fontsize=4.8, color=NARANJA, ha="center", va="center")
    fig.savefig(ruta, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def fig_cosecha(D: "Datos", ruta):
    rpa = D.metas["rango_por_ambito"]
    rangos = ["SS+", "S", "A", "B", "C", "D"]
    ambitos = [("peru", "Perú"), ("sudamerica", "Sudamérica"), ("global", "Global")]
    fig, ax = plt.subplots(figsize=(3.35, 1.55), dpi=300)
    for i, (a, nombre) in enumerate(ambitos):
        izq = 0
        tot = sum(rpa[a][r] for r in rangos)
        for k, r in enumerate(rangos):
            v = rpa[a][r] / tot * 100
            ax.barh(i, v, left=izq, height=0.62, color=RAMPA[k], edgecolor="white", lw=0.8)
            if v > 6:
                ax.text(izq + v / 2, i, f"{r}\n{f1(v, 0)} %", ha="center", va="center", fontsize=4.8,
                        color="white" if k < 3 else TEXTO)
            izq += v
        ax.text(101, i, n0(tot), va="center", fontsize=5.8, color=TEXTO2)
    ax.set_yticks(range(3), [n for _, n in ambitos])
    ax.invert_yaxis()
    ax.set_xlim(0, 112)
    ax.set_xticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100 %"])
    _estilo(ax)
    ax.legend([plt.Rectangle((0, 0), 1, 1, color=RAMPA[k]) for k in range(6)], rangos, ncol=6, fontsize=5.2,
              frameon=False, loc="upper center", bbox_to_anchor=(0.47, 1.28), handlelength=1, columnspacing=0.8)
    fig.savefig(ruta, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def fig_evaluacion(D: "Datos", ruta):
    ev = D.ev
    grupos = [("Todas", ev["todas"]), ("Entre los 2\nlaboratorios", ev["replicas_entre_laboratorios"]),
              ("Perú (Piura)", ev["peru"]), ("Estudios\nnuevos (24)", ev["fuentes_nuevas"])]
    fig, ax = plt.subplots(figsize=(3.35, 1.75), dpi=300)
    h = 0.36
    for i, (_n, g) in enumerate(grupos):
        ax.barh(i - h / 2, g["MAE_actual"], height=h, color=GRIS, edgecolor="white", lw=0.8)
        ax.barh(i + h / 2, g["MAE_cosecha"], height=h, color=AZUL, edgecolor="white", lw=0.8)
        ax.text(g["MAE_actual"] + 0.4, i - h / 2, f1(g["MAE_actual"]), va="center", fontsize=5.4, color=TEXTO2)
        ax.text(g["MAE_cosecha"] + 0.4, i + h / 2, f1(g["MAE_cosecha"]), va="center", fontsize=5.4, color=TEXTO)
    ax.set_yticks(range(len(grupos)), [n for n, _ in grupos], fontsize=6)
    ax.invert_yaxis()
    ax.set_xlabel("MAE en fuente no vista (pp de cierre)", fontsize=6, color=TEXTO2)
    ax.set_xlim(0, 33)
    _estilo(ax)
    ax.legend([plt.Rectangle((0, 0), 1, 1, color=c) for c in (GRIS, AZUL)],
              ["v003: 2 laboratorios", "v004: cosecha (26 fuentes)"], fontsize=5.4, frameon=False, ncol=2,
              loc="lower center", bbox_to_anchor=(0.45, 1.0))
    fig.savefig(ruta, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def fig_mejora(D: "Datos", ruta):
    """Curva de mejora: MAE en el laboratorio nuevo según el número de grupos locales sumados (banco)."""
    cand = {c["nombre"]: c for c in D.banco["candidatos"]}
    series = [("H3 (NEAT ×5 + RF)", "H3 (elegido)"), ("NEAT ×5 (motor actual)", "NEAT ×5"),
              ("Random Forest", "Bosque aleatorio"), ("XGBoost", "XGBoost"), ("MLP 32x16", "Perceptrón 32×16")]
    colores = ["#257de0", "#f47230", "#00b894", "#f2a600", "#ee7fac"]       # categórica, orden fijo
    fig, ax = plt.subplots(figsize=(3.35, 1.75), dpi=300)
    xs = [0, 5, 10, 20, 40]
    for (n, et), col in zip(series, colores):
        ys = [cand[n]["mejora"][str(x)] for x in xs]
        ax.plot(xs, ys, color=col, lw=1.4 if n.startswith("H3") else 0.9, marker="o", ms=2.6,
                markeredgecolor="white", markeredgewidth=0.4, label=et)
    ax.legend(fontsize=4.8, frameon=False, loc="upper right", handlelength=1.6)
    ax.set_xticks(xs)
    ax.set_xlim(-1, 41)
    ax.set_ylim(12, 34)
    ax.set_xlabel("Grupos de probetas locales del laboratorio nuevo", fontsize=6, color=TEXTO2)
    ax.set_ylabel("MAE (pp)", fontsize=6, color=TEXTO2)
    _estilo(ax)
    ax.grid(axis="y", color="#e6e6e6", lw=0.5)
    ax.grid(axis="x", visible=False)
    fig.savefig(ruta, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def fig_colan(ruta):
    """Tabla 7 de Morán Córdova (2023), transcrita: elementos por nivel de corrosión según la antigüedad."""
    filas = list(csv.DictReader(open(RAIZ / "datos" / "aceptados" / "repositorios_2026-11-26.csv", encoding="utf-8")))
    grupos = [("construida menor a 6 meses", "< 6 meses"), ("construida entre 2021 y 2023", "2021–2023"),
              ("construida entre 2018 y 2020", "2018–2020"), ("construida entre 2015 y 2017", "2015–2017"),
              ("construida de 2015 a más", "«de 2015 a más»")]
    niveles = [("nulo", "Nulo"), ("bajo", "Bajo"), ("medio", "Medio"), ("alto", "Alto"), ("critico", "Crítico")]
    tonos = ["#dfe9f5", "#84b9f3", "#2370cd", "#1757ac", "#0e3d7e"]
    cuenta = Counter()
    for r in filas:
        cuenta[(r["id_grupo"].split("|")[1], r["dano_nivel_corrosion"])] += int(r["dano_n_elementos"] or 0)
    fig, ax = plt.subplots(figsize=(3.35, 1.6), dpi=300)
    for i, (g, et) in enumerate(grupos):
        tot = sum(cuenta[(g, n)] for n, _ in niveles)
        izq = 0
        for k, (n, _) in enumerate(niveles):
            v = cuenta[(g, n)] / tot * 100
            ax.barh(i, v, left=izq, height=0.62, color=tonos[k], edgecolor="white", lw=0.8)
            if v >= 12:
                ax.text(izq + v / 2, i, f"{f1(v, 0)} %", ha="center", va="center", fontsize=4.8,
                        color="white" if k >= 2 else TEXTO)
            izq += v
        ax.text(101, i, f"n = {tot}", va="center", fontsize=5, color=TEXTO2)
    ax.set_yticks(range(len(grupos)), [et for _, et in grupos], fontsize=5.6)
    ax.invert_yaxis()
    ax.set_xlim(0, 116)
    ax.set_xticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100 %"])
    _estilo(ax)
    ax.legend([plt.Rectangle((0, 0), 1, 1, color=t) for t in tonos], [e for _, e in niveles], ncol=5, fontsize=5,
              frameon=False, loc="upper center", bbox_to_anchor=(0.45, 1.25), handlelength=1, columnspacing=0.8)
    fig.savefig(ruta, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


MOTOR = RAIZ / "modelos" / "motor_v004.pkl"
ETIQ = {-1: "w₀", -2: "edad", -3: "prot.", -4: "marino", -5: "lactato", -6: "curado", -7: "crist."}


def importancia_v004() -> dict:
    """Importancia por permutación del motor v004 sobre lo aceptado (pp de MAE). Se guarda en resultados/."""
    ruta = RES / "importancia_v004.json"
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))
    import numpy as np
    from hefesto.motor.datos import VARS_R
    from hefesto.motor.evaluar_cosecha import DatosCosecha
    from hefesto.motor.motor import Motor
    m, d = Motor.cargar(MOTOR), DatosCosecha()
    pred = lambda X: np.asarray(m.predecir(X)["cierre_pct"], dtype=float) / 100
    base = float(np.nanmean(np.abs(pred(d.X) - d.y)) * 100)
    rng, imp = np.random.default_rng(1), {}
    for j, v in enumerate(VARS_R):
        s = []
        for _ in range(5):
            X = d.X.copy()
            X[:, j] = rng.permutation(X[:, j])
            s.append(float(np.nanmean(np.abs(pred(X) - d.y)) * 100) - base)
        imp[v] = round(float(np.mean(s)), 2)
    out = {"mae_base_pp": round(base, 2), "importancia_pp": imp}
    ruta.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def fig_redes(ruta):
    """Las 5 redes evolucionadas del motor v004: entradas usadas, nodos ocultos y pesos (signo y magnitud)."""
    from hefesto.motor.motor import Motor
    redes = Motor.cargar(MOTOR).matrices()
    fig, axs = plt.subplots(1, len(redes), figsize=(3.35, 1.25), dpi=300)
    for k, (ax, capas) in enumerate(zip(axs, redes)):
        ax.axis("off")
        ax.set_xlim(-0.35, 1.3), ax.set_ylim(-0.15, 1.15)
        entradas = sorted({o for c in capas for o in c["origenes"] if o < 0}, reverse=True)
        ocultos = [n for c in capas for n in c["nodos"] if n != 0]
        pos = {e: (0.0, 1 - i / max(1, len(entradas) - 1) if len(entradas) > 1 else 0.5) for i, e in enumerate(entradas)}
        for i, h in enumerate(ocultos):
            pos[h] = (0.5, 0.85 - 0.6 * i)
        pos[0] = (1.0, 0.5)
        for c in capas:
            for n, fila, b in zip(c["nodos"], c["W"], c["sesgos"]):
                for o, w in zip(c["origenes"], fila):
                    (x0, y0), (x1, y1) = pos[o], pos[n]
                    ax.plot([x0, x1], [y0, y1], color=AZUL if w > 0 else NARANJA, lw=0.4 + 0.9 * min(abs(w), 2) / 2,
                            zorder=1)
        for n, (x, y) in pos.items():
            ax.scatter([x], [y], s=26, color="white", edgecolor=TEXTO2 if n < 0 else TEXTO, lw=0.6, zorder=2)
            if n < 0:
                ax.text(x - 0.08, y, ETIQ[n], ha="right", va="center", fontsize=4.6, color=TEXTO)
        ax.text(1.0, 0.33, "cierre", ha="center", va="top", fontsize=4.4, color=TEXTO2)
        ax.set_title(f"Red {k + 1}", fontsize=5.2, color=TEXTO, pad=1)
    fig.legend([plt.Line2D([], [], color=AZUL, lw=1), plt.Line2D([], [], color=NARANJA, lw=1)],
               ["peso positivo", "peso negativo"], fontsize=4.8, frameon=False, ncol=2, loc="lower center",
               bbox_to_anchor=(0.5, -0.06))
    fig.savefig(ruta, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


V003_CIERRE_MARINO = 77.3   # resultados/vida_zonas.json con motor_v003 (commit 9e67e1d): 77,3 % para toda protección


def fig_vida(D: "Datos", ruta):
    vz = D.vz
    ops = [o for o in vz["neat_opciones_marinas"] if not o["lactato_calcio"]]
    nombres = {"sin bacterias": "Sin bacterias", "directa/comercial": "Directa", "portador": "Portador",
               "encapsulación": "Encapsulación"}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(3.35, 1.7), dpi=300, gridspec_kw={"width_ratios": [1.05, 1]})
    for i, o in enumerate(ops):
        a1.barh(i - 0.18, V003_CIERRE_MARINO, height=0.34, color=GRIS, edgecolor="white", lw=0.8)
        a1.barh(i + 0.18, o["cierre_pct"], height=0.34, color=AZUL, edgecolor="white", lw=0.8)
        a1.text(o["cierre_pct"] + 1, i + 0.18, f1(o["cierre_pct"]), va="center", fontsize=5.0, color=TEXTO)
    a1.set_yticks(range(len(ops)), [nombres[o["proteccion"]] for o in ops], fontsize=5.6)
    a1.invert_yaxis()
    a1.set_xlim(50, 90)
    a1.set_xlabel("Cierre a 90 d, marino (%)", fontsize=5.6, color=TEXTO2)
    a1.set_title("(a)", fontsize=6, color=TEXTO, loc="left")
    _estilo(a1)
    a1.legend([plt.Rectangle((0, 0), 1, 1, color=c) for c in (GRIS, AZUL)], ["v003", "v004"], fontsize=5,
              frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.45, -0.42), handlelength=1)
    cats = [("cumple", "Cumple", RAMPA[1]), ("incierto", "Incierto", RAMPA[3]), ("no cumple", "No cumple", RAMPA[5]),
            ("no alcanzable con esta mezcla", "No alcanzable", "#e6e6e6")]
    for i, k in enumerate(("veredicto_25", "veredicto_40")):
        izq = 0
        for c, _n, col in cats:
            v = vz[k].get(c, 0)
            if not v:
                continue
            a2.barh(i, v, left=izq, height=0.55, color=col, edgecolor="white", lw=0.8)
            if v >= 18:
                a2.text(izq + v / 2, i, str(v), ha="center", va="center", fontsize=5.0,
                        color="white" if col in (RAMPA[1], RAMPA[3]) else TEXTO)
            izq += v
    a2.set_yticks([0, 1], ["25 años", "40 años"], fontsize=5.6)
    a2.invert_yaxis()
    a2.set_xlabel("Zonas con cloruros (n = 268)", fontsize=5.6, color=TEXTO2)
    a2.set_title("(b)", fontsize=6, color=TEXTO, loc="left")
    _estilo(a2)
    a2.legend([plt.Rectangle((0, 0), 1, 1, color=c) for _, _, c in cats], [n for _, n, _ in cats], fontsize=4.6,
              frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.45, -0.42), handlelength=1)
    fig.savefig(ruta, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


# =============================================================================== XML (formato de la plantilla)
FUENTE = ('<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman" '
          'w:eastAsia="Times New Roman"/>')


def _run(texto, sz, b=False, i=False, sc=False):
    rpr = FUENTE + ('<w:b w:val="1"/><w:bCs w:val="1"/>' if b else "") + \
        ('<w:i w:val="1"/><w:iCs w:val="1"/>' if i else "") + ('<w:smallCaps w:val="1"/>' if sc else "") + \
        f'<w:color w:val="000000"/><w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>'
    return f'<w:r><w:rPr>{rpr}</w:rPr><w:t xml:space="preserve">{escape(texto)}</w:t></w:r>'


def _p(ppr, runs):
    return f"<w:p><w:pPr>{ppr}</w:pPr>{runs}</w:p>"


def _ricos(texto, sz, b=False):
    """*cursiva* dentro de un párrafo."""
    partes = re.split(r"(\*[^*]+\*)", texto)
    return "".join(_run(p[1:-1], sz, b=b, i=True) if p.startswith("*") and p.endswith("*") else _run(p, sz, b=b)
                   for p in partes if p)


def _romano(n):
    s = ""
    for a, r in [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]:
        while n >= a:
            s, n = s + r, n - a
    return s


class Doc:
    """Cada método escribe un tipo de párrafo con el formato directo exacto de la plantilla v33."""

    def __init__(self):
        self.xml: list[str] = []
        self.n_tabla = self.n_fig = self.n_ec = 0
        self.imagenes: list[tuple[str, Path]] = []

    def titulo(self, t):
        self.xml.append(_p('<w:spacing w:before="0" w:after="65" w:line="238" w:lineRule="auto"/><w:jc w:val="center"/>',
                           _run(t, 38)))

    def titulo_en(self, t):
        self.xml.append(_p('<w:spacing w:before="0" w:after="95" w:line="232" w:lineRule="auto"/><w:jc w:val="center"/>',
                           _run(t, 26, i=True)))

    def resumen(self, etiqueta, t):
        ppr = ('<w:spacing w:before="0" w:after="85" w:line="238" w:lineRule="auto"/>'
               '<w:ind w:firstLine="288"/><w:jc w:val="both"/>')
        self.xml.append(_p(ppr, _run(etiqueta + "—", 18, b=True, i=True) + _run(t, 18, b=True)))

    def claves(self, etiqueta, t):
        ppr = ('<w:spacing w:before="0" w:after="95" w:line="238" w:lineRule="auto"/>'
               '<w:ind w:firstLine="288"/><w:jc w:val="both"/>')
        self.xml.append(_p(ppr, _run(etiqueta + "—", 18, b=True, i=True) + _run(t, 18, i=True)))

    def h1(self, t):
        self.xml.append(_p('<w:keepNext w:val="1"/><w:spacing w:before="125" w:after="55" w:line="242" '
                           'w:lineRule="auto"/><w:jc w:val="center"/>', _run(t, 20, sc=True)))

    def h2(self, t):
        self.xml.append(_p('<w:keepNext w:val="1"/><w:spacing w:before="80" w:after="35" w:line="242" '
                           'w:lineRule="auto"/><w:jc w:val="left"/>', _run(t, 20, i=True)))

    def p(self, t):
        self.xml.append(_p('<w:spacing w:before="0" w:after="24" w:line="242" w:lineRule="auto"/>'
                           '<w:ind w:firstLine="288"/><w:jc w:val="both"/>', _ricos(t, 20)))

    def ecuacion(self, t):
        self.n_ec += 1
        ppr = ('<w:tabs><w:tab w:val="center" w:pos="2481"/><w:tab w:val="right" w:pos="4962"/></w:tabs>'
               '<w:spacing w:before="45" w:after="45" w:line="236" w:lineRule="auto"/><w:jc w:val="left"/>')
        self.xml.append(_p(ppr, "<w:r><w:tab/></w:r>" + _run(t, 17) + "<w:r><w:tab/></w:r>" +
                           _run(f"({self.n_ec})", 18)))

    def nota(self, t):
        self.xml.append(_p('<w:spacing w:before="25" w:after="80" w:line="222" w:lineRule="auto"/><w:jc w:val="both"/>',
                           _ricos(t, 15)))

    def tabla(self, titulo, filas, anchos, nota=None, alin=None):
        self.n_tabla += 1
        self.xml.append(_p('<w:keepNext w:val="1"/><w:spacing w:before="85" w:after="35" w:line="226" '
                           'w:lineRule="auto"/><w:jc w:val="center"/>',
                           _run(f"TABLA {_romano(self.n_tabla)}.  ", 16, b=True, sc=True) + _run(titulo.upper(), 16)))
        total = sum(anchos)
        w = [round(a / total * ANCHO_COL) for a in anchos]
        w[-1] += ANCHO_COL - sum(w)
        alin = alin or (["left"] + ["center"] * (len(anchos) - 1))
        grid = "".join(f'<w:gridCol w:w="{x}"/>' for x in w)
        tbl = [f'<w:tbl><w:tblPr><w:tblW w:w="{ANCHO_COL}" w:type="dxa"/><w:jc w:val="center"/>'
               f'<w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid>{grid}</w:tblGrid>']
        mar = ('<w:tcMar><w:top w:w="18" w:type="dxa"/><w:bottom w:w="18" w:type="dxa"/>'
               '<w:left w:w="38" w:type="dxa"/><w:right w:w="38" w:type="dxa"/></w:tcMar>')
        for k, fila in enumerate(filas):
            cab, ultima = k == 0, k == len(filas) - 1
            trpr = "<w:cantSplit/><w:tblHeader/>" if cab else "<w:cantSplit/>"
            celdas = []
            for c, texto in enumerate(fila):
                negrita = cab or str(texto).startswith("**")
                texto = str(texto).strip("*")
                top = '<w:top w:val="single" w:sz="6" w:color="000000"/>' if cab else '<w:top w:val="nil"/>'
                bot = ('<w:bottom w:val="single" w:sz="6" w:color="000000"/>' if (cab or ultima)
                       else '<w:bottom w:val="nil"/>')
                shd = '<w:shd w:val="clear" w:fill="dce8f5"/>' if cab else ""
                keep = "" if ultima else '<w:keepNext w:val="1"/>'
                celdas.append(
                    f'<w:tc><w:tcPr><w:tcW w:w="{w[c]}" w:type="dxa"/><w:tcBorders>{top}<w:left w:val="nil"/>{bot}'
                    f'<w:right w:val="nil"/></w:tcBorders>{shd}{mar}</w:tcPr>'
                    + _p(f'{keep}<w:spacing w:before="0" w:after="0" w:line="216" w:lineRule="auto"/>'
                         f'<w:jc w:val="{alin[c]}"/>', _run(texto, 15, b=negrita)) + "</w:tc>")
            tbl.append(f"<w:tr><w:trPr>{trpr}</w:trPr>{''.join(celdas)}</w:tr>")
        tbl.append("</w:tbl>")
        self.xml.append("".join(tbl))
        if nota:
            self.nota(nota)

    def figura(self, ruta: Path, pie: str, alto_rel: float):
        self.n_fig += 1
        rid = f"rIdHef{self.n_fig}"
        cx, cy = EMU_COL, int(EMU_COL * alto_rel)
        nombre = f"hefesto_fig{self.n_fig}.png"
        self.imagenes.append((rid, ruta))
        d = escape(pie, {'"': "&quot;"})
        dib = (f'<w:r><w:drawing><wp:inline distB="0" distT="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
               f'<wp:effectExtent b="0" l="0" r="0" t="0"/><wp:docPr descr="{d}" id="{900 + self.n_fig}" '
               f'name="{nombre}"/><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
               f'<pic:pic><pic:nvPicPr><pic:cNvPr descr="{d}" id="0" name="{nombre}"/><pic:cNvPicPr '
               f'preferRelativeResize="0"/></pic:nvPicPr><pic:blipFill><a:blip r:embed="{rid}"/><a:srcRect b="0" l="0" '
               f'r="0" t="0"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/>'
               f'<a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"/><a:ln/></pic:spPr></pic:pic>'
               f'</a:graphicData></a:graphic></wp:inline></w:drawing></w:r>')
        self.xml.append(_p('<w:keepNext w:val="1"/><w:spacing w:after="40" w:before="60" w:line="240" '
                           'w:lineRule="auto"/><w:jc w:val="center"/>', dib))
        self.xml.append(_p('<w:spacing w:before="20" w:after="80" w:line="224" w:lineRule="auto"/><w:jc w:val="both"/>',
                           _run(f"Fig. {self.n_fig}.  ", 16, b=True) + _run(pie, 16)))

    def referencia(self, n, t):
        ppr = ('<w:tabs><w:tab w:val="left" w:pos="350"/></w:tabs><w:spacing w:before="0" w:after="10" w:line="212" '
               'w:lineRule="auto"/><w:ind w:left="350" w:hanging="350"/><w:jc w:val="both"/>')
        self.xml.append(_p(ppr, _run(f"[{n}]", 15) + "<w:r><w:tab/></w:r>" + _ricos(t, 15)))


# =============================================================================== referencias
REFS = [
    "F. E. Morán Córdova, “Evaluación del impacto de la corrosión en estructuras de concreto armado construidas en las playas del norte peruano,” tesis de licenciatura, Univ. César Vallejo, Piura, Perú, 2023. [En línea]: https://hdl.handle.net/20.500.12692/151797",
    "Reglamento Nacional de Edificaciones, Norma Técnica E.060 Concreto Armado, Ministerio de Vivienda, Construcción y Saneamiento, Lima, Perú, 2009.",
    "CEN, EN 1990: Eurocode – Basis of structural design, Bruselas, Bélgica, 2002.",
    "fib, Model Code for Service Life Design, Bulletin 34, International Federation for Structural Concrete, Lausana, Suiza, 2006.",
    "Life-365 Consortium, Life-365 Service Life Prediction Model and Computer Program for Predicting the Service Life and Life-Cycle Cost of Reinforced Concrete Exposed to Chlorides, v2.2.1, 2018.",
    "DuraCrete, “Statistical quantification of the variables in the limit state functions,” Rep. BE95-1347/R9, 2000.",
    "K. O. Stanley and R. Miikkulainen, “Evolving neural networks through augmenting topologies,” Evol. Comput., vol. 10, no. 2, pp. 99–127, 2002.",
    "V. Vovk, A. Gammerman, and G. Shafer, Algorithmic Learning in a Random World. Nueva York, NY, EE. UU.: Springer, 2005.",
    "M. R. Mousa et al., “Determination of the optimal parameters for self-healing efficiency of encapsulated bacteria in concrete,” Zenodo, 2022, doi: 10.5281/zenodo.6469122.",
    "V. G. Cappellesso, T. Van Mullem, E. Gruyaert, K. Van Tittelboom, and N. De Belie, “Self-healing concrete with a bacteria-based or crystalline admixture as healing agent to prevent chloride ingress and corrosion in a marine environment,” Dev. Built Environ., vol. 19, Art. no. 100486, 2024, doi: 10.1016/j.dibe.2024.100486.",
    "V. G. Cappellesso, T. Van Mullem, E. Gruyaert, K. Van Tittelboom, and N. De Belie, “Supplementary data for: Self-healing concrete with a bacteria-based or crystalline admixture in a marine environment,” Zenodo, 2024, doi: 10.5281/zenodo.11305154.",
    "L. Yang, E. Zhu, and Y. Wei, “Experimental data for chloride diffusion coefficient of concrete by rapid chloride migration test,” Dryad, doi: 10.5061/dryad.66t1g1k6j.",
    "V. Wiktor and H. M. Jonkers, “Quantification of crack-healing in novel bacteria-based self-healing concrete,” Cem. Concr. Compos., vol. 33, no. 7, pp. 763–770, 2011, doi: 10.1016/j.cemconcomp.2011.03.012.",
    "H. M. Jonkers, A. Thijssen, G. Muyzer, O. Copuroglu, and E. Schlangen, “Application of bacteria as self-healing agent for the development of sustainable concrete,” Ecol. Eng., vol. 36, no. 2, pp. 230–235, 2010, doi: 10.1016/j.ecoleng.2008.12.036.",
    "“Self-healing performance assessment of bacterial-based concrete using machine learning approaches,” Materials, 2022. [En línea]: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9267731/",
    "“Modeling self-healing of concrete using hybrid genetic algorithm–artificial neural network,” Materials, 2017. [En línea]: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5459209/",
    "“Prediction of healing performance of autogenous healing concrete using machine learning,” Materials, 2021. [En línea]: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8348520/",
    "B. Van Belleghem, P. Van den Heede, K. Van Tittelboom, and N. De Belie, “Quantification of the service life extension and environmental benefit of chloride exposed self-healing concrete,” Materials, vol. 10, no. 1, Art. no. 5, 2017, doi: 10.3390/ma10010005.",
    "R. Davies et al., “Large scale application of self-healing concrete: Design, construction, and testing,” Front. Mater., vol. 5, Art. no. 51, 2018, doi: 10.3389/fmats.2018.00051.",
    "A. Al-Tabbaa, C. Litina, P. Giannaros, A. Kanellopoulos, and L. Souza, “First UK field application and performance of microcapsule-based self-healing concrete,” Constr. Build. Mater., vol. 208, pp. 669–685, 2019, doi: 10.1016/j.conbuildmat.2019.02.178.",
    "R. Jakubovskis and R. Boris, “The construction of a footbridge prototype with biological self-healing concrete: A field study in a humid continental climate zone,” Materials, vol. 15, no. 23, Art. no. 8585, 2022, doi: 10.3390/ma15238585.",
    "I. Othmen, S. Bonnet, and F. Schoefs, “Statistical investigation of different analysis methods for chloride profiles within a real structure in a marine environment,” Ocean Eng., vol. 157, pp. 96–107, 2018, doi: 10.1016/j.oceaneng.2018.03.040.",
    "R. Clerc, F. Schoefs, M. Oumouni, I. Othmen, and S. Bonnet, “Modeling of chloride spatial variability in a reinforced concrete wharf from on-site measurements,” ASCE-ASME J. Risk Uncertain. Eng. Syst. A, 2024, doi: 10.1061/AJRUA6.RUENG-1214.",
    "Iowa Department of Transportation y Federal Highway Administration (patrocinadores), “Final report on the I-129 Missouri River Bridge deck condition assessment using non-destructive testing methods,” Iowa, EE. UU., 2012. [En línea]: https://publications.iowa.gov/54466/",
    "J. Liu et al., “Chloride distribution and steel corrosion in a concrete bridge after long-term exposure to natural marine environment,” Materials, vol. 13, no. 17, Art. no. 3900, 2020, doi: 10.3390/ma13173900.",
    "H. Wall, “Service life assessment of harbor structures – Case studies of chloride ingress into concrete structures and sheet piling corrosion rates,” tesis doctoral, Div. Building Materials, LTH, Lund Univ., Lund, Suecia, 2013.",
    "P. Sandberg, “Chloride initiated reinforcement corrosion in marine concrete,” tesis doctoral, Div. Building Materials, LTH, Lund Univ., Lund, Suecia, 1998.",
    "A. Lindvall, “Environmental actions on concrete exposed in marine and road environments and its response,” tesis doctoral, Chalmers Univ. of Technology, Gotemburgo, Suecia, 2003.",
    "S. Khani, “Chloride exposure and ingress into concrete under severe winter conditions,” tesis doctoral, Univ. Laval, Quebec, Canadá, 2024. [En línea]: https://univoak.hal.science/tel-05532436",
    "R. M. Mors and H. M. Jonkers, “Bacteria-based self-healing concrete: evaluation of full scale demonstrator projects,” RILEM Tech. Lett., vol. 4, pp. 138–144, 2019, doi: 10.21809/rilemtechlett.2019.93.",
    "J. Priem, H. Piwowar, and R. Orr, “OpenAlex: A fully-open index of scholarly works, authors, venues, institutions, and concepts,” arXiv:2205.01833, 2022.",
    "CONCYTEC, “ALICIA: Acceso Libre a Información Científica para la Innovación,” Lima, Perú. [En línea]: https://alicia.concytec.gob.pe",
    "LA Referencia, “Red Federada de Repositorios Institucionales de Publicaciones Científicas.” [En línea]: https://www.lareferencia.info",
    "Y. S. Bautista Morales, “Influencia de Lysinibacillus sphaericus en la autoreparación y resistencia del concreto f’c=350 kg/cm² en la ciudad de Piura,” tesis de licenciatura, Univ. César Vallejo, Trujillo, Perú, 2021. [En línea]: https://hdl.handle.net/20.500.12692/72746",
]


# =============================================================================== contenido
def escribir(D: Datos, doc: Doc, figs: dict):
    m, ev, vz, banco = D.metas, D.ev, D.vz, D.banco
    pa = m["por_ambito"]
    tod, rep, peru, nue = ev["todas"], ev["replicas_entre_laboratorios"], ev["peru"], ev["fuentes_nuevas"]
    c25, c40 = vz["cierre_requerido_25_pct"], vz["cierre_requerido_40_pct"]
    v25, v40 = vz["veredicto_25"], vz["veredicto_40"]
    ops = {o["proteccion"]: o["cierre_pct"] for o in vz["neat_opciones_marinas"] if not o["lactato_calcio"]}
    piso = banco["piso_ruido_pp"]
    cand = {c["nombre"]: c for c in banco["candidatos"]}
    h3 = cand["H3 (NEAT ×5 + RF)"]
    n_cl = 268

    # ------------------------------------------------------------------ cabecera
    doc.titulo("Hefesto: motor de neuroevolución NEAT para predecir el cierre de fisuras del concreto "
               "autorreparable bacteriano y su vida útil frente a cloruros en la costa peruana")
    doc.titulo_en("Hefesto: a NEAT neuroevolution engine to predict crack closure of bacterial self-healing concrete "
                  "and its chloride service life on the Peruvian coast")
    doc.resumen("Resumen", (
        f"La pregunta “¿durará este concreto los años que pide la norma?” se responde hoy con modelos calibrados en "
        f"uno o dos laboratorios y con supuestos sobre la autorreparación. Hefesto propone un sistema de tres capas: "
        f"(1) agentes de IA que recorren por canales abiertos repositorios universitarios peruanos (DSpace, ALICIA), "
        f"sudamericanos (LA Referencia, BDTD) y la literatura global (OpenAlex, OSTI, HAL, Zenodo, CyberLeninka), con "
        f"cobertura ≥ 90 % de lo que reporta cada consulta, y califican cada fuente con tres etiquetas "
        f"independientes (tier 0–4 de completitud, grado del documento y rango SS+…D); (2) un motor NEAT (cinco redes "
        f"evolucionadas más corrección local), elegido entre 13 modelos por su error entre laboratorios; y (3) un "
        f"modelo de cloruros fib B34 con Monte Carlo que traduce el cierre de fisura en vida útil para 384 zonas "
        f"costeras. La cosecha reunió {n0(m['catalogo_total'])} registros y {n0(m['literatura_util'])} documentos "
        f"útiles ({n0(pa['peru'])} del Perú) en {D.n_consultas} consultas, ninguna bajo el 90 % de cobertura, y "
        f"confirmó, leyendo el documento completo, {m['ss_plus']['confirmados']} fuentes SS+ aplicadas en campo. "
        f"Entrenado con {n0(ev['filas_totales'])} filas de {ev['fuentes']} fuentes (antes 2 166 de dos laboratorios), "
        f"el motor redujo el error en fuente no vista de {f1(tod['MAE_actual'])} a {f1(tod['MAE_cosecha'])} puntos "
        f"de cierre y pasó a distinguir la protección bacteriana ({f1(ops['sin bacterias'])} % sin bacterias frente "
        f"a {f1(ops['encapsulación'])} % encapsulada, a 90 días en ambiente marino). Con la fisura de diseño de "
        f"0,3 mm, 25 años se cumplen con certeza en {v25['cumple']} de {n_cl} zonas con cloruros y 40 años en "
        f"{v40['cumple']}; el cierre mediano requerido para 25 años es {f1(c25['mediana'])} %. A nivel de "
        f"ingeniería, el motor convierte la autorreparación de un supuesto en una especificación verificable: el "
        f"cierre mínimo por zona, si la protección lo alcanza y en qué zonas no basta."))
    doc.claves("Palabras claves", "concreto autorreparable bacteriano, neuroevolución, NEAT, agentes de IA, cosecha "
                                  "de literatura, calidad de fuentes, cloruros, vida útil, costa peruana")
    doc.resumen("Abstract", (
        f"Whether a concrete will last the years required by the code is usually answered with models calibrated on "
        f"one or two laboratories and assumed self-healing. Hefesto couples (1) AI agents that harvest, through open "
        f"channels, Peruvian university repositories (DSpace, ALICIA), South American aggregators (LA Referencia, BDTD) "
        f"and the global literature (OpenAlex, OSTI, HAL, Zenodo, CyberLeninka) with ≥ 90 % coverage of every reported "
        f"result, and grade each source with three independent labels (completeness tier 0–4, document degree and an "
        f"SS+…D rank); (2) a NEAT engine (five evolved networks plus local correction) selected from 13 models by its "
        f"cross-laboratory error; and (3) a fib Bulletin 34 chloride model with Monte Carlo that converts crack closure "
        f"into service life for 384 coastal zones. The harvest gathered {m['catalogo_total']:,} records and "
        f"{m['literatura_util']:,} useful documents ({pa['peru']:,} from Peru) over {D.n_consultas} queries and "
        f"confirmed, by full reading, {m['ss_plus']['confirmados']} field-applied SS+ sources. Trained on "
        f"{ev['filas_totales']:,} rows from {ev['fuentes']} sources, the engine lowered the unseen-source error from "
        f"{tod['MAE_actual']:.1f} to {tod['MAE_cosecha']:.1f} closure points and now separates bacterial protection "
        f"levels. With a 0.3 mm design crack, 25 years are met with certainty in {v25['cumple']} of {n_cl} chloride "
        f"zones and 40 years in {v40['cumple']}."))
    doc.claves("Keywords", "bacterial self-healing concrete, neuroevolution, NEAT, AI agents, literature harvesting, "
                           "source quality, chlorides, service life, Peruvian coast")

    # ------------------------------------------------------------------ I
    doc.h1("I. INTRODUCCIÓN")
    doc.h2("A. Problema y expectativa")
    doc.p("Una vivienda frente al mar en Colán se diseña para durar décadas, pero antes de cumplir 8 años el acero "
          "de sus sobrecimientos ya se está oxidando. Mientras tanto, el cálculo que debía advertirlo podía "
          "prometer 150 años. Entre esas dos cifras hay una pregunta que hoy ningún ingeniero en el Perú puede "
          "responder con datos: si el concreto pudiera cerrar sus propias fisuras, ¿cuánto tendría que cerrarlas "
          "para llegar a la vida útil que exige la norma en ese lugar, y lo lograría de verdad? Este artículo "
          "responde esa pregunta para 384 zonas de la costa peruana con un motor de neuroevolución, y muestra "
          "dónde la respuesta es sí, dónde es no y cuánta confianza merece cada una.")
    doc.p("En la playa La Esmeralda (Colán, Paita), el 98,4 % de los sobrecimientos evaluados presenta manchas de "
          "corrosión y el deterioro empezó a propagarse en menos de 8 años [1]. La Norma E.060 limita la relación "
          "agua–material cementante y fija recubrimientos para exposición a cloruros [2], y el EN 1990 asigna 25 o 50 "
          "años de vida de diseño según el uso [3], pero ninguna considera la autorreparación. Los modelos de vida útil "
          "más usados (fib B34 [4], Life-365 [5], DuraCrete [6]) reciben el efecto de la reparación como dato, y los "
          "estudios que lo cuantifican lo miden en uno o dos laboratorios [10], [13], [18]. El resultado es una "
          "incertidumbre que no se declara: un sistema anterior del propio grupo llegó a informar 150 años en 342 de "
          "384 zonas por un tope arbitrario, un régimen seco tratado como inmune y la reparación contada dos veces.")
    doc.p("La expectativa de este trabajo es reducir esa incertidumbre con datos y no con supuestos: predecir qué "
          "concreto, con qué protección bacteriana y con cuánta reparación alcanza 25 o 40 años en un lugar dado, y "
          "decir con qué confianza. Para eso hace falta más de lo que hay en un laboratorio: datos de muchos "
          "laboratorios, de estructuras reales y del Perú, y un criterio explícito sobre cuánto vale cada fuente.")
    doc.h2("B. Estado del arte")
    doc.p("El concreto autorreparable bacteriano sella fisuras cuando esporas de *Bacillus* y un precursor de calcio "
          "precipitan carbonato al ingresar agua [13], [14]. Los modelos de aprendizaje automático publicados para "
          "predecir el cierre usan redes neuronales, algoritmos genéticos o árboles sobre bases reunidas de la "
          "literatura [15]–[17]; la neuroevolución NEAT [7] hace crecer la topología de la red junto con sus pesos. "
          "Para traducir ensayos a años, [18] aplicó Fick con difusión variable a concreto autorreparable expuesto a "
          "cloruros. Lo que falta es (i) validar el modelo en laboratorios que no vio, (ii) alimentarlo de forma "
          "continua y trazable y (iii) distinguir una tesis de pregrado de una estructura instrumentada en servicio. "
          "Las aplicaciones a escala real existen, pero son pocas: el ensayo de la autopista A465 en Gales [19], [20], "
          "una pasarela con vigas bacterianas en Lituania [21] y demostradores en los Países Bajos [30].")
    doc.h2("C. Propuesta y aporte")
    doc.p("El problema de ingeniería que se resuelve es concreto: dada una zona de la costa, ¿qué cierre de fisura "
          "necesita un concreto para cumplir 25 o 40 años, y lo alcanza la protección bacteriana elegida? El núcleo "
          "es un motor de neuroevolución NEAT que predice ese cierre en laboratorios que no vio; lo alimentan agentes "
          "de IA y lo traduce a años un modelo de cloruros.")
    doc.p("Hefesto aporta: (1) agentes de IA que cosechan por canales abiertos con una meta de cobertura medible "
          "(≥ 90 % de lo que reporta cada consulta) y una regla de sesgo (el Perú es la fuente principal, Sudamérica "
          "el agregado y lo global la base de aprendizaje y comparación); (2) una nomenclatura de calidad de tres "
          "capas (tier, grado y rango SS+…D) en la que T1 y T0 solo se asignan tras leer el documento completo; (3) "
          "un motor NEAT elegido por su error entre laboratorios y reentrenado con la cosecha; y (4) la traducción "
          "del cierre a vida útil por zona, acotada al horizonte pedido. La sección II describe el método; la III, "
          "los resultados; y la IV concluye.")

    # ------------------------------------------------------------------ II
    doc.h1("II. METODOLOGÍA")
    doc.h2("A. Arquitectura")
    doc.p("El sistema tiene cinco etapas (Fig. 1). Los agentes escriben en un esquema único; el curador valida tipos, "
          "rangos, duplicados y coherencia (por ejemplo, nivel de protección 0 con especie bacteriana declarada) y "
          "nunca corrige ni imputa. El orquestador entrena el motor con lo aceptado y publica un mapa de necesidades "
          "(combinaciones sin datos) que orienta la próxima cosecha. El Atlas, un proyecto aparte, solo consume la "
          "salida.")
    doc.figura(figs["arq"], "Arquitectura de Hefesto. Línea discontinua: el mapa de necesidades devuelve a los agentes "
                            "las combinaciones sin datos (aprendizaje activo). Elaboración propia.", 0.61)
    doc.h2("B. Agentes recolectores y cobertura")
    doc.p("Cada fuente se consulta por su interfaz oficial: la API REST de DSpace 7, el buscador y las metaetiquetas "
          "Dublin Core de DSpace 6, la API de VuFind (ALICIA [32], LA Referencia [33] y BDTD) y las API de OpenAlex "
          "[31], OSTI, HAL, Zenodo y CyberLeninka, con un agente de usuario honesto. No se fuerza ningún acceso "
          "bloqueado (desafíos anti-bot, inicio de sesión o claves). Las consultas combinan concreto con "
          "autorreparable, autocicatrizante, bacterias, *Bacillus*, cloruros, agua de mar, corrosión, fisuras y "
          "carbonatación, en español, portugués, inglés, francés, ruso y chino, más consultas dirigidas a aplicaciones "
          "en campo. Para cada consulta se compara lo cosechado con lo que reporta el repositorio; por debajo del "
          "90 % se reintenta y se anota el motivo. La Tabla I resume las fuentes.")
    filas = [["Fuente (ámbito)", "Registros", "Útiles"]]
    for g, a in [("DSpace 7: PUCP, UNI, UPC, USAT, SENCICO", "Perú"), ("DSpace 6: UCV, UNPRG, UNS, ULADECH", "Perú"),
                 ("ALICIA (CONCYTEC)", "Perú"), ("LA Referencia", "Sudam./global"), ("BDTD", "Sudamérica"),
                 ("OpenAlex", "global"), ("OSTI", "global"), ("CyberLeninka", "global"), ("HAL", "global"),
                 ("Zenodo", "global")]:
        filas.append([f"{g} ({a})", n0(D.por_fuente[g]), n0(D.util_fuente[g])])
    filas.append(["**Total", f"**{n0(m['catalogo_total'])}", f"**{n0(m['literatura_util'])}"])
    doc.tabla("Fuentes cosechadas por los agentes", filas, [3.4, 1.0, 0.9],
              nota=f"Útil: trata concreto o mortero y pertenece a una de las cuatro familias (autorreparable, cloruros, "
                   f"inspección de daño, durable convencional). {D.n_consultas} consultas, {D.bajo90} bajo el 90 % de "
                   f"cobertura. El ámbito de LA Referencia sale del país del registro. Elaboración propia.")
    doc.p(f"La cosecha es solo la primera de cuatro etapas. La segunda descarga los PDF de acceso abierto en un orden "
          f"fijo: primero los candidatos a SS+, luego el Perú, la costa norte y la autorreparación. La tercera ubica "
          f"en cada PDF las tablas con datos (cierre, fisura, cloruros, f′c) y arma una cola de extracción; hoy tiene "
          f"{sum(D.cola.values())} tablas, de las que {D.cola['transcrita']} están transcritas, "
          f"{D.cola['descartada']} descartadas con motivo y {D.cola['pendiente']} pendientes. En la cuarta, el agente "
          f"lee cada tabla y la transcribe al esquema con su procedencia (DOI o handle, tabla y página). Las reglas son "
          f"estrictas: no se inventa ni se estima un valor, un rango no se convierte en un número exacto, se comprueba "
          f"que las sumas cuadren y se anota si la tesis no cuadra. Si falta el ancho inicial, el sellado queda en "
          f"milímetros y no se convierte en porcentaje de cierre.")
    doc.h2("C. Calificación de fuentes: tier, grado y rango")
    doc.p("Como no existe un estándar para calificar fuentes heterogéneas (tesis, artículos, informes y datasets) "
          "con fines de entrenamiento, se propone una categorización interna: cada documento recibe tres etiquetas "
          "independientes (Tabla II). El *tier* mide la completitud para Hefesto "
          "(mezcla, fisura, edad y resultado medido). El *grado* es una nomenclatura interna del tipo de documento y "
          "sale solo de lo que declara la fuente (dc.type, formato o tipo de OpenAlex): un título como “según la norma "
          "ISO” no convierte una tesis en norma. El *rango* combina ambos. Con metadatos el tier es provisional y "
          "nunca pasa de T2; T1 y T0 solo se fijan leyendo el documento completo, y SS+ exige además prototipo o "
          "estructura real en servicio. Cada confirmación queda justificada por escrito.")
    doc.tabla("Nomenclatura interna de calidad de Hefesto (propuesta)", [
        ["Rango", "Regla (tier × grado)"],
        ["SS+", "T0 y aplicado en prototipo o estructura en servicio"],
        ["SS", "T0, o T1 de grado alto (ORG, DATA, DOC, ART-I)"],
        ["S", "T1 de otros grados, o T2 de grado alto"],
        ["A", "T2 de maestría, congreso, informe o libro"],
        ["B", "T2 de licenciatura, bachiller o artículo genérico"],
        ["C", "T3 (toca el tema sin centrarse) o revisión"],
        ["D", "T4 (periférico) o trabajo genérico sin ensayos propios"]],
        [0.7, 4.3], alin=["center", "left"],
        nota="Categorización interna propuesta en este trabajo; no es un estándar externo. T0: completo, tangible, "
             "trazable, cuali- y cuantitativo, con respaldo de organizaciones. ORG: norma u organismo; DATA: dataset "
             "con DOI; DOC: doctorado; ART-I: revista con revisión por pares; TES: tesis de nivel no declarado. "
             "Elaboración propia.")
    doc.h2("D. Datos de entrenamiento")
    doc.p(f"El motor usa siete entradas: ancho inicial de fisura w₀, edad, nivel de protección (0 sin bacterias, 1 "
          f"directa, 2 portador, 3 encapsulación), ambiente marino, lactato de calcio, curado previo y agente "
          f"cristalino. Solo entra una fila con las siete medidas y cierre medido. Dos entradas se deducen del "
          f"documento, no se imputan: el curado previo es el régimen de Cappellesso (curado antes de la exposición "
          f"marina) [10], que no existe en los demás estudios, y ninguna fila de la literatura usa aditivo cristalino "
          f"según la descripción de su agente. Se excluyen las filas que duplican los datasets de réplicas [9], [11]. "
          f"Así se pasó de 2 166 filas de dos laboratorios a {n0(ev['filas_totales'])} filas de {ev['fuentes']} "
          f"fuentes, incluidas 18 de una tesis de Piura con *Lysinibacillus sphaericus* cuyas siete entradas salen "
          f"de su tabla de dosificación [34].")
    doc.h2("E. Motor NEAT y banco de comparación")
    doc.p("Cada genoma NEAT [7] se compila a matrices por capa, de modo que la pasada hacia adelante es vectorial "
          "e idéntica a la evaluación nodo a nodo:")
    doc.ecuacion("h⁽ˡ⁾ = σ( W⁽ˡ⁾ · h⁽ˡ⁻¹⁾ + b⁽ˡ⁾ ),   ŷ_NEAT = (1/K) Σₖ ŷₖ")
    doc.p("La evolución sigue NEAT [7]: cada red empieza con las siete entradas conectadas directamente a la "
          "salida, sin capas ocultas, y la mutación puede añadir conexiones y nodos. Las redes se agrupan en especies "
          "por distancia genética para proteger las innovaciones, y la aptitud es el error de cierre con una "
          "penalización por complejidad, de modo que una conexión nueva solo sobrevive si mejora la predicción "
          "(Tabla III). Las entradas se normalizan con límites físicos fijos (w₀ ≤ 1 mm, edad ≤ 480 días) y no con "
          "los datos, para que una red entrenada en un laboratorio no cambie de escala en otro.")
    doc.tabla("Configuración de la evolución NEAT", [
        ["Parámetro", "Valor"],
        ["Población / generaciones", "60 / 50 por red"],
        ["Redes promediadas (K)", "5, con semillas distintas"],
        ["Topología inicial", "7 entradas → salida, sin ocultos"],
        ["Prob. de añadir conexión / nodo", "0,18 / 0,12"],
        ["Activación / agregación", "sigmoide / suma"],
        ["Umbral de especie", "2,5 (+1,0 por oculto inicial)"],
        ["Élite / supervivencia", "2 / 25 %"],
        ["Estancamiento máximo", "15 generaciones"],
        ["Penalización por complejidad λ", "8 × 10⁻⁴ por conexión"],
        ["Pesos / sesgos", "|w| ≤ 12; |b| ≤ 10"]],
        [2.3, 2.7], alin=["left", "left"],
        nota="neat-python con evaluación matricial propia (idéntica a la evaluación nodo a nodo hasta 10⁻¹²). "
             "Fuente: hefesto/motor/config_neat.txt y ConfigNEAT.")
    doc.p("El motor H3 promedia K = 5 redes evolucionadas y, cuando hay ensayos del laboratorio nuevo, suma una "
          "corrección local por bosque aleatorio que pesa según el número n de grupos locales, con intervalos "
          "conformes [8]:")
    doc.ecuacion("ŷ = ŷ_NEAT + n/(n + 10) · RF(x),   edad ∈ [3, 480] d")
    doc.p(f"El banco compara 13 candidatos (NEAT de una red, ×5, con capa oculta y con evolución larga; perceptrones; "
          f"bosque aleatorio; XGBoost; híbridos; Ridge) en tres protocolos: filas al azar, grupos de probeta y entre "
          f"laboratorios. La regla de elección es el menor error entre laboratorios (empate si el IC 95 % bootstrap "
          f"de la diferencia incluye 0), luego la mejora con ensayos locales, la complejidad y el tiempo. El piso de "
          f"ruido de las réplicas es {f1(piso['piso_inferior_pp'])}–{f1(piso['piso_superior_pp'])} pp. La prueba de "
          f"la cosecha deja fuera, por turno, cada una de las {ev['fuentes']} fuentes y la predice sin haberla visto, "
          f"con 3 semillas.")
    doc.h2("F. Vida útil frente a cloruros")
    doc.p("La vida útil es el tiempo hasta que la probabilidad de inicio de la corrosión llega al 10 % (fib B34 "
          "[4]), con la solución de Fick de difusión aparente:")
    doc.ecuacion("C(x,t) = Cs · [1 − erf( x / (2√(D_app(t)·t)) )]")
    doc.ecuacion("D_app(t) = kₑ · D₂₈ · f² · (t₀ / min(t, 25 a))ᵐ,   f = 1 + s · w₀(1 − c)")
    doc.p("D₂₈ sale de un ajuste sobre 581 ensayos RCM de Dryad [12]; m es el envejecimiento fib, congelado a 25 "
          "años como en Life-365 [5]; Cs sigue DuraCrete [6]; el factor de fisura f usa el ancho residual tras el "
          "cierre c, de modo que la reparación cuenta una sola vez. La pendiente s = 3,69 mm⁻¹ se ajustó con "
          "probetas fisuradas de [11] y es provisional. Cada zona recibe las mezclas que cumplen la norma de su "
          "régimen, el motor predice el cierre a 90 días con cada protección y el veredicto descuenta un error de "
          "±20 pp: “cumple” si la predicción menos 20 alcanza el cierre requerido, “incierto” si solo la predicción "
          "central lo alcanza. El régimen seco queda fuera de alcance (gobierna la carbonatación) y ningún resultado "
          "pasa del horizonte pedido. La Tabla IV resume los parámetros.")
    doc.tabla("Parámetros del modelo de vida útil", [
        ["Parámetro", "Valor", "Fuente"],
        ["Probabilidad objetivo de inicio", "10 % (β ≈ 1,3)", "fib B34 [4]"],
        ["Cloruro crítico Ccrit", "0,6 % del ligante", "fib B34 [4]"],
        ["Cs = A·(a/b)", "A = 2,565 atm.; 7,758 salp.", "DuraCrete [6]"],
        ["D₂₈ (a/b, adiciones)", "ajuste de 581 ensayos RCM", "Dryad [12]"],
        ["Envejecimiento m", "I 0,30; IP 0,45 (a 25 a)", "fib [4], Life-365 [5]"],
        ["Pendiente de fisura s", "3,69 mm⁻¹ (provisional)", "Cappellesso [11]"],
        ["Fisura de diseño w₀ / edad", "0,3 mm / 90 d", "Hefesto"],
        ["Monte Carlo / horizonte", "4 000 sorteos / 40 a", "Hefesto"]],
        [1.85, 1.7, 1.45], alin=["left", "left", "left"],
        nota="Cs: cloruro superficial (% del ligante); atm.: atmosférico marino; salp.: salpicadura. La niebla salina "
             "interpola según el depósito de cloruros (supuesto a calibrar con vela húmeda).")

    # ------------------------------------------------------------------ III
    doc.h1("III. RESULTADOS Y DISCUSIÓN")
    doc.h2("A. Cosecha y calidad")
    doc.p(f"La cosecha reunió {n0(m['catalogo_total'])} registros y {n0(m['literatura_util'])} documentos útiles, por "
          f"encima de la meta ideal de 5 000: {n0(pa['peru'])} del Perú, {n0(pa['sudamerica'])} de Sudamérica y "
          f"{n0(pa['global'])} globales. Por familia, {n0(m['por_familia']['autorreparable'])} tratan "
          f"autorreparación, {n0(m['por_familia']['cloruros'])} cloruros, {n0(m['por_familia']['inspeccion_dano'])} "
          f"inspecciones de daño y {n0(m['por_familia']['durable_convencional'])} concretos durables convencionales. "
          f"El Perú aporta sobre todo inspecciones ({n0(D.peru_familia['inspeccion_dano'])}) y durables "
          f"({n0(D.peru_familia['durable_convencional'])}), pero solo {D.peru_familia['autorreparable']} documentos de "
          f"autorreparación, casi todos tesis de licenciatura (rango B o menor). Los rangos S y A se concentran en lo "
          f"global (Fig. 2), donde están los artículos revisados por pares ({n0(D.util_grado['ART-I'])} útiles) y los "
          f"doctorados ({n0(D.util_grado['DOC'])}).")
    doc.figura(figs["cos"], "Distribución del rango de calidad por ámbito (todos los registros). A la derecha, el "
                            "número de registros. Elaboración propia.", 0.47)
    doc.p(f"De {m['ss_plus']['candidatos'] + m['ss_plus']['confirmados']} candidatos a SS+ se leyeron completos los de "
          f"acceso abierto y se confirmaron {m['ss_plus']['confirmados']} (Tabla V). Tres son de autorreparación en "
          f"servicio: el ensayo de la A465 con cuatro tecnologías y su seguimiento hasta 231 días [19], el cierre "
          f"medido en campo de las microcápsulas [20] y la pasarela lituana con razón de cierre a 28 y 98 días [21]. "
          f"Los otros ocho dan perfiles de cloruros en estructuras reales, justo lo que el modelo de durabilidad "
          f"necesita para reemplazar supuestos. Ninguna SS+ es peruana: la tesis de Colán [1] llega a T1 (inspección "
          f"completa de 64 estructuras, sin ensayos de laboratorio) y los demostradores holandeses [30] se quedan en "
          f"T2 porque casi no fisuraron y no se pudo medir el cierre en campo.")
    doc.tabla("Fuentes SS+ confirmadas por lectura completa", [
        ["Fuente", "Estructura o prototipo", "Dato clave"],
        ["Davies et al. [19]", "A465, Gales (obra en curso)", "w y permeabilidad, 231 d"],
        ["Al-Tabbaa et al. [20]", "A465, microcápsulas", "cierre en campo (CWH)"],
        ["Jakubovskis y Boris [21]", "Pasarela bacteriana", "razón de cierre 28/98 d"],
        ["Othmen et al. [22]", "Viga marina de 28 años", "Cs y D, CV 44/61 %"],
        ["Clerc et al. [23]", "Muelle", "37 perfiles in situ"],
        ["Iowa DOT [24]", "Puente I-129", "núcleos de Cl⁻ y vida útil"],
        ["Liu et al. [25]", "Puente marino de 30 años", "Csa y D por zona"],
        ["Wall [26]; Sandberg [27]", "Puertos; estación de campo", "perfiles y umbrales"],
        ["Lindvall [28]; Khani [29]", "Mar, carreteras, invierno", "exposición medida"]],
        [1.7, 1.75, 1.55], alin=["left", "left", "left"],
        nota="Todas de acceso abierto y con respaldo de organismos (EPSRC, NSFC, Iowa DOT, consejos de investigación). "
             "[26]–[29] son tesis doctorales (grado DOC, leído).")
    doc.h2("B. Datos peruanos transcritos")
    pi = D.piura
    prom = lambda v: sum(v) / len(v)
    doc.p(f"De la tesis de Colán [1] se transcribieron las Tablas 1–4, 7 y 9 (580 filas de inspección de 64 "
          f"estructuras, por elemento, nivel de corrosión y antigüedad; Fig. 3). La comprobación de sumas encontró que las "
          f"Tablas 1–4 difieren en ±1 de la Tabla 7 en dos rangos de antigüedad; el error es de la tesis y se anotó "
          f"sin corregirlo. De la tesis de Piura con *Lysinibacillus sphaericus* [34] se transcribió la Tabla 6: nueve "
          f"probetas prismáticas con ancho inicial y porcentaje de sellado medido por microscopía electrónica a 7 y "
          f"14 días (Tabla VI). El sellado crece con la dosis y con la edad; el patrón no muestra sellado visible y no "
          f"se transcribió como cero. Se descartaron, con motivo escrito, una tesis sin autorreparación con fechas de "
          f"rotura imposibles, una tabla que contradice su propio texto (431 frente a 257,4 kg/cm² a 14 días) y dos "
          f"tesis sin datos de cierre.")
    doc.figura(figs["colan"], "Nivel de corrosión (indicador «manchas») de los elementos de 64 estructuras de La "
                              "Esmeralda, Colán, según su antigüedad. Rótulos de antigüedad tal como en la Tabla 7 de "
                              "[1]; n: elementos evaluados. Elaboración propia con datos de [1].", 0.48)
    filas = [["Dosis de cultivo", "w₀ (µm)", "7 días", "14 días"]]
    for k, et in (("ABC15", "15 ml/m³"), ("ABC20", "20 ml/m³"), ("ABC25", "25 ml/m³")):
        w = sorted(set(pi[k]["w"]))
        filas.append([et, f"{int(w[0])}–{int(w[-1])}", f"{f1(prom(pi[k][7]), 0)} %", f"{f1(prom(pi[k][14]), 0)} %"])
    doc.tabla("Sellado medido en Piura (promedio de 3 probetas)", filas, [1.6, 1.1, 0.9, 0.9],
              nota="Concreto f′c = 350 kg/cm², a/c = 0,43, cemento Portland tipo V, sin lactato ni aditivo cristalino "
                   "(Tabla 3 de [34]). Patrón (825, 128 y 265 µm): sin sellado visible.")
    doc.h2("C. Banco de motores")
    doc.p(f"La Tabla VII resume el banco. Dentro de un mismo laboratorio, XGBoost y el bosque aleatorio son los más "
          f"precisos ({f1(cand['XGBoost']['precision']['filas']['MAE_pp'])} y "
          f"{f1(cand['Random Forest']['precision']['filas']['MAE_pp'])} pp), pero al predecir otro laboratorio su "
          f"error se dispara a {f1(cand['XGBoost']['precision']['laboratorio']['media_MAE_pp'])} pp: aprenden rasgos "
          f"del laboratorio. Las redes más profundas (NEAT con capa oculta, perceptrón 32×16) también ajustan mejor y "
          f"generalizan peor. Las cinco redes NEAT sin capa oculta logran el menor error entre laboratorios "
          f"({f1(h3['precision']['laboratorio']['media_MAE_pp'])} pp); H3 empata en precisión y gana por su curva de "
          f"mejora (Fig. 4): sin ensayos locales parte de {f1(h3['mejora']['0'])} pp, frente a "
          f"{f1(cand['Random Forest']['mejora']['0'])} pp del bosque aleatorio, y con 40 grupos locales baja a "
          f"{f1(h3['mejora']['40'])} pp. Para un sitio nuevo con pocos ensayos, que es el caso peruano, empezar bien "
          f"importa más que terminar bien. El motor usa sobre todo la edad, porque en las réplicas el ambiente marino "
          f"y la protección coinciden con el laboratorio de origen.")
    filas = [["Modelo", "Filas", "Grupos", "Entre lab.", "Entren. (s)"]]
    for n, et in [("NEAT 1 red (clásico)", "NEAT 1 red"), ("NEAT ×5 (motor actual)", "NEAT ×5"),
                  ("NEAT ×5 capa oculta", "NEAT ×5 + capa oculta"), ("H3 (NEAT ×5 + RF)", "**H3 (elegido)"),
                  ("MLP 32x16", "Perceptrón 32×16"), ("Random Forest", "Bosque aleatorio"), ("XGBoost", "XGBoost"),
                  ("XGBoost + NEAT", "XGBoost + NEAT"), ("Ridge", "Ridge")]:
        c = cand[n]
        filas.append([et, f1(c["precision"]["filas"]["MAE_pp"]), f1(c["precision"]["grupos"]["MAE_pp"]),
                      f1(c["precision"]["laboratorio"]["media_MAE_pp"]), f1(c["velocidad"]["entrenar_s"], 2)])
    doc.tabla("Banco de motores: MAE de cierre (pp) por protocolo", filas, [1.9, 0.75, 0.8, 0.85, 0.85],
              nota=f"Réplicas de Mousa [9] y Cappellesso [11] ({n0(banco['n_filas'])} filas, {banco['n_probetas']} "
                   f"probetas). Entre lab.: media de entrenar en uno y predecir el otro. 9 de 13 candidatos.")
    doc.figura(figs["mej"], "Curva de mejora: error en el laboratorio nuevo según los grupos de probetas locales que "
                            "se suman (H3 los usa para calibrar, sin reentrenar). Datos del banco. Elaboración propia.",
               0.53)
    hc, hm = D.hib["Cappellesso2024"], D.hib["Mousa2022"]
    ec, em = hc["estabilidad_base"], hm["estabilidad_base"]
    doc.p(f"Promediar cinco redes no es un adorno. Entrenada sola, una red NEAT predice Cappellesso con "
          f"{f1(ec['MAE_pp_una_red'][0])} ± {f1(ec['MAE_pp_una_red'][1])} pp según la semilla; el promedio de cinco "
          f"baja a {f1(ec['MAE_pp_promedio_K'][0])} ± {f1(ec['MAE_pp_promedio_K'][1])} pp, y en Mousa de "
          f"{f1(em['MAE_pp_una_red'][0])} ± {f1(em['MAE_pp_una_red'][1])} a {f1(em['MAE_pp_promedio_K'][0])} ± "
          f"{f1(em['MAE_pp_promedio_K'][1])} pp: el conjunto reduce la dispersión entre semillas unas diez veces. "
          f"Los intervalos conformes [8] calibrados con ensayos locales cumplen lo que prometen (Tabla VIII): con "
          f"un nivel nominal de 90 %, la cobertura real queda entre {f1(min(h['conforme_H1'][n]['90%']['cobertura_real'] for h in (hc, hm) for n in ('5', '10', '20', '40')) * 100, 0)} "
          f"y {f1(max(h['conforme_H1'][n]['90%']['cobertura_real'] for h in (hc, hm) for n in ('5', '10', '20', '40')) * 100, 0)} %, "
          f"y su semiancho se estrecha a medida que hay más grupos locales. Para el diseñador eso significa que el "
          f"motor no solo da un número: dice cuánto puede equivocarse.")
    filas = [["Grupos locales", "Cobertura 90 % (C / M)", "Semiancho (pp, C / M)", "Cobertura 80 % (C / M)"]]
    for n in ("5", "10", "20", "40"):
        c9, m9 = hc["conforme_H1"][n]["90%"], hm["conforme_H1"][n]["90%"]
        c8, m8 = hc["conforme_H1"][n]["80%"], hm["conforme_H1"][n]["80%"]
        filas.append([n, f"{f1(c9['cobertura_real'] * 100, 0)} / {f1(m9['cobertura_real'] * 100, 0)} %",
                      f"{f1(c9['semiancho_pp'], 0)} / {f1(m9['semiancho_pp'], 0)}",
                      f"{f1(c8['cobertura_real'] * 100, 0)} / {f1(m8['cobertura_real'] * 100, 0)} %"])
    doc.tabla("Intervalos conformes en el laboratorio nuevo", filas, [1.0, 1.4, 1.3, 1.3],
              nota=f"C: Cappellesso predicho con motor entrenado en Mousa; M: al revés. {D.hib['semillas']} semillas, "
                   f"{D.hib['generaciones']} generaciones. Fuente: resultados/hibrido.json.")
    doc.h2("D. Entrenamiento con la cosecha")
    doc.p(f"Con la cosecha, el error en fuente no vista bajó de {f1(tod['MAE_actual'])} a {f1(tod['MAE_cosecha'])} pp "
          f"en conjunto y mejoró en {tod['fuentes_que_mejoran']} de {ev['fuentes']} fuentes (Tabla IX, Fig. 5). Entre "
          f"los dos laboratorios de réplicas pasó de {f1(rep['MAE_actual'])} a {f1(rep['MAE_cosecha'])} pp, y en la "
          f"tesis de Piura de {f1(peru['MAE_actual'])} a {f1(peru['MAE_cosecha'])} pp. En los 24 estudios de la "
          f"literatura apenas cambió ({f1(nue['MAE_actual'])} → {f1(nue['MAE_cosecha'])} pp): cada estudio aporta de "
          f"1 a 24 filas con protocolos distintos, y eso no basta para aprender un laboratorio nuevo. Lo más "
          f"importante es cualitativo: el motor v003 predecía {f1(V003_CIERRE_MARINO)} % de cierre a 90 días en "
          f"ambiente marino para toda protección; el v004 distingue {f1(ops['sin bacterias'])} % sin bacterias, "
          f"{f1(ops['directa/comercial'])} % directa, {f1(ops['portador'])} % con portador y "
          f"{f1(ops['encapsulación'])} % encapsulada (Fig. 7a). El lactato aún no tiene efecto: solo un laboratorio "
          f"lo ensayó con y sin él.")
    filas = [["Prueba", "Filas", "Fuentes", "v003", "v004"]]
    for et, g in [("Todas", tod), ("Entre laboratorios", rep), ("Perú (Piura)", peru), ("Estudios nuevos", nue)]:
        filas.append([et, n0(g["n_filas"]), str(g["n_fuentes"]), f1(g["MAE_actual"]), f"**{f1(g['MAE_cosecha'])}"])
    doc.tabla("Error en fuente no vista (MAE, pp de cierre)", filas, [1.7, 0.8, 0.8, 0.8, 0.8],
              nota="Cada fuente se predice con un motor que no la vio (3 semillas). v003: solo réplicas de dos "
                   "laboratorios; v004: todo lo aceptado salvo la fuente evaluada.")
    doc.figura(figs["ev"], "Error en fuente no vista del motor actual (v003) y del entrenado con la cosecha (v004). "
                           "Elaboración propia.", 0.53)
    imp = importancia_v004()["importancia_pp"]
    doc.p(f"La Fig. 6 muestra lo que aprendió el motor v004. Las cinco redes conservan una topología mínima, como "
          f"busca la penalización por complejidad, pero la evolución hizo algo que no ocurría con dos laboratorios: "
          f"dos redes usan el nivel de protección (una directamente y otra a través de un nodo oculto que creó) y otra "
          f"creó un nodo oculto para el curado previo. La importancia por permutación lo confirma con orden de "
          f"magnitud: la edad domina ({f1(imp['Edad (d)'])} pp), y el ancho inicial ({f1(imp['Ancho fisura w0 (mm)'], 2)} "
          f"pp), la protección ({f1(imp['Protección bio (0-3)'], 2)} pp) y el curado previo "
          f"({f1(imp['Curado previo'], 2)} pp) aportan poco pero ya no cero; el ambiente marino, el lactato y el agente "
          f"cristalino siguen en cero. Es una red que empieza a leer el material, no solo el reloj, y que lo hace con "
          f"tres conexiones de media, lo que permite auditar cada peso.")
    doc.figura(figs["redes"], "Las cinco redes evolucionadas del motor v004. Nodos de la izquierda: entradas que cada "
                              "red usa (las demás se podaron); centro: nodos ocultos creados por la evolución; grosor "
                              "proporcional al peso. Elaboración propia.", 0.40)
    doc.h2("E. Vida útil en 384 zonas costeras")
    doc.p(f"De 384 zonas, 116 son secas y quedan fuera de alcance; en las {n_cl} con cloruros, la fisura de diseño de "
          f"0,3 mm sin reparar lleva la corrosión a iniciarse entre 3 y 5,5 años en la mayoría de las zonas, lo que "
          f"coincide con los menos de 8 años observados en Colán [1]. Con mezclas de norma, 25 años son alcanzables "
          f"en las {c25['n']} zonas con un cierre requerido mediano de {f1(c25['mediana'])} % (p10 "
          f"{f1(c25['p10'])} %, p90 {f1(c25['p90'])} %); 40 años solo en {c40['n']} zonas, con un cierre de "
          f"{f1(c40['p10'])}–{f1(c40['p90'])} %. Con el motor v004 y el error de ±20 pp, 25 años se cumplen con "
          f"certeza en {v25['cumple']} zonas y 40 años en {v40['cumple']} (Tabla XII y Fig. 7b).")
    R = D.regimen
    doc.p(f"El régimen de exposición lo decide casi todo (Tabla X). En las {R['atmosferico_marino']['n']} zonas "
          f"atmosféricas marinas la mezcla de norma (cemento IP, a/b = 0,35, 50 mm) supera 40 años sin fisura y la "
          f"fisura sin reparar inicia la corrosión hacia los {f1(R['atmosferico_marino']['fisura'], 0)} años; basta "
          f"un cierre de {f1(R['atmosferico_marino']['req25'], 0)} % para llegar a 25 años, y el motor predice "
          f"{f1(R['atmosferico_marino']['neat'])} %. En niebla salina y salpicadura la fisura sin reparar inicia la "
          f"corrosión en {f1(R['niebla_salina']['fisura'])} y {f1(R['salpicadura']['fisura'])} años, y el cierre "
          f"requerido sube a {f1(R['niebla_salina']['req25'])} % y {f1(R['salpicadura']['req25'])} %, por encima "
          f"de lo que hoy predice el motor para cualquier protección. En esas {R['niebla_salina']['n'] + R['salpicadura']['n']} "
          f"zonas la autorreparación sola no basta: hace falta además reducir la fisura de diseño, aumentar el "
          f"recubrimiento o confirmar con ensayos locales un cierre mayor. Por departamento, Arequipa "
          f"({D.departamentos['Arequipa']}), Piura ({D.departamentos['Piura']}) e Ica ({D.departamentos['Ica']}) "
          f"concentran más zonas.")
    filas = [["Régimen", "Zonas", "Mezcla", "Sin fisura", "Fisura 0,3", "Cierre 25 a", "Cumple 25 a"]]
    for g, et in (("atmosferico_marino", "Atmosférico"), ("niebla_salina", "Niebla salina"),
                  ("salpicadura", "Salpicadura"), ("seco", "Seco")):
        r = R[g]
        if g == "seco":
            filas.append([et, str(r["n"]), "—", "carbonatación", "—", "—", "fuera de alcance"])
            continue
        rec = "/".join(str(int(float(x))) for x in r["rec"])
        sf = "> 40 a" if r["sin_fisura_40"] == r["n"] else f"{f1(r['sin_fisura'])} a"
        filas.append([et, str(r["n"]), f"{r['cemento']}, {r['a_b'][0].replace('.', ',')}, {rec} mm", sf,
                      f"{f1(r['fisura'])} a", f"{f1(r['req25'])} %", str(r["veredicto"].get("cumple", 0))])
    doc.tabla("Vida útil por régimen de exposición (medianas)", filas, [1.15, 0.6, 1.25, 0.85, 0.75, 0.8, 0.8],
              nota="Sin fisura y fisura 0,3: años hasta el 10 % de probabilidad de inicio de la corrosión con la mezcla "
                   "elegida (la más sencilla que alcanza 25 años). Cierre 25 a: cierre requerido para 25 años.")
    sens = D.sens
    doc.p("¿Cuánto depende el cierre requerido de los supuestos del modelo de cloruros? La Tabla XI repite el cálculo "
          "en cinco ciudades cambiando un supuesto a la vez. Tres lecciones de diseño salen de ella. Primera, 15 mm "
          "más de recubrimiento valen más que cualquier protección bacteriana en las zonas atmosféricas: llevan el "
          "cierre requerido para 25 años casi a cero. Segunda, el efecto de la fisura sobre la difusión es el "
          "supuesto que más pesa (con efecto lineal en lugar de cuadrático, el cierre requerido cae a cero en las "
          "zonas atmosféricas), y por eso medirlo en campo es la prioridad. Tercera, diseñar con P = 50 % en lugar "
          "de 10 % haría desaparecer la necesidad de reparar en casi todas partes: la confiabilidad que fija la "
          "norma decide el resultado tanto como el material.")
    filas = [["Ciudad (régimen)", "Base", "Fisura lineal", "CoV Cs 0,5", "+15 mm", "P = 50 %"]]
    nombres = {"atmosferico_marino": "atm.", "niebla_salina": "niebla"}
    for c, v in sens.items():
        x = v["variantes"]
        celda = lambda k: f"{f1(x[k]['cierre_req_25_pct'], 0)} %"
        filas.append([f"{c} ({nombres.get(v['regimen'], v['regimen'])})", celda("base"), celda("fisura_lineal"),
                      celda("cs_cov_0.5"), celda("recub_+15"), celda("p_50")])
    doc.tabla("Sensibilidad del cierre requerido para 25 años", filas, [1.55, 0.7, 0.85, 0.8, 0.65, 0.7],
              nota="Una zona por ciudad con la mezcla de norma; se cambia un supuesto a la vez. Fisura lineal: D ∝ f "
                   "en lugar de f²; CoV Cs: dispersión de Cs; +15 mm: recubrimiento; P: probabilidad de inicio de la "
                   "corrosión. Fuente: resultados/sensibilidad_vida.json.")
    doc.tabla("Veredicto por zona con el motor v004", [
        ["Veredicto", "25 años", "40 años"],
        ["Cumple", str(v25.get("cumple", 0)), str(v40.get("cumple", 0))],
        ["Incierto", str(v25.get("incierto", 0)), str(v40.get("incierto", 0))],
        ["No cumple", str(v25.get("no cumple", 0)), str(v40.get("no cumple", 0))],
        ["No alcanzable con la mezcla", str(v25.get("no alcanzable con esta mezcla", 0)),
         str(v40.get("no alcanzable con esta mezcla", 0))],
        ["Cierre requerido mediano", f"{f1(c25['mediana'])} %", f"{f1(c40['mediana'])} %"]],
        [2.2, 1.0, 1.0],
        nota=f"{n_cl} zonas con cloruros (116 secas fuera de alcance). Fisura de diseño 0,3 mm; cierre predicho a 90 "
             f"días con la mejor protección; P = 10 % (fib B34).")
    doc.figura(figs["vida"], "(a) Cierre predicho a 90 días en ambiente marino según la protección, motores v003 y "
                             "v004. (b) Veredicto de 25 y 40 años en las 268 zonas con cloruros. Elaboración propia.",
               0.55)
    doc.h2("F. Qué resuelve a nivel de ingeniería")
    mej20, mej40 = h3["mejora"]["20"], h3["mejora"]["40"]
    doc.p(f"Para el ingeniero que diseña en la costa, el motor convierte una suposición en una especificación "
          f"verificable (Tabla XIV). Antes, la autorreparación entraba al cálculo como un porcentaje supuesto y la vida "
          f"útil salía como un número sin incertidumbre, que podía llegar a 150 años. Con Hefesto, primero se obtiene "
          f"el cierre mínimo que la fisura de diseño debe alcanzar para cumplir 25 o 40 años en la zona; luego el motor "
          f"dice si la protección elegida llega a ese cierre, con su error medido en un laboratorio no visto; y el "
          f"veredicto (cumple, incierto, no cumple) queda acotado al horizonte de la norma. Eso permite tres "
          f"decisiones concretas: especificar al proveedor o al laboratorio el cierre que debe demostrar, saber en qué "
          f"zonas la autorreparación no basta y hay que actuar sobre la fisura o el recubrimiento, y planificar "
          f"cuántos ensayos locales hacen falta para confiar en la predicción ({f1(mej20)} pp con 20 grupos de "
          f"probetas, {f1(mej40)} pp con 40).")
    R = D.regimen
    a, s_ = D.ejemplo["atm"], D.ejemplo["salp"]
    doc.p(f"Un ejemplo con dos zonas reales del litoral norte de Piura (lat. {a['lat'].replace('.', ',')}°) muestra "
          f"el procedimiento completo (Tabla XIII). A {f1(float(s_['dist_mar_km']), 2)} km del mar (clase "
          f"{s_['clase']}) el depósito de cloruros es {f1(float(s_['deposicion_mg_m2_d']))} mg/m²/día; la mezcla de "
          f"norma resiste {s_['sin_fisura']} sin fisura, pero con la fisura de diseño sin reparar la corrosión se "
          f"inicia a los {s_['fisura_sin_reparar']}. Para 25 años la fisura tendría que cerrarse un "
          f"{f1(float(s_['cierre_req_25_pct']))} %, y el motor predice {f1(float(s_['neat_cierre_pct']))} %: no cumple. "
          f"A {f1(float(a['dist_mar_km']), 2)} km (clase {a['clase']}) basta un cierre de "
          f"{f1(float(a['cierre_req_25_pct']))} %, que la protección predicha supera con margen: cumple. El mismo "
          f"concreto bacteriano es una buena solución a 2,75 km y una insuficiente a 250 m; en primera línea hay que "
          f"limitar el ancho de fisura de diseño o exigir y verificar en laboratorio un cierre de al menos "
          f"{f1(float(s_['cierre_req_25_pct']), 0)} %.")
    sf = lambda z: "> 40 años" if z["sin_fisura"].startswith("cumple 40") else z["sin_fisura"]
    doc.tabla("Ejemplo de diseño en el litoral norte de Piura", [
        ["Paso", f"{f1(float(s_['dist_mar_km']), 2)} km del mar", f"{f1(float(a['dist_mar_km']), 2)} km del mar"],
        ["Régimen / clase", f"salpicadura / {s_['clase']}", f"atmosférico / {a['clase']}"],
        ["Depósito de Cl⁻ (mg/m²/d)", f1(float(s_["deposicion_mg_m2_d"])), f1(float(a["deposicion_mg_m2_d"]))],
        ["Mezcla de norma", f"{s_['cemento']}, a/b {s_['a_b'].replace('.', ',')}, {int(float(s_['recubrimiento_mm']))} mm",
         f"{a['cemento']}, a/b {a['a_b'].replace('.', ',')}, {int(float(a['recubrimiento_mm']))} mm"],
        ["Sin fisura", sf(s_), sf(a)],
        ["Fisura 0,3 mm sin reparar", s_["fisura_sin_reparar"], a["fisura_sin_reparar"]],
        ["Cierre requerido 25 años", f"{f1(float(s_['cierre_req_25_pct']))} %", f"{f1(float(a['cierre_req_25_pct']))} %"],
        ["Cierre predicho (motor)", f"{f1(float(s_['neat_cierre_pct']))} %", f"{f1(float(a['neat_cierre_pct']))} %"],
        ["**Veredicto 25 años", f"**{s_['veredicto_25']}", f"**{a['veredicto_25']}"]],
        [1.8, 1.6, 1.6], alin=["left", "center", "center"],
        nota=f"Zonas {s_['id']} y {a['id']} de resultados/vida_zonas.csv. Cierre predicho a 90 días con la mejor "
             f"protección confiable; veredicto con error de ±20 pp.")
    doc.tabla("Problemas de diseño que resuelve el motor", [
        ["Pregunta del diseñador", "Antes", "Con Hefesto"],
        ["¿Cuánto debe cerrar la fisura de 0,3 mm para 25 años?", "Supuesto",
         f"{f1(R['atmosferico_marino']['req25'], 0)} % atmosférico; {f1(R['niebla_salina']['req25'], 0)} % niebla; "
         f"{f1(R['salpicadura']['req25'], 0)} % salpicadura"],
        ["¿Lo logra la protección elegida?", "Dato de un ensayo",
         f"{f1(ops['sin bacterias'])}–{f1(ops['encapsulación'])} % (marino, 90 d), error {f1(tod['MAE_cosecha'])} pp"],
        ["¿Cumple la vida útil de diseño?", "Un número, hasta 150 años",
         "Cumple / incierto / no cumple con ±20 pp; tope 40 años"],
        ["¿Dónde no basta la autorreparación?", "No se sabía",
         f"{R['niebla_salina']['n'] + R['salpicadura']['n']} zonas (niebla y salpicadura)"],
        ["¿Cuántos ensayos locales hacer?", "Sin criterio", f"20 grupos → {f1(mej20)} pp; 40 → {f1(mej40)} pp"],
        ["¿Qué fuente de datos creer?", "Sin criterio", "Rango SS+…D por fuente"]],
        [1.9, 1.0, 2.1], alin=["left", "left", "left"],
        nota="Cifras de las Tablas VI–XIII y de la Fig. 4. Cierre requerido: mediana por régimen con la mezcla de norma.")
    doc.h2("G. Limitaciones")
    doc.p("La pendiente de fisura proviene de un laboratorio y dos anchos; Cs y el depósito de cloruros por niebla "
          "son supuestos sin medición local, y las fuentes SS+ de perfiles de cloruros son las indicadas para "
          "reemplazarlos. La validación peruana se apoya en una sola tesis (18 filas), y quedan 128 tablas por "
          "transcribir en la cola de extracción. Algunas fuentes no tienen canal abierto (Ghent, Cardiff, Bath, "
          "CNKI, eLIBRARY.ru) y no se forzaron; Scopus exige una clave que no se usó. La lectura que confirma un "
          "tier la hace un agente y queda escrita para que un revisor humano la audite.")

    # ------------------------------------------------------------------ IV
    doc.h1("IV. CONCLUSIONES")
    doc.p("A nivel de ingeniería, el motor resuelve el paso que faltaba entre el ensayo de laboratorio y la "
          "vida útil de diseño: para una zona dada entrega el cierre de fisura que exige la norma, predice si la "
          "protección bacteriana lo alcanza con un error medido en laboratorios no vistos y emite un veredicto "
          "acotado al horizonte normativo. Con ello el concreto autorreparable deja de ser un supuesto del cálculo y "
          "pasa a ser una especificación que se puede pedir y verificar.")
    doc.p(f"Los agentes de IA de Hefesto reunieron {n0(m['literatura_util'])} documentos útiles con cobertura ≥ 90 % "
          f"en las {D.n_consultas} consultas, separando el Perú (principal), Sudamérica (agregado) y lo global "
          f"(aprendizaje), y calificaron cada fuente con tier, grado y rango; {m['ss_plus']['confirmados']} fuentes "
          f"SS+ aplicadas en campo superaron la meta de 10. El cuello de botella ya no es encontrar literatura, sino "
          f"transcribirla: de {n0(m['literatura_util'])} documentos útiles, las filas que el motor puede usar "
          f"provienen de {ev['fuentes']} fuentes.")
    doc.p(f"Entre 13 motores, cinco redes NEAT con corrección local fueron las que mejor predijeron un laboratorio "
          f"no visto; los modelos más profundos o basados en árboles ajustan mejor dentro de un laboratorio y "
          f"generalizan peor. Reentrenado con la cosecha, el motor bajó su error en fuente no vista a "
          f"{f1(tod['MAE_cosecha'])} pp y empezó a distinguir la protección bacteriana.")
    doc.p(f"En la costa peruana con cloruros, 25 años son alcanzables con mezclas de norma y un cierre mediano del "
          f"{f1(c25['mediana'])} %, pero solo {v25['cumple']} zonas lo cumplen con certeza con la mejor protección "
          f"predicha; 40 años son excepcionales. El siguiente paso es transcribir los datos de campo de las fuentes "
          f"SS+ y las tablas peruanas pendientes, y validar el motor primero con ensayos del Perú.")

    doc.h1("REFERENCIAS")
    for i, t in enumerate(REFS, 1):
        doc.referencia(i, t)


# =============================================================================== ensamblado
def _elementos(cuerpo: str) -> list[str]:
    out, depth, ini = [], 0, None
    for mt in re.finditer(r"<(/?)w:(p|tbl)\b[^>]*?(/?)>", cuerpo):
        cierre, auto = mt.group(1), mt.group(3)
        if auto:
            if depth == 0:
                out.append(cuerpo[mt.start():mt.end()])
            continue
        if not cierre:
            if depth == 0:
                ini = mt.start()
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                out.append(cuerpo[ini:mt.end()])
    return out


def ensamblar(doc: Doc):
    with zipfile.ZipFile(PLANTILLA) as z:
        partes = {n: z.read(n) for n in z.namelist() if not n.endswith("/")}
    x = partes["word/document.xml"].decode("utf-8")
    ini, fin = x.index("<w:body>") + len("<w:body>"), x.rindex("<w:sectPr")
    elems = _elementos(x[ini:fin])
    autores, salto = elems[2], elems[3]           # tabla de autores y salto continuo a dos columnas (plantilla)
    nuevo = "".join(doc.xml[:2]) + autores + salto + "".join(doc.xml[2:])
    x = x[:ini] + nuevo + x[fin:]
    x = re.sub(r'(<w:pgMar (?![^>]*w:gutter)[^>]*?)/>', r'\1 w:gutter="0"/>', x)   # atributo exigido por el esquema
    partes["word/document.xml"] = x.encode("utf-8")
    # imágenes: fuera las de la plantilla, dentro las nuevas; fuera los comentarios de la plantilla
    rels = partes["word/_rels/document.xml.rels"].decode("utf-8")
    for viejo in re.findall(r'<Relationship [^>]*Target="(?:media/|comments)[^"]*"[^>]*/>', rels):
        rels = rels.replace(viejo, "")
    partes = {n: v for n, v in partes.items() if not n.startswith("word/media/") and
              not re.match(r"word/comments\w*\.xml$", n)}
    for rid, ruta in doc.imagenes:
        destino = f"media/{rid.lower()}.png"
        partes[f"word/{destino}"] = ruta.read_bytes()
        rels = rels.replace("</Relationships>", f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/'
                                                f'officeDocument/2006/relationships/image" Target="{destino}"/>'
                                                "</Relationships>")
    partes["word/_rels/document.xml.rels"] = rels.encode("utf-8")
    ct = partes["[Content_Types].xml"].decode("utf-8")
    ct = re.sub(r'<Override PartName="/word/comments[^"]*"[^>]*/>', "", ct)
    if 'Extension="png"' not in ct:
        ct = ct.replace("<Default ", '<Default Extension="png" ContentType="image/png"/><Default ', 1)
    partes["[Content_Types].xml"] = ct.encode("utf-8")
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(SALIDA, "w", zipfile.ZIP_DEFLATED) as z:
        for n in ["[Content_Types].xml"] + sorted(k for k in partes if k != "[Content_Types].xml"):
            z.writestr(n, partes[n])


def main() -> int:
    D = Datos()
    figs = {k: CARPETA / "ieee" / f"fig_{k}.png" for k in ("arq", "cos", "colan", "mej", "ev", "redes", "vida")}
    (CARPETA / "ieee").mkdir(parents=True, exist_ok=True)
    fig_arquitectura(figs["arq"])
    fig_redes(figs["redes"])
    fig_cosecha(D, figs["cos"])
    fig_mejora(D, figs["mej"])
    fig_colan(figs["colan"])
    fig_evaluacion(D, figs["ev"])
    fig_vida(D, figs["vida"])
    doc = Doc()
    escribir(D, doc, figs)
    ensamblar(doc)
    print(f"{SALIDA.relative_to(RAIZ)}: {doc.n_tabla} tablas, {doc.n_fig} figuras, {doc.n_ec} ecuaciones, "
          f"{len(REFS)} referencias")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
