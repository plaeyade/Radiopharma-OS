"""Tests del Digital Platform Core (EDS cap. 51)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.presentation.routers import platform_api


@pytest.fixture()
def client():
    platform_api.init()
    return TestClient(app)


def test_catalogo_servicios_e_imagenes_trazables(client):
    c = client
    r = c.post("/api/v1/platform/services", json={
        "servicio_id": "yield-engine", "responsabilidad": "Cálculo de rendimiento",
        "interfaces": ["REST /api/v1/yield"], "actor": "arquitecto"})
    assert r.status_code == 200
    r = c.post("/api/v1/platform/services", json={
        "servicio_id": "yield-engine", "responsabilidad": "otra",
        "interfaces": ["x"], "actor": "arquitecto"})
    assert r.status_code == 422  # nunca sobrescribe
    r = c.post("/api/v1/platform/services/yield-engine/images", json={
        "version": "0.52.0", "dependencias": ["fastapi", "scipy"],
        "configuracion": {"workers": 2}, "actor": "sre", "firma": "sha256:abc"})
    assert r.status_code == 200 and r.json()["firmada"] is True
    r = c.post("/api/v1/platform/services/yield-engine/images", json={
        "version": "0.52.0", "actor": "sre"})
    assert r.status_code == 422  # imagen duplicada: trazabilidad 51.8
    svc = [s for s in c.get("/api/v1/platform/services").json()
           if s["servicio_id"] == "yield-engine"][0]
    assert len(svc["imagenes"]) == 1 and svc["imagenes"][0]["firma"] == "sha256:abc"


def test_despliegue_exige_evidencia(client):
    c = client
    c.post("/api/v1/platform/services", json={
        "servicio_id": "qc-engine", "responsabilidad": "QC",
        "interfaces": ["REST"], "actor": "arquitecto"})
    r = c.post("/api/v1/platform/services/qc-engine/estado", json={
        "estado": "desplegado", "actor": "sre", "evidencia": ""})
    assert r.status_code == 422  # nunca desplegado sin evidencia (51.9/51.17)
    r = c.post("/api/v1/platform/services/qc-engine/estado", json={
        "estado": "desplegado", "actor": "sre",
        "evidencia": "kubectl rollout status OK"})
    assert r.status_code == 422  # además sin imagen registrada
    c.post("/api/v1/platform/services/qc-engine/images", json={
        "version": "1.0.0", "actor": "sre"})
    r = c.post("/api/v1/platform/services/qc-engine/estado", json={
        "estado": "desplegado", "actor": "sre",
        "evidencia": "kubectl rollout status OK"})
    assert r.status_code == 200 and r.json()["estado"] == "desplegado"


def test_config_versionada_con_historial(client):
    c = client
    r = c.post("/api/v1/platform/config", json={
        "clave": "ye.timeout_s", "valor": 30, "entorno": "produccion",
        "vigencia_desde": "2026-08-01", "responsable": "sre",
        "motivo": "valor inicial"})
    assert r.status_code == 200 and r.json()["version"] == 1
    r = c.post("/api/v1/platform/config", json={
        "clave": "ye.timeout_s", "valor": 45, "entorno": "produccion",
        "vigencia_desde": "2026-08-10", "responsable": "sre",
        "motivo": "timeouts en corridas largas"})
    assert r.json()["version"] == 2  # historial completo, nunca reescrito
    p = c.get("/api/v1/platform/config/ye.timeout_s?entorno=produccion").json()
    assert p["valor"] == 45 and p["responsable"] == "sre" and p["revisiones"] == 2
    h = c.get("/api/v1/platform/config/ye.timeout_s/historial").json()
    assert [x["valor"] for x in h] == [30, 45]
    assert h[0]["motivo"] == "valor inicial"  # toda modificación auditada


def test_config_valida_entorno_y_campos(client):
    c = client
    r = c.post("/api/v1/platform/config", json={
        "clave": "x", "valor": 1, "entorno": "laboratorio",
        "vigencia_desde": "2026-08-01", "responsable": "sre", "motivo": "m"})
    assert r.status_code == 422
    r = c.post("/api/v1/platform/config", json={
        "clave": "y", "valor": 1, "entorno": "produccion",
        "vigencia_desde": "2026-08-01", "responsable": "sre", "motivo": ""})
    assert r.status_code == 422  # motivo obligatorio 51.12
    r = c.get("/api/v1/platform/config/inexistente")
    assert r.status_code == 422


def test_auditoria_alcoa(client):
    c = client
    c.post("/api/v1/platform/services", json={
        "servicio_id": "svc-a", "responsabilidad": "r",
        "interfaces": ["REST"], "actor": "arquitecto"})
    audit = c.get("/api/v1/platform/audit").json()
    assert any(a["accion"] == "servicio_registrado" and a["actor"] == "arquitecto"
               for a in audit)
    assert all("timestamp" in a and "version_motor" in a for a in audit)
