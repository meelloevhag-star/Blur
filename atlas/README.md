# BioCrete Atlas

Mapa interactivo y API que recomiendan **concreto autorreparable por zona** del litoral peruano.

> **Reparto de tareas.** Conseguir datos es tarea de **Blur**: los ensayos (réplicas, aportes, Zenodo) y
> también el territorio — geografía, clima ERA5, relieve, población y capas GIS — que recoge
> `biocrete_neat/territorio` (`python -m biocrete_neat.territorio`). **El Atlas no descarga nada**: lee lo que
> Blur deja en `biocrete_neat/datos/`, lo resume por zona, entrena, diseña recetas y pinta el mapa. Una
> prueba (`test_atlas_no_descarga_nada`) impide que vuelva a salir a la red. Cada zona recibe una receta completa (dosificación por m³, cemento, agregados, aditivos y agente autorreparador), su vida útil estimada frente a cloruros y su viabilidad (costo por m³ y facilidad de conseguir los insumos). El Atlas **se alimenta de los datos que reúne Blur**: cada réplica, dataset o aporte validado que entra al repositorio re-entrena los modelos y regenera el mapa.

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
| Clima | Un año horario de ERA5 por celda de 0,25° (237 celdas costeras, recogidas por Blur): temperatura, humedad, punto de rocío, nubes bajas y viento; **temperatura corregida por altitud** con el DEM | Blur: `biocrete_neat/territorio/clima.py` (Open-Meteo, CC BY 4.0) | `ambiente.py` |
| Niebla / garúa | Índice 0–1 regional (horas con HR ≥ 95 % y T−Td ≤ 1 °C, nubes bajas, HR ≥ 85 %) **amplificado en cerros y lomas** donde la ladera al mar corta la capa de nubes | ERA5 + DEM | `niebla.py` |
| Cloruros en el aire | Perfil exponencial doble según distancia y viento; la niebla extiende la cola tierra adentro y **las crestas la frenan** | supuesto a calibrar | `niebla.py` |
| Régimen y norma | salpicadura (XS3 / C2), niebla salina (XS1 / C2), **niebla orográfica: lomas y cerros** (C2 si la sal ≥ 60 mg/m²·d), atmosférico marino (XS1 / C1–C2), seco (XC4 / C1): a/c máx., cemento mín. y máx. (450 kg), f′c especificado (E.060 tabla 5.3), recubrimiento y agentes permitidos | E.060 (2019) / ACI 318-19 / EN 206 / EN 1992-1-1 | `normas.py` |
| Prioridad | Población × probabilidad de que el concreto común (Tipo I, a/c 0,55, 40 mm) se despasive antes de 50 años | todo lo anterior | `optimizar.py` |
| Dosificación | ACI 211.1 por volumen absoluto; superplastificante si a/c ≤ 0,45 | — | `diseno_mezcla.py` |
| Cierre de fisura | Conjunto XGBoost (bootstrap por grupos, monotonía física) + NEAT, ponderados por R² agrupado | 2.167 réplicas (Mousa 2022, Cappellesso 2024) y aportes | `modelos.py` |
| Vida útil | **fib Bulletin 34 probabilista** (Monte Carlo, 10 000 muestras): una receta cumple 25/50/75/100 años si la probabilidad de despasivación a esa edad es ≤ 10 % (β ≥ 1,3, ISO 16204). D_RCM vs a/c ajustado a la base Dryad, C_crit Beta(0,6; 0,15), envejecimiento Beta(0,30; 0,12) en OPC, Cs lognormal con tope atmosférico de DuraCrete, Δx en salpicadura, recubrimiento con tolerancia de 8 mm. Concreto sin fisurar: el sellado de fisura se informa aparte y no suma años; solo el cristalizante tiene un crédito conservador (D × 0,8). Nunca se reportan más de 100 años | 239 ensayos RCM de Blur | `durabilidad.py` |
| Viabilidad | Precio de catálogo, flete desde la planta de cemento más cercana e índice de disponibilidad según la distancia al proveedor | catálogo con fuente y fecha | `viabilidad.py`, `catalogo/` |
| Recetas | Combinaciones que cumplen la norma (cemento × a/c × agente × curado × TMN × recubrimiento mínimo +0/10/20 mm) y tres recetas: **mejor desempeño** (la vida de diseño más alta), **económica** y **disponible** (ambas cumpliendo 50 años con β ≥ 1,3). Si ninguna llega, la zona lo avisa | — | `optimizar.py` |

El modelo de cierre distingue el **portador** (ninguno, cristalino, Basilisk, LWA, hidrogel, CNC), si hay bacterias y nutriente, el ambiente marino y el curado previo. Así sube el R² agrupado de 0,22–0,54 (6 variables) a **0,63** (validación con GroupKFold por fisura o probeta, sin fugas). Las combinaciones sin datos en el ambiente de la zona (por ejemplo, hidrogel en mar) se marcan **extrapoladas** y no compiten como receta ideal.

## Uso

```bash
pip install -r biocrete_neat/requirements.txt -r atlas/requirements.txt
python -m biocrete_neat.territorio todo   # Blur recoge geografía, clima, relieve, población y GIS (solo lo que falta)
python -m atlas territorio        # el Atlas resume relieve y población por zona (sin red)
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
- La deposición de cloruros, el paso de deposición a Cs (A entre 0,5 y 2,565), el factor del cemento IP (0,70) y su envejecimiento (0,45), la tarifa de flete y varios precios son **SUPUESTO** o **ESTIMADO**. Deben calibrarse con vela húmeda (ISO 9225), perfiles de cloruro en estructuras existentes (ASTM C1556), ensayos NT Build 492 por proveedor y cotizaciones. Los cementos HS y GU (NTP 334.082, por desempeño) se tratan como OPC frente a cloruros.
- Los agentes bacterianos sellan fisuras pero, con los datos marinos disponibles (Cappellesso 2024), no se les acredita vida útil frente a cloruros. En salpicadura solo se recomienda cristalizante; LWA, hidrogel y el consorcio agrícola quedan fuera de los regímenes con sal.
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
