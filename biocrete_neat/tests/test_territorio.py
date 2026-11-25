"""Recolectores de datos del territorio de Blur (sin red: solo lógica y datos ya recogidos)."""
import json

from biocrete_neat.territorio import clima
from biocrete_neat.territorio.registro import DIR, Registro


def test_registro_reemplaza_en_vez_de_acumular(tmp_path):
    r = Registro(tmp_path / "registro.json")
    r.reemplazar("gis:osm", {"canteras": {"estado": "error", "detalle": "timeout"}})
    r.reemplazar("gis:osm", {"canteras": {"estado": "ok", "elementos": 3}})
    r.guardar()
    d = json.loads((tmp_path / "registro.json").read_text(encoding="utf-8"))
    assert d["gis:osm"]["canteras"] == {"estado": "ok", "elementos": 3}
    assert r.resumen() == ["gis:osm: 1/1 capas ok"]


def test_registro_conserva_fecha_si_no_cambia(tmp_path):
    r = Registro(tmp_path / "registro.json")
    r.reemplazar("clima", {"estado": "ok", "celdas": 2})
    f0 = r.datos["clima"]["_fecha"]
    r.datos["clima"]["_fecha"] = "2000-01-01T00:00:00+00:00"
    r.reemplazar("clima", {"estado": "ok", "celdas": 2})
    assert r.datos["clima"]["_fecha"] == "2000-01-01T00:00:00+00:00" != f0


def test_celdas_de_clima_salen_de_la_costa():
    cel = clima.celdas_costeras("PER")
    assert len(cel) > 150
    lats = [float(k.split(",")[0]) for k in cel]
    assert -18.6 < min(lats) and max(lats) < -3.0                 # Tacna–Tumbes
    assert clima.celda(-12.06, -77.13) in cel                     # Callao
    assert clima.celda(-12.0, -72.0) not in cel                   # sierra, lejos del mar


def test_cache_de_clima_cubre_las_celdas_costeras():
    c = clima.leer("PER")["celdas"]
    faltan = [k for k in clima.celdas_costeras("PER") if k not in c]
    assert faltan == [], f"ejecuta python -m biocrete_neat.territorio clima ({len(faltan)} celdas)"
    assert (DIR / "registro.json").exists()
