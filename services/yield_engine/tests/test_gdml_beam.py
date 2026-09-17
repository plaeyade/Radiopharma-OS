# -*- coding: utf-8 -*-
"""Tests Fase 34: GDML del blanco + haz primario parametrizado."""
import xml.etree.ElementTree as ET

import pytest

from app.domain.beam_model import haz_desde_ciclotron
from app.infrastructure.gate.gdml_target import escribir_gdml, info_gdml


def test_info_gdml_desde_catalogo():
    i = info_gdml("agua18_nirta_conical_nb")
    assert i.material_cuerpo == "Nb"
    assert i.radio_mm == pytest.approx(12.0)
    assert i.densidad_contenido == pytest.approx(1.11)
    assert any("escenario declarado" in m for m in i.marcadores)


def test_gdml_valido_xml_y_dimensiones(tmp_path):
    p = escribir_gdml("gas_n2_c11", tmp_path / "t.gdml")
    root = ET.parse(p).getroot()
    assert root.tag == "gdml"
    define = {c.get("name"): c.get("value") for c in root.find("define")}
    assert float(define["R_TGT"]) == pytest.approx(15.0)   # 1,5 cm
    assert float(define["L_TGT"]) == pytest.approx(150.0)  # 15 cm
    mats = [m.get("name") for m in root.find("materials")]
    assert "Havar" in mats and "Cuerpo_Al" in mats


def test_gdml_marcadores_en_comentario(tmp_path):
    p = escribir_gdml("solido_ni64_cu64", tmp_path / "n.gdml")
    txt = p.read_text()
    assert "escenario declarado" in txt
    assert "IAEA Pub1717" in txt or "tabulada" in txt


def test_blanco_desconocido_rechazado(tmp_path):
    with pytest.raises(ValueError):
        escribir_gdml("inventado", tmp_path / "x.gdml")


def test_haz_energia_citada():
    h = haz_desde_ciclotron("ge_pettrace_890", corriente_ua=160.0)
    assert h.energia_mev == 16.5
    assert "PT800" in h.fuente_energia
    assert h.potencia_haz_w() == pytest.approx(2640.0)


def test_haz_perfil_declarado():
    h = haz_desde_ciclotron("abt_bg75", corriente_ua=5.0)
    assert "pendiente de medición" in h.marcador_perfil
    assert h.densidad_pico_w_mm2() == pytest.approx(37.5 / (2 * 3.14159265 * 9), rel=1e-3)


def test_haz_ciclotron_desconocido():
    with pytest.raises(ValueError):
        haz_desde_ciclotron("ciclotron_x", corriente_ua=10.0)
