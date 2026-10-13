"""Pruebas del módulo de dosis as-built (Fase 53)."""
from __future__ import annotations

import pytest

from app.domain.dosis_asbuilt import (
    FUENTES, H_STAR_PSV_CM2, P_OBJETIVO_USV_SEM, Q_NS,
    dosis_usv_sem, escenario_este, flujo_geometrico,
    verificar_normalizacion_tally)


def test_flujo_geometrico_inverso_cuadratico():
    f1 = flujo_geometrico(1.0)
    f2 = flujo_geometrico(2.0)
    assert f1 / f2 == pytest.approx(4.0, rel=1e-12)
    assert f1 == pytest.approx(Q_NS / (4 * 3.141592653589793 * 1e4),
                               rel=1e-9)
    with pytest.raises(ValueError):
        flujo_geometrico(0.0)


def test_dosis_conversion_unidades():
    # 1 n/cm²/s × 385 pSv·cm² × 1 h = 1,386e-3 µSv
    d = dosis_usv_sem(1.0, 1.0)
    assert d == pytest.approx(385e-12 * 3600 * 1e6, rel=1e-12)
    with pytest.raises(ValueError):
        dosis_usv_sem(1.0, -1.0)


def test_escenario_este_requiere_tvl_extra():
    r = escenario_este()
    assert r["estado"] == "escenario_analitico_citado"
    assert r["dosis_externa_usv_sem"] > P_OBJETIVO_USV_SEM
    assert r["tvl_adicionales_requeridos"] > 0
    assert r["dosis_externa_usv_sem"] == pytest.approx(
        r["dosis_interna_usv_sem"] * 0.0282, rel=1e-9)


def test_verificacion_normalizacion_tally_honesta():
    # el valor real del tally F42b (cara interna ~0,0338/partícula)
    # discrepa ~3,6 órdenes de la ancla geométrica → no_demostrable
    r = verificar_normalizacion_tally(0.0338)
    assert r["estado"] == "no_demostrable_normalizacion_tally"
    assert r["ratio"] > 1e3
    # un valor coherente con 1/4πr² por partícula sí pasaría
    ok = verificar_normalizacion_tally(flujo_geometrico(3.0, q_ns=1.0))
    assert ok["estado"] == "consistente"


def test_fuentes_declaradas():
    for k in ("ISO8529_CF252", "MDPI2025", "NCRP151", "F32_TALYS"):
        assert k in FUENTES
    assert H_STAR_PSV_CM2 == 385.0
