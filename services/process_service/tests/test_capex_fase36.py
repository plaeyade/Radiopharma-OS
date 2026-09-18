# -*- coding: utf-8 -*-
"""Tests Fase 36 — CAPEX con cotización real del fabricante."""
import pytest

from app.domain.cost_engine import CostEngine


@pytest.fixture()
def engine(tmp_path):
    return CostEngine(tmp_path / "corridas.json")


def test_kiube_cotizacion_real(engine):
    c = engine.capex_ciclotron("iba_cyclone_kiube")
    assert c["precio"] == 3_435_000 and c["moneda"] == "EUR"
    assert c["estado"] == "cotizacion_real_fabricante"
    assert "2025/8499" in c["fuente"]
    assert "DDP" in c["incoterm"]
    # el alcance aclara que NO es solo el ciclotrón
    assert "NO es el ciclotrón solo" in c["alcance"]


def test_pettrace_declarado_pendiente_documento(engine):
    c = engine.capex_ciclotron("ge_pettrace_840")
    assert c["precio"] == 3_200_000 and c["moneda"] == "USD"
    assert c["estado"] == "declarado_usuario_pendiente_documento"
    assert "FASTlab" in c["alcance"]


def test_modelo_sin_cotizacion_no_se_estima(engine):
    c = engine.capex_ciclotron("ge_pettrace_890")
    assert c["precio"] is None
    assert c["estado"] == "pendiente_cotizacion"
    assert "nunca se estima" in c["nota"]


def test_ciclotron_desconocido_rechazado(engine):
    with pytest.raises(ValueError):
        engine.capex_ciclotron("inventado_9000")


def test_conversion_mxn_marcada_pendiente(engine):
    c = engine.capex_ciclotron("iba_cyclone_kiube")
    assert "pendiente_fuente" in c["conversion_mxn"]


def test_catalogo_capex_completo(engine):
    cap = engine.capex_ciclotrones()
    assert set(cap) == {"iba_cyclone_kiube", "ge_pettrace_840"}
    for v in cap.values():
        assert v["fuente"]  # 49.11: toda entrada tiene fuente
