# -*- coding: utf-8 -*-
"""Tests del módulo de rutas de neutrones (Fase 31)."""
import pytest

from app.domain import neutron_routes as nr


def test_cuatro_rutas_presentes():
    assert set(nr.RUTAS_NEUTRONES) == {"F-18", "C-11", "N-13", "O-15"}


def test_cada_ruta_tiene_fuente_citada():
    for iso, r in nr.RUTAS_NEUTRONES.items():
        assert r["fuente"], iso
        assert r["origen"] in ("talys_corrida_real", "referencia_canonica")


def test_n13_canal_cerrado():
    r = nr.RUTAS_NEUTRONES["N-13"]
    assert r["sigma_produccion_n_mb"] == 0.0
    assert "CERRADO" in r["fuente"]


def test_orden_tabla_f18_domina():
    filas = nr.tabla_rutas()
    assert filas[0]["isotopo"] == "F-18"
    assert filas[-1]["isotopo"] == "N-13"
    sigmas = [f["sigma_produccion_n_mb"] for f in filas]
    assert sigmas == sorted(sigmas, reverse=True)


def test_valores_talys_reales():
    assert nr.RUTAS_NEUTRONES["O-15"]["sigma_produccion_n_mb"] == pytest.approx(249.32)
    assert nr.RUTAS_NEUTRONES["C-11"]["sigma_produccion_n_mb"] == pytest.approx(149.16)


def test_comparacion_f18_menor_a_uno_en_nuevas_rutas():
    comp = nr.comparacion_f18()
    assert comp["F-18"] == pytest.approx(1.0)
    for iso in ("C-11", "N-13", "O-15"):
        assert comp[iso] < 1.0


def test_implicaciones_marcadas_recomendacion():
    imp = nr.implicaciones_blindaje()
    assert "RECOMENDACIÓN" in imp["naturaleza"]
    assert "18.10" in imp["naturaleza"]
    assert "no incrementan" in imp["conclusion"] or "NO incrementan" in imp["conclusion"]
    assert imp["medicion_bunker"]["fuente"].startswith("Jakubowska")
