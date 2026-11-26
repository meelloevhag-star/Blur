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
  Perú org.       SENCICO (DSpace 7): informes, manuales y normas → grado ORG.
  Global          OpenAlex: comunidad científica (revistas Scopus/WoS, congresos, revisiones), más tesis de
                  posgrado (type:dissertation) e informes técnicos (type:report); consultas en inglés, español
                  y chino. El país sale de la institución de los autores.
                  OSTI.gov: informes de laboratorios nacionales de EE. UU. (LLNL, ORNL, Sandia…) → ORG.
                  HAL (Francia): tesis doctorales, HDR, informes y artículos.
                  Zenodo: informes de proyectos, entregables, tesis y artículos depositados.
                  CyberLeninka (Rusia): revistas rusas de acceso abierto (VAK/RSCI).
  Sin acceso por canal abierto (no se fuerza): OATD (desafío anti-bots), DART-Europe (cerrado), eLIBRARY.ru,
                  CNKI y Wanfang (de pago); Scopus requiere clave de Elsevier.

Meta de calidad: 10 fuentes SS+ (T0 confirmado y aplicado en prototipo o estructura real). `descargar`
pone primero a los candidatos (aplicado en campo, sobre el tema y con datos propios).

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
                "concrete corrosion marine environment chloride", "autogenous healing concrete",
                # aplicaciones reales: la vía hacia fuentes SS+ (T0 en prototipo o estructura en servicio)
                "self-healing concrete field application", "self-healing concrete full-scale",
                "bacteria-based self-healing concrete in situ", "self-healing concrete pilot structure",
                "self-healing concrete real structure monitoring"]
# China publica sobre todo en inglés (OpenAlex la cubre por país de autores); esto suma revistas chinas.
CONSULTAS_ZH = ["自修复混凝土", "微生物 自愈合 混凝土", "混凝土 氯离子 扩散", "海洋环境 混凝土 腐蚀", "裂缝 混凝土 氯离子"]
# CyberLeninka (Rusia, acceso abierto; revistas de las listas VAK/RSCI)
CONSULTAS_RU = ["самовосстанавливающийся бетон", "самозалечивание бетона", "бактерии бетон", "биобетон",
                "хлориды бетон", "коррозия арматуры хлориды", "морская вода бетон", "трещины бетона"]
META_SS_PLUS = 10
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
    campo_confirmado: str = ""  # si/no: aplicado en campo según el documento completo (manda sobre el resumen)
    grado_confirmado: str = ""  # grado leído en el documento (p. ej. DOC cuando la fuente solo dice "dissertation")
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
        self.tema_cloruros = "si" if re.search(r"хлорид|морск|氯离子|氯盐|海水|海洋|chlorur|clorur|cloret|chlorid|ion cloruro|agua de mar|água do mar|seawater|"
                                                r"ambiente marino|marine|salinidad|brisa marina", t) else "no"
        de_concreto = re.search(r"concret|b[ée]ton|бетон|混凝土|砂浆|mortero|argamassa|mortar|hormig[oó]n|cemen|pavimento r[ií]gido", t)
        autorrep = re.search(r"самовосстан|самозалеч|биобетон|бактери|自修复|自愈合|微生物|"
                             r"autocicatris|auto-cicatris|autorrepar|autoreparab|autocicatriz|autocurativ|auto-?sanaci|autosellan|bioconcret|"
                             r"self-?heal|autogenous heal|cicatriza|bacteri|micp|calcite precipitation", t)
        efecto_cl = self.tema_cloruros == "si" and re.search(r"penetra|difusi|diffus|ingress|ataque|attack|efecto|effect|"
                                                             r"influencia|influence|corros|migra|проникн|диффуз|коррози|"
                                                             r"扩散|渗透|侵蚀|腐蚀", t)
        if not de_concreto:
            self.familia = "otro"
        elif autorrep:
            self.familia = "autorreparable"
        elif efecto_cl:
            self.familia = "cloruros"
        elif re.search(r"коррози|трещин|дефект|обследов|поврежд|裂缝|损伤|corrosi|corros|patolog|deterioro|lesiones|inspecci|fisura|grieta|crack|damage", t):
            self.familia = "inspeccion_dano"
        elif re.search(r"долговечн|карбониз|проницаем|耐久|碳化|carbonat|durabilid|durabil|permeab|micros[ií]lice|silica fume|puzolan|ceniza|fly ash", t):
            self.familia = "durable_convencional"
        else:
            self.familia = "otro"
        self.zona = "; ".join(sorted({z.replace("Colan", "Colán") for z in ZONAS if re.search(rf"\b{z.lower()}\b", t)}))
        rx_rev = r"revisi[oó]n (te[oó]rica|literaria|sistem[aá]tica|documental|bibliogr)|\breview\b|estado del arte"
        medida = re.search(r"ensay|resultad|se obtuv|kg/cm|mpa|%|d[ií]as|days|probetas|specimens|muestras|inspecci|"
                           r"evalu|measured|tested|испытан|результат|сут|试验|结果", t)
        # revisión: lo dice el título, o el resumen lo dice y no reporta mediciones propias
        revision = re.search(rx_rev, self.titulo.lower()) or (re.search(rx_rev, t) and not medida)
        self.con_datos = "no" if revision else "probable" if medida else "incierto"
        c = calificar(self.tipo_doc, self.familia, self.con_datos, self.titulo, self.resumen, self.revista,
                      self.tier_confirmado, self.fuente, self.campo_confirmado, self.grado_confirmado)
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
    """Comunidad científica (revistas indexadas en Scopus/WoS, congresos, revisiones). Con `tipo` se limita a
    tesis de posgrado ("dissertation") o informes técnicos ("report"), buscando en título y resumen.
    El ámbito sale del país de las instituciones de los autores."""
    API = "https://api.openalex.org/works"
    ambito = "global"

    def __init__(self, tipo: str = ""):
        super().__init__()
        self.tipo = tipo
        self.nombre = f"OpenAlex ({tipo})" if tipo else "OpenAlex"

    def cosechar(self, maximo):
        out = {}
        for q in CONSULTAS_EN + CONSULTAS_ES[:9] + CONSULTAS_ZH:
            pagina, n, total = 1, 0, None  # paginación por número: sin clave hasta 10 000 resultados
            # título y resumen (no texto completo): el texto completo trae decenas de miles de trabajos ajenos
            filtro = (f"type:{self.tipo}," if self.tipo else "") + "title_and_abstract.search:"
            busca = f"filter={filtro}{urllib.parse.quote(q.replace(',', ' '))}"
            while pagina:
                d = json.loads(self.get(f"{self.API}?{busca}&per-page=200&page={pagina}"
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
                pagina = pagina + 1 if res and pagina * 200 < min(total, 10000) else None
                if maximo and n >= maximo:
                    break
                time.sleep(0.2)
            self.registrar(q, total, min(n, total or n), "límite --max-por-consulta" if maximo else "")
            print(f"  {self.nombre} {q!r}: {n}/{total}", flush=True)
        return list(out.values())


class CyberLeninka(Fuente):
    """CyberLeninka (Rusia): artículos de acceso abierto en revistas rusas (listas VAK y RSCI = revisadas por pares).
    La API devuelve como máximo 1 000 resultados por consulta; por eso las consultas son específicas."""
    nombre, ambito = "CyberLeninka", "global"
    API = "https://cyberleninka.ru/api/search"

    def cosechar(self, maximo):
        out = {}
        for q in CONSULTAS_RU:
            inicio, n, total = 0, 0, None
            while True:
                cuerpo = json.dumps({"mode": "articles", "q": q, "size": 100, "from": inicio}).encode()
                try:
                    req = urllib.request.Request(self.API, data=cuerpo, headers={**AGENTE, "Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=90) as r:
                        d = json.loads(r.read().decode("utf-8", "ignore") or "{}")
                except Exception:  # noqa: BLE001 — red inestable: corta esta consulta y lo registra
                    break
                total = d.get("found", total or 0)
                arts = d.get("articles", [])
                limpio = lambda x: " ".join(re.sub(r"</?b>", "", x or "").split())
                for a in arts:
                    cat = ", ".join(c.get("acronym", "") for c in a.get("catalogs") or [])
                    t = Tesis(institucion=a.get("journal", ""), handle=a.get("link", ""),
                              url="https://cyberleninka.ru" + a.get("link", ""), titulo=limpio(a.get("name")),
                              autores="; ".join(a.get("authors") or []), anio=str(a.get("year") or ""), acceso="abierto",
                              resumen=limpio(a.get("annotation")), ambito="global", pais="RU", fuente=self.nombre,
                              revista=a.get("journal", "") if cat else "",
                              tipo_doc=f"article; {cat}" if cat else "article", terminos={q})
                    out.setdefault(clave(t.url, t.handle), t).terminos.add(q)
                    n += 1
                inicio += 100
                if not arts or inicio >= min(total, 1000) or (maximo and n >= maximo):
                    break
                time.sleep(1.0)
            self.registrar(q, total, min(n, total or n), "tope de 1 000 de la API" if (total or 0) > 1000 else "")
            print(f"  CyberLeninka {q!r}: {n}/{total}", flush=True)
        return list(out.values())


def _y(q: str) -> str:
    """'chloride ingress cracked concrete' → 'chloride AND ingress AND cracked AND concrete' (Solr/Elasticsearch)."""
    return " AND ".join(f'"{w}"' if "-" in w else w for w in q.split())


class OSTI(Fuente):
    """OSTI.gov (Departamento de Energía de EE. UU.): informes técnicos de laboratorios nacionales
    (LLNL, ORNL, Sandia, NREL…) y artículos que financian. Informe de laboratorio → grado ORG."""
    nombre, ambito = "OSTI", "global"
    API = "https://www.osti.gov/api/v1/records"

    def cosechar(self, maximo):
        out = {}
        for q in CONSULTAS_EN:
            pagina, n, total = 1, 0, None
            while True:
                url = f"{self.API}?q={urllib.parse.quote(_y(q))}&rows=100&page={pagina}"
                recs = None
                for intento in range(5):          # OSTI es lento: reintenta con espera creciente
                    try:
                        with urllib.request.urlopen(urllib.request.Request(url, headers=AGENTE), timeout=180) as r:
                            total = int(r.headers.get("X-Total-Count") or 0) if total is None else total
                            recs = json.loads(r.read().decode("utf-8", "ignore") or "[]")
                        break
                    except Exception:  # noqa: BLE001
                        time.sleep(10 * (intento + 1))
                if recs is None:
                    break
                for w in recs:
                    enlace = next((x["href"] for x in w.get("links", []) if x.get("rel") == "citation"), "")
                    doi = w.get("doi") or ""
                    t = Tesis(institucion="; ".join(w.get("research_orgs") or [])[:200], handle=str(w.get("osti_id", "")),
                              url=f"https://doi.org/{doi}" if doi else enlace, titulo=" ".join((w.get("title") or "").split()),
                              autores="; ".join(re.sub(r"\s*\[.*", "", a) for a in (w.get("authors") or [])[:8]),
                              anio=(w.get("publication_date") or "")[:4], acceso="abierto",
                              resumen=" ".join((w.get("description") or "").split()), ambito="global", pais="US",
                              fuente=self.nombre, doi=doi, revista=w.get("journal_name") or "",
                              tipo_doc=("Technical Report; laboratorio nacional"
                                        if w.get("product_type") == "Technical Report" else w.get("product_type") or ""),
                              terminos={q})
                    out.setdefault(clave(t.url, t.handle), t).terminos.add(q)
                    n += 1
                pagina += 1
                if not recs or n >= total or (maximo and n >= maximo):
                    break
                time.sleep(0.4)
            self.registrar(q, total, min(n, total or n), "límite --max-por-consulta" if maximo else "")
            print(f"  OSTI {q!r}: {n}/{total}", flush=True)
        return list(out.values())


class HAL(Fuente):
    """HAL (Francia): tesis doctorales (THESE), habilitaciones (HDR), informes (REPORT), artículos y congresos."""
    nombre, ambito = "HAL", "global"
    API = "https://api.archives-ouvertes.fr/search/"
    TIPOS = {"THESE": "doctoralThesis", "HDR": "doctoralThesis (HDR)", "REPORT": "report", "ART": "article",
             "COMM": "conference paper", "OUV": "book", "COUV": "book chapter", "MEM": "masterThesis"}
    CONSULTAS = CONSULTAS_EN + ["béton autocicatrisant", "béton chlorures corrosion", "béton bactéries"]

    def cosechar(self, maximo):
        out = {}
        campos = "docid,title_s,authFullName_s,producedDateY_i,abstract_s,uri_s,doiId_s,journalTitle_s,docType_s,country_s"
        for q in self.CONSULTAS:
            inicio, n, total = 0, 0, None
            while True:
                d = json.loads(self.get(f"{self.API}?q={urllib.parse.quote(_y(q))}&fl={campos}&rows=100&start={inicio}"
                                        "&wt=json") or "{}").get("response", {})
                total = d.get("numFound", total or 0)
                docs = d.get("docs", [])
                for w in docs:
                    paises = {c.upper() for c in w.get("country_s") or []}
                    t = Tesis(institucion="HAL", handle=str(w.get("docid", "")),
                              url=f"https://doi.org/{w['doiId_s']}" if w.get("doiId_s") else w.get("uri_s", ""),
                              titulo=" ".join(" ".join(w.get("title_s") or []).split()),
                              autores="; ".join((w.get("authFullName_s") or [])[:8]), anio=str(w.get("producedDateY_i") or ""),
                              acceso="abierto", resumen=" ".join(" ".join(w.get("abstract_s") or []).split()),
                              ambito="peru" if "PE" in paises else "sudamerica" if paises & SUDAMERICA else "global",
                              pais=",".join(sorted(paises))[:40] or "FR", fuente=self.nombre, doi=w.get("doiId_s", ""),
                              revista=w.get("journalTitle_s", ""), tipo_doc=self.TIPOS.get(w.get("docType_s"), w.get("docType_s", "")),
                              terminos={q})
                    out.setdefault(clave(t.url, t.handle), t).terminos.add(q)
                    n += 1
                inicio += 100
                if not docs or inicio >= total or (maximo and n >= maximo):
                    break
                time.sleep(0.3)
            self.registrar(q, total, min(n, total or n), "límite --max-por-consulta" if maximo else "")
            print(f"  HAL {q!r}: {n}/{total}", flush=True)
        return list(out.values())


class Zenodo(Fuente):
    """Zenodo (CERN): informes de proyectos (p. ej. europeos), tesis, entregables y artículos depositados."""
    nombre, ambito = "Zenodo", "global"
    API = "https://zenodo.org/api/records"

    def cosechar(self, maximo):
        out = {}
        for q in CONSULTAS_EN:
            pagina, n, total = 1, 0, None
            while True:
                d = json.loads(self.get(f"{self.API}?q={urllib.parse.quote(_y(q))}&size=25&page={pagina}") or "{}")
                hits = d.get("hits", {})
                total = hits.get("total", total or 0)
                recs = hits.get("hits", [])
                for w in recs:
                    m = w.get("metadata", {})
                    rt = m.get("resource_type", {})
                    t = Tesis(institucion="; ".join(sorted({c.get("affiliation") or "" for c in m.get("creators", [])}))[:200],
                              handle=str(w.get("id", "")), url=w.get("doi_url") or f"https://zenodo.org/records/{w.get('id')}",
                              titulo=" ".join((m.get("title") or "").split()),
                              autores="; ".join(c.get("name", "") for c in m.get("creators", [])[:8]),
                              anio=(m.get("publication_date") or "")[:4],
                              acceso="abierto" if m.get("access_right") == "open" else "restringido",
                              resumen=" ".join(re.sub(r"<[^>]+>", " ", html.unescape(m.get("description") or "")).split()),
                              ambito="global", pais="", fuente=self.nombre, doi=w.get("doi", ""),
                              revista=(m.get("journal") or {}).get("title", ""),
                              tipo_doc=f"{rt.get('subtype') or rt.get('type') or ''}; {rt.get('title', '')}", terminos={q})
                    out.setdefault(clave(t.url, t.handle), t).terminos.add(q)
                    n += 1
                pagina += 1
                if not recs or n >= total or n >= 9900 or (maximo and n >= maximo):
                    break
                time.sleep(0.5)
            self.registrar(q, total, min(n, total or n), "límite --max-por-consulta" if maximo else
                           ("tope de 10 000 de la API" if (total or 0) > 9900 else ""))
            print(f"  Zenodo {q!r}: {n}/{total}", flush=True)
        return list(out.values())


def fuentes(grupos: set[str]) -> list[Fuente]:
    lista = []
    if "peru" in grupos:
        lista += [DSpace7("PUCP", "repositorio.pucp.edu.pe"), DSpace7("UNI", "repositorio.uni.edu.pe"),
                  DSpace7("UPC", "repositorioacademico.upc.edu.pe"), DSpace7("USAT", "repositorio.usat.edu.pe"),
                  DSpace6("UCV", "repositorio.ucv.edu.pe"), DSpace6("UNPRG", "repositorio.unprg.edu.pe"),
                  DSpace6("UNS", "repositorio.uns.edu.pe"), DSpace6("ULADECH", "repositorio.uladech.edu.pe"),
                  DSpace7("SENCICO", "repositorio.sencico.gob.pe"),
                  VuFind("ALICIA", "https://alicia.concytec.gob.pe/vufind/api/v1/search", "peru", CONSULTAS_ALICIA, "PE")]
    if "sudamerica" in grupos:
        lista += [VuFind("LA Referencia", "https://www.lareferencia.info/vufind/api/v1/search", "sudamerica",
                         CONSULTAS_ALICIA + CONSULTAS_PT),
                  VuFind("BDTD", "https://bdtd.ibict.br/vufind/api/v1/search", "sudamerica", CONSULTAS_PT, "BR")]
    if "global" in grupos:
        lista += [OpenAlex(), OpenAlex("dissertation"), OpenAlex("report"), OSTI(), HAL(), Zenodo(), CyberLeninka()]
    nombres = {g.lower() for g in grupos} - {"peru", "sudamerica", "global"}
    if nombres:                      # también acepta fuentes sueltas: --fuentes SENCICO,OSTI
        todas = fuentes({"peru", "sudamerica", "global"})
        lista += [f for f in todas if f.nombre.lower() in nombres and f not in lista]
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


def candidato_ss_plus(t) -> bool:
    """Puede llegar a SS+ si al leerlo resulta T0: aplicado en campo, sobre el tema y con datos propios."""
    g = lambda c: getattr(t, c, None) if not isinstance(t, dict) else t.get(c)
    return (g("aplicado_campo") == "si" and g("familia") in ("autorreparable", "cloruros")
            and g("con_datos") != "no" and g("rango") not in ("SS+", "D"))


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
               "ss_plus": {"meta": META_SS_PLUS, "confirmados": sum(t.rango == "SS+" for t in tesis.values()),
                           "candidatos": sum(candidato_ss_plus(t) for t in tesis.values())},
               "por_tier": {f"T{i}": sum(t.tier == str(i) for t in tesis.values()) for i in range(5)},
               "por_grado": {g: sum(t.grado == g for t in tesis.values())
                             for g in sorted({t.grado for t in tesis.values()})},
               "rango_por_ambito": {a: {r: sum(t.ambito == a and t.rango == r for t in tesis.values()) for r in RANGOS}
                                    for a in ("peru", "sudamerica", "global")},
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


def normalizar(t: Tesis) -> Tesis:
    """Los id de LA Referencia y ALICIA llevan el país delante ("ES_<32 hex>"). Ese prefijo:
    1) decide el ámbito (LA Referencia también incluye España, Portugal, México…, que son globales);
    2) se guarda como "ES:<hex>", porque "ES_<32 hex>" tiene la forma de un secreto de hCaptcha y el
       escáner de GitHub bloquea el push (falso positivo)."""
    m = re.fullmatch(r"([A-Z]{2})[_:]([0-9a-f]{32})", t.handle or "")
    if m:
        t.handle = f"{m.group(1)}:{m.group(2)}"
        if t.fuente in ("LA Referencia", "ALICIA", "BDTD"):
            pais = m.group(1)
            t.pais = pais
            t.ambito = "peru" if pais == "PE" else "sudamerica" if pais in SUDAMERICA else "global"
    return t


def unir(catalogo: dict[str, Tesis], t: Tesis):
    """Suma un registro al catálogo: el repositorio directo manda sobre el agregador; si ya estaba, completa
    los campos vacíos y conserva el tier confirmado."""
    t = normalizar(t)
    k = clave(t.url, t.handle)
    previa = catalogo.get(k)
    if previa is None:
        catalogo[k] = t.clasificar()
        return
    previa.terminos |= t.terminos
    if previa.fuente in ("ALICIA", "LA Referencia", "") and t.fuente not in ("ALICIA", "LA Referencia", ""):
        t.terminos, t.tier_confirmado = previa.terminos, previa.tier_confirmado or t.tier_confirmado
        t.campo_confirmado = previa.campo_confirmado or t.campo_confirmado
        t.grado_confirmado = previa.grado_confirmado or t.grado_confirmado
        previa = catalogo[k] = t
    else:
        for c in ("tipo_doc", "revista", "citas", "resumen", "doi", "acceso", "anio", "autores", "tier_confirmado",
                  "campo_confirmado", "grado_confirmado"):
            if not getattr(previa, c) and getattr(t, c):
                setattr(previa, c, getattr(t, c))
    previa.clasificar()


PARCIALES = LIT / "parciales"


def cosechar(grupos: set[str], maximo: int | None, parcial: str = ""):
    """Con `parcial`, escribe en datos/literatura/parciales/<parcial>_*.{csv,json} para correr varias fuentes en
    paralelo sin pisarse; luego `fusionar` las une al catálogo principal."""
    global CATALOGO, COBERTURA, METAS
    if parcial:
        PARCIALES.mkdir(parents=True, exist_ok=True)
        CATALOGO, COBERTURA, METAS = (PARCIALES / f"{parcial}_catalogo.csv", PARCIALES / f"{parcial}_cobertura.csv",
                                      PARCIALES / f"{parcial}_metas.json")
    catalogo = {k: a_tesis(r) for k, r in leer_catalogo().items()}
    cobertura = []
    for fuente in fuentes(grupos):
        print(f"[{fuente.ambito}] {fuente.nombre}", flush=True)
        for t in fuente.cosechar(maximo):
            unir(catalogo, t)
        cobertura += fuente.cobertura
        escribir_cobertura(cobertura)
        escribir_catalogo(catalogo)


def fusionar():
    """Une los catálogos parciales al principal y reemplaza la cobertura de cada fuente por la más reciente."""
    global CATALOGO, COBERTURA
    principal, cob_principal = CATALOGO, COBERTURA
    catalogo = {k: a_tesis(r) for k, r in leer_catalogo().items()}
    filas_cob = list(csv.DictReader(open(COBERTURA, encoding="utf-8"))) if COBERTURA.exists() else []
    for cat in sorted(PARCIALES.glob("*_catalogo.csv")):
        CATALOGO = cat
        for r in leer_catalogo().values():
            unir(catalogo, a_tesis(r))
        cob = cat.with_name(cat.name.replace("_catalogo.csv", "_cobertura.csv"))
        if cob.exists():
            nuevas = list(csv.DictReader(open(cob, encoding="utf-8")))
            fuentes_ = {r["fuente"] for r in nuevas}
            filas_cob = [r for r in filas_cob if r["fuente"] not in fuentes_] + nuevas
        print(f"unido {cat.name}")
    CATALOGO, COBERTURA = principal, cob_principal
    escribir_cobertura(filas_cob)
    escribir_catalogo({k: t.clasificar() for k, t in catalogo.items()})


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
    # primero los candidatos a SS+ (meta: 10 confirmados); después, como siempre, Perú manda
    prioridad = lambda r: (0 if candidato_ss_plus(r) else 1, {"peru": 0, "sudamerica": 1, "global": 2}.get(r["ambito"], 3),
                           RANGOS.index(r["rango"]) if r.get("rango") in RANGOS else 9,
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


def agregar(ident: str) -> str:
    """Trae un trabajo concreto de OpenAlex (DOI o id W…) al catálogo; devuelve su clave."""
    camino = ("doi:" + re.search(r"10\.\d{4,9}/\S+", ident).group(0)) if "10." in ident else ident.rstrip("/").split("/")[-1]
    w = json.loads(Fuente.get(f"{OpenAlex.API}/{camino}") or "{}")
    if not w.get("id"):
        sys.exit(f"OpenAlex no encuentra {ident}")
    paises = {c for a in w.get("authorships", []) for c in a.get("countries", [])}
    inv = w.get("abstract_inverted_index") or {}
    doi = (w.get("doi") or "").replace("https://doi.org/", "")
    t = Tesis(institucion="; ".join(sorted({i.get("display_name", "") for a in w.get("authorships", [])
                                             for i in a.get("institutions", [])}))[:200],
              handle=w["id"], url=w.get("doi") or w["id"], titulo=" ".join((w.get("title") or "").split()),
              autores="; ".join(a.get("author", {}).get("display_name", "") for a in w.get("authorships", [])[:8]),
              anio=str(w.get("publication_year") or ""),
              acceso="abierto" if (w.get("open_access") or {}).get("is_oa") else "restringido",
              resumen=" ".join(p for _, p in sorted((p, pal) for pal, ps in inv.items() for p in ps)),
              ambito="peru" if "PE" in paises else "sudamerica" if paises & SUDAMERICA else "global",
              pais=",".join(sorted(paises))[:40], fuente="OpenAlex", doi=doi, tipo_doc=w.get("type") or "",
              revista=(((w.get("primary_location") or {}).get("source") or {}).get("display_name") or "")[:150],
              citas=str(w.get("cited_by_count") or ""), terminos={"agregado a mano"})
    filas = {k: a_tesis(r) for k, r in leer_catalogo().items()}
    unir(filas, t)
    escribir_catalogo(filas)
    return clave(t.url, t.handle)


def confirmar(handle: str, tier: str, campo: str = "", grado_: str = ""):
    """El agente fija el tier al terminar de leer el documento completo (T1/T0 solo así)."""
    filas = leer_catalogo()
    k = clave(handle, handle)
    if k not in filas:
        sys.exit(f"{handle} no está en el catálogo")
    filas[k]["tier_confirmado"] = tier
    if campo:
        filas[k]["campo_confirmado"] = campo
    if grado_:
        filas[k]["grado_confirmado"] = grado_
    escribir_catalogo({c: a_tesis(r).clasificar() for c, r in filas.items()})
    t = a_tesis(filas[k]).clasificar()
    print(f"{t.titulo[:80]} → T{t.tier} · {t.grado} · rango {t.rango}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="etapa", required=True)
    c = sub.add_parser("cosechar")
    c.add_argument("--fuentes", default="peru,sudamerica,global")
    c.add_argument("--max-por-consulta", type=int, default=None, help="sin límite por defecto (cobertura ≥ 90 %)")
    c.add_argument("--parcial", default="", help="nombre del catálogo parcial (para cosechar en paralelo)")
    sub.add_parser("fusionar", help="une datos/literatura/parciales/* al catálogo principal")
    d = sub.add_parser("descargar")
    d.add_argument("--limite", type=int, default=60)
    sub.add_parser("preparar")
    sub.add_parser("reclasificar")
    k = sub.add_parser("confirmar", help="fija el tier tras leer el documento completo")
    k.add_argument("handle", help="handle o DOI, p. ej. 20.500.12692/151797")
    k.add_argument("tier", choices=list("01234"))
    k.add_argument("--campo", choices=["si", "no"], default="", help="aplicado en prototipo/estructura real (leído)")
    k.add_argument("--grado", default="", help="grado leído en el documento: DOC, MAG, LIC, ORG, ART-I…")
    g = sub.add_parser("agregar", help="trae un trabajo de OpenAlex por DOI o id W…")
    g.add_argument("ident")
    a = ap.parse_args(argv)
    if a.etapa == "cosechar":
        cosechar(set(a.fuentes.split(",")), a.max_por_consulta, a.parcial)
    elif a.etapa == "fusionar":
        fusionar()
    elif a.etapa == "descargar":
        descargar(a.limite)
    elif a.etapa == "preparar":
        preparar()
    elif a.etapa == "agregar":
        print(agregar(a.ident))
    elif a.etapa == "confirmar":
        confirmar(a.handle, a.tier, a.campo, a.grado)
    else:
        escribir_catalogo({k: normalizar(a_tesis(r)).clasificar() for k, r in leer_catalogo().items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
