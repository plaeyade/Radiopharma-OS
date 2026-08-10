"""Tests del Enterprise Governance Core (EDS cap. 46).

Verifica: políticas versionadas 46.6, publicación con validación 46.17
(las incompletas permanecen en revisión), reglas declarativas con
evaluación desacoplada 46.7/46.20, Architecture Manager 46.9 con
dependencias, registro oficial 46.10 y auditoría 46.19.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.presentation.routers import governance_api


@pytest.fixture()
def client() -> TestClient:
    governance_api.init()
    return TestClient(app)


def test_politicas_versionadas_y_publicacion(client: TestClient) -> None:
    r = client.post("/api/v1/governance/policies", json={
        "politica_id": "pol-datos-001", "version": "1.0.0",
        "alcance": "gobierno de datos", "vigencia_desde": "2026-01-01",
        "responsable": "cdo",
        "contenido": "toda serie temporal exige calidad y origen"})
    assert r.status_code == 201
    r = client.post("/api/v1/governance/policies/pol-datos-001/publish",
                    json={"usuario": "comite"})
    assert r.json()["estado"] == "publicada"
    # misma versión: nunca sobrescribe
    r2 = client.post("/api/v1/governance/policies", json={
        "politica_id": "pol-datos-001", "version": "1.0.0",
        "alcance": "x", "vigencia_desde": "2027-01-01",
        "responsable": "cdo"})
    assert r2.status_code == 422
    # revisión nueva
    r3 = client.post("/api/v1/governance/policies", json={
        "politica_id": "pol-datos-001", "version": "1.1.0",
        "alcance": "gobierno de datos", "vigencia_desde": "2027-01-01",
        "responsable": "cdo", "contenido": "revisada"})
    assert r3.status_code == 201
    pols = client.get("/api/v1/governance/policies").json()
    assert pols[0]["revisiones"] == ["1.0.0", "1.1.0"]


def test_publicacion_incompleta_queda_en_revision(client: TestClient) -> None:
    client.post("/api/v1/governance/policies", json={
        "politica_id": "pol-incompleta", "version": "1.0.0",
        "alcance": "modelos", "vigencia_desde": "2026-01-01",
        "responsable": "cio"})           # sin contenido
    r = client.post("/api/v1/governance/policies/pol-incompleta/publish",
                    json={})
    assert r.status_code == 422
    assert "revisión" in r.json()["detail"]
    pols = client.get("/api/v1/governance/policies").json()
    assert pols[0]["estado"] == "revision"


def test_reglas_evaluacion_desacoplada(client: TestClient) -> None:
    r = client.post("/api/v1/governance/rules", json={
        "regla_id": "reg-qc-01", "ambito": "procesos",
        "campo": "pureza_radioquimica_pct", "operador": ">=",
        "valor": 95.0, "descripcion": "pureza mínima FDG"})
    assert r.status_code == 201
    ok = client.post("/api/v1/governance/rules/reg-qc-01/evaluate",
                     json={"contexto": {"pureza_radioquimica_pct": 97.5}})
    assert ok.json()["resultado"] is True
    mal = client.post("/api/v1/governance/rules/reg-qc-01/evaluate",
                      json={"contexto": {"pureza_radioquimica_pct": 90.0}})
    assert mal.json()["resultado"] is False
    # campo ausente: resultado honesto null
    na = client.post("/api/v1/governance/rules/reg-qc-01/evaluate",
                     json={"contexto": {"otra_cosa": 1}})
    assert na.json()["resultado"] is None
    # desactivada: no evaluable
    client.post("/api/v1/governance/rules/reg-qc-01/deactivate", json={})
    r2 = client.post("/api/v1/governance/rules/reg-qc-01/evaluate",
                     json={"contexto": {"pureza_radioquimica_pct": 99.0}})
    assert r2.status_code == 422


def test_reglas_validacion(client: TestClient) -> None:
    r = client.post("/api/v1/governance/rules", json={
        "regla_id": "reg-x", "ambito": "inventado", "campo": "a",
        "operador": ">=", "valor": 1})
    assert r.status_code == 422
    r = client.post("/api/v1/governance/rules", json={
        "regla_id": "reg-y", "ambito": "datos", "campo": "a",
        "operador": "~=", "valor": 1})
    assert r.status_code == 422


def test_arquitectura_con_dependencias(client: TestClient) -> None:
    client.post("/api/v1/governance/architecture", json={
        "componente_id": "yield-engine", "dominio": "physics_twin",
        "version": "0.46.0", "interfaces": ["/api/v1/production"],
        "dependencias": ["nuclear-data-service"]})
    client.post("/api/v1/governance/architecture", json={
        "componente_id": "nuclear-data-service", "dominio": "datos",
        "version": "0.46.0"})
    deps = client.get(
        "/api/v1/governance/architecture/yield-engine/dependencies").json()
    assert deps["dependencias"] == ["nuclear-data-service"]
    assert deps["dependencias_no_registradas"] == []
    # dependencia no registrada: marcada honestamente
    client.post("/api/v1/governance/architecture", json={
        "componente_id": "dashboard", "dominio": "presentacion",
        "version": "0.44.0", "dependencias": ["grafana"]})
    deps2 = client.get(
        "/api/v1/governance/architecture/dashboard/dependencies").json()
    assert deps2["dependencias_no_registradas"] == ["grafana"]


def test_registro_oficial_y_auditoria(client: TestClient) -> None:
    client.post("/api/v1/governance/policies", json={
        "politica_id": "pol-1", "version": "1.0.0", "alcance": "datos",
        "vigencia_desde": "2026-01-01", "responsable": "cdo",
        "contenido": "c"})
    client.post("/api/v1/governance/policies/pol-1/publish", json={})
    client.post("/api/v1/governance/rules", json={
        "regla_id": "reg-1", "ambito": "datos", "campo": "x",
        "operador": "==", "valor": 1})
    reg = client.get("/api/v1/governance/registry").json()
    assert reg["n_politicas"] == 1 and reg["politicas_publicadas"] == 1
    assert reg["reglas_activas"] == 1
    aud = client.get("/api/v1/governance/audit").json()
    acciones = {a["accion"] for a in aud}
    assert {"registrar_politica", "publicar_politica",
            "registrar_regla"} <= acciones
    assert all(a["usuario"] and a["fecha"] for a in aud)
