"""
Confiabilidad de cada fuente: tres etiquetas independientes.

1. TIER (0–4) · qué tan completa y útil es la información para Hefesto
   T0  completa + tangible, trazable, cualitativa y cuantitativa, con respaldo científico u
       organizacional (norma, laboratorio, dataset público con DOI).
   T1  completa en todo lo que Hefesto necesita (mezcla, fisura, edad y resultado medido).
   T2  parcial pero útil (ensayos o mediciones propias sobre el tema).
   T3  toca el tema pero no se centra en él (revisión, mención lateral, solo en el texto completo).
   T4  periférica: puede desviar la causa.
   Con solo los metadatos el tier es PROVISIONAL y nunca pasa de T2. T1 y T0 se confirman al
   transcribir las tablas del documento completo (`tier_confirmado`), nunca por el resumen.

2. GRADO (nomenclatura interna) · tipo de documento, independiente del tier
   ORG    norma u organización (ISO, ASTM, ACI, fib, RILEM, ministerio, laboratorio)
   DATA   dataset público con DOI
   DOC    tesis doctoral (doctor, PhD, Doctor of Philosophy)
   ART-I  artículo revisado por pares en revista identificada
   MAG    tesis de maestría o magíster
   CONF   ponencia de congreso
   INF    informe técnico · LIB capítulo o libro
   LIC    tesis de título profesional o licenciatura
   BAC    bachiller o trabajo de investigación de pregrado
   ART-G  artículo sin revista identificable o genérico
   REV    revisión de literatura (útil para orientar, no aporta datos propios)
   ?      no declarado

3. RANGO (SS+ … D) · confiabilidad combinada
   SS+  T0 y además aplicada en prototipo, piloto o estructura real en servicio: la fuente perfecta.
   SS   T0, o T1 de grado alto (ORG, DATA, DOC, ART-I).
   S    T1 de otros grados, o T2 de grado alto.
   A    T2 de maestría, congreso, informe o libro.
   B    T2 de licenciatura, bachiller o artículo genérico.
   C    T3, o una revisión sin datos propios.
   D    T4, o un trabajo genérico basado en supuestos y sin ensayos propios (p. ej. para aprobar un curso).
"""

from __future__ import annotations

import re

ALTO = {"ORG", "DATA", "DOC", "ART-I"}
MEDIO = {"MAG", "CONF", "INF", "LIB"}
BAJO = {"LIC", "BAC", "ART-G"}
RANGOS = ["SS+", "SS", "S", "A", "B", "C", "D"]


def grado(tipo_doc: str, titulo: str = "", revista: str = "") -> str:
    """El grado sale SOLO del tipo que declara la fuente: un título como "según la norma ISO" o
    "plan maestro" no convierte una tesis en norma ni en maestría. Del título solo se toma si es revisión."""
    t = (tipo_doc or "").lower()
    if re.search(r"\b(standard|norma|reglamento|guideline)\b", t):
        return "ORG"
    if re.search(r"revisi[oó]n (te[oó]rica|literaria|sistem|documental|bibliogr)|\breview\b|state of the art|"
                 r"estado del arte", (titulo or "").lower()):
        return "REV"
    if re.search(r"dataset|conjunto de datos", t):
        return "DATA"
    if re.search(r"doctoral|doctor|phd|ph\.d", t):
        return "DOC"
    if re.search(r"master|maestr|mag[ií]ster", t):
        return "MAG"
    if re.search(r"review|revisi[oó]n (te[oó]rica|literaria|sistem|documental|bibliogr)", t):
        return "REV"
    if re.search(r"conference|congres|proceedings|ponencia|conferencia", t):
        return "CONF"
    if re.search(r"report|informe", t):
        return "INF"
    if re.search(r"book|libro|cap[ií]tulo", t):
        return "LIB"
    if re.search(r"trabajo de investigaci[oó]n|bachiller", t):
        return "BAC"
    if re.search(r"bachelorthesis|tesis|t[ií]tulo profesional|licenciatur|undergraduate", t):
        return "LIC"
    if re.search(r"article|art[ií]culo", t):
        return "ART-I" if revista else "ART-G"
    return "?"


def aplicado_en_campo(texto: str) -> bool:
    return bool(re.search(r"prototipo|piloto|en servicio|estructura real|aplicad[oa] en (obra|campo)|"
                          r"field (trial|application)|in[- ]situ|full[- ]scale|real structure|pilot", texto.lower()))


def respaldo_org(texto: str) -> bool:
    return bool(re.search(r"\b(astm|iso|aci|rilem|fib|ntp|nt build|en 206|en 12390)\b|laboratorio acreditado|"
                          r"inacal|sencico|doi\.org|zenodo|dryad", texto.lower()))


def tier_provisional(familia: str, con_datos: str, titulo: str, resumen: str) -> int:
    """Solo con metadatos: como máximo T2."""
    if familia in ("", "otro"):
        return 4
    tema = (r"autorrepar|autoreparab|autocicatriz|autocurativ|bacteri|bioconcret|self-?heal|clorur|chlorid|corros|"
            r"fisur|grieta|crack|patolog|durabil|carbonat")
    if con_datos == "no" or not re.search(tema, titulo.lower()):
        return 3
    return 2 if con_datos == "probable" else 3


def rango(tier: int, grado_: str, aplicado: bool, con_datos: str) -> str:
    if tier >= 4:
        return "D"
    if con_datos == "no" and grado_ in BAJO | {"?"}:
        return "D"
    if tier == 3 or grado_ == "REV":
        return "C"
    if tier == 0:
        return "SS+" if aplicado else "SS"
    if tier == 1:
        return "SS" if grado_ in ALTO else "S"
    if grado_ in ALTO:
        return "S"
    if grado_ in MEDIO:
        return "A"
    return "B"


def calificar(tipo_doc: str, familia: str, con_datos: str, titulo: str, resumen: str, revista: str = "",
              tier_confirmado: str = "") -> dict:
    g = grado(tipo_doc, titulo, revista=revista)
    texto = f"{titulo} {resumen}"
    confirmado = str(tier_confirmado).isdigit()
    t = int(tier_confirmado) if confirmado else tier_provisional(familia, con_datos, titulo, resumen)
    ap = aplicado_en_campo(texto)
    motivo = [f"tier {'confirmado' if confirmado else 'provisional'} T{t}", f"grado {g}"]
    if ap:
        motivo.append("aplicado en campo o prototipo")
    if respaldo_org(texto):
        motivo.append("cita normas u organizaciones")
    return {"grado": g, "tier": t, "rango": rango(t, g, ap, con_datos), "aplicado_campo": "si" if ap else "no",
            "motivo_calidad": "; ".join(motivo)}
