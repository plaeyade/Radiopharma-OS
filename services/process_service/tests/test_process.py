"""
Tests del Process Twin: física de la cascada EOB -> EOS, catálogo de
protocolos y API REST.
"""
from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.application.process_service import ProcessService, ProtocolCatalog
from app.domain.entities import Protocol, ProtocolStep
from app.domain.process_chain import decay_factor, simulate_chain

client = TestClient(app)
service = ProcessService()

HL_F18 = 109.77


def _proto(steps, half_life=HL_F18, dose=0.37) -> Protocol:
    return Protocol(
        protocol_id="test", name="Test", nuclide="18F",
        half_life_min=half_life, dose_per_patient_gbq=dose,
        validated=False, source="test", steps=tuple(steps))


# ---------------- física de decaimiento ----------------

def test_decay_factor_una_vida_media():
    assert math.isclose(decay_factor(HL_F18, HL_F18), 0.5, rel_tol=1e-12)


def test_decay_factor_cero_tiempo():
    assert decay_factor(0.0, HL_F18) == 1.0


def test_decay_factor_dos_vidas_medias():
    assert math.isclose(decay_factor(2 * HL_F18, HL_F18), 0.25, rel_tol=1e-12)


def test_decay_factor_vida_media_invalida():
    with pytest.raises(ValueError):
        decay_factor(10.0, 0.0)


def test_decay_factor_duracion_negativa():
    with pytest.raises(ValueError):
        decay_factor(-1.0, HL_F18)


# ---------------- cascada ----------------

def test_cascada_paso_unico_exacto():
    """Un paso de una vida media con η=1 deja exactamente la mitad."""
    p = _proto([ProtocolStep("sintesis", HL_F18, 1.0)])
    r = simulate_chain(p, 100.0)
    assert math.isclose(r.eos_activity_gbq, 50.0, rel_tol=1e-12)
    assert r.steps[0].activity_in_gbq == 100.0
    assert math.isclose(r.steps[0].activity_after_decay_gbq, 50.0, rel_tol=1e-12)


def test_cascada_encadena_pasos():
    """La salida de cada paso es la entrada del siguiente."""
    p = _proto([ProtocolStep("a", 10.0, 0.9),
                ProtocolStep("b", 20.0, 0.8),
                ProtocolStep("c", 5.0, 0.95)])
    r = simulate_chain(p, 100.0)
    for prev, cur in zip(r.steps, r.steps[1:]):
        assert cur.activity_in_gbq == prev.activity_out_gbq
    assert math.isclose(r.eos_activity_gbq, r.steps[-1].activity_out_gbq)


def test_cascada_cierre_analitico():
    """EOS = EOB · 0.5^(Σt/T½) · Πη exactamente."""
    steps = [ProtocolStep("a", 10.0, 0.9), ProtocolStep("b", 25.0, 0.7)]
    r = simulate_chain(_proto(steps), 100.0)
    esperado = 100.0 * 0.5 ** (35.0 / HL_F18) * (0.9 * 0.7)
    assert math.isclose(r.eos_activity_gbq, esperado, rel_tol=1e-12)
    assert math.isclose(r.overall_decay_factor, 0.5 ** (35.0 / HL_F18), rel_tol=1e-12)
    assert math.isclose(r.overall_efficiency, 0.63, rel_tol=1e-12)
    assert r.total_time_min == 35.0


def test_cascada_dosis_floor():
    """Dosis = floor(EOS / dosis_paciente), sin redondeo hacia arriba."""
    p = _proto([ProtocolStep("x", 0.0, 1.0)], dose=0.37)
    r = simulate_chain(p, 1.0)  # EOS=1.0 -> 2.702... dosis
    assert r.patient_doses == 2


def test_cascada_sin_dosis_suficiente():
    p = _proto([ProtocolStep("x", 0.0, 1.0)], dose=0.37)
    r = simulate_chain(p, 0.3)
    assert r.patient_doses == 0


def test_cascada_mas_tiempo_menos_eos():
    corto = simulate_chain(_proto([ProtocolStep("a", 10.0, 1.0)]), 100.0)
    largo = simulate_chain(_proto([ProtocolStep("a", 60.0, 1.0)]), 100.0)
    assert largo.eos_activity_gbq < corto.eos_activity_gbq


def test_cascada_eob_invalido():
    with pytest.raises(ValueError):
        simulate_chain(_proto([ProtocolStep("a", 1.0, 1.0)]), 0.0)


def test_cascada_sin_pasos():
    with pytest.raises(ValueError):
        simulate_chain(_proto([]), 100.0)


def test_cascada_eficiencia_fuera_de_rango():
    with pytest.raises(ValueError):
        simulate_chain(_proto([ProtocolStep("a", 1.0, 0.0)]), 100.0)
    with pytest.raises(ValueError):
        simulate_chain(_proto([ProtocolStep("a", 1.0, 1.5)]), 100.0)


# ---------------- catálogo ----------------

def test_catalogo_tres_protocolos():
    protos = service.list_protocols()
    assert len(protos) == 3
    ids = {p.protocol_id for p in protos}
    assert ids == {"fdg_18f", "met_11c", "psma_68ga"}


def test_catalogo_honestidad_no_validados():
    """Ningún protocolo está validado con datos reales todavía."""
    for p in service.list_protocols():
        assert p.validated is False
        assert p.source


def test_catalogo_get_desconocido():
    with pytest.raises(KeyError):
        service.get_protocol("no_existe")


def test_catalogo_vida_media_coherente():
    assert math.isclose(service.get_protocol("fdg_18f").half_life_min, HL_F18)
    assert math.isclose(service.get_protocol("met_11c").half_life_min, 20.38)
    assert math.isclose(service.get_protocol("psma_68ga").half_life_min, 67.71)


# ---------------- API ----------------

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "process-service"


def test_api_lista_protocolos():
    r = client.get("/api/v1/process/protocols")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    fdg = next(p for p in data if p["protocol_id"] == "fdg_18f")
    assert fdg["n_steps"] == 5
    assert fdg["total_time_min"] == 90.0
    assert fdg["validated"] is False


def test_api_detalle_protocolo():
    r = client.get("/api/v1/process/protocols/met_11c")
    assert r.status_code == 200
    data = r.json()
    assert data["nuclide"] == "11C"
    assert len(data["steps"]) == 5
    assert data["steps"][0]["name"] == "transferencia"


def test_api_protocolo_no_encontrado():
    r = client.get("/api/v1/process/protocols/inexistente")
    assert r.status_code == 404


def test_api_simular_fdg():
    """EOB=100 GBq 18F-FDG: cierre analítico EOS = 100·0.5^(90/109.77)·Πη."""
    r = client.post("/api/v1/process/simulate",
                    json={"protocol_id": "fdg_18f", "eob_activity_gbq": 100.0})
    assert r.status_code == 200
    d = r.json()
    esperado = 100.0 * 0.5 ** (90.0 / HL_F18) * (0.98 * 0.60 * 0.90 * 0.95 * 1.0)
    assert math.isclose(d["eos_activity_gbq"], esperado, rel_tol=1e-4)
    assert d["patient_doses"] == math.floor(esperado / 0.37)
    assert len(d["steps"]) == 5
    # encadenamiento en la respuesta
    for prev, cur in zip(d["steps"], d["steps"][1:]):
        assert math.isclose(cur["activity_in_gbq"], prev["activity_out_gbq"])
    assert d["validated"] is False


def test_api_simular_11c_decae_mucho_mas():
    """Con la misma EOB, 11C (T½≈20 min) pierde mucho más que 18F."""
    body_11c = {"protocol_id": "met_11c", "eob_activity_gbq": 100.0}
    body_18f = {"protocol_id": "fdg_18f", "eob_activity_gbq": 100.0}
    r11 = client.post("/api/v1/process/simulate", json=body_11c).json()
    r18 = client.post("/api/v1/process/simulate", json=body_18f).json()
    assert r11["eos_activity_gbq"] < r18["eos_activity_gbq"] * 0.5


def test_api_simular_protocolo_desconocido():
    r = client.post("/api/v1/process/simulate",
                    json={"protocol_id": "nope", "eob_activity_gbq": 10.0})
    assert r.status_code == 404


def test_api_simular_eob_invalida():
    r = client.post("/api/v1/process/simulate",
                    json={"protocol_id": "fdg_18f", "eob_activity_gbq": 0.0})
    assert r.status_code == 422


def test_api_simular_escala_lineal():
    """La cascada es lineal: doble EOB -> doble EOS y mismo factor."""
    a = client.post("/api/v1/process/simulate",
                    json={"protocol_id": "psma_68ga",
                          "eob_activity_gbq": 10.0}).json()
    b = client.post("/api/v1/process/simulate",
                    json={"protocol_id": "psma_68ga",
                          "eob_activity_gbq": 20.0}).json()
    assert math.isclose(b["eos_activity_gbq"], 2 * a["eos_activity_gbq"],
                        rel_tol=1e-3)  # la API redondea a 4 decimales
    assert math.isclose(a["overall_decay_factor"], b["overall_decay_factor"])
