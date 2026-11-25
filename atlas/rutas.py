from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent      # raíz del repo Blur
ATLAS = RAIZ / "atlas"
DATOS = ATLAS / "datos"
# los datos del territorio los recoge Blur (biocrete_neat/territorio); el Atlas solo los lee
TERRITORIO = RAIZ / "biocrete_neat" / "datos" / "territorio"
GEO = TERRITORIO / "geo"
DEM = TERRITORIO / "dem"
WORLDPOP_DIR = TERRITORIO / "worldpop"
CLIMA = TERRITORIO / "clima_era5_{pais}.json"
GIS = TERRITORIO / "gis"
AVISO_BLUR = "falta en Blur: ejecuta `python -m biocrete_neat.territorio {que}`"
CATALOGO = ATLAS / "catalogo"
SALIDA = ATLAS / "salida"
MODELOS = ATLAS / "modelos"
NEAT_DIR = RAIZ / "biocrete_neat"
