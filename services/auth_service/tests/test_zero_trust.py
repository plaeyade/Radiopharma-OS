"""Tests del Cybersecurity & Zero Trust Engine (EDS cap. 48).

Verifica: políticas versionadas 48.6, verificación Zero Trust con
default-deny 48.4/48.1 — toda solicitud registrada —, endpoints
conformes 48.10, eventos centralizados 48.7/48.12, detección de
amenazas SOLO sobre eventos reales con disparadores documentados
48.8, segmentación default-deny 48.9 e incidentes vinculados a
evidencia real 48.11.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.presentation.routers import zerotrust_api


@pytest.fixture()
def client() -> TestClient:
    zerotrust_api.init()
    c = TestClient(app)
    assert c.post("/api/v1/security/policies", json={
        "politica_id": "zt-qc-api", "version": "1.0.0",
        "recursos": ["/api/v1/qc/*"], "roles_permitidos": ["operador_qc",
                                                           "jefe_calidad"],
        "requiere_endpoint_conforme": True,
        "usuario": "ciso"}).status_code == 201
    assert c.post("/api/v1/security/endpoints", json={
        "endpoint_id": "ws-qc-01", "identidad": "op-qc-7"}
        ).status_code == 201
    return c


def test_default_deny_sin_politica(client: TestClient) -> None:
    r = client.post("/api/v1/security/verify-access", json={
        "identidad": "op-1", "rol": "operador_qc",
        "recurso": "/api/v1/admin/secret", "endpoint_id": "ws-qc-01"})
    d = r.json()
    assert d["permitido"] is False
    assert "denegado por defecto" in d["motivos"][0]
    # la solicitud denegada queda REGISTRADA (48.1)
    evs = client.get("/api/v1/security/events",
                     params={"tipo": "acceso"}).json()
    assert evs[-1]["resultado"] == "denegado"


def test_acceso_completo_zero_trust(client: TestClient) -> None:
    # endpoint no conforme: denegado aunque el rol sea correcto
    r = client.post("/api/v1/security/verify-access", json={
        "identidad": "op-qc-7", "rol": "operador_qc",
        "recurso": "/api/v1/qc/release", "endpoint_id": "ws-qc-01"})
    assert r.json()["permitido"] is False
    client.post("/api/v1/security/endpoints/ws-qc-01/state",
                json={"estado": "conforme", "usuario": "ciso"})
    r2 = client.post("/api/v1/security/verify-access", json={
        "identidad": "op-qc-7", "rol": "operador_qc",
        "recurso": "/api/v1/qc/release", "endpoint_id": "ws-qc-01"})
    assert r2.json()["permitido"] is True
    assert r2.json()["politica_aplicada"] == "zt-qc-api"
    # rol no permitido: denegado
    r3 = client.post("/api/v1/security/verify-access", json={
        "identidad": "ext-1", "rol": "invitado",
        "recurso": "/api/v1/qc/release", "endpoint_id": "ws-qc-01"})
    assert r3.json()["permitido"] is False


def test_politicas_versionadas(client: TestClient) -> None:
    assert client.post("/api/v1/security/policies", json={
        "politica_id": "zt-qc-api", "version": "1.0.0",
        "recursos": ["/x"], "roles_permitidos": ["y"]}
        ).status_code == 422
    assert client.post("/api/v1/security/policies", json={
        "politica_id": "zt-qc-api", "version": "2.0.0",
        "recursos": ["/api/v1/qc/*"],
        "roles_permitidos": ["jefe_calidad"]}).status_code == 201
    pols = client.get("/api/v1/security/policies").json()
    assert pols[0]["revisiones"] == ["1.0.0", "2.0.0"]


def test_deteccion_sobre_eventos_reales(client: TestClient) -> None:
    # sin eventos: sin alertas — el motor nunca las fabrica
    assert client.get("/api/v1/security/alerts").json() == []
    for _ in range(3):
        client.post("/api/v1/security/events", json={
            "tipo": "intento_fallido", "origen": "10.0.0.55",
            "destino": "/auth/login", "resultado": "credencial_invalida"})
    alerts = client.get("/api/v1/security/alerts").json()
    assert len(alerts) == 1
    a = alerts[0]
    assert a["origen"] == "10.0.0.55"
    assert len(a["eventos_disparadores"]) == 3     # evidencia documentada
    # dos intentos más: no se repite la misma alerta
    client.post("/api/v1/security/events", json={
        "tipo": "intento_fallido", "origen": "10.0.0.55",
        "destino": "/auth/login", "resultado": "credencial_invalida"})
    assert len(client.get("/api/v1/security/alerts").json()) == 1


def test_segmentacion_default_deny(client: TestClient) -> None:
    r = client.get("/api/v1/security/network/check", params={
        "origen": "dmz", "destino": "scada"}).json()
    assert r["permitido"] is False
    assert "denegado por defecto" in r["motivo"]
    client.post("/api/v1/security/network/segments", json={
        "zona": "dmz", "permitidas": ["api-gateway"], "usuario": "net-1"})
    ok = client.get("/api/v1/security/network/check", params={
        "origen": "dmz", "destino": "api-gateway"}).json()
    assert ok["permitido"] is True
    no = client.get("/api/v1/security/network/check", params={
        "origen": "dmz", "destino": "scada"}).json()
    assert no["permitido"] is False


def test_incidentes_vinculados_a_evidencia(client: TestClient) -> None:
    for _ in range(3):
        client.post("/api/v1/security/events", json={
            "tipo": "intento_fallido", "origen": "192.168.1.9",
            "destino": "/auth/login", "resultado": "fallo"})
    alerta = client.get("/api/v1/security/alerts").json()[0]
    # incidente contra alerta inexistente: rechazado (48.11)
    r = client.post("/api/v1/security/incidents", json={
        "incidente_id": "inc-x", "severidad": "alta",
        "descripcion": "x", "alerta_id": "alert-fantasma"})
    assert r.status_code == 422
    r = client.post("/api/v1/security/incidents", json={
        "incidente_id": "inc-2026-001", "severidad": "alta",
        "descripcion": "fuerza bruta contra /auth/login",
        "alerta_id": alerta["alerta_id"], "usuario": "soc-1"})
    assert r.status_code == 201
    client.post("/api/v1/security/incidents/inc-2026-001/actions", json={
        "accion": "bloquear origen en firewall", "usuario": "soc-1",
        "nuevo_estado": "contenido"})
    incs = client.get("/api/v1/security/incidents").json()
    assert incs[0]["estado"] == "contenido"
    assert incs[0]["alerta_id"] == alerta["alerta_id"]
    assert len(incs[0]["acciones"]) == 1


def test_auditoria_seguridad(client: TestClient) -> None:
    aud = client.get("/api/v1/security/audit").json()
    acciones = {a["accion"] for a in aud}
    assert {"registrar_politica", "registrar_endpoint"} <= acciones
    assert all(a["fecha"] for a in aud)
