"""
Agente REPOSITORIOS · tesis de universidades peruanas, de la búsqueda a la cola de extracción.

Tres etapas (cada una se puede correr sola):
  1. cosechar   ALICIA (CONCYTEC, agrega ~167 instituciones: UCV, PUCP, UPC, URP, ULIMA, UNI, UDEP,
                UNP, USAT…) + UCV directa. Metadatos y clasificación de cada tesis:
                  familia      autorreparable | durable_convencional | inspeccion_dano | otro
                  bacterias    especies nombradas (Bacillus subtilis, megaterium, Lysinibacillus…)
                  zona         lugares de la costa y del país mencionados
                  con_datos    el resumen indica ensayos o mediciones propias (no revisión teórica)
  2. descargar  PDF de acceso abierto de las tesis útiles, desde el repositorio de origen
                (DSpace 6 y 7). Van a datos/literatura/raw/ (no se suben: .gitignore).
  3. preparar   ubica en cada PDF las tablas con datos (cierre, fisuras, corrosión, cloruros,
                resistencia, permeabilidad) → datos/literatura/cola_extraccion.csv con tesis,
                tabla y página. El agente de IA transcribe esas tablas al esquema de Hefesto
                (datos/entrantes/), sin estimar valores, y el curador las valida.

Uso:
    python -m hefesto.agentes.repositorios cosechar [--max 300]
    python -m hefesto.agentes.repositorios descargar [--limite 40]
    python -m hefesto.agentes.repositorios preparar
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
from dataclasses import asdict, dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
LIT = RAIZ / "datos" / "literatura"
CATALOGO = LIT / "catalogo_repositorios.csv"
COLA = LIT / "cola_extraccion.csv"
RAW = LIT / "raw" / "repositorios"
AGENTE = {"User-Agent": "Hefesto-cosecha-academica/1.0 (investigación sin fines de lucro)"}

TERMINOS = [
    "concreto autorreparable", "concreto autocurativo", "bacterias concreto", "Bacillus concreto", "bioconcreto",
    "corrosión concreto armado", "patologías concreto", "patología estructural concreto", "fisuras concreto",
    "deterioro concreto", "cloruros concreto", "carbonatación concreto", "concreto ambiente marino",
    "concreto durabilidad microsílice", "concreto puzolana durabilidad", "estructuras concreto zona costera",
]
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
CLAVES_TABLA = r"cierre|fisur|grieta|corrosi|clorur|carbonat|resistencia a (la )?compresi|f.?c|permeab|absorci|autorrepar|sellado|ancho"


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
    familia: str = ""
    usa_bacterias: str = ""
    bacterias: str = ""
    zona: str = ""
    con_datos: str = ""
    terminos: set = field(default_factory=set)

    def clasificar(self) -> "Tesis":
        t = f"{self.titulo} {self.resumen}".lower()
        esp = [e for e, rx in ESPECIES.items() if re.search(rx, t)]
        if len(esp) > 1 and "Bacillus (sin especie)" in esp:
            esp.remove("Bacillus (sin especie)")
        self.bacterias = "; ".join(esp)
        self.usa_bacterias = "si" if esp or re.search(r"bacteri", t) else "no"
        de_concreto = re.search(r"concreto|mortero|hormig[oó]n|cemento|pavimento r[ií]gido", t)
        if not de_concreto:
            self.familia = "otro"
        elif re.search(r"autorrepar|autoreparab|autocurativ|auto-?sanaci|bioconcreto|bacteri", t):
            self.familia = "autorreparable"
        elif re.search(r"corrosi|patolog|deterioro|lesiones|inspecci|fisura|grieta", t):
            self.familia = "inspeccion_dano"
        elif re.search(r"clorur|carbonat|durabilid|ambiente marino|permeab|micros[ií]lice|puzolan|ceniza", t):
            self.familia = "durable_convencional"
        else:
            self.familia = "otro"
        self.zona = "; ".join(sorted({z.replace("Colan", "Colán") for z in ZONAS if re.search(rf"\b{z.lower()}\b", t)}))
        revision = re.search(r"revisi[oó]n (te[oó]rica|literaria|sistem[aá]tica|documental|bibliogr)", t)
        medida = re.search(r"ensay|resultad|se obtuv|kg/cm|mpa|%|d[ií]as|probetas|muestras|inspecci|evalu", t)
        self.con_datos = "no" if revision else "probable" if medida else "incierto"
        return self

    def fila(self) -> dict:
        d = asdict(self)
        d["terminos"] = "; ".join(sorted(self.terminos))
        d["resumen"] = self.resumen[:600]
        return d


# ============================================================================ fuentes
class Fuente(ABC):
    nombre = ""

    @staticmethod
    def get(url: str, intentos: int = 3, binario: bool = False):
        for k in range(intentos):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=AGENTE), timeout=90) as r:
                    datos = r.read()
                    return datos if binario else datos.decode("utf-8", "ignore")
            except Exception:  # noqa: BLE001 — red inestable: reintenta y sigue
                time.sleep(2 * (k + 1))
        return b"" if binario else ""

    @abstractmethod
    def buscar(self, termino: str, maximo: int) -> list[Tesis]: ...


class Alicia(Fuente):
    """Agregador nacional (VuFind). Trae título, autores, institución, año, resumen y enlace."""
    nombre = "ALICIA"
    API = "https://alicia.concytec.gob.pe/vufind/api/v1/search"

    def buscar(self, termino, maximo):
        salida, pagina = [], 1
        campos = "".join(f"&field[]={c}" for c in ("id", "title", "authors", "institutions", "urls",
                                                       "publicationDates", "summary"))
        while len(salida) < maximo:
            q = urllib.parse.quote_plus(termino)
            t = self.get(f"{self.API}?lookfor={q}&type=AllFields&limit=100&page={pagina}{campos}")
            try:
                recs = json.loads(t).get("records", []) if t else []
            except json.JSONDecodeError:
                recs = []
            if not recs:
                break
            for r in recs:
                url = next((u["url"] for u in r.get("urls", []) if "handle" in u.get("url", "")),
                           (r.get("urls") or [{}])[0].get("url", ""))
                autores = list((r.get("authors", {}).get("primary") or {}).keys()) + \
                    list((r.get("authors", {}).get("secondary") or {}).keys())
                salida.append(Tesis(institucion=", ".join(r.get("institutions", [])), handle=r.get("id", ""),
                                    url=url, titulo=" ".join(r.get("title", "").split()), autores="; ".join(autores),
                                    anio=(r.get("publicationDates") or [""])[0][:4],
                                    resumen=" ".join(" ".join(r.get("summary", [])).split()), terminos={termino}))
            pagina += 1
            time.sleep(0.4)
        return salida[:maximo]


class UCV(Fuente):
    """Repositorio de la UCV (DSpace 6): su buscador encuentra más que ALICIA en esta universidad."""
    nombre = "UCV"
    BASE = "https://repositorio.ucv.edu.pe"

    def buscar(self, termino, maximo):
        handles, pagina = [], 1
        while len(handles) < maximo:
            t = self.get(f"{self.BASE}/discover?query={urllib.parse.quote_plus(termino)}&rpp=50&page={pagina}")
            nuevos = [h for h in re.findall(r'<a href="/handle/(20\.500\.12692/\d+)"[^>]*>\s*<h4', t) if h not in handles]
            if not nuevos:
                break
            handles += nuevos
            pagina += 1
            time.sleep(0.5)
        salida = []
        for h in handles[:maximo]:
            x = self.get(f"{self.BASE}/oai/request?verb=GetRecord&metadataPrefix=oai_dc"
                         f"&identifier=oai:repositorio.ucv.edu.pe:{h}")
            g = lambda tag: [html.unescape(v).strip() for v in re.findall(rf"<dc:{tag}[^>]*>(.*?)</dc:{tag}>", x, re.S)]
            if not g("title"):
                continue
            salida.append(Tesis(institucion="UCV", handle=h, url=f"https://hdl.handle.net/{h}",
                                titulo=" ".join(g("title")[0].split()), autores="; ".join(g("creator")),
                                anio=next((d[:4] for d in g("date") if re.match(r"\d{4}", d)), ""),
                                acceso="abierto" if any("openAccess" in r for r in g("rights")) else "restringido",
                                resumen=" ".join(" ".join(g("description")).split()), terminos={termino}))
            time.sleep(0.25)
        return salida


TERMINOS_UCV = ["concreto autorreparable", "autoreparable concreto", "bacterias concreto", "Bacillus",
                "bioconcreto", "corrosión estructuras concreto", "corrosión playas", "patologías concreto Piura",
                "patologías concreto Tumbes", "patologías concreto Chimbote", "fisuras concreto Piura"]


# ============================================================================ etapas
def cosechar(maximo: int) -> dict[str, Tesis]:
    previas = leer_catalogo()
    nuevas: dict[str, Tesis] = {}
    consultas = [(Alicia(), t) for t in TERMINOS + ["autoreparable", "auto reparable concreto", "autosanación concreto"]]
    consultas += [(UCV(), t) for t in TERMINOS_UCV]
    for fuente, termino in consultas:
        res = fuente.buscar(termino, maximo if fuente.nombre == "ALICIA" else min(maximo, 150))
        print(f"{fuente.nombre} {termino!r}: {len(res)}", flush=True)
        for t in res:
            clave = t.url or t.handle
            if clave in nuevas:
                nuevas[clave].terminos |= t.terminos
            else:
                nuevas[clave] = t.clasificar()
    for clave, fila in previas.items():   # conserva lo cosechado antes (p. ej. UCV directa) y su acceso
        if clave not in nuevas:
            nuevas[clave] = Tesis(**{k: v for k, v in fila.items() if k != "terminos"},
                                  terminos=set(filter(None, fila.get("terminos", "").split("; "))))
        elif fila.get("acceso"):
            nuevas[clave].acceso = fila["acceso"]
    escribir_catalogo(nuevas)
    return nuevas


def leer_catalogo() -> dict[str, dict]:
    if not CATALOGO.exists():
        return {}
    with open(CATALOGO, encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    out = {}
    for r in filas:
        r.setdefault("institucion", r.pop("universidad", ""))
        r.pop("universidad", None)
        for k in ("resumen", "familia", "con_datos"):
            r.setdefault(k, "")
        if not r.get("familia") and r.get("tipo"):
            r["familia"] = {"durabilidad": "durable_convencional"}.get(r["tipo"], r["tipo"])
        r.pop("tipo", None)
        out[r.get("url") or r["handle"]] = r
    return out


def escribir_catalogo(tesis: dict[str, Tesis]):
    campos = list(Tesis.__dataclass_fields__)
    LIT.mkdir(parents=True, exist_ok=True)
    orden = {"autorreparable": 0, "inspeccion_dano": 1, "durable_convencional": 2, "otro": 3}
    with open(CATALOGO, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        w.writerows(t.fila() for t in sorted(tesis.values(), key=lambda t: (orden.get(t.familia, 9), t.institucion,
                                                                            t.anio)))
    print(f"{len(tesis)} tesis en {CATALOGO.relative_to(RAIZ)}")


def enlace_pdf(url: str) -> str | None:
    """Busca el PDF de acceso abierto en la página del handle (DSpace 6) o en la API (DSpace 7)."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=AGENTE), timeout=90) as r:
            pagina, final = r.read().decode("utf-8", "ignore"), r.geturl()
    except Exception:  # noqa: BLE001
        return None
    origen = re.match(r"https?://[^/]+", final).group(0)
    m = re.search(r'citation_pdf_url"\s+content="([^"]+)"', pagina)          # DSpace 6 y 7
    if m and "isAllowed=n" not in m.group(1):
        return html.unescape(m.group(1))
    candidatos = [h for h in re.findall(r'href="([^"]*/bitstream/[^"]*\.pdf[^"]*)"', pagina, re.I)
                  if "isAllowed=n" not in h]
    if candidatos:
        h = html.unescape(candidatos[0])
        return h if h.startswith("http") else origen + h
    return None


def descargar(limite: int):
    filas = leer_catalogo()
    utiles = [r for r in filas.values() if r["familia"] in ("autorreparable", "inspeccion_dano", "durable_convencional")
              and r.get("con_datos") != "no"]
    # primero la costa norte, luego autorreparables, luego lo más reciente
    prioridad = lambda r: (0 if re.search(r"Piura|Paita|Colán|Talara|Tumbes|Sechura|Sullana", r.get("zona", "")) else 1,
                           0 if r["familia"] == "autorreparable" else 1, -int(r.get("anio") or 0))
    RAW.mkdir(parents=True, exist_ok=True)
    hechos = 0
    for r in sorted(utiles, key=prioridad):
        if hechos >= limite:
            break
        nombre = RAW / (re.sub(r"[^\w]+", "_", r["url"].split("handle/")[-1] or r["handle"])[:80] + ".pdf")
        if nombre.exists():
            continue
        pdf = enlace_pdf(r["url"]) if r.get("url") else None
        if not pdf:
            continue
        datos = Fuente.get(pdf, binario=True)
        if datos[:4] == b"%PDF":
            nombre.write_bytes(datos)
            hechos += 1
            print(f"  PDF {nombre.name} ({len(datos) // 1024} KB) · {r['titulo'][:70]}", flush=True)
        time.sleep(0.5)
    print(f"{hechos} PDF nuevos en {RAW.relative_to(RAIZ)}")


def preparar():
    """Busca en cada PDF los títulos de tabla con datos útiles y arma la cola para el agente."""
    filas = leer_catalogo()
    por_nombre = {re.sub(r"[^\w]+", "_", r["url"].split("handle/")[-1] or r["handle"])[:80]: r for r in filas.values()}
    cola = []
    for pdf in sorted(RAW.glob("*.pdf")):
        r = por_nombre.get(pdf.stem, {})
        try:
            texto = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True,
                                   timeout=120).stdout
        except (OSError, subprocess.TimeoutExpired):
            continue
        for n, pag in enumerate(texto.split("\f"), 1):
            for m in re.finditer(r"^\s*(Tabla|Cuadro)\s+N?[°º]?\s*(\d+)[:.\-–]?\s*(.{0,140})$", pag, re.M | re.I):
                titulo = m.group(3).strip()
                es_indice = re.search(r"\.{5,}|-{5,}|_{5,}|\s\d{1,3}\s*$", titulo)
                if re.search(CLAVES_TABLA, titulo.lower()) and not es_indice and r.get("familia") != "otro":
                    cola.append({"institucion": r.get("institucion", ""), "url": r.get("url", ""),
                                 "titulo_tesis": r.get("titulo", "")[:150], "familia": r.get("familia", ""),
                                 "pdf": str(pdf.relative_to(RAIZ)), "tabla": f"{m.group(1)} {m.group(2)}",
                                 "pagina": n, "titulo_tabla": titulo, "estado": "pendiente"})
    vistos, unicos = set(), []
    for c in cola:
        k = (c["pdf"], c["tabla"])
        if k not in vistos:
            vistos.add(k)
            unicos.append(c)
    with open(COLA, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(unicos[0]) if unicos else ["pdf"])
        w.writeheader()
        w.writerows(unicos)
    print(f"{len(unicos)} tablas con datos en {len({c['pdf'] for c in unicos})} tesis → {COLA.relative_to(RAIZ)}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="etapa", required=True)
    c = sub.add_parser("cosechar")
    c.add_argument("--max", type=int, default=300)
    d = sub.add_parser("descargar")
    d.add_argument("--limite", type=int, default=40)
    sub.add_parser("preparar")
    sub.add_parser("reclasificar")
    a = ap.parse_args(argv)
    if a.etapa == "cosechar":
        cosechar(a.max)
    elif a.etapa == "reclasificar":
        filas = leer_catalogo()
        tesis = {k: Tesis(**{c: v for c, v in r.items() if c in Tesis.__dataclass_fields__ and c != "terminos"},
                          terminos=set(filter(None, r.get("terminos", "").split("; ")))).clasificar()
                 for k, r in filas.items()}
        escribir_catalogo(tesis)
    elif a.etapa == "descargar":
        descargar(a.limite)
    else:
        preparar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
