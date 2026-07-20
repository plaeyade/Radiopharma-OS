"""
Tests del Process Twin F4: plan de campaña (demanda → mínimo número de
lotes viables con decaimiento entre administraciones y turnaround).
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.application.process_service import ProcessService
from app.domain.campaign import plan_campaign
from app.domain.dose_calendar import Appointment, dose_calendar
from app.domain.entities import Protocol, ProtocolStep

client = TestClient(app)
service = ProcessService()

HL_F18 = 109.77
T0 = datetime(2026, 7, 21, 8, 0, tzinfo=timezone.utc)


def _proto(dose=0.37, half_life=HL_F18) -> Protocol:
    return Protocol(
        protocol_id="test", name="Test", nuclide="18F",
        half_life_min=half_life, dose_per_patient_gbq=dose,
        validated=False, source="test",
        steps=(ProtocolStep("sintesis", 30.0, 0.6),))


def _appts(n: int, cada_min: float, dosis: float,
           inicio: datetime = T0) -> list[Appointment]:
    return [Appointment(time=inicio + timedelta(minutes=i * cada_min),
                        dose_gbq=dosis, label=f"P{i + 1}")
            for i in range(n)]


# --- dominio -----------------------------------------------------------------

def test_un_lote_si_cabe_todo():
    proto = _proto()
    appts = _appts(5, 30.0, 0.37)
    r = plan_campaign(proto, appts, capacity_gbq=40.0)
    assert len(r.batches) == 1
    assert r.n_served == 5 and not r.unserved
    b = r.batches[0]
    assert b.eos_time == T0 - timedelta(minutes=30.0)   # prep por defecto
    assert b.required_eos_gbq <= b.capacity_gbq
    assert 0.0 < b.utilization <= 1.0
    assert b.total_dose_gbq == pytest.approx(5 * 0.37)


def test_inversa_exacta_remanente_cero():
    # Servir el grupo con la EOS requerida debe dejar inventario ≈ 0
    proto = _proto()
    appts = _appts(4, 45.0, 0.37)
    r = plan_campaign(proto, appts, capacity_gbq=40.0)
    b = r.batches[0]
    cal = dose_calendar(proto, b.required_eos_gbq, b.eos_time, appts)
    assert cal.remaining_after_last_gbq == pytest.approx(0.0, abs=1e-9)
    assert cal.patients_served == 4


def test_division_por_capacidad():
    proto = _proto()
    appts = _appts(8, 30.0, 0.37)
    r1 = plan_campaign(proto, appts, capacity_gbq=40.0)
    r2 = plan_campaign(proto, appts, capacity_gbq=1.6)
    assert len(r2.batches) > len(r1.batches)
    assert r2.n_served + len(r2.unserved) == 8


def test_monotonia_en_capacidad():
    proto = _proto()
    appts = _appts(10, 30.0, 0.37)
    caps = [2.0, 5.0, 20.0, 100.0]
    nb = [len(plan_campaign(proto, appts, capacity_gbq=c).batches)
          for c in caps]
    assert all(a >= b for a, b in zip(nb, nb[1:]))


def test_turnaround_separa_lotes():
    proto = _proto()
    appts = _appts(6, 30.0, 0.37)
    r = plan_campaign(proto, appts, capacity_gbq=1.6,
                      turnaround_min=240.0)
    for a, b in zip(r.batches, r.batches[1:]):
        assert (b.eos_time - a.eos_time).total_seconds() >= 240.0 * 60.0 - 1e-6


def test_turnaround_puede_dejar_cita_sin_servir():
    proto = _proto()
    # dos citas juntas, capacidad para una sola y turnaround enorme:
    # el segundo lote no puede nacer antes de la segunda cita
    appts = _appts(2, 20.0, 0.37)
    r = plan_campaign(proto, appts, capacity_gbq=0.5,
                      prep_min=30.0, turnaround_min=10000.0)
    assert r.n_served == 1
    assert len(r.unserved) == 1
    assert r.unserved[0].label == "P2"


def test_cita_imposible_no_servida_honesto():
    proto = _proto()
    # una dosis que ni sola cabe en la capacidad
    appts = [Appointment(time=T0, dose_gbq=50.0, label="imposible"),
             Appointment(time=T0 + timedelta(hours=1), dose_gbq=0.37,
                         label="normal")]
    r = plan_campaign(proto, appts, capacity_gbq=40.0)
    assert [a.label for a in r.unserved] == ["imposible"]
    assert r.n_served == 1


def test_citas_desordenadas_se_ordenan():
    proto = _proto()
    appts = _appts(3, 30.0, 0.37)
    appts.reverse()
    r = plan_campaign(proto, appts, capacity_gbq=40.0)
    assert r.batches[0].first_appointment == T0


def test_validaciones_dominio():
    proto = _proto()
    with pytest.raises(ValueError):
        plan_campaign(proto, _appts(2, 30.0, 0.37), capacity_gbq=0.0)
    with pytest.raises(ValueError):
        plan_campaign(proto, [], capacity_gbq=40.0)
    with pytest.raises(ValueError):
        plan_campaign(proto, [Appointment(time=T0, dose_gbq=-1.0)],
                      capacity_gbq=40.0)
    with pytest.raises(ValueError):
        plan_campaign(proto, _appts(2, 30.0, 0.37), capacity_gbq=40.0,
                      prep_min=-5.0)


def test_fisica_decaimiento_en_la_inversa():
    # con citas muy espaciadas la EOS requerida crece por decaimiento
    proto = _proto()
    juntas = plan_campaign(proto, _appts(3, 15.0, 0.37),
                           capacity_gbq=100.0).batches[0]
    lejas = plan_campaign(proto, _appts(3, 110.0, 0.37),
                          capacity_gbq=100.0).batches[0]
    assert lejas.required_eos_gbq > juntas.required_eos_gbq
    assert lejas.required_eos_gbq > 3 * 0.37  # más que la suma de dosis


# --- API ---------------------------------------------------------------------

def _payload(cap=40.0, n=6, cada=30.0):
    return {
        "protocol_id": "fdg_18f",
        "capacity_gbq": cap,
        "prep_min": 30.0,
        "turnaround_min": 240.0,
        "appointments": [
            {"time": (T0 + timedelta(minutes=i * cada))
             .isoformat().replace("+00:00", "Z"),
             "dose_gbq": 0.37, "label": f"P{i + 1}"}
            for i in range(n)],
    }


def test_api_campaign_un_lote():
    resp = client.post("/api/v1/process/campaign", json=_payload())
    assert resp.status_code == 200
    d = resp.json()
    assert d["n_appointments"] == 6 and d["n_served"] == 6
    assert len(d["batches"]) == 1
    b = d["batches"][0]
    assert b["required_eos_gbq"] <= b["capacity_gbq"]
    assert b["utilization"] <= 1.0


def test_api_campaign_divide_y_reporta():
    # citas cada 90 min: caben 2 por lote; el turnaround separa los lotes
    resp = client.post("/api/v1/process/campaign",
                       json=_payload(cap=1.6, cada=90.0))
    assert resp.status_code == 200
    d = resp.json()
    assert len(d["batches"]) >= 2
    assert d["n_served"] + len(d["unserved"]) == d["n_appointments"]
    for a, b in zip(d["batches"], d["batches"][1:]):
        ta = datetime.fromisoformat(a["eos_time"].replace("Z", "+00:00"))
        tb = datetime.fromisoformat(b["eos_time"].replace("Z", "+00:00"))
        assert (tb - ta).total_seconds() >= 240.0 * 60.0 - 1e-6


def test_api_campaign_dosis_por_defecto_del_protocolo():
    p = _payload()
    for a in p["appointments"]:
        del a["dose_gbq"]
    resp = client.post("/api/v1/process/campaign", json=p)
    assert resp.status_code == 200
    assert resp.json()["total_dose_gbq"] == pytest.approx(6 * 0.37)


def test_api_campaign_errores():
    resp = client.post("/api/v1/process/campaign",
                       json=_payload() | {"protocol_id": "no_existe"})
    assert resp.status_code == 404
    resp = client.post("/api/v1/process/campaign",
                       json=_payload() | {"capacity_gbq": -1.0})
    assert resp.status_code == 422
    resp = client.post("/api/v1/process/campaign",
                       json=_payload() | {"appointments": []})
    assert resp.status_code == 422
