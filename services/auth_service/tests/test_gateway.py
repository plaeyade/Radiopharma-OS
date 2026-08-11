"""Tests del API Gateway & Integration Layer (EDS cap. 53)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.presentation.routers import gateway_api


@pytest.fixture()
def client():
    gateway_api.init()
    return TestClient(app)


def _api_publicada(c: TestClient) -> str:
    assert c.post("/api/v1/gateway/apis", json={
        "api_id": "yield-api", "version": "1.0.0", "propietario": "fisica",
        "documentacion": "openapi-yield-v1", "rutas": ["/yield", "/health"],
        "actor": "arquitecto"}).status_code == 200
    r = c.post("/api/v1/gateway/apis/yield-api/transicion", json={
        "estado": "publicada", "actor": "arquitecto", "motivo": "validada en OQ"})
    assert r.status_code == 200
    return "yield-api"


def test_registry_versionado_y_compatibilidad(client):
    c = client
    _api_publicada(c)
    r = c.post("/api/v1/gateway/apis/yield-api/versions", json={
        "version": "1.1.0", "documentacion": "openapi-yield-v1.1",
        "rutas": ["/yield", "/health", "/metrics"], "actor": "arquitecto"})
    assert r.status_code == 200 and r.json()["version_vigente"] == "1.1.0"
    r = c.post("/api/v1/gateway/apis/yield-api/versions", json={
        "version": "2.0.0", "documentacion": "doc",
        "rutas": ["/yield"], "actor": "arquitecto"})
    assert r.status_code == 422  # retira /health: incompatible (53.9)
    r = c.post("/api/v1/gateway/apis", json={
        "api_id": "yield-api", "version": "9.9", "propietario": "x",
        "documentacion": "d", "rutas": ["/x"], "actor": "x"})
    assert r.status_code == 422  # catálogo nunca sobrescribe (53.7)


def test_ciclo_de_vida_transiciones(client):
    c = client
    _api_publicada(c)
    r = c.post("/api/v1/gateway/apis/yield-api/transicion", json={
        "estado": "diseno", "actor": "a", "motivo": "m"})
    assert r.status_code == 422  # publicada no vuelve a diseño
    r = c.post("/api/v1/gateway/apis/yield-api/transicion", json={
        "estado": "retirada", "actor": "arquitecto",
        "motivo": "sustituida por yield-api v2"})
    assert r.status_code == 200 and r.json()["retirada_en"]
    r = c.post("/api/v1/gateway/apis/yield-api/versions", json={
        "version": "9.0", "documentacion": "d",
        "rutas": ["/yield", "/health"], "actor": "a"})
    assert r.status_code == 422  # retirada no admite versiones


def test_validacion_de_solicitudes_registrada(client):
    c = client
    _api_publicada(c)
    ok = c.post("/api/v1/gateway/validate", json={
        "api_id": "yield-api", "version": "1.0.0", "ruta": "/yield",
        "consumidor": "dashboard"}).json()
    assert ok["resultado"] == "admitida"
    bad = c.post("/api/v1/gateway/validate", json={
        "api_id": "yield-api", "version": "1.0.0", "ruta": "/admin",
        "consumidor": "dashboard"}).json()
    assert bad["resultado"] == "rechazada" and "ruta no publicada" in bad["motivo"]
    ghost = c.post("/api/v1/gateway/validate", json={
        "api_id": "api-fantasma", "version": "1", "ruta": "/x",
        "consumidor": "dashboard"}).json()
    assert ghost["resultado"] == "rechazada"  # nunca enruta a lo inexistente
    inter = c.get("/api/v1/gateway/interactions?api_id=yield-api").json()
    assert len(inter) == 2  # TODA interacción registrada (53.12)


def test_traffic_manager_limita_de_verdad(client):
    c = client
    _api_publicada(c)
    r = c.post("/api/v1/gateway/apis/yield-api/traffic-policy", json={
        "max_solicitudes": 2, "ventana_s": 3600, "actor": "sre"})
    assert r.status_code == 200
    for i in range(2):
        res = c.post("/api/v1/gateway/validate", json={
            "api_id": "yield-api", "version": "1.0.0", "ruta": "/yield",
            "consumidor": "scheduler"}).json()
        assert res["resultado"] == "admitida"
    res = c.post("/api/v1/gateway/validate", json={
        "api_id": "yield-api", "version": "1.0.0", "ruta": "/yield",
        "consumidor": "scheduler"}).json()
    assert res["resultado"] == "limitada" and "excedido" in res["motivo"]  # 53.11
    # otro consumidor no está limitado por la cuota ajena
    res = c.post("/api/v1/gateway/validate", json={
        "api_id": "yield-api", "version": "1.0.0", "ruta": "/yield",
        "consumidor": "otro"}).json()
    assert res["resultado"] == "admitida"


def test_integraciones_documentadas(client):
    c = client
    _api_publicada(c)
    r = c.post("/api/v1/gateway/integrations", json={
        "integracion_id": "int-his", "tipo": "clinica", "sistema": "HIS central",
        "documentacion": "HL7 FHIR R4 — convenio 2026-08",
        "apis": ["yield-api"], "actor": "integrador"})
    assert r.status_code == 200 and r.json()["estado"] == "activa"
    r = c.post("/api/v1/gateway/integrations", json={
        "integracion_id": "int-x", "tipo": "clinica", "sistema": "s",
        "documentacion": "", "apis": [], "actor": "integrador"})
    assert r.status_code == 422  # documentación obligatoria (53.8)
    r = c.post("/api/v1/gateway/integrations", json={
        "integracion_id": "int-y", "tipo": "clinica", "sistema": "s",
        "documentacion": "doc", "apis": ["api-fantasma"], "actor": "i"})
    assert r.status_code == 422  # APIs referenciadas deben existir


def test_estado_proxy_honesto_y_auditoria(client):
    c = client
    _api_publicada(c)
    proxy = c.get("/api/v1/gateway/proxy").json()
    assert proxy["proxy_externo"] == "no_configurado"
    audit = c.get("/api/v1/gateway/audit").json()
    assert any(a["accion"] == "api_transicion" for a in audit)
    assert all("timestamp" in a and "version_motor" in a for a in audit)
