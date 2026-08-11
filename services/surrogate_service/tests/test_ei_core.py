"""Tests del Enterprise Intelligence & AI Twin Core (EDS cap. 41)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.presentation.routers import ei_api, mlops_api


@pytest.fixture()
def client():
    mlops_api.init()
    ei_api.init()
    return TestClient(app)


def _modelo_desplegado(c: TestClient, modelo_id: str = "m-yield", version: str = "1.0.0"):
    assert c.post("/api/v1/mlops/datasets", json={
        "dataset_id": "ds-1", "version": "1.0", "origen": "yield_engine",
        "fecha": "2026-08-01", "n_registros": 41,
        "usuario": "mlops"}).status_code == 201
    assert c.post("/api/v1/mlops/experiments", json={
        "experimento_id": "exp-1", "modelo_id": modelo_id,
        "algoritmo": "ridge", "hiperparametros": {},
        "dataset_id": "ds-1", "dataset_version": "1.0",
        "metricas": {"rmse_pct": 1.7}, "usuario": "mlops"}).status_code == 201
    assert c.post("/api/v1/mlops/models", json={
        "modelo_id": modelo_id, "version": version,
        "experimento_id": "exp-1", "usuario": "mlops"}).status_code in (200, 201)
    assert c.post(f"/api/v1/mlops/models/{modelo_id}/approve", json={
        "responsable": "jefe-ia", "documentacion": "doc tecnica v1",
        "usuario": "mlops"}).status_code == 200
    r = c.post(f"/api/v1/mlops/models/{modelo_id}/deploy", json={
        "entorno": "produccion", "usuario": "mlops"})
    assert r.status_code == 200, r.text
    return modelo_id, version


def test_feature_store_versionado_y_trazable(client):
    c = client
    r = c.post("/api/v1/ei/features", json={
        "feature_id": "rendimiento_eob", "twin_origen": "physics",
        "descripcion": "Rendimiento al fin de bombardeo", "unidad": "GBq",
        "actor": "fisico1"})
    assert r.status_code == 200 and r.json()["version"] == 1
    r = c.post("/api/v1/ei/features", json={
        "feature_id": "rendimiento_eob", "twin_origen": "physics",
        "descripcion": "Rendimiento EOB revisado", "unidad": "GBq",
        "actor": "fisico1"})
    assert r.json()["version"] == 2  # nunca sobrescribe (41.6/41.7)
    f = c.get("/api/v1/ei/features/rendimiento_eob").json()
    assert f["descripcion"] == "Rendimiento EOB revisado" and f["revisiones"] == 2
    v1 = c.get("/api/v1/ei/features/rendimiento_eob?version=1").json()
    assert v1["descripcion"] == "Rendimiento al fin de bombardeo"


def test_valor_feature_exige_fuente_y_timestamp(client):
    c = client
    c.post("/api/v1/ei/features", json={
        "feature_id": "pureza_qc", "twin_origen": "qc",
        "descripcion": "Pureza radioquímica", "unidad": "%", "actor": "qc1"})
    r = c.post("/api/v1/ei/features/pureza_qc/valores", json={
        "valor": 99.1, "timestamp_dato": "2026-08-10T12:00:00+00:00",
        "fuente": "", "actor": "qc1"})
    assert r.status_code == 422  # fuente obligatoria (41.7)
    r = c.post("/api/v1/ei/features/pureza_qc/valores", json={
        "valor": 99.1, "timestamp_dato": "2026-08-10T12:00:00+00:00",
        "fuente": "hplc-run-4471", "actor": "qc1"})
    assert r.status_code == 200
    vals = c.get("/api/v1/ei/features/pureza_qc/valores").json()
    assert vals[0]["fuente"] == "hplc-run-4471"


def test_inferencia_rechaza_modelo_no_desplegado(client):
    c = client
    _modelo_desplegado(c)
    r = c.post("/api/v1/ei/inference/execute", json={
        "modelo_id": "m-yield", "version_modelo": "1.0.0",
        "datos": {"corriente_uA": 70}, "usuario": "fisico1"})
    assert r.status_code == 503  # desplegado pero SIN runtime: honesto, no inventa
    r = c.post("/api/v1/ei/inference/execute", json={
        "modelo_id": "m-fantasma", "version_modelo": "9.9",
        "datos": {"x": 1}, "usuario": "fisico1"})
    assert r.status_code == 422  # no registrado en el Model Registry (41.20)


def test_inferencia_real_documentada(client):
    c = client
    _modelo_desplegado(c)
    r = c.post("/api/v1/ei/inference/runtimes", json={
        "modelo_id": "m-yield", "version_modelo": "1.0.0",
        "actor": "mlops", "expresion": "corriente_uA * 0.5 + 1"})
    assert r.status_code == 200
    r = c.post("/api/v1/ei/inference/execute", json={
        "modelo_id": "m-yield", "version_modelo": "1.0.0",
        "datos": {"corriente_uA": 70}, "usuario": "fisico1"})
    assert r.status_code == 200
    assert r.json()["resultado"] == pytest.approx(36.0)
    hist = c.get("/api/v1/ei/inference/history?modelo_id=m-yield").json()
    assert len(hist) == 1
    h = hist[0]
    assert h["version_modelo"] == "1.0.0" and h["usuario"] == "fisico1"
    assert h["datos"] == {"corriente_uA": 70} and h["hash_datos"]  # 41.8/41.12


def test_recomendacion_diferenciada_y_resolucion_por_usuario(client):
    c = client
    r = c.post("/api/v1/ei/recommendations", json={
        "area": "mantenimiento", "titulo": "Adelantar mantenimiento del blanco",
        "detalle": "Tendencia térmica creciente en las últimas 10 corridas",
        "soporte": {"feature_ids": ["temp_blanco"], "hallazgos": ["deriva +2 C/corrida"]},
        "generada_por": "motor-ei"})
    assert r.status_code == 200
    rec = r.json()
    assert rec["estado"] == "propuesta"
    assert "RECOMENDACIÓN" in rec["naturaleza"] and "nunca" not in rec["naturaleza"] or \
        "responsabilidad de usuarios autorizados" in rec["naturaleza"]  # 41.3/41.9
    r = c.post(f"/api/v1/ei/recommendations/{rec['recomendacion_id']}/resolver", json={
        "decision": "aceptada", "usuario": "jefe-mantenimiento",
        "motivo": "ventana programada disponible"})
    assert r.status_code == 200 and r.json()["estado"] == "aceptada"
    r = c.post(f"/api/v1/ei/recommendations/{rec['recomendacion_id']}/resolver", json={
        "decision": "rechazada", "usuario": "otro", "motivo": "x"})
    assert r.status_code == 422  # no se re-resuelve


def test_recomendacion_sin_soporte_rechazada(client):
    c = client
    r = c.post("/api/v1/ei/recommendations", json={
        "area": "produccion", "titulo": "Subir corriente", "detalle": "x",
        "soporte": {}, "generada_por": "motor-ei"})
    assert r.status_code == 422  # nunca sin fundamento


def test_auditoria_alcoa(client):
    c = client
    c.post("/api/v1/ei/features", json={
        "feature_id": "f1", "twin_origen": "economic",
        "descripcion": "costo por dosis", "unidad": "USD", "actor": "econ1"})
    audit = c.get("/api/v1/ei/audit").json()
    assert any(a["accion"] == "feature_registrada" and a["actor"] == "econ1"
               for a in audit)
    assert all("timestamp" in a and "version_motor" in a for a in audit)
