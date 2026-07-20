"""
Tests del Process Twin F3: calendario multi-paciente con decaimiento
entre administraciones e inversa exacta (EOS requerida).
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.application.process_service import ProcessService
from app.domain.dose_calendar import (Appointment, dose_calendar,
                                      required_eos_for_calendar)
from app.domain.entities import Protocol, ProtocolStep

client = TestClient(app)
service = ProcessService()

HL_F18 = 109.77
EOS_T = datetime(2026, 7, 20, 12, 30, tzinfo=timezone.utc)


def _proto(dose=0.37, half_life=HL_F18) -> Protocol:
    return Protocol(
        protocol_id="test", name="Test", nuclide="18F",
        half_life_min=half_life, dose_per_patient_gbq=dose,
        validated=False, source="test",
        steps=(ProtocolStep("sintesis", 30.0, 0.6),))


def _appts(n: int, cada_min: float, dosis: float,
           inicio: datetime = EOS_T) -> list[Appointment]:
    return [Appointment(time=inicio + timedelta(minutes=i * cada_min),
                        dose_gbq=dosis, label=f"P{i + 1}")
            for i in range(n)]


# ---------------- dominio ----------------

def test_primera_cita_en_eos_sin_decaimiento():
    """Cita exactamente en eos_time: inventario = EOS, sin decaimiento."""
    r = dose_calendar(_proto(), 10.0, EOS_T, _appts(1, 30, 0.37))
    s = r.slots[0]
    assert s.inventory_before_gbq == 10.0
    assert s.feasible
    assert math.isclose(s.inventory_after_gbq, 10.0 - 0.37)


def test_decaimiento_entre_citas_exacto():
    """Una vida media entre citas: el inventario se reduce a la mitad."""
    r = dose_calendar(_proto(), 10.0, EOS_T,
                      _appts(1, HL_F18, 0.37, inicio=EOS_T + timedelta(minutes=HL_F18)))
    assert math.isclose(r.slots[0].inventory_before_gbq, 5.0, rel_tol=1e-12)


def test_cita_no_viable_no_descuenta():
    """Dosis que excede el inventario: no viable y no se descuenta."""
    r = dose_calendar(_proto(), 0.5, EOS_T, _appts(1, 30, 1.0))
    s = r.slots[0]
    assert not s.feasible
    assert s.inventory_after_gbq == s.inventory_before_gbq
    assert r.patients_served == 0
    assert r.total_drawn_gbq == 0.0


def test_monotonia_viabilidad():
    """Con dosis iguales, una vez no viable, todas las siguientes tampoco."""
    r = dose_calendar(_proto(), 1.0, EOS_T, _appts(5, 60, 0.37))
    flags = [s.feasible for s in r.slots]
    assert flags == sorted(flags, reverse=True)  # True...False, nunca rebota


def test_citas_desordenadas_se_ordenan():
    appts = [Appointment(EOS_T + timedelta(minutes=60), 0.37, "tarde"),
             Appointment(EOS_T + timedelta(minutes=15), 0.37, "pronto")]
    r = dose_calendar(_proto(), 10.0, EOS_T, appts)
    assert r.slots[0].label == "pronto"
    assert r.slots[1].label == "tarde"


def test_errores_dominio():
    p = _proto()
    with pytest.raises(ValueError):
        dose_calendar(p, 0.0, EOS_T, _appts(1, 30, 0.37))          # EOS <= 0
    with pytest.raises(ValueError):
        dose_calendar(p, 10.0, EOS_T, [])                          # sin citas
    with pytest.raises(ValueError):
        dose_calendar(p, 10.0, EOS_T,
                      [Appointment(EOS_T - timedelta(minutes=5), 0.37)])  # cita < EOS
    with pytest.raises(ValueError):
        dose_calendar(p, 10.0, EOS_T,
                      [Appointment(EOS_T, -0.1)])                  # dosis <= 0


def test_required_eos_invierte_calendario():
    """La EOS requerida sirve exactamente a todos (último queda a ~0)."""
    p = _proto()
    appts = _appts(4, 45, 0.37)
    req = required_eos_for_calendar(p, EOS_T, appts)
    r = dose_calendar(p, req, EOS_T, appts)
    assert r.patients_served == 4
    assert math.isclose(r.remaining_after_last_gbq, 0.0, abs_tol=1e-9)


def test_required_eos_mayor_que_suma_dosis():
    """El decaimiento obliga a producir más que la suma de dosis."""
    appts = _appts(3, 60, 0.37)
    req = required_eos_for_calendar(_proto(), EOS_T, appts)
    assert req > 3 * 0.37


def test_fechas_naive_como_utc():
    r = dose_calendar(_proto(), 10.0, datetime(2026, 7, 20, 12, 30),
                      [Appointment(datetime(2026, 7, 20, 13, 0), 0.37)])
    assert r.slots[0].feasible


# ---------------- API ----------------

def test_api_calendario_basico():
    r = client.post("/api/v1/process/dose-calendar", json={
        "protocol_id": "fdg_18f", "eos_activity_gbq": 66.7,
        "eos_time": "2026-07-20T12:30:00Z",
        "appointments": [
            {"time": "2026-07-20T13:00:00Z", "label": "P1"},
            {"time": "2026-07-20T14:00:00Z", "label": "P2"},
            {"time": "2026-07-20T15:00:00Z", "label": "P3"},
        ]})
    assert r.status_code == 200
    d = r.json()
    assert d["patients_total"] == 3
    assert d["patients_served"] == 3
    # dosis por defecto = la del protocolo
    assert all(math.isclose(s["dose_gbq"], 0.37) for s in d["slots"])
    # inventario decrece cita a cita
    antes = [s["inventory_before_gbq"] for s in d["slots"]]
    assert antes == sorted(antes, reverse=True)
    # EOS requerida < EOS disponible (sobra para estas 3 citas)
    assert d["required_eos_gbq"] < d["eos_activity_gbq"]


def test_api_calendario_limite_viabilidad():
    """Con EOS justa, las últimas citas dejan de ser viables."""
    r = client.post("/api/v1/process/dose-calendar", json={
        "protocol_id": "fdg_18f", "eos_activity_gbq": 1.0,
        "eos_time": "2026-07-20T12:30:00Z",
        "appointments": [
            {"time": "2026-07-20T13:00:00Z"},
            {"time": "2026-07-20T14:00:00Z"},
            {"time": "2026-07-20T15:00:00Z"},
            {"time": "2026-07-20T16:00:00Z"},
        ]})
    d = r.json()
    flags = [s["feasible"] for s in d["slots"]]
    assert flags == sorted(flags, reverse=True)
    assert d["patients_served"] < 4
    assert d["required_eos_gbq"] > 1.0


def test_api_calendario_11c_mas_exigente():
    """11C (T½≈20 min): la misma EOS sirve a menos citas espaciadas."""
    body = {
        "eos_activity_gbq": 2.0, "eos_time": "2026-07-20T12:30:00Z",
        "appointments": [{"time": f"2026-07-20T{13 + i}:00:00Z"} for i in range(4)],
    }
    d11 = client.post("/api/v1/process/dose-calendar",
                      json={"protocol_id": "met_11c", **body}).json()
    d18 = client.post("/api/v1/process/dose-calendar",
                      json={"protocol_id": "fdg_18f", **body}).json()
    assert d11["required_eos_gbq"] > d18["required_eos_gbq"]


def test_api_calendario_errores():
    # protocolo desconocido
    r = client.post("/api/v1/process/dose-calendar", json={
        "protocol_id": "nope", "eos_activity_gbq": 10.0,
        "eos_time": "2026-07-20T12:30:00Z",
        "appointments": [{"time": "2026-07-20T13:00:00Z"}]})
    assert r.status_code == 404
    # EOS inválida
    r = client.post("/api/v1/process/dose-calendar", json={
        "protocol_id": "fdg_18f", "eos_activity_gbq": 0.0,
        "eos_time": "2026-07-20T12:30:00Z",
        "appointments": [{"time": "2026-07-20T13:00:00Z"}]})
    assert r.status_code == 422
    # cita anterior a EOS
    r = client.post("/api/v1/process/dose-calendar", json={
        "protocol_id": "fdg_18f", "eos_activity_gbq": 10.0,
        "eos_time": "2026-07-20T12:30:00Z",
        "appointments": [{"time": "2026-07-20T12:00:00Z"}]})
    assert r.status_code == 422
