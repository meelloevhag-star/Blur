from hefesto.agentes.calidad import calificar, grado, rango


def test_grado_sale_del_tipo_declarado_no_del_titulo():
    assert grado("info:eu-repo/semantics/bachelorThesis; Título Profesional", "Diseño según norma ISO 9001") == "LIC"
    assert grado("", "Plan maestro de agua potable") == "?"
    assert grado("info:eu-repo/semantics/doctoralThesis") == "DOC"
    assert grado("masterThesis") == "MAG"
    assert grado("info:eu-repo/semantics/report; Título Profesional; Ingeniero Civil") == "LIC"
    assert grado("article", revista="Construction and Building Materials") == "ART-I"
    assert grado("article") == "ART-G"
    assert grado("article", "A review of bacterial self-healing concrete") == "REV"


def test_tier_automatico_nunca_pasa_de_T2():
    c = calificar("doctoralThesis", "autorreparable", "probable", "Concreto autorreparable con bacterias", "ensayos 28 días")
    assert c["tier"] == 2 and c["rango"] == "S"


def test_rangos():
    assert rango(0, "DOC", True, "probable") == "SS+"
    assert rango(0, "LIC", False, "probable") == "SS"
    assert rango(1, "LIC", False, "probable") == "S"
    assert rango(2, "MAG", False, "probable") == "A"
    assert rango(2, "LIC", False, "probable") == "B"
    assert rango(3, "DOC", False, "probable") == "C"
    assert rango(4, "DOC", False, "probable") == "D"
    assert rango(2, "LIC", False, "no") == "D"


def test_confirmado_manda_sobre_provisional():
    c = calificar("bachelorThesis", "cloruros", "probable", "Corrosión en Colán", "", tier_confirmado="1")
    assert c["tier"] == 1 and c["rango"] == "S" and "confirmado" in c["motivo_calidad"]


def test_nuevas_fuentes_y_ss_plus():
    from hefesto.agentes.calidad import aplicado_en_campo
    from hefesto.agentes.repositorios import Tesis, candidato_ss_plus
    assert grado("Technical Report; laboratorio nacional") == "ORG"
    assert grado("info:eu-repo/semantics/report", fuente="SENCICO") == "ORG"
    assert grado("dissertation") == "TES"
    assert aplicado_en_campo("full-scale field application of bacteria-based concrete")
    t = Tesis("X", "h", "u", "Bacteria-based self-healing concrete: full-scale field application",
              resumen="tested specimens", tipo_doc="article", revista="Cement and Concrete Research").clasificar()
    assert t.familia == "autorreparable" and t.aplicado_campo == "si" and candidato_ss_plus(t)
    ru = Tesis("Y", "h2", "u2", "Самовосстанавливающийся бетон с бактериями", resumen="результаты испытаний").clasificar()
    zh = Tesis("Z", "h3", "u3", "微生物自修复混凝土 氯离子 扩散", resumen="试验结果").clasificar()
    assert ru.familia == "autorreparable" and zh.familia == "autorreparable" and zh.tema_cloruros == "si"
