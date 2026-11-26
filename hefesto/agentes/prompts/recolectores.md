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

## 2. REPOSITORIOS UNIVERSITARIOS (UCV, UPC, RENATI, ALICIA, DSpace)

### Repositorios prioritarios (comprobados el 26-11-2026: públicos y con OAI-PMH)
| Universidad | Búsqueda | OAI-PMH | Qué tiene |
|---|---|---|---|
| **UCV** (César Vallejo) | `https://repositorio.ucv.edu.pe/discover?query=<términos>` | `https://repositorio.ucv.edu.pe/oai/request` | 62 tesis de concreto autorreparable (Piura, Tumbes, Trujillo, Lima) y muchas inspecciones de daño en la costa norte |
| **UPC** | API DSpace 7: `https://repositorioacademico.upc.edu.pe/server/api/discover/search/objects?query=<términos>&dsoType=ITEM` | `https://repositorioacademico.upc.edu.pe/server/oai/request` | Diseño de concretos durables: 233 tesis sobre cloruros y durabilidad, 403 sobre ambiente marino y 5 de autorreparable |

Los metadatos de una tesis salen de `?verb=GetRecord&metadataPrefix=oai_dc&identifier=oai:<host>:<handle>`. El PDF se descarga solo si la tesis es `openAccess` y el enlace dice `isAllowed=y`. Va a `datos/literatura/raw/`, que no se sube.

### Tres familias de datos (campo `mezcla_familia`)
1. **`autorreparable`:** ensayos con bacteria o agente, con cierre a 7, 28, 56 y 90 días, resistencia y permeabilidad.
2. **`durable_convencional`:** concretos diseñados para ambientes con cloruros o marinos que **no** se autorreparan. Por ejemplo, microsílice, ceniza, metacaolín o baja permeabilidad (muchos de la UPC).
   - Se registran la mezcla, la adición y su %, y los resultados de durabilidad: `resultado_fc_mpa`, `resultado_d_rcm_1e12_m2_s`, `resultado_penetracion_cloruros_mm`, `resultado_carga_pasante_coulomb`, `resultado_absorcion_pct` y `resultado_resistividad_kohm_cm`.
   - Son **bases** que ya funcionan en ese ambiente: Hefesto evalúa qué ganaría cada una si se le añade autorreparación.
3. **Inspecciones de daño** en estructuras reales: `dano_tipo`, `dano_elemento`, `dano_nivel_corrosion` y `dano_n_elementos` (para tablas de conteo), la edad de la estructura y la zona. Sirven para contrastar el modelo de vida útil con la realidad.
   - **Hecho:** Morán Córdova, F. E. (2023, UCV), *Evaluación del impacto de la corrosión en estructuras de concreto armado construidas en las playas del norte peruano*, `hdl.handle.net/20.500.12692/151797`. Tiene 64 estructuras en La Esmeralda, Colán. La **Tabla 7** ya está transcrita en `datos/entrantes/repositorios_2026-11-26.csv`. **Pendiente:** las Tablas 1–4 (por elemento), la 9 (con protección) y lo que reporte de distancia al mar.

### Otras fuentes
- RENATI (SUNEDU), ALICIA (CONCYTEC) y los repositorios DSpace de UNI, PUCP, UDEP, UNP, UNMSM, UNSA, UNT y otras.
- **Términos:** "concreto autorreparable", "bacterias", "Bacillus", "cierre de fisuras", "patologías del concreto", "corrosión", "cloruros", "ambiente marino", "durabilidad", "microsílice", "Paita", "Colán", "Piura", "Talara", "Tumbes" y "Callao".
- **Reglas:** nunca se convierten rangos a valores exactos (por ejemplo, la antigüedad "entre 2018 y 2020" queda como etiqueta, no como 4 años). Se copian los números tal cual de la tabla y se comprueba que las sumas cuadren; si la tesis no cuadra, se anota.

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
