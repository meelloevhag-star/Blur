"""
Agente REPOSITORIOS · literatura para Hefesto, de la búsqueda a la cola de extracción.

Ámbitos (campo `ambito`), para no sesgar el objetivo: Hefesto diseña para el Perú.
  peru         fuente PRINCIPAL: prioridad al descargar, extraer, entrenar y validar.
  sudamerica   agregado: condiciones y materiales parecidos.
  global       literatura aplicada: aprender, mejorar y comparar; nunca decide sola.

Fuentes
  Perú directas   DSpace 7 (API): PUCP, UNI, UPC, USAT · DSpace 6 (buscador): UCV, UNPRG, UNS, ULADECH.
                  Se recorren TODAS las páginas de cada consulta: la cobertura debe ser ≥ 90 % de lo que
                  el repositorio reporta (datos/literatura/cobertura_cosecha.csv).
  Perú agregado   ALICIA (CONCYTEC, ~167 instituciones; llega a las que no tienen acceso directo).
  Sudamérica      LA Referencia (tesis y artículos de la región) y BDTD (tesis de Brasil).
  Global          OpenAlex (artículos; el país sale de la institución de los autores).

Metas de literatura útil (familia ≠ otro): mínimo 1 000 · óptimo 3 000 · ideal 5 000
(datos/literatura/metas_cosecha.json, en total y por ámbito).

Etapas:
  cosechar      metadatos + clasificación (familia, bacterias, tema_cloruros, zona, con_datos)
                y calidad (hefesto/agentes/calidad.py): grado del documento, tier 0–4 y rango SS+…D
  descargar     PDF de acceso abierto (primero Perú, costa norte, autorreparables y cloruros)
  preparar      tablas con datos en cada PDF → datos/literatura/cola_extraccion.csv
  reclasificar  vuelve a clasificar el catálogo con las reglas actuales
El agente de IA lee cada tabla de la cola y la transcribe al esquema (datos/entrantes/); el curador valida.

Uso:
    python -m hefesto.agentes.repositorios cosechar [--fuentes peru,sudamerica,global] [--max-por-consulta N]
    python -m hefesto.agentes.repositorios descargar [--limite 60]
    python -m hefesto.agentes.repositorios preparar
    python -m hefesto.agentes.repositorios confirmar <handle> <tier 0-4>   (tras transcribir el documento)
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

try:
    from hefesto.agentes.calidad import RANGOS, calificar
except ImportError:  # ejecutado como script suelto
    from calidad import RANGOS, calificar  # type: ignore

RAIZ = Path(__file__).resolve().parents[2]
LIT = RAIZ / "datos" / "literatura"
CATALOGO = LIT / "catalogo_repositorios.csv"
COBERTURA = LIT / "cobertura_cosecha.csv"
METAS = LIT / "metas_cosecha.json"
COLA = LIT / "cola_extraccion.csv"
RAW = LIT / "raw" / "repositorios"
AGENTE = {"User-Agent": "Hefesto-cosecha-academica/1.0 (investigación sin fines de lucro)"}
META = {"minimo": 1000, "optimo": 3000, "ideal": 5000}
COBERTURA_MINIMA = 0.90
csv.field_size_limit(10**7)

# Consultas con sintaxis Solr (exigen ambas palabras). Los repositorios buscan también en el texto
# completo de los PDF, así que traen mucho; la clasificación separa después lo útil.
CONSULTAS_ES = [
    "concreto AND autorreparable", "concreto AND autoreparable", "concreto AND autocicatrizante",
    "concreto AND autocicatrización", "concreto AND autosellante", "concreto AND autocurativo",
    "concreto AND bacterias", "concreto AND Bacillus", "bioconcreto",
    "concreto AND cloruros", 'concreto AND "ion cloruro"', 'concreto AND "agua de mar"',
    "concreto AND corrosión", "concreto AND patologías", "concreto AND carbonatación", "concreto AND fisuras",
]
CONSULTAS_ALICIA = [
    "concreto autorreparable", "concreto autocicatrizante", "autocicatrizante", "concreto autocurativo",
    "bacterias concreto", "Bacillus concreto", "bioconcreto", "corrosión concreto armado", "patologías concreto",
    "fisuras concreto", "deterioro concreto", "cloruros concreto", "ion cloruro concreto", "penetración de cloruros",
    "agua de mar concreto", "carbonatación concreto", "concreto ambiente marino", "concreto durabilidad",
]
CONSULTAS_PT = ["concreto autocicatrizante", "autocicatrização concreto", "bactérias concreto", "cloretos concreto",
                "corrosão concreto armado", "durabilidade concreto ambiente marinho"]
CONSULTAS_EN = ["bacterial self-healing concrete", "self-healing concrete crack closure", "microbially induced calcite "
                "precipitation concrete", "chloride ingress cracked concrete", "chloride diffusion concrete marine",
                "concrete corrosion marine environment chloride", "autogenous healing concrete"]
SUDAMERICA = {"AR", "BO", "BR", "CL", "CO", "EC", "GY", "PY", "PE", "SR", "UY", "VE", "GF"}

ESPECIES = {
    "Bacillus subtilis": r"b(?:acillus|\.)\s*subtilis", "Bacillus sphaericus": r"bacillus\s+sphaericus",
    "Lysinibacillus sphaericus": r"lysinibacillus", "Bacillus pseudofirmus": r"pseudofirmus",
    "Sporosarcina pasteurii": r"pasteurii", "Bacillus megaterium": r"megaterium", "Bacillus cohnii": r"cohnii",
    "Paenibacillus polymyxa": r"pa?enybacillus|paenibacillus", "Bacillus licheniformis": r"licheniformis",
    "Bacillus cereus": r"bacillus\s+cereus", "Bacillus (sin especie)": r"\bbacillus\b",
}
ZONAS = ["Piura", "Paita", "Colán", "Colan", "Talara", "Sullana", "Sechura", "Máncora", "Tumbes", "Zarumilla",
         "Chiclayo", "Lambayeque", "Trujillo", "Chimbote", "Huanchaco", "Lima", "Callao", "Chorrillos", "Ica",
         "Pisco", "Arequipa", "Moquegua", "Ilo", "Tacna", "Huaraz", "Juliaca", "Puno", "Cusco", "Tarapoto",
         "Cajamarca", "Huancayo", "Ayacucho", "Iquitos", "Pucallpa"]
CLAVES_TABLA = (r"cierre|fisur|grieta|corrosi|clorur|carbonat|resistencia a (la )?compresi|f.?c|permeab|absorci|"
                r"autorrepar|autocicatriz|sellado|ancho|crack|chloride|healing|compressive")
COSTA_NORTE = r"Piura|Paita|Colán|Talara|Tumbes|Sechura|Sullana|Máncora|Chiclayo|Lambayeque|Trujillo|Chimbote"


def clave(url: str, handle: str = "") -> str:
    m = re.search(r"(\d+(?:\.\d+)+/\d+)", url or "") or re.search(r"(\d+(?:\.\d+)+/\d+)", handle or "")
    if m:
        return "hdl:" + m.group(1)
    m = re.search(r"10\.\d{4,9}/\S+", url or "")
    return ("doi:" + m.group(0).lower()) if m else (url or handle)


@dataclass
class Tesis:
    institucion: str
    handle: str
    url: str
    titulo: str
    autores: str = ""
    anio: str = ""
    acceso: str = ""
    resumen: str = ""
    ambito: str = "peru"
    pais: str = "PE"
    fuente: str = ""
    doi: str = ""
    familia: str = ""
    usa_bacterias: str = ""
    bacterias: str = ""
    tema_cloruros: str = ""
    zona: str = ""
    con_datos: str = ""
    tipo_doc: str = ""          # tal como lo declara la fuente (dc.type, formats, type de OpenAlex)
    revista: str = ""
    citas: str = ""
    grado: str = ""             # nomenclatura interna: ORG, DATA, DOC, ART-I, MAG, CONF, INF, LIB, LIC, BAC, ART-G, REV, ?
    tier: str = ""              # 0–4 (provisional ≤ 2 hasta leer las tablas del documento)
    tier_confirmado: str = ""   # lo fija el agente al transcribir el documento completo
    rango: str = ""             # SS+ … D
    aplicado_campo: str = ""
    motivo_calidad: str = ""
    terminos: set = field(default_factory=set)

    def clasificar(self) -> "Tesis":
        t = f"{self.titulo} {self.resumen}".lower()
        esp = [e for e, rx in ESPECIES.items() if re.search(rx, t)]
        if len(esp) > 1 and "Bacillus (sin especie)" in esp:
            esp.remove("Bacillus (sin especie)")
        self.bacterias = "; ".join(esp)
        self.usa_bacterias = "si" if esp or re.search(r"bacteri|bactéri|micro.?organ|biomineral|micp", t) else "no"
        self.tema_cloruros = "si" if re.search(r"clorur|cloret|chlorid|ion cloruro|agua de mar|água do mar|seawater|"
                                                r"ambiente marino|marine|salinidad|brisa marina", t) else "no"
        de_concreto = re.search(r"concret|mortero|argamassa|mortar|hormig[oó]n|cemen|pavimento r[ií]gido", t)
        autorrep = re.search(r"autorrepar|autoreparab|autocicatriz|autocurativ|auto-?sanaci|autosellan|bioconcret|"
                             r"self-?heal|autogenous heal|cicatriza|bacteri|micp|calcite precipitation", t)
        efecto_cl = self.tema_cloruros == "si" and re.search(r"penetra|difusi|diffus|ingress|ataque|attack|efecto|effect|"
                                                             r"influencia|influence|corros|migra", t)
        if not de_concreto:
            self.familia = "otro"
        elif autorrep:
            self.familia = "autorreparable"
        elif efecto_cl:
            self.familia = "cloruros"
        elif re.search(r"corrosi|corros|patolog|deterioro|lesiones|inspecci|fisura|grieta|crack|damage", t):
            self.familia = "inspeccion_dano"
        elif re.search(r"carbonat|durabilid|durabil|permeab|micros[ií]lice|silica fume|puzolan|ceniza|fly ash", t):
            self.familia = "durable_convencional"
        else:
            self.familia = "otro"
        self.zona = "; ".join(sorted({z.replace("Colan", "Colán") for z in ZONAS if re.search(rf"\b{z.lower()}\b", t)}))
        rx_rev = r"revisi[oó]n (te[oó]rica|literaria|sistem[aá]tica|documental|bibliogr)|\breview\b|estado del arte"
        medida = re.search(r"ensay|resultad|se obtuv|kg/cm|mpa|%|d[ií]as|days|probetas|specimens|muestras|inspecci|"
                           r"evalu|measured|tested", t)
        # revisión: lo dice el título, o el resumen lo dice y no reporta mediciones propias
        revision = re.search(rx_rev, self.titulo.lower()) or (re.search(rx_rev, t) and not medida)
        self.con_datos = "no" if revision else "probable" if medida else "incierto"
        c = calificar(self.tipo_doc, self.familia, self.con_datos, self.titulo, self.resumen, self.revista,
                      self.tier_confirmado)
        self.grado, self.tier, self.rango = c["grado"], str(c["tier"]), c["rango"]
        self.aplicado_campo, self.motivo_calidad = c["aplicado_campo"], c["motivo_calidad"]
        return self

    def fila(self) -> dict:
        d = asdict(self)
        d["terminos"] = "; ".join(sorted(self.terminos))[:400]
        d["resumen"] = self.resumen[:800]
        return d


# ============================================================================ fuentes
class Fuente(ABC):
    nombre = ""
    ambito = "peru"

    def __init__(self):
        self.cobertura: list[dict] = []

    @staticmethod
    def get(url: str, intentos: int = 3, binario: bool = False):
        for k in range(intentos):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=AGENTE), timeout=90) as r:
                    datos = r.read()
                    return datos if binario else datos.decode("utf-8", "ignore")
            except Exception:  # noqa: BLE001 — red inestable: reintenta con espera creciente
                time.sleep(3 * (k + 1))
        return b"" if binario else ""

    def registrar(self, consulta: str, reportado: int | None, cosechado: int, nota: str = ""):
        pct = (cosechado / reportado) if reportado else None
        estado = ("sin resultados" if reportado == 0 else "ok" if pct is None or pct >= COBERTURA_MINIMA
                  else f"incompleta ({nota or 'faltan páginas o metadatos'})")
        self.cobertura.append({"fuente": self.nombre, "ambito": self.ambito, "consulta": consulta,
                               "reportado": reportado if reportado is not None else "", "cosechado": cosechado,
                               "pct": "" if pct is None else round(100 * pct, 1), "estado": estado})

    @abstractmethod
    def cosechar(self, maximo: int | None) -> list[Tesis]: ...


class DSpace7(Fuente):
    """API REST de DSpace 7: los metadatos vienen en la misma respuesta de la búsqueda."""

    def __init__(self, sigla: str, host: str):
        super().__init__()
        self.nombre, self.host = sigla, host

    def cosechar(self, maximo):
        out = {}
        for q in CONSULTAS_ES:
            total, pagina, obtenidos = None, 0, set()
            while True:
                url = (f"https://{self.host}/server/api/discover/search/objects?query={urllib.parse.quote(q)}"
                       f"&dsoType=ITEM&size=100&page={pagina}")
                try:
                    r = json.loads(self.get(url) or "{}")["_embedded"]["searchResult"]
                except (KeyError, json.JSONDecodeError):
                    break
                total = r["page"]["totalElements"]
                objs = r.get("_embedded", {}).get("objects", [])
                for o in objs:
                    it = o["_embedded"]["indexableObject"]
                    md = it.get("metadata", {})
                    v = lambda k: [x["value"] for x in md.get(k, [])]
                    h = it.get("handle") or ""
                    t = Tesis(institucion=self.nombre, handle=h, url=f"https://hdl.handle.net/{h}",
                              titulo=" ".join((v("dc.title") or [""])[0].split()),
                              autores="; ".join(v("dc.contributor.author")),
                              anio=next((d[:4] for d in v("dc.date.issued") if d[:4].isdigit()), ""),
                              acceso="abierto" if any("openAccess" in x for x in v("dc.rights")) else "restringido",
                              resumen=" ".join(" ".join(v("dc.description.abstract")).split()), fuente=self.nombre,
                              tipo_doc="; ".join(v("dc.type") + v("dc.type.other") + v("thesis.degree.level")
                                                 + v("thesis.degree.name"))[:200],
                              revista=(v("dc.relation.ispartof") or v("dc.source") or [""])[0][:150],
                              terminos={q})
                    k = clave(t.url, h)
                    obtenidos.add(k)
                    out.setdefault(k, t).terminos.add(q)
                pagina += 1
                if not objs or pagina * 100 >= total or (maximo and len(obtenidos) >= maximo):
                    break
                time.sleep(0.4)
            self.registrar(q, total, len(obtenidos))
            print(f"  {self.nombre} {q!r}: {len(obtenidos)}/{total}", flush=True)
        return list(out.values())


class DSpace6(Fuente):
    """Buscador de DSpace 6 (XMLUI): lista de handles por página + metadatos de la página de cada tesis."""

    def __init__(self, sigla: str, host: str):
        super().__init__()
        self.nombre, self.host = sigla, host

    def _handles(self, q):
        handles, total, pagina = [], None, 1
        while True:
            t = self.get(f"https://{self.host}/discover?query={urllib.parse.quote_plus(q)}&rpp=100&page={pagina}")
            if total is None:
                m = re.search(r"(?:Mostrando|Now showing)[^<]*?(?:de|of)\s*([\d.,]+)", html.unescape(t))
                total = int(re.sub(r"[.,]", "", m.group(1))) if m else 0
            nuevos = [h for h in re.findall(r'href="/handle/(\d+(?:\.\d+)*/\d+)"', t) if h not in handles]
            if not nuevos:
                break
            handles += nuevos
            pagina += 1
            if len(handles) >= total:
                break
            time.sleep(0.4)
        return handles, total

    def _ficha(self, h) -> Tesis | None:
        t = self.get(f"https://{self.host}/handle/{h}")
        meta = lambda n: [html.unescape(x).strip() for x in
                          re.findall(rf'<meta[^>]+name="{n}"[^>]+content="([^"]*)"', t)]
        titulo = (meta("DC.title") or meta("citation_title") or [""])[0]
        if not titulo:
            return None
        anio = next((d[:4] for d in meta("DCTERMS.issued") + meta("DC.date") + meta("citation_date") if d[:4].isdigit()), "")
        derechos = " ".join(meta("DC.rights") + meta("DCTERMS.accessRights"))
        return Tesis(institucion=self.nombre, handle=h, url=f"https://hdl.handle.net/{h}", titulo=" ".join(titulo.split()),
                     autores="; ".join(meta("DC.creator") or meta("citation_author")), anio=anio,
                     acceso="abierto" if "openAccess" in derechos or meta("citation_pdf_url") else "restringido",
                     resumen=" ".join(" ".join(meta("DCTERMS.abstract") or meta("DC.description")).split()),
                     tipo_doc="; ".join(meta("DC.type") + meta("citation_dissertation_name"))[:200],
                     revista=(meta("citation_journal_title") or [""])[0][:150], fuente=self.nombre)

    def cosechar(self, maximo):
        por_consulta, todos = {}, {}
        for q in CONSULTAS_ES:
            hs, total = self._handles(q)
            hs = hs[:maximo] if maximo else hs
            por_consulta[q] = (hs, total)
            for h in hs:
                todos.setdefault(h, set()).add(q)
            print(f"  {self.nombre} {q!r}: {len(hs)} handles de {total}", flush=True)
        fichas = {}
        with ThreadPoolExecutor(max_workers=6) as pool:
            for h, f in zip(todos, pool.map(self._ficha, list(todos))):
                if f:
                    f.terminos = todos[h]
                    fichas[h] = f
        for q, (hs, total) in por_consulta.items():
            self.registrar(q, total, sum(1 for h in hs if h in fichas))
        return list(fichas.values())


class VuFind(Fuente):
    """Agregadores con API VuFind: ALICIA (Perú), LA Referencia (Latinoamérica), BDTD (Brasil)."""

    def __init__(self, nombre, api, ambito, consultas, pais_por_defecto=""):
        super().__init__()
        self.nombre, self.api, self.ambito, self.consultas, self.pais = nombre, api, ambito, consultas, pais_por_defecto

    def cosechar(self, maximo):
        out = {}
        campos = "".join(f"&field[]={c}" for c in ("id", "title", "authors", "institutions", "urls",
                                                       "publicationDates", "summary", "formats", "containerTitle"))
        for q in self.consultas:
            total, pagina, n = None, 1, 0
            while True:
                t = self.get(f"{self.api}?lookfor={urllib.parse.quote_plus(q)}&type=AllFields&limit=100&page={pagina}{campos}")
                try:
                    d = json.loads(t) if t else {}
                except json.JSONDecodeError:
                    d = {}
                total = d.get("resultCount", total or 0)
                recs = d.get("records", [])
                for r in recs:
                    urls = [u.get("url", "") for u in r.get("urls", [])]
                    url = next((u for u in urls if "handle" in u), urls[0] if urls else "")
                    autores = list((r.get("authors", {}).get("primary") or {}).keys()) + \
                        list((r.get("authors", {}).get("secondary") or {}).keys())
                    inst = ", ".join(r.get("institutions", []))
                    t_ = Tesis(institucion=inst, handle=r.get("id", ""), url=url, titulo=" ".join(r.get("title", "").split()),
                               autores="; ".join(autores), anio=(r.get("publicationDates") or [""])[0][:4],
                               resumen=" ".join(" ".join(r.get("summary", [])).split()), fuente=self.nombre,
                               ambito=self.ambito, pais=self.pais, terminos={q},
                               tipo_doc="; ".join(r.get("formats") or [])[:200],
                               revista=str(r.get("containerTitle") or "")[:150])
                    if self.nombre == "LA Referencia" and re.search(r"\.pe\b|Per[uú]", url + " " + inst):
                        t_.ambito, t_.pais = "peru", "PE"
                    k = clave(url, t_.handle)
                    out.setdefault(k, t_).terminos.add(q)
                    n += 1
                pagina += 1
                if not recs or (pagina - 1) * 100 >= total or (maximo and n >= maximo):
                    break
                time.sleep(0.4)
            self.registrar(q, total, min(n, total or n), "límite --max-por-consulta" if maximo else "")
            print(f"  {self.nombre} {q!r}: {n}/{total}", flush=True)
        return list(out.values())


class OpenAlex(Fuente):
    """Artículos científicos. El ámbito sale del país de las instituciones de los autores."""
    nombre = "OpenAlex"
    API = "https://api.openalex.org/works"

    def cosechar(self, maximo):
        out = {}
        for q in CONSULTAS_EN + CONSULTAS_ES[:9]:
            cursor, n, total = "*", 0, None
            while cursor:
                d = json.loads(self.get(f"{self.API}?search={urllib.parse.quote(q)}&per-page=200&cursor={cursor}"
                                        "&select=id,doi,title,publication_year,authorships,abstract_inverted_index,"
                                        "open_access,primary_location,type,cited_by_count") or "{}")
                total = d.get("meta", {}).get("count", total or 0)
                res = d.get("results", [])
                for w in res:
                    paises = {c for a in w.get("authorships", []) for c in a.get("countries", [])}
                    ambito = "peru" if "PE" in paises else "sudamerica" if paises & SUDAMERICA else "global"
                    inv = w.get("abstract_inverted_index") or {}
                    pos = sorted((p, pal) for pal, ps in inv.items() for p in ps)
                    doi = (w.get("doi") or "").replace("https://doi.org/", "")
                    t = Tesis(institucion="; ".join(sorted({i.get("display_name", "") for a in w.get("authorships", [])
                                                          for i in a.get("institutions", [])}))[:200],
                              handle=w.get("id", ""), url=w.get("doi") or w.get("id", ""),
                              titulo=" ".join((w.get("title") or "").split()),
                              autores="; ".join(a.get("author", {}).get("display_name", "") for a in w.get("authorships", [])[:8]),
                              anio=str(w.get("publication_year") or ""), acceso="abierto" if (w.get("open_access") or {}).get("is_oa") else "restringido",
                              resumen=" ".join(p for _, p in pos), ambito=ambito, pais=",".join(sorted(paises))[:40],
                              fuente="OpenAlex", doi=doi, terminos={q}, tipo_doc=w.get("type") or "",
                              revista=(((w.get("primary_location") or {}).get("source") or {}).get("display_name")
                                       or "")[:150],
                              citas=str(w.get("cited_by_count") or ""))
                    k = clave(t.url, t.handle)
                    out.setdefault(k, t).terminos.add(q)
                    n += 1
                cursor = d.get("meta", {}).get("next_cursor") if res else None
                if maximo and n >= maximo:
                    break
                time.sleep(0.2)
            self.registrar(q, total, min(n, total or n), "límite --max-por-consulta" if maximo else "")
            print(f"  OpenAlex {q!r}: {n}/{total}", flush=True)
        return list(out.values())


def fuentes(grupos: set[str]) -> list[Fuente]:
    lista = []
    if "peru" in grupos:
        lista += [DSpace7("PUCP", "repositorio.pucp.edu.pe"), DSpace7("UNI", "repositorio.uni.edu.pe"),
                  DSpace7("UPC", "repositorioacademico.upc.edu.pe"), DSpace7("USAT", "repositorio.usat.edu.pe"),
                  DSpace6("UCV", "repositorio.ucv.edu.pe"), DSpace6("UNPRG", "repositorio.unprg.edu.pe"),
                  DSpace6("UNS", "repositorio.uns.edu.pe"), DSpace6("ULADECH", "repositorio.uladech.edu.pe"),
                  VuFind("ALICIA", "https://alicia.concytec.gob.pe/vufind/api/v1/search", "peru", CONSULTAS_ALICIA, "PE")]
    if "sudamerica" in grupos:
        lista += [VuFind("LA Referencia", "https://www.lareferencia.info/vufind/api/v1/search", "sudamerica",
                         CONSULTAS_ALICIA + CONSULTAS_PT),
                  VuFind("BDTD", "https://bdtd.ibict.br/vufind/api/v1/search", "sudamerica", CONSULTAS_PT, "BR")]
    if "global" in grupos:
        lista += [OpenAlex()]
    return lista


# ============================================================================ catálogo, cobertura y metas
def leer_catalogo() -> dict[str, dict]:
    if not CATALOGO.exists():
        return {}
    out = {}
    with open(CATALOGO, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            r.setdefault("institucion", r.pop("universidad", ""))
            r.pop("universidad", None)
            r.pop("tipo", None)
            for k in Tesis.__dataclass_fields__:
                r.setdefault(k, "")
            r["ambito"] = r["ambito"] or "peru"
            out[clave(r.get("url", ""), r.get("handle", ""))] = r
    return out


def a_tesis(r: dict) -> Tesis:
    return Tesis(**{c: v for c, v in r.items() if c in Tesis.__dataclass_fields__ and c != "terminos"},
                 terminos=set(filter(None, r.get("terminos", "").split("; "))))


def escribir_catalogo(tesis: dict[str, Tesis]):
    orden_f = {"autorreparable": 0, "cloruros": 1, "inspeccion_dano": 2, "durable_convencional": 3, "otro": 4}
    orden_a = {"peru": 0, "sudamerica": 1, "global": 2}
    LIT.mkdir(parents=True, exist_ok=True)
    with open(CATALOGO, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(Tesis.__dataclass_fields__), extrasaction="ignore")
        w.writeheader()
        w.writerows(t.fila() for t in sorted(tesis.values(), key=lambda t: (
            orden_a.get(t.ambito, 9), RANGOS.index(t.rango) if t.rango in RANGOS else 9,
            orden_f.get(t.familia, 9), t.institucion)))
    utiles = [t for t in tesis.values() if t.familia != "otro"]
    por_ambito = {a: sum(t.ambito == a for t in utiles) for a in ("peru", "sudamerica", "global")}
    por_familia = {fa: sum(t.familia == fa for t in utiles) for fa in orden_f if fa != "otro"}
    n = len(utiles)
    nivel = "ideal" if n >= META["ideal"] else "óptimo" if n >= META["optimo"] else "mínimo" if n >= META["minimo"] \
        else "por debajo del mínimo"
    resumen = {"catalogo_total": len(tesis), "literatura_util": n, "metas": META, "nivel_alcanzado": nivel,
               "por_ambito": por_ambito, "por_familia": por_familia,
               "por_rango": {r: sum(t.rango == r for t in tesis.values()) for r in RANGOS},
               "por_tier": {f"T{i}": sum(t.tier == str(i) for t in tesis.values()) for i in range(5)},
               "por_grado": {g: sum(t.grado == g for t in tesis.values())
                             for g in sorted({t.grado for t in tesis.values()})},
               "peru_por_rango": {r: sum(t.ambito == "peru" and t.rango == r for t in tesis.values()) for r in RANGOS},
               "peru_util_con_bacterias": sum(t.ambito == "peru" and t.familia == "autorreparable" and
                                              t.usa_bacterias == "si" for t in utiles),
               "peru_util_cloruros": sum(t.ambito == "peru" and t.tema_cloruros == "si" for t in utiles)}
    METAS.write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False, indent=1))


def escribir_cobertura(filas: list[dict]):
    with open(COBERTURA, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["fuente", "ambito", "consulta", "reportado", "cosechado", "pct", "estado"])
        w.writeheader()
        w.writerows(filas)
    bajas = [r for r in filas if str(r["estado"]).startswith("incompleta")]
    print(f"cobertura: {len(filas)} consultas · {len(bajas)} por debajo del {int(100 * COBERTURA_MINIMA)} %")


def cosechar(grupos: set[str], maximo: int | None):
    catalogo = {k: a_tesis(r) for k, r in leer_catalogo().items()}
    cobertura = []
    for fuente in fuentes(grupos):
        print(f"[{fuente.ambito}] {fuente.nombre}", flush=True)
        for t in fuente.cosechar(maximo):
            k = clave(t.url, t.handle)
            if k in catalogo:                         # ya estaba: suma términos; el directo manda sobre el agregador
                previa = catalogo[k]
                previa.terminos |= t.terminos
                if previa.fuente in ("ALICIA", "LA Referencia", "") and t.fuente not in ("ALICIA", "LA Referencia"):
                    t.terminos, t.tier_confirmado = previa.terminos, previa.tier_confirmado
                    previa = catalogo[k] = t
                else:                                # completa lo que faltaba (tipo, revista, resumen, citas)
                    for c in ("tipo_doc", "revista", "citas", "resumen", "doi", "acceso", "anio", "autores"):
                        if not getattr(previa, c) and getattr(t, c):
                            setattr(previa, c, getattr(t, c))
                previa.clasificar()
            else:
                catalogo[k] = t.clasificar()
        cobertura += fuente.cobertura
        escribir_cobertura(cobertura)
        escribir_catalogo(catalogo)


# ============================================================================ descarga y cola
def enlace_pdf(url: str) -> str | None:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=AGENTE), timeout=90) as r:
            pagina, final = r.read().decode("utf-8", "ignore"), r.geturl()
    except Exception:  # noqa: BLE001
        return None
    origen = re.match(r"https?://[^/]+", final).group(0)
    m = re.search(r'citation_pdf_url"\s+content="([^"]+)"', pagina)
    if m and "isAllowed=n" not in m.group(1):
        return html.unescape(m.group(1))
    cand = [h for h in re.findall(r'href="([^"]*/bitstream/[^"]*\.pdf[^"]*)"', pagina, re.I) if "isAllowed=n" not in h]
    if cand:
        h = html.unescape(cand[0])
        return h if h.startswith("http") else origen + h
    return None


def _nombre_pdf(r: dict) -> str:
    return re.sub(r"[^\w]+", "_", clave(r.get("url", ""), r.get("handle", "")))[:90]


def descargar(limite: int):
    filas = leer_catalogo()
    utiles = [r for r in filas.values() if r["familia"] not in ("otro", "") and r.get("con_datos") != "no"]
    prioridad = lambda r: ({"peru": 0, "sudamerica": 1, "global": 2}.get(r["ambito"], 3),
                           0 if re.search(COSTA_NORTE, r.get("zona", "")) else 1,
                           {"autorreparable": 0, "cloruros": 1}.get(r["familia"], 2), -int(r.get("anio") or 0))
    RAW.mkdir(parents=True, exist_ok=True)
    hechos = 0
    for r in sorted(utiles, key=prioridad):
        if hechos >= limite:
            break
        destino = RAW / (_nombre_pdf(r) + ".pdf")
        if destino.exists() or r.get("acceso") == "restringido":
            continue
        pdf = enlace_pdf(r["url"]) if r.get("url", "").startswith("http") else None
        if not pdf:
            continue
        datos = Fuente.get(pdf, binario=True)
        if datos[:4] == b"%PDF":
            destino.write_bytes(datos)
            hechos += 1
            print(f"  [{r['ambito']}] {destino.name} ({len(datos) // 1024} KB) · {r['titulo'][:70]}", flush=True)
        time.sleep(0.5)
    print(f"{hechos} PDF nuevos en {RAW.relative_to(RAIZ)}")


def preparar():
    filas = {_nombre_pdf(r): r for r in leer_catalogo().values()}
    previa = {}
    if COLA.exists():
        with open(COLA, encoding="utf-8") as f:
            previa = {(r["pdf"], r["tabla"]): r for r in csv.DictReader(f)}
    cola, vistos = [], set()
    for pdf in sorted(RAW.glob("*.pdf")):
        r = filas.get(pdf.stem, {})
        if r.get("familia") in ("otro", None, ""):
            continue
        try:
            texto = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True,
                                   timeout=180).stdout
        except (OSError, subprocess.TimeoutExpired):
            continue
        for n, pag in enumerate(texto.split("\f"), 1):
            for m in re.finditer(r"^\s*(Tabla|Cuadro|Table|Tabela)\s+N?[°º]?\s*(\d+)[:.\-–]?\s*(.{0,140})$", pag, re.M | re.I):
                titulo = m.group(3).strip()
                indice = re.search(r"\.{5,}|-{5,}|_{5,}|\s\d{1,3}\s*$", titulo)
                k = (str(pdf.relative_to(RAIZ)), f"{m.group(1)} {m.group(2)}")
                if re.search(CLAVES_TABLA, titulo.lower()) and not indice and k not in vistos:
                    vistos.add(k)
                    cola.append({"ambito": r.get("ambito", ""), "institucion": r.get("institucion", "")[:60],
                                 "url": r.get("url", ""), "titulo_tesis": r.get("titulo", "")[:150],
                                 "familia": r.get("familia", ""), "pdf": k[0], "tabla": k[1], "pagina": n,
                                 "titulo_tabla": titulo, "estado": previa.get(k, {}).get("estado", "pendiente")})
    orden = {"peru": 0, "sudamerica": 1, "global": 2}
    cola.sort(key=lambda c: (orden.get(c["ambito"], 3), c["estado"] != "pendiente"))
    with open(COLA, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(cola[0]) if cola else ["pdf"])
        w.writeheader()
        w.writerows(cola)
    print(f"{len(cola)} tablas con datos en {len({c['pdf'] for c in cola})} documentos → {COLA.relative_to(RAIZ)}")


def confirmar(handle: str, tier: str):
    """El agente fija el tier al terminar de leer el documento completo (T1/T0 solo así)."""
    filas = leer_catalogo()
    k = clave(handle, handle)
    if k not in filas:
        sys.exit(f"{handle} no está en el catálogo")
    filas[k]["tier_confirmado"] = tier
    escribir_catalogo({c: a_tesis(r).clasificar() for c, r in filas.items()})
    t = a_tesis(filas[k]).clasificar()
    print(f"{t.titulo[:80]} → T{t.tier} · {t.grado} · rango {t.rango}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="etapa", required=True)
    c = sub.add_parser("cosechar")
    c.add_argument("--fuentes", default="peru,sudamerica,global")
    c.add_argument("--max-por-consulta", type=int, default=None, help="sin límite por defecto (cobertura ≥ 90 %)")
    d = sub.add_parser("descargar")
    d.add_argument("--limite", type=int, default=60)
    sub.add_parser("preparar")
    sub.add_parser("reclasificar")
    k = sub.add_parser("confirmar", help="fija el tier tras leer el documento completo")
    k.add_argument("handle", help="handle o DOI, p. ej. 20.500.12692/151797")
    k.add_argument("tier", choices=list("01234"))
    a = ap.parse_args(argv)
    if a.etapa == "cosechar":
        cosechar(set(a.fuentes.split(",")), a.max_por_consulta)
    elif a.etapa == "descargar":
        descargar(a.limite)
    elif a.etapa == "preparar":
        preparar()
    elif a.etapa == "confirmar":
        confirmar(a.handle, a.tier)
    else:
        escribir_catalogo({k: a_tesis(r).clasificar() for k, r in leer_catalogo().items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
