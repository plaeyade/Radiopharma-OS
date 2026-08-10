"""Tests del MLOps & AI Lifecycle Management Engine (EDS cap. 42).

Verifica: datasets versionados 42.6, Experiment Tracker con dataset
exacto obligatorio 42.7, Model Registry 42.8 — sólo aprobados se
despliegan —, aprobación con validación 42.20 (en revisión si
incompleto), reversiones/retiros documentados 42.9, Monitoring 42.10
y gestión temporal 42.12.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.presentation.routers import mlops_api


@pytest.fixture()
def client() -> TestClient:
    mlops_api.init()
    c = TestClient(app)
    assert c.post("/api/v1/mlops/datasets", json={
        "dataset_id": "ds-yield", "origen": "yield_engine:calibracion",
        "version": "1.0.0", "fecha": "2026-06-01",
        "n_registros": 41, "usuario": "ml-1"}).status_code == 201
    assert c.post("/api/v1/mlops/experiments", json={
        "experimento_id": "exp-001", "modelo_id": "surrogate-yield",
        "algoritmo": "ridge-loglog-g5",
        "hiperparametros": {"alpha": 1e-3, "grado": 5},
        "dataset_id": "ds-yield", "dataset_version": "1.0.0",
        "metricas": {"rmse_pct": 1.7}, "usuario": "ml-1"}
        ).status_code == 201
    return c


def test_datasets_versionados(client: TestClient) -> None:
    assert client.post("/api/v1/mlops/datasets", json={
        "dataset_id": "ds-yield", "origen": "x", "version": "1.0.0",
        "fecha": "2026-07-01"}).status_code == 422
    assert client.post("/api/v1/mlops/datasets", json={
        "dataset_id": "ds-yield", "origen": "yield_engine:v2",
        "version": "2.0.0", "fecha": "2026-07-01",
        "n_registros": 61}).status_code == 201
    ds = client.get("/api/v1/mlops/datasets").json()
    assert ds[0]["versiones"] == ["1.0.0", "2.0.0"]


def test_experimento_exige_dataset_exacto(client: TestClient) -> None:
    r = client.post("/api/v1/mlops/experiments", json={
        "experimento_id": "exp-002", "modelo_id": "otro",
        "algoritmo": "xgb", "hiperparametros": {},
        "dataset_id": "ds-yield", "dataset_version": "9.9.9",
        "metricas": {}})
    assert r.status_code == 422
    assert "reproducibilidad" in r.json()["detail"]


def test_solo_aprobados_se_despliegan(client: TestClient) -> None:
    client.post("/api/v1/mlops/models", json={
        "modelo_id": "surrogate-yield", "version": "1.0.0",
        "experimento_id": "exp-001", "usuario": "ml-1"})
    # desplegar sin aprobar: rechazado (42.8)
    r = client.post("/api/v1/mlops/models/surrogate-yield/deploy",
                    json={"entorno": "produccion"})
    assert r.status_code == 422
    assert "42.8" in r.json()["detail"]
    # aprobar sin documentación: queda en revisión (42.20)
    r2 = client.post("/api/v1/mlops/models/surrogate-yield/approve",
                     json={"responsable": "comite-ia"})
    assert r2.status_code == 422
    modelos = client.get("/api/v1/mlops/models").json()
    assert modelos[0]["estado"] == "en_revision"
    # aprobación completa y despliegue
    r3 = client.post("/api/v1/mlops/models/surrogate-yield/approve",
                     json={"responsable": "comite-ia",
                           "documentacion": "model-card-v1"})
    assert r3.json()["estado"] == "aprobado"
    r4 = client.post("/api/v1/mlops/models/surrogate-yield/deploy",
                     json={"entorno": "produccion", "usuario": "sre-1"})
    assert r4.status_code == 200
    assert r4.json()["accion"] == "despliegue"


def test_reversion_y_retiro_documentados(client: TestClient) -> None:
    client.post("/api/v1/mlops/models", json={
        "modelo_id": "surrogate-yield", "version": "1.0.0",
        "experimento_id": "exp-001"})
    client.post("/api/v1/mlops/models/surrogate-yield/approve", json={
        "responsable": "comite", "documentacion": "mc-v1"})
    client.post("/api/v1/mlops/models/surrogate-yield/deploy",
                json={"entorno": "produccion"})
    r = client.post("/api/v1/mlops/models/surrogate-yield/revert",
                    json={"motivo": "drift detectado", "usuario": "sre"})
    assert r.json()["estado"] == "revertido"
    # revertir sin estar desplegado: rechazado
    assert client.post("/api/v1/mlops/models/surrogate-yield/revert",
                       json={"motivo": "x"}).status_code == 422
    r2 = client.post("/api/v1/mlops/models/surrogate-yield/retire",
                     json={"usuario": "comite"})
    assert r2.json()["estado"] == "retirado"
    deps = client.get("/api/v1/mlops/deployments").json()
    assert [d["accion"] for d in deps] == ["despliegue", "reversion"]


def test_modelo_exige_experimento_registrado(client: TestClient) -> None:
    r = client.post("/api/v1/mlops/models", json={
        "modelo_id": "fantasma", "version": "1.0.0",
        "experimento_id": "exp-inexistente"})
    assert r.status_code == 422
    assert "entrenamiento registrado" in r.json()["detail"]


def test_monitoreo_asociado_a_version(client: TestClient) -> None:
    client.post("/api/v1/mlops/models", json={
        "modelo_id": "surrogate-yield", "version": "1.0.0",
        "experimento_id": "exp-001"})
    assert client.post("/api/v1/mlops/models/surrogate-yield/metrics",
                       json={"metrica": "rmse_pct", "valor": 1.9}
                       ).status_code == 201
    mets = client.get("/api/v1/mlops/models/surrogate-yield/metrics").json()
    assert mets[0]["version"] == "1.0.0"
    assert mets[0]["valor"] == pytest.approx(1.9)


def test_historial_temporal_y_auditoria(client: TestClient) -> None:
    client.post("/api/v1/mlops/models", json={
        "modelo_id": "surrogate-yield", "version": "1.0.0",
        "experimento_id": "exp-001", "usuario": "ml-1"})
    hist = client.get(
        "/api/v1/mlops/models/surrogate-yield/history").json()
    assert hist[0]["estado"] == "entrenado"
    assert hist[0]["usuario"] == "ml-1"
    aud = client.get("/api/v1/mlops/audit").json()
    acciones = {a["accion"] for a in aud}
    assert {"registrar_dataset", "registrar_experimento",
            "registrar_modelo"} <= acciones
    assert all(a["fecha"] for a in aud)
