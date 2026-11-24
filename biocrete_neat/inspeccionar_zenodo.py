"""Inspección limpia de las columnas reales de los archivos Excel oficiales descargados de Zenodo/Dryad."""
import zipfile
from pathlib import Path
import openpyxl

BASE = Path(r"C:\Users\ecv_0\Desktop\Art\datasets_reales_zenodo")

# Descomprimir Zenodo 6469122 (Mousa et al. LSU)
z_mousa = BASE / "Encapsulated_Bacteria_Optimal_SH" / "All_methods_info.zip"
dir_mousa = BASE / "Encapsulated_Bacteria_Optimal_SH" / "extraido"
dir_mousa.mkdir(exist_ok=True)
with zipfile.ZipFile(z_mousa) as zf:
    zf.extractall(dir_mousa)

archivos = [
    BASE / "Dryad_RCM_Chloride_Diffusion_Database" / "Experimental_data_for_chloride_diffusion_coefficient_of_concrete_by_rapid_chloride_migration_test.xlsx",
    dir_mousa / "All cracks summary combined Hydrogel LWA CNC (version 2).xlsx",
    dir_mousa / "Compessive Strength all methods.xlsx",
    BASE / "Cappellesso2024_Marine_CAB_Cloruros" / "02_Mar_Microscope measurements.xlsx",
    BASE / "Cappellesso2024_Marine_CAB_Cloruros" / "03_Mar_Silver nitrate measurements.xlsx",
]

for path in archivos:
    print(f"\n==================== {path.name} ====================")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    print("Hojas:", wb.sheetnames)
    for sheet in wb.sheetnames[:3]:
        ws = wb[sheet]
        print(f"  -- Hoja: {sheet} (rows={ws.max_row}, cols={ws.max_column}) --")
        for r_idx, row in enumerate(ws.iter_rows(max_row=6, max_col=14, values_only=True), 1):
            if any(v is not None for v in row):
                print(f"    F{r_idx}: {[v for v in row if v is not None][:10]}")
    wb.close()
