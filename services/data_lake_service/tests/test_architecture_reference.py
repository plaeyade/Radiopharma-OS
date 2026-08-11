"""Tests de Deployment Technology Reference y Master Reference
Architecture (EDS caps. 59+60)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.presentation.routers import archref_api


@pytest.fixture()
def client():
    archref_api.init()
    return TestClient(app)


def test_capas_tecnologicas_canonicas(client):
    c = client
    r = c.get("/api/v1/architecture/tech-layers").json()
    assert r["capas"] == ["presentacion", "apis", "servicios", "eventos",
                          "persistencia", "analitica", "inteligencia_artificial",
                          "infraestructura"]
    assert "referencia" in r["nota"]  # recomendadas, nunca impuestas (59.6)


def test_decisiones_tecnologia_versionadas(client):
    c = client
    r = c.post("/api/v1/architecture/tech-decisions", json={
        "capa": "persistencia", "tecnologia": "PostgreSQL 16",
        "estado": "seleccionada", "justificacion": "metadatos transaccionales ALCOA+",
        "responsable": "comite-arquitectura"})
    assert r.status_code == 200 and r.json()["version"] == 1
    r = c.post("/api/v1/architecture/tech-decisions", json={
        "capa": "persistencia", "tecnologia": "InfluxDB",
        "estado": "seleccionada", "justificacion": "series temporales de telemetría",
        "responsable": "comite-arquitectura"})
    assert r.json()["version"] == 2  # nunca reescritas
    r = c.post("/api/v1/architecture/tech-decisions", json={
        "capa": "nube", "tecnologia": "x", "estado": "seleccionada",
        "justificacion": "j", "responsable": "r"})
    assert r.status_code == 422
    r = c.post("/api/v1/architecture/tech-decisions", json={
        "capa": "persistencia", "tecnologia": "x", "estado": "seleccionada",
        "justificacion": "", "responsable": "r"})
    assert r.status_code == 422  # justificación obligatoria
    decs = c.get("/api/v1/architecture/tech-decisions?capa=persistencia").json()
    assert len(decs) == 2 and all(d["justificacion"] for d in decs)


def test_arquitectura_maestra_canonica(client):
    c = client
    capas = c.get("/api/v1/architecture/master-layers").json()
    assert capas["n"] == 10 and "gemelos_digitales" in capas["capas"]
    vols = c.get("/api/v1/architecture/volumes").json()
    assert len(vols["volumenes"]) == 10
    assert vols["volumenes"][7]["dominio"] == "Enterprise Intelligence & AI Twin"


def test_flujo_general_canonico_no_redfinible(client):
    c = client
    f = c.get("/api/v1/architecture/flows/general").json()
    assert f["etapas"] == ["sensores", "sistemas_operacionales", "gemelos_digitales",
                           "event_bus", "plataforma_datos",
                           "inteligencia_artificial", "soporte_decision_ejecutiva"]
    r = c.post("/api/v1/architecture/flows/general", json={
        "etapas": ["otra"], "actor": "x"})
    assert r.status_code == 422  # 60.7 canónico


def test_flujos_integrales_y_coherencia_real(client):
    c = client
    coh = c.get("/api/v1/architecture/coherence").json()
    assert coh["coherente"] is False  # honesto: faltan flujos
    assert "cientifico" in coh["flujos_pendientes"]
    for flujo, etapas in {
        "cientifico": ["sensores", "gemelos_digitales", "plataforma_datos"],
        "operacional": ["sistemas_operacionales", "gemelos_digitales", "event_bus"],
        "economico": ["gemelos_digitales", "plataforma_datos"],
        "documental": ["servicios_negocio", "plataforma_datos"],
        "regulatorio": ["seguridad_gobernanza", "plataforma_datos"],
        "inteligencia_artificial": ["plataforma_datos", "inteligencia_artificial"],
        "infraestructura": ["infraestructura_tecnologica",
                            "observabilidad_operaciones"],
    }.items():
        r = c.post(f"/api/v1/architecture/flows/{flujo}",
                   json={"etapas": etapas, "actor": "arquitecto"})
        assert r.status_code == 200, flujo
    r = c.post("/api/v1/architecture/flows/cientifico",
               json={"etapas": ["x"], "actor": "y"})
    assert r.status_code == 422  # nunca se reescribe
    r = c.post("/api/v1/architecture/flows/magico",
               json={"etapas": ["x"], "actor": "y"})
    assert r.status_code == 422
    coh = c.get("/api/v1/architecture/coherence").json()
    assert coh["coherente"] is True  # calculada sobre el registro real


def test_auditoria_alcoa(client):
    c = client
    c.post("/api/v1/architecture/tech-decisions", json={
        "capa": "apis", "tecnologia": "FastAPI", "estado": "seleccionada",
        "justificacion": "REST tipado con validación", "responsable": "comite"})
    audit = c.get("/api/v1/architecture/audit").json()
    assert any(a["accion"] == "decision_tecnologia" and a["actor"] == "comite"
               for a in audit)
    assert all("timestamp" in a and "version_motor" in a for a in audit)
