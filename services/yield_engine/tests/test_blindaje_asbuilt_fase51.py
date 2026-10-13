"""Pruebas del módulo de blindaje as-built (Fase 51)."""
from __future__ import annotations

import pytest

from app.domain.blindaje_asbuilt import (
    FUENTES, TRANSMISION_MURO_ESTE, espesor_para_transmision,
    evaluar_opciones, tvl_efectivo_empirico, tvl_por_densidad)


def test_tvl_empirico_derivado_del_tally():
    r = tvl_efectivo_empirico()
    assert r["estado"] == "empirico_tally_f42b"
    assert r["n_tvl_en_espesor"] == pytest.approx(1.5498, rel=1e-3)
    assert r["tvl_efectivo_m"] == pytest.approx(1.097, rel=1e-2)
    assert r["caveats"]  # nunca vacío


def test_escalado_por_densidad_regla_citada():
    r = tvl_por_densidad(3.5, 1.0)
    assert r["tvl_m"] == pytest.approx(2.35 / 3.5, rel=1e-9)
    assert r["fuente_regla"] == "BIGGS2010"
    with pytest.raises(ValueError):
        tvl_por_densidad(0.0, 1.0)


def test_espesor_para_transmision():
    assert espesor_para_transmision(1e-4, 0.5) == pytest.approx(2.0)
    with pytest.raises(ValueError):
        espesor_para_transmision(1.0, 0.5)


def test_evaluar_opciones_mayor_densidad_menor_espesor():
    r = evaluar_opciones()
    o = r["opciones"]
    assert o["3.5"]["espesor_m_empirico"] < o["2.5"]["espesor_m_empirico"]
    assert o["3.5"]["espesor_m_biggs2010_contraste"] < \
        o["2.5"]["espesor_m_biggs2010_contraste"]
    # ratio inverso de densidades (misma densidad área)
    assert (o["2.5"]["espesor_m_empirico"] / o["3.5"]["espesor_m_empirico"]
            == pytest.approx(3.5 / 2.5, rel=1e-9))
    assert "pendiente_fuente" in r["nota_objetivo"]
    assert "18.10" in r["nota_1810"]


def test_fuentes_y_transmision_declaradas():
    assert "BIGGS2010" in FUENTES and "NCRP151" in FUENTES
    assert TRANSMISION_MURO_ESTE["estado"] == "empirico_tally_f42b"
    assert 0 < TRANSMISION_MURO_ESTE["valor"] < 1
