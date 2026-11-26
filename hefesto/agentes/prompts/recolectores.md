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
   - **Hecho:** Morán Córdova, F. E. (2023, UCV), *Evaluación del impacto de la corrosión en estructuras de concreto armado construidas en las playas del norte peruano*, `hdl.handle.net/20.500.12692/151797`. Tiene 64 estructuras en La Esmeralda, Colán. Ya están transcritas las **Tablas 1–4, 7 y 9** (`datos/entrantes/repositorios_2026-11-26*.csv`). Las Tablas 1–4 sumadas difieren en ±1 de la Tabla 7 en dos rangos de antigüedad; el error está en la tesis. **Pendiente:** lo que reporte de distancia al mar.

### Cómo trabajar: tres etapas (`python -m hefesto.agentes.repositorios <etapa>`)
1. **`cosechar`** (`--fuentes peru,sudamerica,global`). Cada estudio lleva un **`ambito`**:
   - **Perú (principal):**
     - repositorios directos que se recorren **completos**: DSpace 7 (PUCP, UNI, UPC, USAT) y DSpace 6 (UCV, UNPRG, UNS, ULADECH);
     - **ALICIA** (CONCYTEC, unas 167 instituciones) para las que no tienen acceso directo.
   - **Sudamérica (agregado):** LA Referencia y BDTD (Brasil).
   - **Global (aprendizaje y comparación):** el ámbito sale del país de los autores.
     - **OpenAlex:** artículos de revistas indexadas en Scopus y WoS, tesis de posgrado e informes técnicos, con consultas en inglés, español y chino.
     - **OSTI.gov:** laboratorios nacionales de EE. UU.
     - **HAL:** tesis doctorales e informes de Francia.
     - **Zenodo:** informes de proyectos y entregables.
     - **CyberLeninka:** revistas rusas.

     Las tesis chinas de CNKI y Wanfang son de pago; China entra por OpenAlex, que reúne sus artículos en inglés y en revistas chinas. eLIBRARY.ru y OATD no se fuerzan.
   - **SENCICO** (Perú): sus informes y normas son grado ORG.
   - **Meta de calidad: 10 fuentes SS+.**
     - Los candidatos son los documentos aplicados en campo o en prototipo, sobre autorreparación o cloruros y con datos propios. `descargar` los pone primero.
     - El agente lee cada uno completo y lo confirma como T0 solo si es trazable, cuantitativo y tiene respaldo de normas u organizaciones.
   - **Cobertura:** por cada consulta se cosecha **≥ 90 %** de lo que el repositorio reporta (`datos/literatura/cobertura_cosecha.csv`). Si queda por debajo, se marca el motivo y se reintenta.
   - **Familias:**
     - `autorreparable` (incluye *autocicatrizante*, autosellante y *self-healing*);
     - `cloruros` (estudios de cómo los cloruros afectan al concreto);
     - `inspeccion_dano`;
     - `durable_convencional`.

     Además se registra `tema_cloruros`, `bacterias`, `zona` y `con_datos`.
   - **Metas de literatura útil:** mínimo **1 000**, óptimo **3 000**, ideal **5 000**, en total y por ámbito (`datos/literatura/metas_cosecha.json`).
   - **Regla de sesgo:** Perú manda. Al descargar, extraer y validar va primero. Lo global sirve para aprender y comparar, pero un modelo no puede ganar solo por acertar con datos de otros países. Cada fila que entre al esquema lleva `procedencia_ambito`.
2. **`descargar`:** baja los PDF de acceso abierto de las tesis útiles, primero la costa norte y las autorreparables, a `datos/literatura/raw/repositorios/`, que no se sube.
3. **`preparar`:** ubica en cada PDF las tablas con datos y arma `datos/literatura/cola_extraccion.csv` (tesis, tabla, página, estado).

### Calidad de cada fuente (`hefesto/agentes/calidad.py`): tres etiquetas independientes
- **Tier 0–4:** qué tan completa es la información.
  - **T0:** completa, tangible, trazable, cualitativa y cuantitativa, con respaldo de organizaciones (norma, laboratorio, dataset con DOI).
  - **T1:** completa en todo lo que Hefesto necesita.
  - **T2:** parcial pero útil.
  - **T3:** toca el tema sin centrarse en él.
  - **T4:** periférica.

  Con solo metadatos el tier es **provisional y nunca pasa de T2**. T1 y T0 se fijan **solo después de leer el documento completo**, con `python -m hefesto.agentes.repositorios confirmar <handle> <tier>`.
  - Al leer el documento completo, también se confirma si se aplicó en campo (`--campo si`) y el grado real (`--grado DOC` cuando la fuente solo dice "dissertation").
  - Para traer un trabajo concreto al catálogo: `python -m hefesto.agentes.repositorios agregar <DOI o id W…>`.
  - Cada confirmación se justifica en `datos/literatura/confirmaciones_calidad.md`. Ahí están las 11 SS+ confirmadas, las leídas que no llegan a SS+ y las que no tienen canal abierto.
- **Grado** (nomenclatura interna del tipo de documento): `ORG`, `DATA`, `DOC` (doctorado o PhD), `ART-I` (revista con revisión por pares), `MAG`, `CONF`, `INF`, `LIB`, `LIC` (título profesional), `BAC`, `ART-G` (artículo genérico), `REV` (revisión) y `?`.
  - Sale **solo** del tipo que declara la fuente (`dc.type`, `formats`, `type`).
  - Un título como "según la norma ISO" no convierte una tesis en norma.
- **Rango SS+ … D:**

  | Rango | Regla |
  |---|---|
  | SS+ | T0 aplicada en prototipo o estructura en servicio |
  | SS | T0, o T1 de grado alto (ORG, DATA, DOC, ART-I) |
  | S | T1 de otros grados, o T2 de grado alto |
  | A | T2 de MAG, CONF, INF o LIB |
  | B | T2 de LIC, BAC o ART-G |
  | C | T3 o revisión |
  | D | T4, o un trabajo genérico sin ensayos propios |

- **Prioridad:** dentro de cada ámbito se descarga y transcribe en orden de rango. Perú sigue mandando.
- **Ya confirmados:**
  - Morán Córdova: T1, rango S.
  - Bioconcreto Piura (`20.500.12692/134208`): T2, rango B (falta w0).

Luego **tú lees cada tabla pendiente** (`pdftotext -layout -f <p> -l <p+2>`) y la transcribes al esquema en `datos/entrantes/`. Después cambias su `estado` en la cola a `transcrita`, `transcrita (sin w0: no entra al motor)` o `descartada (motivo)`. Si el catálogo cambia de reglas, usa la etapa `reclasificar`.
- **Si falta el ancho inicial de fisura,** el sellado va en `resultado_ancho_sellado_mm` y no se convierte a % de cierre. Ejemplo: la Tabla 22 de `hdl.handle.net/20.500.12692/134208` (bioconcreto en Piura).
- **La Universidad del Pacífico** no tiene ingeniería civil: no aporta tesis de concreto.
- **Bloquean el acceso directo:** PUCP y UPN (403), y UNP y UNSA no responden. Sus tesis se encuentran por ALICIA; si el PDF no baja, se registra la tesis en el catálogo y se deja como pendiente.

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
