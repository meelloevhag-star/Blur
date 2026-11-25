"""Pruebas del Atlas. El fixture de paridad lo usa también la prueba de Go (api/internal/modelo)."""
import json
from pathlib import Path

import numpy as np
import pytest

from atlas import niebla as nb
from atlas.diseno_mezcla import dosificar, fc_estimado
from atlas.durabilidad import vida_util, ajuste_drcm
from atlas.ingesta import NOMBRES_CIERRE, dataset_cierre, vector_cierre
from atlas.normas import reglas
from atlas.rutas import MODELOS, RAIZ, SALIDA
from atlas.viabilidad import catalogo

FIXTURE = Path(__file__).parent / "fixture_paridad.json"


def test_dataset_cierre_lee_blur():
    X, y, g, f = dataset_cierre()
    assert X.shape[1] == len(NOMBRES_CIERRE)
    assert len(y) > 2000 and 0 <= y.min() and y.max() <= 1
    assert {"Mousa2022", "Cappellesso2024"} <= set(f)


def test_reglas_mas_estrictas_en_salpicadura():
    assert reglas("salpicadura")["a_c_max"] < reglas("atmosferico_marino")["a_c_max"] < reglas("seco")["a_c_max"]


def test_dosificacion_suma_un_m3():
    c = catalogo()
    r = dosificar(0.45, 19.0, c["cementos"]["IP"] | {"id": "IP"}, 320,
                  {"arena": c["agregados"]["arena"], "piedra": c["agregados"]["piedra_34"]})
    vol = (r["agua_kg"] / 1000 + r["cemento_kg"] / 2850 + r["piedra_kg"] / 2680 + r["arena_kg"] / 2620
           + r["aire_pct"] / 100)
    assert abs(vol - 1.0) < 1e-3   # cantidades redondeadas a 0,1 kg
    assert fc_estimado(0.40) > fc_estimado(0.50)


def test_vida_util_monotona():
    a = vida_util(0.40, "HS", "salpicadura", 500, 20, 65, 0.45)
    b = vida_util(0.50, "HS", "salpicadura", 500, 20, 65, 0.45)
    assert a >= b
    assert vida_util(0.45, "I", "salpicadura", 500, 20, 65, 0.3, cierre_frac=0.9) >= \
        vida_util(0.45, "I", "salpicadura", 500, 20, 65, 0.3, cierre_frac=0.0)
    assert ajuste_drcm()["b"] > 0      # más a/c → más difusión


def test_deposicion_decae_y_niebla_la_extiende():
    amb = {"viento_medio_ms": 5, "frac_horas_niebla": 0.1, "nubes_bajas_media_pct": 40, "frac_horas_hr85": 0.8}
    seco = {"viento_medio_ms": 5, "frac_horas_niebla": 0.0, "nubes_bajas_media_pct": 0, "frac_horas_hr85": 0.0}
    assert nb.deposicion_cloruros(0.1, amb, 1) > nb.deposicion_cloruros(5, amb, 1)
    assert nb.deposicion_cloruros(10, amb, nb.indice_niebla(amb)) > nb.deposicion_cloruros(10, seco, nb.indice_niebla(seco))


@pytest.mark.skipif(not (MODELOS / "modelo_cierre.json").exists(), reason="sin modelo exportado")
def test_fixture_paridad_go():
    """Genera/actualiza el fixture que la prueba de Go compara con tolerancia 1e-9."""
    from atlas.modelos import ModeloCierre, evaluar_neat_json, evaluar_xgb_json
    m = ModeloCierre()
    rng = np.random.default_rng(0)
    casos = []
    for _ in range(50):
        port = ["ninguno", "cristalino", "Basilisk", "LWA", "hidrogel", "CNC"][rng.integers(6)]
        x = vector_cierre(float(rng.uniform(0.05, 0.8)), float(rng.choice([7, 28, 90, 180])), port,
                          int(rng.integers(2)), ["ninguno", "lactato"][rng.integers(2)], int(rng.integers(2)),
                          int(rng.integers(2)))
        xn = np.clip(np.array(x) / m.max, 0, 1)
        bs = np.clip([evaluar_xgb_json(t, 0.5, xn) for t in m.p["xgb"]["bootstrap"]], 0, 1)
        casos.append({"x": x, "xgb_media": float(bs.mean()), "neat": float(evaluar_neat_json(m.p["neat"], xn))})
    FIXTURE.write_text(json.dumps(casos), encoding="utf-8")
    assert all(0 <= c["xgb_media"] <= 1 for c in casos)


@pytest.mark.skipif(not (SALIDA / "zonas_per.geojson").exists(), reason="sin salida construida")
def test_geojson_recetas_completas():
    g = json.loads((SALIDA / "zonas_per.geojson").read_text(encoding="utf-8"))
    assert len(g["features"]) > 300
    for f in g["features"]:
        p = f["properties"]
        for tipo in ("ideal", "economica", "disponible"):
            r = p["recetas"][tipo]
            assert r["agente"] != "ninguno"
            assert r["dosificacion"]["a_c"] <= p["reglas"]["a_c_max"] + 1e-9
            assert r["viabilidad"]["costo_m3_pen"] > 0


# --------------------------------------------------------------------------- v2: relieve, urbano, fuentes

class _DEMSintetico:
    """Ladera que sube hacia el este (tierra adentro, mar al oeste): 0 m en lon −77,0 → 1 200 m en lon −76,8."""

    def muestrear(self, lon, lat):
        return np.clip((np.asarray(lon) + 77.0) / 0.2 * 1200, 0, None).astype(np.float32)


def _zona(lon0, lon1, lat0=-12.05, lat1=-11.95):
    from atlas.zonas import Zona
    pol = [[lon0, lat0], [lon1, lat0], [lon1, lat1], [lon0, lat1], [lon0, lat0]]
    return Zona(id="T", pais="PER", departamento="X", dist_mar_km=7.5,
                lat=(lat0 + lat1) / 2, lon=(lon0 + lon1) / 2, poligono=pol)


def test_ladera_al_mar_en_cinturon_sube_la_niebla():
    from atlas.relieve import estadisticas_zona
    costa = (-77.05, -12.0)
    loma = estadisticas_zona(_DEMSintetico(), _zona(-76.95, -76.88), costa)      # 300–720 m, mira al mar
    llano = estadisticas_zona(_DEMSintetico(), _zona(-77.04, -77.01), costa)     # 0–0 m
    assert loma["frac_loma"] > 0.8 and llano["frac_loma"] == 0
    amb = {"frac_horas_niebla": 0.03, "nubes_bajas_media_pct": 20, "frac_horas_hr85": 0.4, "viento_medio_ms": 4}
    assert nb.indice_niebla_orografica(amb, loma) > nb.indice_niebla_orografica(amb, llano) == nb.indice_niebla(amb)
    assert nb.regimen(3, 50, nb.indice_niebla_orografica(amb, loma), loma) == "niebla_orografica"


def test_cresta_atenua_cloruros():
    amb = {"viento_medio_ms": 5, "frac_horas_niebla": 0.05, "nubes_bajas_media_pct": 20, "frac_horas_hr85": 0.5}
    assert nb.deposicion_cloruros(8, amb, 0.5, barrera_m=800) < 0.1 * nb.deposicion_cloruros(8, amb, 0.5, barrera_m=0)


def test_clase_urbana_umbrales():
    from atlas.urbano import clase_urbana
    assert [clase_urbana(d) for d in (5000, 800, 50, 3)] == ["urbano", "periurbano", "rural", "deshabitado"]


def test_comodines_de_fuentes(tmp_path, monkeypatch):
    import atlas.ingesta as ing
    (tmp_path / "datos" / "replicas" / "lote1").mkdir(parents=True)
    (tmp_path / "datos" / "replicas" / "lote1" / "nuevo.csv").write_text("w0_mm,edad_dias,cierre_pct\n0.2,28,50\n")
    monkeypatch.setattr(ing, "RAIZ", tmp_path)
    f = ing.expandir({"id": "agentes", "ruta": "datos/replicas/**/*.csv", "tipo": "replicas_cierre"})
    assert [x["id"] for x in f] == ["agentes:datos/replicas/lote1/nuevo.csv"]


@pytest.mark.skipif(not (SALIDA / "zonas_per.geojson").exists(), reason="sin salida construida")
def test_malla_hexagonal_sin_huecos_ni_solapes():
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from atlas.zonas import TAM_HEX_KM
    g = json.loads((SALIDA / "zonas_per.geojson").read_text(encoding="utf-8"))
    assert g["metadata"]["malla"]["tipo"] == "hexagonal"
    P = [Polygon(f["geometry"]["coordinates"][0]) for f in g["features"]]
    assert all(p.is_valid for p in P)
    u = unary_union(P)
    assert u.area == pytest.approx(sum(p.area for p in P), rel=1e-4)                     # sin solapes
    assert sum(len(x.interiors) for x in getattr(u, "geoms", [u])) == 0                    # sin huecos
    # tamaño parejo: ninguna celda supera 1,6 veces el hexágono nominal (≈ 87 km² a 10 km)
    km2 = 111.32 ** 2
    import math
    nominal = math.sqrt(3) / 2 * TAM_HEX_KM ** 2
    areas = [p.area * km2 * math.cos(math.radians(p.centroid.y)) for p in P]
    assert max(areas) < 1.6 * nominal
    props = {f["properties"]["distrito"]: f["properties"] for f in g["features"]}
    assert g["metadata"]["poblacion_total_zonas"] == sum(f["properties"]["poblacion"] for f in g["features"])
    lima = [f["properties"] for f in g["features"] if f["properties"]["distrito"] in ("Lima", "Callao")]
    assert any(p["clase_urbana"] == "urbano" for p in lima)
    assert {"Atiquipa", "Colan"} <= set(props)


def test_frente_marino_es_salpicadura():
    g = json.loads((SALIDA / "zonas_per.geojson").read_text(encoding="utf-8"))
    orilla = [f["properties"] for f in g["features"] if f["properties"]["frente_marino"]]
    assert orilla and all(p["frente"]["regimen"] == "salpicadura" for p in orilla)
    assert all(p["frente"] is None for p in (f["properties"] for f in g["features"]) if not p["frente_marino"])


def test_paridad_fick_python_typescript(tmp_path):
    """El visor web (web/src/fick.ts) reproduce la vida útil de durabilidad.py con los parámetros exportados."""
    import shutil
    import subprocess
    from atlas.durabilidad import parametros_fick, vida_util
    esbuild = RAIZ / "web" / "node_modules" / ".bin" / "esbuild"
    if not shutil.which("node") or not esbuild.exists():
        pytest.skip("sin Node o sin web/node_modules (npm ci)")
    casos = [(0.45, "IP", "atmosferico_marino", 80, 19, 50, 0.45, 0.6, "basilisk"),
             (0.55, "I", "salpicadura", 2000, 22, 40, 0.3, 0.0, "ninguno"),
             (0.40, "HS", "niebla_salina", 300, 17, 65, 0.6, 0.4, "cristalino")]
    params = [parametros_fick(*c[:7], cierre_frac=c[7], agente=c[8]) for c in casos]
    esperado = [vida_util(*c[:7], cierre_frac=c[7], agente=c[8]) for c in casos]
    web = RAIZ / "web"
    script = tmp_path / "p.mjs"
    out = tmp_path / "fick.mjs"
    subprocess.run([str(esbuild), str(web / "src" / "fick.ts"), "--format=esm", f"--outfile={out}", "--log-level=error"],
                   cwd=web, check=True)
    script.write_text(f"import {{ anioInicio }} from {json.dumps(str(out))};\n"
                      f"console.log(JSON.stringify({json.dumps(params)}.map((f) => anioInicio(f, 150) ?? 150)));")
    r = subprocess.run(["node", str(script)], capture_output=True, text=True, check=True)
    assert json.loads(r.stdout) == pytest.approx(esperado, abs=1)
