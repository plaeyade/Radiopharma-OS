"""Tests del Data Lakehouse & Analytics Platform (EDS cap. 54)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.presentation.routers import lakehouse_api


@pytest.fixture()
def client():
    lakehouse_api.init()
    return TestClient(app)


def _dataset(c: TestClient) -> str:
    r = c.post("/api/v1/lakehouse/datasets", json={
        "dataset_id": "lotes-f18", "propietario": "operaciones",
        "dominio": "process",
        "esquema": ["lote_id", "actividad_gbqe", "fecha"],
        "clasificacion": "regulado", "vigencia_desde": "2026-08-01",
        "actor": "data-steward"})
    assert r.status_code == 200
    return "lotes-f18"


def test_catalogo_versionado_compatible(client):
    c = client
    _dataset(c)
    r = c.post("/api/v1/lakehouse/datasets", json={
        "dataset_id": "lotes-f18", "propietario": "x", "dominio": "qc",
        "esquema": ["a"], "clasificacion": "interno",
        "vigencia_desde": "2026-08-02", "actor": "x"})
    assert r.status_code == 422  # catálogo nunca sobrescribe (54.8)
    r = c.post("/api/v1/lakehouse/datasets/lotes-f18/versions", json={
        "esquema": ["lote_id", "actividad_gbqe", "fecha", "pureza_pct"],
        "clasificacion": "regulado", "vigencia_desde": "2026-08-10",
        "actor": "data-steward"})
    assert r.status_code == 200 and r.json()["version_vigente"] == 2
    r = c.post("/api/v1/lakehouse/datasets/lotes-f18/versions", json={
        "esquema": ["lote_id"], "clasificacion": "regulado",
        "vigencia_desde": "2026-08-11", "actor": "data-steward"})
    assert r.status_code == 422  # incompatible: retira campos (54.12)


def test_ingesta_exige_origen_y_esquema(client):
    c = client
    _dataset(c)
    r = c.post("/api/v1/lakehouse/datasets/lotes-f18/ingest", json={
        "registros": [{"lote_id": "L-1", "actividad_gbqe": 148.0,
                       "fecha": "2026-08-01"}],
        "origen": "", "modo": "lotes", "actor": "etl"})
    assert r.status_code == 422  # origen obligatorio: nunca se inventan datos
    r = c.post("/api/v1/lakehouse/datasets/lotes-f18/ingest", json={
        "registros": [{"lote_id": "L-1", "campo_raro": 1}],
        "origen": "process-service", "modo": "lotes", "actor": "etl"})
    assert r.status_code == 422  # campos fuera del esquema vigente
    r = c.post("/api/v1/lakehouse/datasets/lotes-f18/ingest", json={
        "registros": [{"lote_id": "L-1", "actividad_gbqe": 148.0,
                       "fecha": "2026-08-01"},
                      {"lote_id": "L-2", "actividad_gbqe": 152.5,
                       "fecha": "2026-08-02"}],
        "origen": "process-service", "modo": "flujo", "actor": "etl"})
    assert r.status_code == 200 and r.json()["total"] == 2
    regs = c.get("/api/v1/lakehouse/datasets/lotes-f18/records").json()
    assert all(r["_origen"] == "process-service" for r in regs)


def test_calidad_calculada_sobre_datos_reales(client):
    c = client
    _dataset(c)
    r = c.post("/api/v1/lakehouse/datasets/lotes-f18/quality", json={
        "campo_clave": "lote_id", "evaluador": "dq-engine"})
    assert r.status_code == 422  # NUNCA se declara calidad sin datos
    c.post("/api/v1/lakehouse/datasets/lotes-f18/ingest", json={
        "registros": [
            {"lote_id": "L-1", "actividad_gbqe": 148.0, "fecha": "2026-08-01"},
            {"lote_id": "L-1", "actividad_gbqe": 148.0, "fecha": "2026-08-01"},
            {"lote_id": "L-2", "actividad_gbqe": None, "fecha": "2026-08-02"}],
        "origen": "process-service", "modo": "lotes", "actor": "etl"})
    q = c.post("/api/v1/lakehouse/datasets/lotes-f18/quality", json={
        "campo_clave": "lote_id", "evaluador": "dq-engine"})
    assert q.status_code == 200
    q = q.json()
    assert q["n_registros"] == 3
    assert q["unicidad"] == pytest.approx(2 / 3 * 100, rel=1e-2)  # L-1 duplicado
    assert q["completitud"] == pytest.approx(2 / 3 * 100, rel=1e-2)  # un None
    assert q["integridad"] == 100.0
    evs = c.get("/api/v1/lakehouse/quality?dataset_id=lotes-f18").json()
    assert len(evs) == 1  # resultados disponibles para consumidores (54.10)


def test_politicas_gobernanza_versionadas(client):
    c = client
    r = c.post("/api/v1/lakehouse/policies", json={
        "politica_id": "ret-lotes", "tipo": "retencion",
        "contenido": "10 años conforme a GMP", "responsable": "calidad"})
    assert r.status_code == 200 and r.json()["version"] == 1
    r = c.post("/api/v1/lakehouse/policies", json={
        "politica_id": "ret-lotes", "tipo": "retencion",
        "contenido": "10 años + archivo permanente del registro maestro",
        "responsable": "calidad"})
    assert r.json()["version"] == 2  # nunca sobrescrita
    r = c.post("/api/v1/lakehouse/policies", json={
        "politica_id": "p-x", "tipo": "magica",
        "contenido": "x", "responsable": "x"})
    assert r.status_code == 422
    pols = c.get("/api/v1/lakehouse/policies?tipo=retencion").json()
    assert pols[0]["revisiones"] == 2


def test_auditoria_alcoa(client):
    c = client
    _dataset(c)
    audit = c.get("/api/v1/lakehouse/audit").json()
    assert any(a["accion"] == "dataset_registrado" and a["actor"] == "data-steward"
               for a in audit)
    assert all("timestamp" in a and "version_motor" in a for a in audit)
