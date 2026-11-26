"""
Mapea los datos existentes al esquema unificado (esquema/esquema_datos.json).

Salidas en datos/entrantes/ (las procesa luego el agente curador):
    replicas.csv     2167 réplicas de cierre (Mousa 2022, Cappellesso 2024)
    literatura.csv   condiciones verificadas del meta-dataset v2 (usar_en_modelo = si)
Los campos que la fuente no reporta quedan vacíos (no se imputan).

Uso:
    python -m hefesto.esquema.mapear
"""

import csv
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ESQUEMA = json.loads((RAIZ / "hefesto" / "esquema" / "esquema_datos.json").read_text(encoding="utf-8"))
CAMPOS = list(ESQUEMA["properties"])
ENTRANTES = RAIZ / "datos" / "entrantes"


def _escribir(ruta: Path, filas: list[dict]) -> int:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS)
        w.writeheader()
        for f in filas:
            w.writerow({k: f.get(k, "") for k in CAMPOS})
    return len(filas)


def mapear_replicas() -> list[dict]:
    with open(RAIZ / "datos" / "replicas_cierre_fisuras.csv", encoding="utf-8") as fh:
        filas = list(csv.DictReader(fh))
    return [{
        "fuente": r["fuente"], "id_grupo": r["grupo_probeta"],
        "zona_ambiente_marino": r["ambiente_marino"],
        "zona_ciclos_humectacion": "1" if r["fuente"] == "Mousa2022" else "",
        "dano_tipo": "fisura", "dano_ancho_fisura_mm": r["w0_mm"], "dano_uso": "laboratorio",
        "mezcla_nivel_proteccion": r["nivel_proteccion"], "mezcla_precursor": r["nutriente"],
        # Cappellesso no añade lactato de calcio como precursor aparte (agente comercial Basilisk de
        # composición no declarada): se codifica 0, igual que en todos los análisis de Blur.
        "mezcla_lactato_calcio": r["usa_lactato"] or ("0" if r["fuente"] == "Cappellesso2024" else ""),
        "mezcla_curado_previo": "1" if r["regimen"] == "curado_previo" else "0",
        "mezcla_agente_cristalino": "1" if r["portador"] == "cristalino" else "0",
        "resultado_edad_dias": r["edad_dias"], "resultado_cierre_pct": r["cierre_pct"],
        "resultado_protocolo": "microscopía óptica superficial (ancho de fisura)",
        "procedencia_doi_o_url": r["doi"], "procedencia_tipo": "dataset",
        "procedencia_ubicacion": f"{r['hoja']} {r['fila_excel']}".strip(), "procedencia_verificado": "si",
        "procedencia_notas": ("lactato de calcio = 0: sin precursor añadido aparte; agente Basilisk de composición "
                              "no declarada" if r["fuente"] == "Cappellesso2024" else ""),
    } for r in filas]


# DOI de los datasets que entran como réplicas (Mousa 2022 en Zenodo; Cappellesso 2024)
DOI_DATASETS = {"10.5281/zenodo.6469122", "10.5281/zenodo.11305154", "10.1016/j.dibe.2024.100486"}


def mapear_literatura() -> list[dict]:
    with open(RAIZ / "datos" / "literatura" / "meta_dataset_cab_v2.csv", encoding="utf-8") as fh:
        filas = [r for r in csv.DictReader(fh) if r["usar_en_modelo"].strip() == "si"]
    salida = []
    for r in filas:
        doi = r["doi"].strip()
        if doi in DOI_DATASETS:          # ya están como réplicas individuales: no se cuentan dos veces
            continue
        salida.append({
            "fuente": r["estudio"][:60], "id_grupo": r["estudio"][:60],
            "zona_ambiente_marino": r["ambiente_marino"], "dano_tipo": "fisura",
            "dano_ancho_fisura_mm": r["ancho_fisura_mm"], "dano_uso": "laboratorio",
            "mezcla_a_c": r["a_c"], "mezcla_nivel_proteccion": r["nivel_proteccion"],
            "mezcla_lactato_calcio": r["usa_lactato"],
            # Deducidos del documento, no imputados:
            # - curado previo = régimen de Cappellesso (curado antes de exponer a agua de mar). Fuera de ese
            #   ensayo no existe: los estudios no marinos nunca van a agua de mar y los marinos de esta tabla
            #   (Palin, Khan) cicatrizan directamente en agua de mar → 0.
            # - agente cristalino: la nota de cada fila describe el agente (bacterias en LWA, hidrogel, cápsulas,
            #   nanocristales de celulosa…); ninguna usa aditivo cristalino → 0.
            "mezcla_curado_previo": "0", "mezcla_agente_cristalino": "0",
            "resultado_edad_dias": r["edad_curado_dias"], "resultado_cierre_pct": r["cierre_fisura_pct"],
            "resultado_alpha": r["alpha_equiv"] if r["alpha_base"].strip() == "referencia" else "",
            "resultado_alpha_propiedad": r["alpha_propiedad"],
            "procedencia_doi_o_url": doi if doi.startswith(("10.", "http")) else "",
            "procedencia_tipo": "articulo", "procedencia_ubicacion": r["ubicacion"] or r["fuente_dato"],
            "procedencia_verificado": r["verificado"] or "no", "procedencia_notas": r["nota"][:200],
        })
    return salida


def main() -> int:
    n1 = _escribir(ENTRANTES / "replicas.csv", mapear_replicas())
    n2 = _escribir(ENTRANTES / "literatura.csv", mapear_literatura())
    print(f"replicas: {n1} · literatura: {n2} -> {ENTRANTES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
