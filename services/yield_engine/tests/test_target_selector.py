# -*- coding: utf-8 -*-
"""Tests del selector de blancos FEM/MC (Fase 32)."""
import pytest

from app.domain.target_selector import (
    BLANCOS_SELECCIONABLES, catalogo_blancos,
    caso_fem_desde_blanco, caso_mc_desde_blanco,
)


def test_seis_blancos_catalogados():
    assert len(BLANCOS_SELECCIONABLES) == 6
    assert {"agua18_ag_estandar", "agua18_nirta_conical_nb", "agua18_cuerpo_ta",
            "agua_natural_n13", "gas_n2_c11", "solido_ni64_cu64"} == set(BLANCOS_SELECCIONABLES)


def test_todo_blanco_tiene_fuentes():
    for bid, b in BLANCOS_SELECCIONABLES.items():
        assert b["fuente_densidad"], bid
        assert b["fuente_conductividad"], bid


def test_fem_usa_conductividad_del_cuerpo():
    caso = caso_fem_desde_blanco("agua18_nirta_conical_nb", beam_power_w=500.0)
    assert caso.conductivity_w_cm_k == pytest.approx(0.537)  # Nb
    caso_ta = caso_fem_desde_blanco("agua18_cuerpo_ta", beam_power_w=500.0)
    assert caso_ta.conductivity_w_cm_k == pytest.approx(0.57)  # Ta
    caso_ag = caso_fem_desde_blanco("agua18_ag_estandar", beam_power_w=500.0)
    assert caso_ag.conductivity_w_cm_k == pytest.approx(4.15)  # Ag


def test_fem_geometria_del_blanco():
    caso = caso_fem_desde_blanco("gas_n2_c11", beam_power_w=200.0)
    assert caso.spot_radius_cm == pytest.approx(1.5)
    assert caso.target_thickness_cm == pytest.approx(15.0)


def test_mc_densidad_y_geometria():
    caso = caso_mc_desde_blanco("solido_ni64_cu64", beam_energy_mev=16.5)
    assert caso.target_density_g_cm3 == pytest.approx(8.9)
    assert caso.target_thickness_cm == pytest.approx(0.02)
    caso_gas = caso_mc_desde_blanco("gas_n2_c11")
    assert caso_gas.target_density_g_cm3 == pytest.approx(0.0224)


def test_blanco_desconocido_rechazado():
    with pytest.raises(ValueError):
        caso_fem_desde_blanco("blanco_inventado", beam_power_w=100.0)
    with pytest.raises(ValueError):
        caso_mc_desde_blanco("blanco_inventado")


def test_catalogo_expone_todo():
    cat = catalogo_blancos()
    assert cat is BLANCOS_SELECCIONABLES
    assert cat["gas_n2_c11"]["tipo"] == "gaseoso"
