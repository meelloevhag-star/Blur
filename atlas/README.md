# BioCrete Atlas

Mapa interactivo y API que recomiendan **concreto autorreparable por zona** del litoral peruano. Cada zona recibe una receta completa (dosificación por m³, cemento, agregados, aditivos y agente autorreparador), su vida útil estimada frente a cloruros y su viabilidad (costo por m³ y facilidad de conseguir los insumos). El Atlas **se alimenta de los datos que reúne Blur**: cada réplica, dataset o aporte validado que entra al repositorio re-entrena los modelos y regenera el mapa.

```
biocrete_neat/datos ─┐                      ┌─ atlas/modelos/modelo_cierre.json ─► api/ (Go)  ─► /api/*
literatura, Zenodo ──┼─► atlas (Python) ────┤                                        ▲
aportes validados ───┘   ingest → entrenar  └─ atlas/salida/zonas_per.geojson ─────► web/ (TypeScript + Leaflet)
        ▲                → construir                                                  │
        └──────── validar_aportes.py ◄── atlas sync --aportes ◄── POST /api/aportes ◄─┘
```

## Qué calcula, y con qué datos

| Pieza | Método | Datos de Blur que usa | Dónde |
|---|---|---|---|
| Zonas | **Malla hexagonal de 10 km** (≈ 87 km² por celda, 1.097 celdas) sobre la franja de 0–35 km del mar, en proyección equivalente de Lambert: sin huecos ni solapes, recortada solo contra el mar. Las celdas con orilla (`frente_marino`) se evalúan además para una obra a 250 m del mar (salpicadura). Cada celda con su distrito (UBIGEO) | Natural Earth 10m, distritos INEI | `zonas.py` |
| Relieve | Elevación, pendiente, % del área en el **cinturón de niebla (300–1.000 m)**, % de **ladera que mira al mar** y **cresta** entre el mar y la zona | Copernicus DEM GLO-90 | `relieve.py` |
| Población | Habitantes 2022, densidad y clase urbana (urbano ≥ 1.500 hab/km², periurbano ≥ 300, rural ≥ 25); ciudad y vía principal más cercanas | WorldPop 2022 (Censo 2017 INEI), Natural Earth | `urbano.py` |
| Clima | Un año horario de ERA5 por celda de 0,25° (213 celdas): temperatura, humedad, punto de rocío, nubes bajas y viento; **temperatura corregida por altitud** con el DEM | Open-Meteo Archive (CC BY 4.0) | `ambiente.py` |
| Niebla / garúa | Índice 0–1 regional (horas con HR ≥ 95 % y T−Td ≤ 1 °C, nubes bajas, HR ≥ 85 %) **amplificado en cerros y lomas** donde la ladera al mar corta la capa de nubes | ERA5 + DEM | `niebla.py` |
| Cloruros en el aire | Perfil exponencial doble según distancia y viento; la niebla extiende la cola tierra adentro y **las crestas la frenan** | supuesto a calibrar | `niebla.py` |
| Régimen y norma | salpicadura (XS3), niebla salina (XS2), **niebla orográfica: lomas y cerros (XS2)**, atmosférico marino (XS1), seco (XC): límites de a/c, cemento mínimo, f′c y recubrimiento | E.060 / ACI 318 / EN 206 | `normas.py` |
| Prioridad | Población × severidad (cuánto dura el concreto común: Tipo I, a/c 0,55, 40 mm de recubrimiento, sin agente) | todo lo anterior | `optimizar.py` |
| Dosificación | ACI 211.1 por volumen absoluto; superplastificante si a/c ≤ 0,45 | — | `diseno_mezcla.py` |
| Cierre de fisura | Conjunto XGBoost (bootstrap por grupos, monotonía física) + NEAT, ponderados por R² agrupado | 2.167 réplicas (Mousa 2022, Cappellesso 2024) y aportes | `modelos.py` |
| Vida útil | Fick con envejecimiento (fib B34); D_RCM vs a/c ajustado a la base Dryad; efecto de la fisura y de cada agente según Cappellesso 2024 | 239 ensayos RCM y la penetración AgNO₃ marina | `durabilidad.py` |
| Viabilidad | Precio de catálogo, flete desde la planta de cemento más cercana e índice de disponibilidad según la distancia al proveedor | catálogo con fuente y fecha | `viabilidad.py`, `catalogo/` |
| Recetas | Todas las combinaciones que cumplen la norma, frente de Pareto y tres recetas: **ideal**, **económica** (la más barata con ≥ 50 años) y **disponible**, más una referencia sin agente | — | `optimizar.py` |

El modelo de cierre distingue el **portador** (ninguno, cristalino, Basilisk, LWA, hidrogel, CNC), si hay bacterias y nutriente, el ambiente marino y el curado previo. Así sube el R² agrupado de 0,22–0,54 (6 variables) a **0,63** (validación con GroupKFold por fisura o probeta, sin fugas). Las combinaciones sin datos en el ambiente de la zona (por ejemplo, hidrogel en mar) se marcan **extrapoladas** y no compiten como receta ideal.

## Uso

```bash
pip install -r biocrete_neat/requirements.txt -r atlas/requirements.txt
python -m atlas territorio        # relieve (DEM), población (WorldPop) y clima por celda; solo descarga lo que falta
python -m atlas sync --forzar     # ingesta → entrenar → recetas (atlas/salida/zonas_per.geojson)
```

```bash
cd api && go test ./... && go run ./cmd/servidor -raiz .. -web ../web/dist
```

```bash
cd web && npm ci && npm run build        # dist/ para servir con la API
npm run artefacto                         # dist-artefacto/ página estática publicable
```

Para usar la versión web con la API en vivo, abre la página con `?api=https://tu-servidor`. Sin ese parámetro lee el GeoJSON estático.

### API (detalle en `api/openapi.yaml`)

| Ruta | Para qué |
|---|---|
| `GET /api/zonas` | GeoJSON ligero para pintar el mapa |
| `GET /api/zonas/{id}` · `/recomendacion?tipo=ideal\|economica\|disponible` | Zona completa y recetas |
| `POST /api/predecir` | Cierre predicho para una mezcla libre, con IC 95 % y avisos de extrapolación |
| `POST /api/aportes` | Ensayos en JSON o CSV (`aportes/plantilla_aportes_atlas.csv`); requiere `X-API-Key` |
| `GET /api/modelo/version` | Versión del modelo y métricas |

Los modelos se evalúan en Go de forma nativa: la paridad con Python está comprobada a 1e-9 (`api/internal/modelo`). El servidor recarga el modelo y las zonas cuando `atlas sync` los regenera.

### Cómo entra un dato nuevo
1. **Desde los agentes de Blur:** cada CSV de réplicas que llegue a `biocrete_neat/datos/replicas/**/*.csv` (vía PR aprobado) entra solo: `fuentes.yaml` admite comodines y cada archivo es una fuente con su huella. El esquema mínimo está en la cabecera de `fuentes.yaml`. También se puede agregar una entrada nueva en `fuentes.yaml` sin tocar código. Con el merge, el workflow `atlas-sync` re-entrena y regenera el mapa.
2. **Desde la API:** `POST /api/aportes` → `atlas/aportes/pendientes/*.csv` → `python -m atlas sync --aportes atlas/aportes/pendientes`. Los aportes pasan por `validar_aportes.py` de Blur y entran a `aportes_validados.csv`, la misma fuente de verdad.
3. El nuevo modelo **solo reemplaza al vigente si iguala o mejora** su R² agrupado. Cada versión queda en `modelos/registro.json`, con las huellas de los datos y cuántos registros aportó cada fuente.

## Límites conocidos (léelos antes de usar una receta)
- Es una **guía para planificar ensayos**, no un diseño estructural firmado.
- Los únicos datos marinos de cierre son los de Cappellesso 2024 (Basilisk, cristalino, sin agente). Por eso, en la costa la receta ideal suele ser bacteriana tipo Basilisk y la económica, con cristalizante. Los ensayos de Paita cambiarán esto cuando entren como aportes.
- La deposición de cloruros, el factor por tipo de cemento, la tarifa de flete y varios precios están marcados **SUPUESTO** o **ESTIMADO** en `catalogo/` y en el código. Deben calibrarse con candela húmeda, ensayos RCM locales y cotizaciones.
- ERA5 (celdas de ~28 km) suaviza la niebla costera; el relieve (DEM de 90 m) aporta el detalle de lomas y cerros, pero el cinturón de 300–1.000 m, el factor orográfico y la atenuación por crestas son **supuestos a calibrar** (por ejemplo con colectores de niebla o mediciones en lomas de Lachay, Atiquipa o Lima).
- La población es la de WorldPop (1 km), que distribuye el Censo 2017 con covariables satelitales: sirve para comparar zonas, no reemplaza el padrón del INEI por manzana. OpenStreetMap (plantas de premezclado, uso de suelo) quedó pendiente porque los servidores Overpass no respondían.
- El efecto de la temperatura sobre las bacterias es un supuesto documentado; la humedad todavía no es una variable del modelo.

## Mejoras propuestas (en orden)
1. **Ensayos de Paita como aportes**, con lat/lon, temperatura y humedad. Son los primeros datos de un consorcio agrícola en el mar peruano.
2. **Humedad y régimen como entradas del modelo** en cuanto haya aportes que los registren. La plantilla extendida ya tiene las columnas.
3. **Plantas de premezclado y canteras desde OpenStreetMap** para afinar la disponibilidad local.
4. **Aprendizaje activo:** marcar en el mapa dónde la incertidumbre es mayor, para decidir dónde ensayar primero.
4. **Medir la deposición de cloruros** (ISO 9225) en 3 o 4 puntos (Paita, Callao, Pisco, Ilo) para calibrar `niebla.py`.
5. **Rutas reales con OSRM** y precios por ciudad (INEI) en lugar de un precio nacional.
6. **Otros países:** las zonas, el clima y los precios ya dependen del código ISO-3. Para sumar Ecuador o Chile basta `python -m atlas.zonas --pais ECU` más un `precios_<iso>`.
