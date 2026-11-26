# Flujo PRISMA: ampliación del meta-dataset BSHC

Fecha de las búsquedas: 2026-11-24. La búsqueda la hizo un solo revisor (agente automatizado) en una sesión, así que el cribado es parcial (ver "Limitaciones").

## Fuentes y consultas

1. **Europe PMC REST** (`/webservices/rest/search`, solo OA; el texto completo se bajó en JATS XML vía `/{PMCID}/fullTextXML`, con NCBI efetch como respaldo):
   - `(TITLE_ABS:"self-healing" OR TITLE_ABS:"self healing" OR TITLE_ABS:"crack healing") AND (TITLE_ABS:concrete OR TITLE_ABS:mortar OR TITLE_ABS:cementitious) AND (TITLE_ABS:bacteria OR TITLE_ABS:bacterial OR TITLE_ABS:microbial OR TITLE_ABS:Bacillus OR TITLE_ABS:MICP OR TITLE_ABS:"microbially") AND OPEN_ACCESS:y AND PUB_YEAR:[2010 TO 2026]` → **109** registros.
   - Una segunda consulta más amplia (`ABSTRACT:healing ... AND (bacteria|Bacillus|MICP|microbial)`) devolvió HTTP 503 y no se repitió.
2. **OpenAlex** (`/works`, `filter=title_and_abstract.search:<q>,open_access.is_oa:true,from_publication_date:2010-01-01,type:article`, 2 páginas de 100) con las consultas: "bacteria self-healing concrete crack", "bacterial self-healing mortar crack closure", "microbial self-healing concrete permeability", "encapsulated bacteria self-healing cementitious", "bacteria-based healing agent concrete", "MICP self-healing concrete crack width" → **336** registros únicos.
3. **Zenodo** (`/api/records`, `type=dataset`, 5 consultas, 2 páginas de 25) → ~100 registros; **14** relevantes para BSHC (ver `datasets_abiertos.md`).
4. **Repositorios institucionales** con los PDF que localizó OpenAlex: biblio.ugent.be, lirias.kuleuven.be, purehost.bath.ac.uk, J-STAGE, Frontiers, Nature, Springer (`/content/pdf/`), dergipark y jresm.
5. Crossref se usó solo para resolver DOI de datasets y artículos.

Accesos bloqueados desde este entorno (HTTP 403): mdpi.com (solo se pudo leer MDPI cuando el artículo está en PMC), sciencedirect.com, onlinelibrary.wiley.com, tandfonline.com y researchgate.net. iopscience, Hindawi/Wiley y scielo devolvieron HTML en lugar del PDF.

## Conteos

| Etapa | n |
|---|---|
| Registros identificados (Europe PMC 109 + OpenAlex 336 + 1 registro adicional de Zenodo/repositorio) | 446 |
| Tras eliminar duplicados por DOI (29 en Europe PMC y OpenAlex) | **417** (catálogo) |
| Excluidos en cribado por título/resumen | **111** (revisión 75; fuera de alcance 23; modelado/simulación/ML 13) |
| Sin evaluar a texto completo en esta sesión (pendientes) | **256** |
| Evaluados a texto completo (artículo, PDF de repositorio o dataset) | **50** |
| Excluidos a texto completo | **25**: cierre solo en figuras o solo cualitativo (9); sin datos de fisura/cierre (6); aplicación externa o reparación, no autocicatrización (2); métrica distinta (resistencia/UPV/penetración) (4); geopolímero (1); datos duplicados de otro estudio (1); ML secundario (1); ya en el meta original (1) |
| **Incluidos con datos extraídos** | **25 fuentes**: 24 nuevas + 1 ya en el meta original (Cappellesso et al. 2024, con 20 condiciones nuevas) |
| Condiciones extraídas (`literatura_extraida.csv`) | **206** |

Fuentes incluidas por origen:

| Origen | n |
|---|---|
| PMC (XML) | 14 |
| PDF OA de repositorio o editorial | 8 |
| Datasets Zenodo usados como fuente principal | 3 (Cappellesso 2024, Tran-SET 2019, LSU 2021) |

Dos de los datasets (Tran-SET 18CLSU02 y LSU 6469122) corresponden a informes técnicos, no a artículos arbitrados.

## Criterios

- **Inclusión:** estudio experimental primario (2010–2026) de material cementicio Portland con bacterias o sus controles abióticos. Debe reportar en texto, tabla o dataset al menos el cierre óptico de fisura (%) o una reducción de transporte (permeabilidad, absorción o cloruros) asociada a un ancho de fisura.
- **Exclusión:** revisiones, modelos o ML; aplicación externa de bacterias sobre la fisura; matrices no Portland; valores disponibles solo en figuras (no se digitalizaron); métricas basadas solo en resistencia o UPV.

## Limitaciones

256 registros potencialmente relevantes quedaron sin evaluar a texto completo, sobre todo de MDPI fuera de PMC y de Elsevier. No se digitalizó ninguna figura: todas las filas vienen de texto, tablas o datasets (`verificado=si`). La búsqueda la hizo un único revisor automatizado, sin doble cribado.
