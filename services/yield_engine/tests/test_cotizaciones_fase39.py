"""Tests F39 — cotizaciones de blindaje (documentos reales citados)."""
import json

import pytest

from app.domain.cotizaciones_blindaje import (
    COTIZACIONES,
    comparar,
    validar_suma,
)


def test_ambas_cotizaciones_verifican_aritmetica():
    for nombre in COTIZACIONES:
        r = validar_suma(nombre)
        assert r["estado"] == "verificada", (nombre, r)


def test_totales_contra_documento():
    assert COTIZACIONES["tabique_2p5"]["total_mxn"] == 20_672_979.83
    c = COTIZACIONES["contuplex_3p5"]
    assert c["total_mxn"] == 41_791_379.45
    assert c["subtotal_mxn"] == 36_027_051.25
    assert c["iva_mxn"] == 5_764_328.20


def test_comparacion_derivada_declarada():
    r = comparar()
    assert r["ratio_total"] == pytest.approx(2.0214, rel=1e-3)
    assert r["delta_densidad_g_cm3"] == 1.0
    assert r["total_usd_contuplex"] == pytest.approx(
        41_791_379.45 / 17.71, rel=1e-9)
    assert "sesgo" in r["nota_iva"]
    assert "18.10" in r["nota_honesta"]


def test_unidad_cantidad_pendiente_fuente():
    assert "pendiente_fuente" in COTIZACIONES["tabique_2p5"]["unidad_cantidad"]


def test_serializable_alcoa():
    s = json.dumps({"cotizaciones": COTIZACIONES, "comparacion": comparar()},
                   ensure_ascii=False)
    assert "CONTUPLEX" in s and "20,672,979" not in s  # floats, no formato
