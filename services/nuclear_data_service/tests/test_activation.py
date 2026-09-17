"""Tests Fase 28 — Activación Bateman por isótopo."""
from __future__ import annotations

import math

import pytest

from app.domain.activation import (CULPABLES, ActivacionInvalida,
                                   ActivationEngine, CalculoActivacion)


@pytest.fixture()
def eng() -> ActivationEngine:
    return ActivationEngine()


def _base(**kw) -> CalculoActivacion:
    d = dict(calculo_id="CAL-1", isotopo="Co-60", n_nucleos_padre=1e20,
             flujo_n_cm2_s=1e8, origen_flujo="mesh_tally:pendiente-demo",
             t_pulso_s=3600.0, n_pulsos=1, t_entre_pulsos_s=0.0,
             motivo="test")
    d.update(kw)
    return CalculoActivacion(**d)


def test_culpables_con_fuentes_citadas(eng):
    cat = eng.culpables()
    for iso, c in cat.items():
        assert c["fuente_sigma"], iso
        assert c["fuente_t12"], iso
        assert c["sigma_b"] > 0 and c["t12_s"] > 0
    assert cat["Co-60"]["sigma_b"] == pytest.approx(37.18)


def test_un_pulso_formula_exacta(eng):
    # A = N·σ·φ·(1−e^(−λt)) para un solo pulso sin decaimiento posterior
    r = eng.calcular(_base(), "test")
    lam = math.log(2) / CULPABLES["Co-60"]["t12_s"]
    esperado = 1e20 * 37.18e-24 * 1e8 * (-math.expm1(-lam * 3600.0))
    assert r["actividad_apagado_bq"] == pytest.approx(esperado, rel=1e-12)
    assert r["estado_flujo"] == "flujo_mc_real"


def test_flujo_no_mc_queda_marcado(eng):
    r = eng.calcular(_base(calculo_id="C-2",
                           origen_flujo="declarado: estimación orden de "
                                        "magnitud, pendiente mesh tally"),
                     "test")
    assert r["estado_flujo"] == "flujo_declarado_pendiente_mesh_tally"


def test_decaimiento_tras_enfriamiento(eng):
    t12 = CULPABLES["Na-24"]["t12_s"]
    r = eng.calcular(_base(calculo_id="C-3", isotopo="Na-24",
                           t_enfriamiento_s=t12), "test")
    assert r["actividad_tras_enfriamiento_bq"] == \
        pytest.approx(r["actividad_apagado_bq"] / 2.0, rel=1e-9)


def test_pulsos_acumulan_y_decae_entre_pulsos(eng):
    # Na-24 (T½ 15 h): pulsos diarios de 2 h durante 5 días ≈ cerca del
    # equilibrio; 2 pulsos deben dar MÁS que 1 pulso.
    r1 = eng.calcular(_base(calculo_id="C-4", isotopo="Na-24",
                            t_pulso_s=7200.0, n_pulsos=1,
                            t_entre_pulsos_s=79200.0), "test")
    r5 = eng.calcular(_base(calculo_id="C-5", isotopo="Na-24",
                            t_pulso_s=7200.0, n_pulsos=5,
                            t_entre_pulsos_s=79200.0), "test")
    assert r5["actividad_apagado_bq"] > r1["actividad_apagado_bq"]
    # Co-60 (T½ 5.27 a) no satura en un año de operación (250 lotes)
    r = eng.calcular(_base(calculo_id="C-6", t_pulso_s=7200.0,
                           n_pulsos=250, t_entre_pulsos_s=79200.0),
                     "test")
    assert r["fraccion_saturacion"] < 0.2


def test_duplicado_rechazado(eng):
    eng.calcular(_base(), "test")
    with pytest.raises(ActivacionInvalida):
        eng.calcular(_base(), "test")


def test_sin_origen_flujo_rechazado(eng):
    with pytest.raises(ActivacionInvalida):
        eng.calcular(_base(origen_flujo=" "), "test")


def test_isotopo_fuera_catalogo_exige_fuentes(eng):
    with pytest.raises(ActivacionInvalida):
        eng.calcular(_base(isotopo="Zn-65"), "test")
    r = eng.calcular(_base(
        calculo_id="C-7", isotopo="Zn-65", sigma_b=0.76,
        fuente_sigma="declarada — tabla ENDF", t12_s=243.9 * 86400.0,
        fuente_t12="ENSDF — declarada"), "test")
    assert r["fuente_sigma"].startswith("declarada")


def test_auditoria(eng):
    eng.calcular(_base(), "op1")
    assert eng.auditoria()[0]["accion"] == "calcular_activacion"
