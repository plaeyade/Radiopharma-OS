"""
Tests del Process Twin F2: planificación inversa (backward scheduling)
y análisis de cuello de botella.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.application.process_service import ProcessService
from app.domain.bottleneck import bottleneck_analysis
from app.domain.entities import Protocol, ProtocolStep
from app.domain.process_chain import simulate_chain
from app.domain.scheduling import backward_schedule, required_eob

client = TestClient(app)
service = ProcessService()

HL_F18 = 109.77
DOSIS = datetime(2026, 7, 20, 14, 0, tzinfo=timezone.utc)


def _proto(steps, half_life=HL_F18, dose=0.37) -> Protocol:
    return Protocol(
        protocol_id="test", name="Test", nuclide="18F",
        half_life_min=half_life, dose_per_patient_gbq=dose,
        validated=False, source="test", steps=tuple(steps))


FDG_STEPS = [ProtocolStep("transferencia", 5.0, 0.98),
             ProtocolStep("sintesis", 30.0, 0.60),
             ProtocolStep("purificacion", 20.0, 0.90),
             ProtocolStep("formulacion", 15.0, 0.95),
             ProtocolStep("transporte", 20.0, 1.0)]


# ---------------- planificación inversa (dominio) ----------------

def test_required_eob_invierte_simulacion():
    """required_eob es la inversa exacta de simulate_chain."""
    p = _proto(FDG_STEPS)
    eob = required_eob(p, 30.0)
    r = simulate_chain(p, eob)
    assert math.isclose(r.eos_activity_gbq, 30.0, rel_tol=1e-9)


def test_required_eob_invalido():
    with pytest.raises(ValueError):
        required_eob(_proto(FDG_STEPS), 0.0)


def test_schedule_linea_temporal():
    """El último paso acaba a la hora de dosis; EOB = inicio del primero."""
    p = _proto(FDG_STEPS)
    r = backward_schedule(p, 30.0, DOSIS, irradiation_time_min=60.0,
                          setup_min=10.0)
    assert r.steps[-1].end == DOSIS
    assert r.eob_time == r.steps[0].start
    # duraciones conservadas
    for s, orig in zip(r.steps, FDG_STEPS):
        delta = (s.end - s.start).total_seconds() / 60.0
        assert math.isclose(delta, orig.duration_min)
    # inicio de haz = EOB - irradiación - preparación
    esperado = r.eob_time - timedelta(minutes=70.0)
    assert r.beam_start == esperado
    # lead total = 70 + 90 = 160 min
    assert math.isclose(r.total_lead_time_min, 160.0)


def test_schedule_actividades_coherentes():
    """Las actividades planificadas coinciden con la simulación hacia delante."""
    p = _proto(FDG_STEPS)
    r = backward_schedule(p, 30.0, DOSIS, irradiation_time_min=60.0)
    fwd = simulate_chain(p, r.eob_required_gbq)
    for s, f in zip(r.steps, fwd.steps):
        assert math.isclose(s.activity_out_gbq, f.activity_out_gbq,
                            rel_tol=1e-12)
    assert math.isclose(fwd.eos_activity_gbq, 30.0, rel_tol=1e-9)
    assert r.patient_doses == fwd.patient_doses


def test_schedule_dosis_naive_es_utc():
    p = _proto(FDG_STEPS)
    r = backward_schedule(p, 30.0, datetime(2026, 7, 20, 14, 0), 60.0)
    assert r.dose_time.tzinfo is not None
    assert r.steps[-1].end == DOSIS


def test_schedule_errores():
    p = _proto(FDG_STEPS)
    with pytest.raises(ValueError):
        backward_schedule(p, 30.0, DOSIS, 0.0)          # irradiación <= 0
    with pytest.raises(ValueError):
        backward_schedule(p, 30.0, DOSIS, 60.0, -5.0)   # setup negativo
    with pytest.raises(ValueError):
        backward_schedule(p, -1.0, DOSIS, 60.0)         # objetivo inválido


# ---------------- cuello de botella (dominio) ----------------

def test_bottleneck_perdidas_suman_total():
    p = _proto(FDG_STEPS)
    b = bottleneck_analysis(p, 100.0)
    suma = sum(s.loss_gbq for s in b.steps)
    assert math.isclose(suma, b.total_loss_gbq, rel_tol=1e-9)
    assert math.isclose(b.total_loss_gbq, 100.0 - b.eos_activity_gbq,
                        rel_tol=1e-9)
    # descomposición decaimiento + eficiencia = pérdida del paso
    for s in b.steps:
        assert math.isclose(s.decay_loss_gbq + s.efficiency_loss_gbq,
                            s.loss_gbq, rel_tol=1e-9)


def test_bottleneck_paso_dominante_es_sintesis():
    """La síntesis (η=0.60) domina las pérdidas del protocolo FDG."""
    b = bottleneck_analysis(_proto(FDG_STEPS), 100.0)
    assert b.dominant_loss_step == "sintesis"


def test_bottleneck_ganancia_tiempo_igual_en_todos_los_pasos():
    """1 min menos en cualquier paso gana lo mismo: EOS·(2^(1/T½)-1)."""
    p = _proto(FDG_STEPS)
    b = bottleneck_analysis(p, 100.0)
    esperado = b.eos_activity_gbq * (2 ** (1.0 / HL_F18) - 1)
    for s in b.steps:
        assert math.isclose(s.eos_gain_1min_faster_gbq, esperado,
                            rel_tol=1e-9)


def test_bottleneck_ganancia_eta_mayor_donde_menor_eta():
    """+1 pp de eficiencia vale más en síntesis (η=0.60) que en purificación."""
    b = bottleneck_analysis(_proto(FDG_STEPS), 100.0)
    ganancias = {s.name: s.eos_gain_1pp_efficiency_gbq for s in b.steps}
    assert ganancias["sintesis"] > ganancias["purificacion"]
    assert ganancias["purificacion"] > ganancias["transferencia"]
    # paso con η=1 no puede mejorar
    assert ganancias["transporte"] == 0.0


def test_bottleneck_paso_corto_sin_ganancia_temporal():
    p = _proto([ProtocolStep("rapido", 0.5, 0.9)])
    b = bottleneck_analysis(p, 100.0)
    assert b.steps[0].eos_gain_1min_faster_gbq == 0.0


# ---------------- API F2 ----------------

def test_api_schedule_por_actividad():
    r = client.post("/api/v1/process/schedule", json={
        "protocol_id": "fdg_18f", "dose_time": "2026-07-20T14:00:00Z",
        "irradiation_time_min": 60.0, "setup_min": 10.0,
        "eos_target_gbq": 30.0})
    assert r.status_code == 200
    d = r.json()
    assert math.isclose(d["total_lead_time_min"], 160.0)
    assert len(d["steps"]) == 5
    assert d["steps"][-1]["end"].startswith("2026-07-20T14:00")
    # inicio de haz 160 min antes de la dosis
    assert d["beam_start"].startswith("2026-07-20T11:20")
    # EOB requerida coherente con el factor global
    unit = client.post("/api/v1/process/simulate", json={
        "protocol_id": "fdg_18f", "eob_activity_gbq": 1.0}).json()
    factor = unit["overall_decay_factor"] * unit["overall_efficiency"]
    assert math.isclose(d["eob_required_gbq"], 30.0 / factor, rel_tol=1e-3)


def test_api_schedule_por_dosis():
    r = client.post("/api/v1/process/schedule", json={
        "protocol_id": "fdg_18f", "dose_time": "2026-07-20T14:00:00Z",
        "irradiation_time_min": 60.0, "target_doses": 80})
    assert r.status_code == 200
    d = r.json()
    assert math.isclose(d["eos_target_gbq"], 80 * 0.37, rel_tol=1e-3)
    assert d["patient_doses"] == 80


def test_api_schedule_sin_objetivo():
    r = client.post("/api/v1/process/schedule", json={
        "protocol_id": "fdg_18f", "dose_time": "2026-07-20T14:00:00Z",
        "irradiation_time_min": 60.0})
    assert r.status_code == 422


def test_api_schedule_protocolo_desconocido():
    r = client.post("/api/v1/process/schedule", json={
        "protocol_id": "nope", "dose_time": "2026-07-20T14:00:00Z",
        "irradiation_time_min": 60.0, "eos_target_gbq": 10.0})
    assert r.status_code == 404


def test_api_bottleneck_fdg():
    r = client.post("/api/v1/process/bottleneck", json={
        "protocol_id": "fdg_18f", "eob_activity_gbq": 108.947})
    assert r.status_code == 200
    d = r.json()
    assert d["dominant_loss_step"] == "sintesis"
    assert len(d["steps"]) == 5
    suma = sum(s["loss_gbq"] for s in d["steps"])
    assert math.isclose(suma, d["total_loss_gbq"], rel_tol=1e-3)


def test_api_bottleneck_protocolo_desconocido():
    r = client.post("/api/v1/process/bottleneck", json={
        "protocol_id": "nope", "eob_activity_gbq": 10.0})
    assert r.status_code == 404


def test_api_bottleneck_eob_invalida():
    r = client.post("/api/v1/process/bottleneck", json={
        "protocol_id": "fdg_18f", "eob_activity_gbq": -1.0})
    assert r.status_code == 422
