"""
Descargador oficial de bases de datos abiertas de Zenodo / Dryad con DOI verificable:
  1. Zenodo 11305154 (Cappellesso et al., 2024 - Ghent Univ.): datos crudos marinos de CAB (microscopía, nitrato de plata, titulación cloruros 12 meses).
  2. Zenodo 8184530  (Dryad 10.5061/dryad.66t1g1k6j): base de datos experimental de D_RCM (coeficiente de difusión de cloruros NT Build 492).
  3. Zenodo 10849616 (Ghent Univ., 2024): absorción capilar y penetración de cloruros en ambientes ricos en cloruros.
  4. Zenodo 6469122  (Encapsulated bacteria optimal self-healing): parámetros óptimos de bacterias encapsuladas.
"""

import json
import urllib.request
import zipfile
from pathlib import Path

import openpyxl

DESTINO = Path(r"C:\Users\ecv_0\Desktop\Art\datasets_reales_zenodo")

REGISTROS = [
    ("11305154", "Cappellesso2024_Marine_CAB_Cloruros"),
    ("8184530",  "Dryad_RCM_Chloride_Diffusion_Database"),
    ("10849616", "Ghent2024_Chloride_Rich_Capillary_AgNO3"),
    ("6469122",  "Encapsulated_Bacteria_Optimal_SH"),
]


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    catalogo = []

    for rec_id, carpeta in REGISTROS:
        sub = DESTINO / carpeta
        sub.mkdir(exist_ok=True)
        url_meta = f"https://zenodo.org/api/records/{rec_id}"
        req = urllib.request.Request(url_meta, headers={"User-Agent": "BioCrete-Research/1.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
        meta = data.get("metadata", {})
        titulo = meta.get("title", "")
        doi = meta.get("doi", "")
        autores = [c.get("name", "") for c in meta.get("creators", [])[:4]]
        print(f"\n=== [Zenodo {rec_id}] {titulo} ===")
        print(f"DOI: {doi} | Autores: {autores}")

        archivos_desc = []
        for f in data.get("files", []):
            key = f["key"]
            size_b = f.get("size", 0)
            if key.lower().endswith((".xlsx", ".csv", ".md", ".txt", ".zip")) and size_b < 5_000_000:
                out_path = sub / key
                if not out_path.exists():
                    req_f = urllib.request.Request(f["links"]["self"], headers={"User-Agent": "BioCrete-Research/1.0"})
                    with urllib.request.urlopen(req_f, timeout=60) as resp:
                        out_path.write_bytes(resp.read())
                archivos_desc.append({"archivo": key, "kb": round(size_b / 1024, 1)})
                if key.lower().endswith(".xlsx"):
                    try:
                        wb = openpyxl.load_workbook(out_path, read_only=True, data_only=True)
                        hojas = [(s, wb[s].max_row, wb[s].max_column) for s in wb.sheetnames]
                        wb.close()
                        print(f"  [XLSX] {key} ({round(size_b/1024,1)} KB) -> hojas: {hojas[:8]}")
                    except Exception as e:
                        print(f"  [XLSX] {key}: error lectura {e}")
                elif key.lower().endswith(".zip"):
                    with zipfile.ZipFile(out_path) as zf:
                        print(f"  [ZIP]  {key} ({round(size_b/1024,1)} KB) -> {len(zf.namelist())} archivos: {zf.namelist()[:6]}")
                else:
                    print(f"  [FILE] {key} ({round(size_b/1024,1)} KB)")

        catalogo.append({
            "zenodo_id": rec_id,
            "carpeta": carpeta,
            "titulo": titulo,
            "doi": doi,
            "autores": autores,
            "archivos": archivos_desc,
        })

    (DESTINO / "catalogo_datasets_descargados.json").write_text(
        json.dumps(catalogo, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n[OK] Descarga oficial completada en: {DESTINO}")


if __name__ == "__main__":
    main()
