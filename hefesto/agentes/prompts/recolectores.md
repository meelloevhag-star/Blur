# Instrucciones de los agentes recolectores (Zona, Daño, Materiales)

Se usarán como prompts de tareas programadas cuando el usuario las active. Normas comunes a los tres:

- **Antes de buscar**, leer `necesidades.md` del repositorio `meelloevhag-star/Blur-con-esteroides`: lo que pide el orquestador va primero.
- **Salida:** CSV con las columnas de `esquema/esquema_datos.json` en `datos/entrantes/<agente>_<AAAA-MM-DD>.csv`. Luego ejecutar `python -m agentes.curador` y `python -m agentes.orquestador`.
- **Nunca inventar ni estimar valores.** Lo que la fuente no reporta se deja vacío. Toda fila lleva `procedencia_doi_o_url`, `procedencia_ubicacion` (tabla, figura, página u hoja) y `procedencia_verificado`.
- Valores leídos de figuras solo si son legibles, con `procedencia_verificado = no`.
- Las tesis y los artículos se **citan**, no se copian ni se suben al repositorio.
- **Entrega:** rama `recoleccion/<agente>-<AAAA-MM-DD>` y pull request con un resumen. Sin merge: revisa el usuario.

## Agente ZONA (exposición y microclima)
**Objetivo:** caracterizar zonas, priorizando Paita, Colán, Piura y otras costas con niebla, bruma o garúa.
- **Primero:** ejecutar `python -m agentes.zona_estaciones`. Usa NOAA ISD (abierto y sin clave), con las estaciones de Talara (84390099999) y Piura (84401099999): humedad, neblina, niebla, llovizna o garúa, y viento. Añadir otras estaciones costeras del Perú a `ESTACIONES` si existen en ISD; METAR en vivo en aviationweather.gov.
- **Fuentes estatales:**
  - **ANA – SNIRH** (snirh.ana.gob.pe, accesible): estaciones hidrometeorológicas y calidad de agua, con cloruros y salinidad.
  - **DHN** (dhn.mil.pe): mareógrafo y temperatura del mar en Paita.
  - **SENAMHI:** no responde desde la nube; si el usuario sube descargas a `datos/zona/manual/`, se procesan.
  - **PISCO** (grilla de lluvia y temperatura de SENAMHI): en IRI Data Library (iridl.ldeo.columbia.edu/SOURCES/.SENAMHI/.HSR/.PISCO) **requiere iniciar sesión**; usar solo si hay series descargadas por el usuario. Paquetes de referencia en GitHub: GeomarPerales/RPisco.
- **Otras fuentes:**
  - **Open-Meteo** (ERA5 por coordenadas, sin clave; tiene un límite diario compartido);
  - mapas de corrosividad atmosférica (ISO 9223) y el proyecto MICAT;
  - artículos con depósito de cloruros atmosféricos (vela húmeda, ISO 9225) en costas de Perú y Latinoamérica.
- **Campos:** `zona_region`, `zona_lat`, `zona_lon`, `zona_distancia_mar_km`, `zona_humedad_relativa_pct`, `zona_dias_niebla_anio`, `zona_temperatura_media_c`, `zona_cloruros_atmosfericos_mg_m2_dia`, `zona_clase_exposicion` (EN 206 XS1 para niebla salina sin contacto directo con el agua de mar; XS2/XS3 para sumergido o mareas).
- `procedencia_tipo = clima`.

## Agente DAÑO (inspecciones y patologías)
**Objetivo:** saber qué daño aparece en cada zona y uso (viviendas, puertos, puentes, pavimentos, tanques, túneles, obras hidráulicas).
- **Fuentes:** RENATI (SUNEDU), ALICIA (CONCYTEC), repositorios universitarios (UPC, UNI, PUCP, UDEP, UNP…), informes técnicos públicos. Búsquedas del tipo "patologías del concreto", "fisuras", "corrosión por cloruros" + zona.
- **Campos:** `dano_tipo`, `dano_ancho_fisura_mm`, `dano_profundidad_cloruros_mm`, `dano_profundidad_carbonatacion_mm`, `dano_edad_estructura_anios`, `dano_uso`, más los campos de zona que reporte la tesis.
- `id_grupo` = estructura inspeccionada. `procedencia_tipo = tesis` o `informe`.

## Agente MATERIALES (dosificaciones y resultados de autorreparación)
**Objetivo:** llenar las combinaciones vacías del mapa de necesidades, por ejemplo agua de mar + lactato de calcio, o agua de mar + portador o encapsulación.
- **Fuentes:** OpenAlex (`is_oa:true`), Europe PMC, Zenodo, Figshare, Mendeley Data y tesis de laboratorio en RENATI y ALICIA.
- **Prioridad:** datasets crudos con réplicas; después, tablas de artículos.
- **También buscar:** penetración o difusión de cloruros en fisuras reparadas y sin reparar a varios anchos (0,05–0,5 mm). Ese dato reemplaza el parámetro provisional de fisura de `nucleo/vida_util.py`, que hoy solo tiene un laboratorio y dos anchos.
- **Campos:** `mezcla_*` (a/c, cemento, agregados, aditivos, especie y dosis de bacteria con unidades, nivel de protección, precursor, lactato de calcio, curado previo, aditivo cristalino), `dano_ancho_fisura_mm`, `resultado_edad_dias`, `resultado_cierre_pct` y/o `resultado_alpha` con `resultado_alpha_propiedad`, `resultado_protocolo`, `resultado_norma`.
- `id_grupo` = probeta, fisura o estudio. `procedencia_tipo = articulo`, `dataset` o `tesis`.
