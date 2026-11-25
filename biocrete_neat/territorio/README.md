# Blur · datos del territorio

Blur consigue los datos; el BioCrete Atlas (`atlas/`) solo los lee. Este módulo recoge todo lo que el
Atlas necesita del territorio y lo deja en `biocrete_neat/datos/territorio/`, con un registro común
(`registro.json`) que anota para cada fuente la URL, la licencia, la fecha, la huella y el estado.

```bash
python -m biocrete_neat.territorio todo                 # solo descarga lo que falta
python -m biocrete_neat.territorio clima relieve
python -m biocrete_neat.territorio gis --solo osm ingemmet
python -m biocrete_neat.territorio geo --forzar
```

| Recolector | Qué recoge | Fuente y licencia | Dónde queda |
|---|---|---|---|
| `geo.py` | Costa, país, departamentos, ciudades y vías; distritos (UBIGEO) | Natural Earth 10m (dominio público); INEI vía juaneladio/peru-geojson | `geo/` |
| `clima.py` | Un año horario de ERA5 resumido por celda de 0,25° que toque tierra a < 40 km del mar | Open-Meteo Archive (ERA5, CC BY 4.0) | `clima_era5_<pais>.json` |
| `relieve.py` | Teselas DEM de 1° de la franja costera | Copernicus DEM GLO-90 (licencia abierta Copernicus) | `dem/` (no se versiona; tamaños en el registro) |
| `poblacion.py` | Población 2022, 1 km, ajustada a la ONU (Censo 2017) | WorldPop (CC BY 4.0) | `worldpop/` (no se versiona; huella en el registro) |
| `gis.py` | Rocas y minerales industriales (canteras de árido, caliza, puzolana…); plantas de concreto, canteras, puertos y puentes | INGEMMET y MINAM (ArcGIS REST, datos abiertos del Estado); OpenStreetMap (ODbL) | `gis/<fuente>/` |

- Cada corrida **reemplaza** la entrada de su fuente en el registro (no quedan errores viejos) y solo cambia
  la fecha si el contenido cambió.
- La red usa reintentos y completa la cadena TLS de servidores que no envían su certificado intermedio
  (descarga el intermedio indicado por el propio certificado), **sin desactivar la verificación** (`red.py`).
- En GitHub: el workflow `blur-territorio` corre esto desde los servidores de GitHub (algunos sitios del
  Estado no responden desde otras redes) y guarda los cambios; al terminar, `atlas-sync` recalcula el mapa.
- Inventario completo de fuentes GIS evaluadas, con su estado: `INVENTARIO_GIS.md` y `fuentes_gis.yaml`.
- Para sumar un dato nuevo del territorio basta con dejarlo aquí y declararlo en `atlas/fuentes.yaml`
  (`tipo: territorio`); el Atlas lo detecta por su huella.
