"""Tests Fase 28 — Sistema de vacío (bombas + tramos/mangueras)."""
from __future__ import annotations

import pytest

from app.domain.facility_twin import Activo, FacilityTwin
from app.domain.vacuum_system import (BombaVacio, MedicionVacio, TramoLinea,
                                      VacioInvalido, VacuumSystem)

UMBRAL = "declaración interna — pendiente manual del fabricante (49.11)"


@pytest.fixture()
def vs() -> VacuumSystem:
    twin = FacilityTwin()
    twin.registrar_activo(Activo(activo_id="CYC-1", tipo="equipo",
                                 nombre="Ciclotrón"), "test")
    v = VacuumSystem(twin)
    v.registrar_bomba(BombaVacio(
        bomba_id="BP-001", tipo="turbomolecular", activo_id="CYC-1",
        presion_base_ref_pa=1e-5, factor_degradacion=2.0,
        horas_mantenimiento=8000.0, fuente_umbral=UMBRAL), "test")
    v.registrar_tramo(TramoLinea(
        tramo_id="MANG-001", tipo="manguera", activo_id="CYC-1",
        umbral_fuga_mbar_l_s=1e-6, umbral_caida_presion_pa=50.0,
        fuente_umbral=UMBRAL), "test")
    return v


def test_registro_y_marcador_umbral(vs):
    assert vs.salud_bomba("BP-001")["estado_umbral"] == \
        "declarado_interno_pendiente_fuente"
    assert vs.salud_tramo("MANG-001")["estado_umbral"] == \
        "declarado_interno_pendiente_fuente"


def test_duplicado_rechazado(vs):
    with pytest.raises(VacioInvalido):
        vs.registrar_bomba(BombaVacio(
            bomba_id="BP-001", tipo="criogenica", activo_id="CYC-1",
            presion_base_ref_pa=1e-6, factor_degradacion=2.0,
            horas_mantenimiento=100.0, fuente_umbral="f"), "test")


def test_medicion_sin_origen_rechazada(vs):
    with pytest.raises(VacioInvalido):
        vs.registrar_medicion("BP-001", MedicionVacio(
            variable="presion_base_pa", valor=1e-5, origen=" "), "test")


def test_variable_incorrecta_rechazada(vs):
    with pytest.raises(VacioInvalido):
        vs.registrar_medicion("BP-001", MedicionVacio(
            variable="tasa_fuga_mbar_l_s", valor=1e-7, origen="x"), "test")


def test_bomba_degradada_roja_con_recomendacion(vs):
    vs.registrar_medicion("BP-001", MedicionVacio(
        variable="presion_base_pa", valor=2.5e-5,
        origen="prueba vacío base T-2026-09"), "test")
    s = vs.salud_bomba("BP-001")
    assert s["estado"] == "rojo"
    assert s["factor_actual"] == pytest.approx(2.5)
    assert "RECOMENDACIÓN" in s["recomendacion"]
    assert "18.10" in s["recomendacion"]


def test_bomba_horas_acumuladas_ambar(vs):
    for _ in range(7):
        vs.registrar_medicion("BP-001", MedicionVacio(
            variable="horas_operacion", valor=1000.0,
            origen="turno registrado"), "test")
    s = vs.salud_bomba("BP-001")
    assert s["horas_operacion"] == 7000.0
    assert s["estado"] == "ambar"


def test_bomba_sin_mediciones_honesta(vs):
    s = vs.salud_bomba("BP-001")
    assert s["presion_base_actual_pa"] is None
    assert s["factor_actual"] == "sin_mediciones"
    assert s["estado"] == "verde"


def test_tramo_fuga_roja(vs):
    vs.registrar_medicion("MANG-001", MedicionVacio(
        variable="tasa_fuga_mbar_l_s", valor=5e-6,
        origen="prueba He leak detector P-114"), "test")
    s = vs.salud_tramo("MANG-001")
    assert s["estado"] == "rojo"
    assert any("FUGA" in c for c in s["causas"])


def test_tramo_caida_presion_ambar(vs):
    vs.registrar_medicion("MANG-001", MedicionVacio(
        variable="caida_presion_pa", valor=80.0,
        origen="manómetros extremos, lectura registrada"), "test")
    s = vs.salud_tramo("MANG-001")
    assert s["estado"] == "ambar"


def test_tablero_y_auditoria(vs):
    t = vs.tablero()
    assert len(t["bombas"]) == 1 and len(t["tramos"]) == 1
    vs.registrar_medicion("MANG-001", MedicionVacio(
        variable="tasa_fuga_mbar_l_s", valor=1e-8, origen="prueba He"),
        "op1")
    assert any(a["accion"] == "registrar_medicion"
               for a in vs.auditoria())
