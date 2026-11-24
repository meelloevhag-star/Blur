# Datasets abiertos encontrados (BSHC)

Fecha de búsqueda: 2026-11-24. Fuentes consultadas: API de Zenodo (`type=dataset`, consultas "self-healing concrete bacteria", "bacterial self-healing mortar", "microbial self-healing concrete", "self-healing concrete crack", "bacteria concrete crack healing data"); Figshare, Dryad y Mendeley Data responden, pero no se cribaron a fondo por falta de tiempo. Todos los archivos se descargaron en `raw/<fuente>/` y no se han modificado (las carpetas `x/` y `extract/` son descompresiones de los zip).

## Datasets con datos crudos usados para extraer condiciones

| DOI | Qué contiene | n registros | Ruta local | Uso |
|---|---|---|---|---|
| 10.5281/zenodo.11305154 (Cappellesso et al. 2024, DIBE, 10.1016/j.dibe.2024.100486) | Anchos de fisura medidos con microscopio por zona y probeta (REF/BAS/CA; fisuras de 100 y 300 µm; series "healed" y "unhealed"; de 0 a 16 meses en agua de mar artificial ASTM D1141); penetración de Cl⁻ con AgNO₃; titulación; corrosión | 12 hojas de microscopía, cada una con 12–15 probetas × ~20 lecturas | `raw/zenodo_11305154_cappellesso_marino/` | 20 condiciones nuevas de un estudio ya presente en el meta original. El cierre se calculó a partir de los datos crudos |
| 10.5281/zenodo.7388208 (Cappellesso et al. 2023, CCC, 10.1016/j.cemconcomp.2023.105016) | Anchos de fisura, permeabilidad al agua, ingreso de cloruros y escamado por hielo-deshielo con sales | 6 xlsx | `raw/zenodo_7388208_frost_salt/` | Los valores se tomaron del PDF (Lirias); el dataset sirve de respaldo |
| 10.5281/zenodo.18277063 (Cappellesso et al. 2026, CCC, 10.1016/j.cemconcomp.2026.106514) | Microscopía, expansión y masa bajo ataque por sulfatos | 1 xlsx descargado (de 5) | `raw/zenodo_18277063_sulfato/` | **No usado.** Las hojas de microscopía de la fase de curación coinciden número a número con las de 10.5281/zenodo.11305154 (mismas probetas o datos reutilizados). Se excluyó para no duplicar |
| 10.5281/zenodo.3471961 (Tran-SET 18CLSU02, LSU, 2019) | Diseño de mezcla (a/c 0.48), anchos de fisura medios por viga (>300 lecturas/viga) a 0, 3, 7, 14 y 28 d de ciclos húmedo/seco; B. pseudofirmus y D. nitroreducens en perlas de alginato | 8 grupos × 3 vigas × 2 caras | `raw/zenodo_3471961_transet_lsu/` | 16 condiciones. Es un informe técnico, no un artículo arbitrado |
| 10.5281/zenodo.6469122 (LSU 2021; artículo asociado JMCE 2024, 10.1061/JMCEE7.MTENG-16130, cerrado) | Anchos de fisura laterales e inferiores a 0, 3, 7, 14 y 28 d con hidrogel, LWA o CNC × acetato de Mg, lactato de Ca o lactato de Na, con y sin bacterias, más SE por muestra | 21 muestras × 2 caras | `raw/zenodo_6469122_lsu_encaps/` | 21 condiciones (solo fisuras laterales). El dataset no trae a/c. Es la misma fuente que `datos/mousa2022_fisuras_reales.csv` del repo |

## Datasets secundarios o no aplicables (descargados como referencia, sin filas extraídas)

| DOI | Contenido | n | Ruta | Motivo para no usarlo |
|---|---|---|---|---|
| 10.5281/zenodo.21481200 (Akdağ 2026, revisión sistemática "Anchored for transport, unanchored for strength") | Tabla de evidencia de 120 estudios de BSHC (bacteria, portador, ancho, healing %, medida, transporte, citas textuales), PRISMA, sesgo | 120 estudios | `raw/zenodo_21481200_refstate/` | Es una fuente secundaria. Sirve como hoja de ruta: muchos de sus DOI son de Elsevier, cerrados o bloqueados desde este entorno. No se copiaron sus valores |
| 10.5281/zenodo.18509859 (GRU + ruido gaussiano, 2026) | `Final_SHC.csv` con cemento, arena, LW fino, agua, tipo de bacteria, concentración, curado, encapsulación, precursor, ancho inicial, tiempo y healing efficiency | 1552 filas | `raw/zenodo_18509859_ml_shc/` | Compilación sin DOI de origen por fila, así que no es trazable. Parte parece venir de los datasets LSU. No se usó |
| 10.5281/zenodo.14848035 (B. megaterium) | Mezcla (a/c 168/400 = 0.42), resistencias a 7–180 d por concentración | ~5 hojas | `raw/zenodo_14848035_megaterium/` | Sin datos de fisura ni cierre |

## Otros encontrados y no descargados

- 10.5281/zenodo.4559868 y 10.5281/zenodo.3865635 (SARCOS RRT2 y RRT5): MgO y macrocápsulas. No son bacterianos.
- 10.5281/zenodo.14568863: imágenes y tabla para deep learning de ancho de fisura y autocicatrización. Sin revisar.
- 10.5281/zenodo.6956144: registro de frost/bacteria sin archivos.
- 10.5281/zenodo.21500208: SAP en hormigón costero. No es bacteriano.
- 10.5281/zenodo.10849616: agentes aplicados manualmente (WRA, silicato, PU). No es bacteriano.
- Ya presentes en el repo: `datos/cappellesso2024_agno3_marino.csv`, `datos/dryad_opc_drcm_real.csv`, `datos/mousa2022_fisuras_reales.csv`.
