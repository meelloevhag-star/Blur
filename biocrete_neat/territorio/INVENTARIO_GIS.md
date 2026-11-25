# Inventario de fuentes GIS para el Atlas

Comprobado el 25 de noviembre de 2026 desde el entorno de desarrollo. El detalle de cada servicio, con su URL y su estado, está en [`fuentes_gis.yaml`](fuentes_gis.yaml).

## Qué funciona ya (descargué datos de prueba)

| Para qué | Fuente | Cómo |
|---|---|---|
| Colegios, salud, mercados, manzanas 2025, predios, red vial, agua y electricidad | SIGRID / CENEPRED, servicio *Elementos expuestos* | ArcGIS REST → GeoJSON (1 000 registros por consulta) |
| Puntos críticos y manzanas en riesgo por El Niño 2027 | SIGRID, *COEN_FEN_2027* | ArcGIS REST → GeoJSON |
| Edificios existentes (m³ de concreto expuesto) | Google Open Buildings v3, Microsoft Building Footprints (277 archivos de Perú), VIDA (GeoParquet de Perú) | descarga |
| Crecimiento urbano 1975–2030 | GHSL GHS-BUILT-S, 100 m | descarga |
| Neblina diaria, temperatura de superficie, cobertura del suelo | Planetary Computer: MODIS 09A1, GOES-16, Landsat, Sentinel-2, ESA WorldCover | STAC |
| Oleaje por tramo de costa | Open-Meteo Marine | API |
| Química del suelo (pH, CEC, textura) | SoilGrids 250 m | WCS |
| Rutas y superficie de vías | HDX (Roads of Peru, Planet road surface) | descarga |

## Qué existe pero no se pudo descargar desde aquí

| Fuente | Motivo | Cómo resolverlo |
|---|---|---|
| **INGEMMET GEOCATMIN**: canteras y concesiones no metálicas, catastro minero | El proxy de este entorno no acepta el certificado TLS del servidor | Funciona desde QGIS, ArcGIS o un navegador; también desde GitHub Actions |
| **INEI**: manzanas y zonas censales | Usa el puerto 6443, que este entorno no admite | Igual que el anterior |
| **OpenStreetMap** (Geofabrik, Overpass): plantas de premezclado, puertos, uso de suelo | La red de este entorno corta la conexión | Descargar en GitHub Actions |
| **MINAM Geoservidor**: humedales, ZEE, batimetría litoral | El propio sitio respondió 403 (filtro anti-robots) | Navegador o solicitud de acceso |
| **MEF GeoInvierte**: proyectos de inversión | Sin servicio REST público documentado | Escribir a ssi@mef.gob.pe |

## Qué no encontré

- Un servicio público con **salinidad o sulfatos de suelo de Perú**. La alternativa son los mapas globales de ISRIC (1986–2016) y el GSASmap de FAO.
- Una capa de **licuefacción** o de **tsunami** en SIGRID. Los servicios de peligros que se citan en la web cambiaron de nombre y hay que ubicarlos en las carpetas actuales.
- Un **WMS o WFS de oleaje** de la DHN. Solo publica cartas en PDF o raster.
- Un producto listo de **frecuencia de neblina para Perú**. Se puede calcular con las banderas de nubes de MODIS o GOES (método de Werner et al. para California, adaptable).

## Prioridades propuestas

1. **Edificios existentes** (Google, Microsoft o VIDA) + **manzanas 2025 de SIGRID** → m³ de concreto expuesto y prioridad por zona.
2. **Neblina satelital** (MODIS 09A1 o GOES-16) → reemplaza a ERA5 en lomas y valles.
3. **Canteras de INGEMMET** (desde GitHub Actions) → costo real de agregados.
4. **Infraestructura crítica de SIGRID** (colegios, salud, vías) → qué estructuras públicas están en zonas severas.
5. **Oleaje** (Open-Meteo Marine) → afinar la franja de salpicadura.
