"""Tests del Identity & Access Management (EDS cap. 47)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.presentation.routers import iam_api


@pytest.fixture()
def client():
    iam_api.init()
    return TestClient(app)


def _rol_radioquimico(c: TestClient):
    r = c.post("/api/v1/iam/roles", json={
        "rol": "radioquimico", "descripcion": "Opera síntesis y dispensación",
        "permisos": [{"recurso": "sintesis", "accion": "ejecutar"},
                     {"recurso": "sintesis", "accion": "consultar"}],
        "actor": "admin"})
    assert r.status_code == 200
    return r.json()


def test_identity_registry_tipos_y_unicidad(client):
    c = client
    for iid, tipo in [("u-ana", "usuario"), ("svc-yield", "servicio"),
                      ("plc-01", "dispositivo"), ("agt-plan", "agente_inteligente")]:
        r = c.post("/api/v1/iam/identities", json={
            "identidad_id": iid, "tipo": tipo, "nombre": iid, "actor": "admin"})
        assert r.status_code == 200, (iid, r.text)
    r = c.post("/api/v1/iam/identities", json={
        "identidad_id": "u-ana", "tipo": "usuario", "nombre": "otra", "actor": "admin"})
    assert r.status_code == 422  # identificador único 47.6, nunca sobrescribe
    r = c.post("/api/v1/iam/identities", json={
        "identidad_id": "x-1", "tipo": "robot", "nombre": "x", "actor": "admin"})
    assert r.status_code == 422
    devs = c.get("/api/v1/iam/identities?tipo=dispositivo").json()
    assert [d["identidad_id"] for d in devs] == ["plc-01"]


def test_role_manager_versionado(client):
    c = client
    assert _rol_radioquimico(c)["version"] == 1
    r = c.post("/api/v1/iam/roles", json={
        "rol": "radioquimico", "descripcion": "Rol ampliado",
        "permisos": [{"recurso": "sintesis", "accion": "*"},
                     {"recurso": "dispensacion", "accion": "ejecutar"}],
        "actor": "admin"})
    assert r.json()["version"] == 2  # definición configurable, nunca sobrescrita
    vigente = c.get("/api/v1/iam/roles/radioquimico").json()
    assert vigente["descripcion"] == "Rol ampliado" and vigente["revisiones"] == 2
    v1 = c.get("/api/v1/iam/roles/radioquimico?version=1").json()
    assert v1["permisos"] == [{"recurso": "sintesis", "accion": "ejecutar"},
                              {"recurso": "sintesis", "accion": "consultar"}]


def test_identidad_requiere_roles_existentes(client):
    c = client
    r = c.post("/api/v1/iam/identities", json={
        "identidad_id": "u-x", "tipo": "usuario", "nombre": "x",
        "roles": ["superusuario"], "actor": "admin"})
    assert r.status_code == 422


def test_pep_decision_registrada_y_default_deny(client):
    c = client
    _rol_radioquimico(c)
    c.post("/api/v1/iam/identities", json={
        "identidad_id": "u-ana", "tipo": "usuario", "nombre": "Ana",
        "roles": ["radioquimico"], "actor": "admin"})
    ses = c.post("/api/v1/iam/sessions", json={
        "identidad_id": "u-ana", "origen": "10.0.0.5"}).json()
    ok = c.post("/api/v1/iam/pep/verificar", json={
        "sesion_id": ses["sesion_id"], "recurso": "sintesis",
        "accion": "ejecutar", "contexto": {"turno": "noche"}}).json()
    assert ok["permitido"] is True and ok["identidad_id"] == "u-ana"
    deny = c.post("/api/v1/iam/pep/verificar", json={
        "sesion_id": ses["sesion_id"], "recurso": "sintesis",
        "accion": "eliminar"}).json()
    assert deny["permitido"] is False and "default-deny" in deny["motivo"]
    decisiones = c.get("/api/v1/iam/pep/decisiones?identidad_id=u-ana").json()
    assert len(decisiones) == 2  # TODA decisión registrada (47.8)


def test_session_manager_ciclo_completo(client):
    c = client
    c.post("/api/v1/iam/identities", json={
        "identidad_id": "svc-qc", "tipo": "servicio", "nombre": "QC Engine",
        "actor": "admin"})
    ses = c.post("/api/v1/iam/sessions", json={
        "identidad_id": "svc-qc"}).json()
    assert ses["estado"] == "activa" and ses["renovaciones"] == 0
    ren = c.post(f"/api/v1/iam/sessions/{ses['sesion_id']}/renovar").json()
    assert ren["estado"] == "renovada" and ren["renovaciones"] == 1
    cer = c.post(f"/api/v1/iam/sessions/{ses['sesion_id']}/cerrar").json()
    assert cer["estado"] == "cerrada" and cer["cerrada_en"]
    d = c.post("/api/v1/iam/pep/verificar", json={
        "sesion_id": ses["sesion_id"], "recurso": "sintesis", "accion": "consultar"}).json()
    assert d["permitido"] is False and "cerrada" in d["motivo"]
    hist = c.get("/api/v1/iam/sessions?identidad_id=svc-qc").json()
    assert len(hist) == 1  # trazabilidad completa (47.10)


def test_identidad_suspendida_no_accede(client):
    c = client
    _rol_radioquimico(c)
    c.post("/api/v1/iam/identities", json={
        "identidad_id": "u-luis", "tipo": "usuario", "nombre": "Luis",
        "roles": ["radioquimico"], "actor": "admin"})
    r = c.post("/api/v1/iam/identities/u-luis/estado", json={
        "estado": "suspendida", "actor": "admin", "motivo": "investigación interna"})
    assert r.status_code == 200 and r.json()["estado"] == "suspendida"
    r = c.post("/api/v1/iam/sessions", json={"identidad_id": "u-luis"})
    assert r.status_code == 403  # no puede iniciar sesión


def test_auditoria_alcoa(client):
    c = client
    _rol_radioquimico(c)
    audit = c.get("/api/v1/iam/audit").json()
    assert any(a["accion"] == "rol_definido" and a["actor"] == "admin" for a in audit)
    assert all("timestamp" in a and "version_motor" in a for a in audit)
