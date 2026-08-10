"""Tests del Clinical Delivery & Dose Management Engine (EDS cap. 32).

Verifica: asignación trazable 32.6, decaimiento EXCLUSIVO vía NNDC 32.8
(503 honesto sin servicio, λ física con cliente inyectado), validación
32.21 (sólo lotes liberados por QC 32.15), secuencia de entrega 32.9,
administración 32.10, reprogramación nunca automática 32.11 y
auditoría 32.23.
"""
import math

import pytest
from fastapi.testclient import TestClient

from app.domain.clinical_delivery import (ClinicalDeliveryEngine,
                                          NndsDecayClient, NndsUnavailable)
from app.main import app
from app.presentation.routers import clinical_api

T12_F18_S = 109.77 * 60.0
LAMBDA_F18 = math.log(2) / T12_F18_S


class _NndsFalso:
    """Doble del NNDC Service: λ física del ¹⁸F (NNDC)."""

    def constante_decaimiento_s(self, nuclide: str) -> float:
        assert nuclide == "F-18"
        return LAMBDA_F18


@pytest.fixture()
def client() -> TestClient:
    clinical_api.init(clinical_api._State(
        ClinicalDeliveryEngine(_NndsFalso())))
    return TestClient(app)


LOTE = {"lote_id": "lote-1", "nuclide": "F-18", "actividad_gbq": 10.0,
        "referencia_temporal": "2026-08-10T08:00:00+00:00",
        "liberado_qc": True}


def _programar(client: TestClient, cita: str = "cita-1") -> None:
    r = client.post("/api/v1/clinical/schedule", json={
        "cita_id": cita, "procedimiento": "PET-FDG",
        "horario": "2026-08-10T10:00:00+00:00", "usuario": "planif-1"})
    assert r.status_code == 201


def _asignar(client: TestClient, dosis: str = "dosis-1", **kw) -> dict:
    cuerpo = {"dosis_id": dosis, "lote_id": "lote-1", "cita_id": "cita-1",
              "actividad_asignada_gbq": 2.0, "volumen_ml": 3.0,
              "destino": "sala-pet-1",
              "instante_administracion": "2026-08-10T09:49:46.2+00:00",
              "lote": LOTE, "usuario": "radiofarm-1"}
    cuerpo.update(kw)
    return client.post("/api/v1/clinical/doses/assign", json=cuerpo)


def test_asignacion_con_decaimiento_nndc_exacto(client: TestClient) -> None:
    _programar(client)
    r = _asignar(client)
    assert r.status_code == 201
    cuerpo = r.json()
    # 109.77 min = T½ exacta: la actividad estimada es la mitad
    assert cuerpo["actividad_estimada_administracion_gbq"] == pytest.approx(
        1.0, rel=1e-3)
    assert cuerpo["fuente_decaimiento"] == "NNDC Service (32.8)"


def test_solo_lotes_liberados_por_qc(client: TestClient) -> None:
    _programar(client)
    r = _asignar(client, lote={**LOTE, "liberado_qc": False})
    assert r.status_code == 422
    assert "32.15" in r.json()["detail"]
    # el rechazo queda auditado
    aud = client.get("/api/v1/clinical/audit").json()
    assert any("rechazada" in a["resultado"] for a in aud)


def test_validacion_impide_exceso_de_actividad(client: TestClient) -> None:
    _programar(client)
    _asignar(client, "dosis-a", actividad_asignada_gbq=8.0)
    r = _asignar(client, "dosis-b", actividad_asignada_gbq=5.0)
    assert r.status_code == 422
    assert "32.21" in r.json()["detail"]


def test_nunca_sobrescribe_dosis_ni_cita(client: TestClient) -> None:
    _programar(client)
    r = client.post("/api/v1/clinical/schedule", json={
        "cita_id": "cita-1", "procedimiento": "PET-FDG",
        "horario": "2026-08-10T11:00:00+00:00"})
    assert r.status_code == 422
    _asignar(client)
    assert _asignar(client).status_code == 422


def test_secuencia_entrega_y_administracion(client: TestClient) -> None:
    _programar(client)
    _asignar(client)
    # administrar sin entrega confirmada: imposible
    r = client.post("/api/v1/clinical/doses/dosis-1/transition",
                    json={"evento": "administracion"})
    assert r.status_code == 422
    # saltarse una transición: imposible
    r = client.post("/api/v1/clinical/doses/dosis-1/transition",
                    json={"evento": "recepcion"})
    assert r.status_code == 422
    for evento in ("preparacion", "despacho", "recepcion",
                   "confirmacion_entrega"):
        r = client.post("/api/v1/clinical/doses/dosis-1/transition",
                        json={"evento": evento, "usuario": "mensajero-1"})
        assert r.status_code == 201
    r = client.post("/api/v1/clinical/doses/dosis-1/transition",
                    json={"evento": "administracion", "usuario": "enf-1"})
    assert r.status_code == 201
    tr = client.get("/api/v1/clinical/doses/dosis-1").json()
    assert tr["estado"] == "administrada"
    assert len(tr["tiempos"]) == 6   # asignación + 4 entrega + administración


def test_reprogramacion_nunca_automatica(client: TestClient) -> None:
    _programar(client)
    r = client.post("/api/v1/clinical/rescheduling/propose", json={
        "cita_id": "cita-1", "retraso_min": 45.0,
        "nuevo_horario": "2026-08-10T10:45:00+00:00", "usuario": "motor"})
    assert r.status_code == 201
    prop = r.json()
    assert prop["estado"] == "pendiente_confirmacion"
    # la cita NO cambia hasta confirmación de usuario autorizado
    prog = client.get("/api/v1/clinical/schedule").json()
    assert prog[0]["horario"] == "2026-08-10T10:00:00+00:00"
    r2 = client.post(
        f"/api/v1/clinical/rescheduling/{prop['propuesta_id']}/confirm",
        json={"usuario_autorizado": "jefe-planta"})
    assert r2.status_code == 200
    prog2 = client.get("/api/v1/clinical/schedule").json()
    assert prog2[0]["horario"] == "2026-08-10T10:45:00+00:00"
    assert prog2[0]["estado"] == "reprogramado"
    # doble confirmación: rechazada
    r3 = client.post(
        f"/api/v1/clinical/rescheduling/{prop['propuesta_id']}/confirm",
        json={"usuario_autorizado": "jefe-planta"})
    assert r3.status_code == 422


def test_auditoria_completa(client: TestClient) -> None:
    _programar(client)
    _asignar(client)
    aud = client.get("/api/v1/clinical/audit").json()
    assert len(aud) >= 2
    assert all(a["usuario"] and a["fecha"] for a in aud)
    assert any(a["accion"] == "asignar_dosis" and a["dosis_id"] == "dosis-1"
               and a["lote_id"] == "lote-1" for a in aud)


def test_decay_status_honesto_sin_nndc(client: TestClient) -> None:
    clinical_api.init(clinical_api._State(
        ClinicalDeliveryEngine(NndsDecayClient(base_url=""))))
    c = TestClient(app)
    r = c.get("/api/v1/clinical/decay-status")
    assert r.status_code == 200
    assert r.json()["nuclear_data_url_configurada"] is False
    # asignación: 503 honesto, nunca λ local simulada
    c.post("/api/v1/clinical/schedule", json={
        "cita_id": "cita-x", "procedimiento": "PET-FDG",
        "horario": "2026-08-10T10:00:00+00:00"})
    r2 = c.post("/api/v1/clinical/doses/assign", json={
        "dosis_id": "dosis-x", "lote_id": "lote-1", "cita_id": "cita-x",
        "actividad_asignada_gbq": 1.0, "volumen_ml": 1.0,
        "destino": "sala-pet-1",
        "instante_administracion": "2026-08-10T09:00:00+00:00",
        "lote": LOTE})
    assert r2.status_code == 503
    with pytest.raises(NndsUnavailable):
        NndsDecayClient(base_url="").constante_decaimiento_s("F-18")
