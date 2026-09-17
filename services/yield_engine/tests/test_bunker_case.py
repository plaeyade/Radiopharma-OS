# -*- coding: utf-8 -*-
"""Tests del caso de búnker OIEA (Fase 32)."""
import json

import pytest

from app.infrastructure.gate.bunker_case import BunkerCase, build_bunker_case


def test_build_genera_script_y_case(tmp_path):
    p = build_bunker_case(tmp_path, BunkerCase(spectrum_file="/x/nspec_o18.tot"))
    assert p.name == "run_bunker.py"
    case = json.loads((tmp_path / "case.json").read_text())
    assert case["spectrum_file"] == "/x/nspec_o18.tot"
    assert case["physics_list"] == "FTFP_BERT"
    assert "OIEA" in case["geometria"]


def test_script_usa_espectro_real_no_fabricado(tmp_path):
    p = build_bunker_case(tmp_path, BunkerCase(spectrum_file="/x/nspec.tot"))
    src = p.read_text()
    assert 'src.energy.type = "histogram"' in src          # espectro TALYS real
    assert "mono" not in src.split("histogram")[0][-200:]  # sin energía inventada
    assert "G4_CONCRETE" in src                             # muros de concreto
    assert "laberinto" in src                               # laberinto OIEA
    assert 'src.particle = "neutron"' in src


def test_geometria_declarada_pendiente_plano():
    c = BunkerCase(spectrum_file="/x.tot")
    assert "pendiente" in c.geometria and "declarada" in c.geometria


def test_mesh_bins_configurables(tmp_path):
    p = build_bunker_case(tmp_path, BunkerCase(spectrum_file="/x.tot",
                                               mesh_bins=(55, 55, 30)))
    case = json.loads((tmp_path / "case.json").read_text())
    assert case["mesh_bins"] == [55, 55, 30]
