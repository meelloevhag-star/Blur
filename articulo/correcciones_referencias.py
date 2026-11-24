"""
F6 · Correcciones de referencias verificadas contra Crossref y DataCite (24-11-2026).

Lo usan generar_articulo.py y generar_revista.py, de modo que ambos documentos salen corregidos.
"""

CORRECCIONES = [
    # [15] El DOI original apuntaba a un artículo de geopolímeros; Crossref confirma el correcto.
    ("doi: 10.1016/j.conbuildmat.2015.05.059", "doi: 10.1016/j.conbuildmat.2015.03.117"),
    # [12] DataCite: publicationYear = 2021.
    ("simulated subtropical climate,” Zenodo Dataset, 2022,", "simulated subtropical climate,” Zenodo Dataset, 2021,"),
    # [10] DataCite: publicationYear = 2025 (faltaba el año); el DOI es de Dryad.
    ("rapid chloride migration test,” Dryad / Zenodo Dataset, doi:", "rapid chloride migration test,” Dryad Dataset, 2025, doi:"),
]


def corregir(texto: str) -> str:
    for viejo, nuevo in CORRECCIONES:
        texto = texto.replace(viejo, nuevo)
    return texto
