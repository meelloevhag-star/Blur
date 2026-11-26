# Agentes de IA que cosechan datos para Hefesto

Cuatro agentes programados recorren fuentes públicas y llevan datos al **curador** de Hefesto, que los valida contra `hefesto/esquema/esquema_datos.json` antes de que el motor los use. No son scripts fijos: cada agente decide qué consultar a partir de lo que pide `necesidades.md`, lee y extrae.

## Normas comunes
- **Antes de buscar**, lee `necesidades.md`, que dice qué combinaciones no tienen datos. Lo que pide el orquestador va primero.
- **Nunca inventes ni estimes valores.** Lo que la fuente no reporta queda vacío. Cada fila lleva:
  - `procedencia_doi_o_url`;
  - `procedencia_ubicacion` (tabla, figura, página u hoja);
  - `procedencia_verificado`.

  Un valor leído de una figura solo vale si es legible, y va con `procedencia_verificado = no`.
- **Las tesis y los artículos se citan; no se copian ni se suben.** Los PDF van a `datos/literatura/raw/`, que está en `.gitignore`.
- **Salida:** `datos/entrantes/<agente>_<AAAA-MM-DD>.csv` con las columnas del esquema. Después ejecuta:
  ```bash
  python -m hefesto.esquema.mapear && python -m hefesto.agentes.curador && python -m hefesto.agentes.orquestador
  ```
  ```bash
  python -m pytest -q
  ```
- **Entrega:** rama `cosecha/<agente>-<AAAA-MM-DD>` y pull request. **Sin merge:** el autor revisa.
- **Registro:** añade lo revisado a `datos/literatura/catalogo_literatura.csv` (incluido o excluido, con motivo) para no repetir.

## 1. LITERATURA (Scopus, OpenAlex, Europe PMC, Crossref)
- **Busca:** artículos con ensayos de autorreparación bacteriana (cierre de fisura, permeabilidad, cloruros) y de difusión de cloruros en fisuras reparadas y sin reparar a varios anchos.
- **Scopus:** usa la API de Elsevier (`api.elsevier.com`) solo si la sesión tiene la credencial guardada; nunca pidas la clave por chat. Sin credencial, usa OpenAlex (`is_oa:true`), Europe PMC y Crossref.
- **Extrae** de tablas: mezcla (a/c, cemento, adiciones), bacteria (especie, dosis con unidades), protección, precursor, curado, ancho, edad, cierre %, α y su propiedad, norma y protocolo.

## 2. REPOSITORIOS UNIVERSITARIOS (RENATI, ALICIA, DSpace)
- **Recorre:** RENATI (SUNEDU), ALICIA (CONCYTEC) y los repositorios DSpace o OAI-PMH de UNI, PUCP, UDEP, UNP, UPC, UNMSM, UNSA, UNT y otras, por ejemplo con el endpoint OAI-PMH `/oai/request?verb=ListRecords&metadataPrefix=oai_dc` o con búsqueda web.
- **Términos:** "concreto autorreparable", "bacterias", "Bacillus", "cierre de fisuras", "patologías del concreto", "corrosión por cloruros", "Paita", "Piura", "Talara" y "Callao".
- **Extrae:**
  - ensayos de laboratorio de tesis (cierre a 7, 28, 56 y 90 días);
  - inspecciones de estructuras reales: tipo de daño, ancho, profundidad de cloruros o carbonatación y edad, con `id_grupo` = estructura.

## 3. DATASETS (Zenodo, Figshare, Mendeley Data, Dryad)
- **Busca:** datasets crudos con réplicas de cierre de fisura o de cloruros. Son lo más valioso, porque traen probetas individuales.
- **Si son nuevos:** descárgalos a `datos/zenodo/<carpeta>/` con su README (DOI y licencia) y mapéalos al esquema.

## 4. ZONA (clima, niebla y cloruros en el aire)
- **Primero:** ejecuta `python -m hefesto.agentes.zona_estaciones` (NOAA ISD). Añade a `ESTACIONES` otras estaciones costeras peruanas con datos (Paita, Sechura, Chiclayo, Trujillo, Chimbote, Callao, Pisco, Ilo).
- **Lo más valioso:** depósito de cloruros medido con vela húmeda (ISO 9225, proyecto MICAT y artículos). Reemplaza los supuestos de `hefesto/durabilidad/exposicion.py`.
- **Otras fuentes:**
  - Open-Meteo (ERA5, sin clave; si da error 429, se deja para la próxima vez);
  - ANA-SNIRH (calidad de agua: cloruros y salinidad);
  - DHN (temperatura del mar).
- **SENAMHI y PISCO:** solo si el autor sube archivos a `datos/zona/manual/`.
- **Campos:** `zona_*` del esquema, con `procedencia_tipo = clima`.
