"""Tests de Observability & Monitoring Platform (EDS cap. 55)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.presentation.routers import observability_api


@pytest.fixture()
def client():
    observability_api.init()
    return TestClient(app)


def test_metricas_por_dominio_con_origen(client):
    c = client
    r = c.post("/api/v1/observability/metrics", json={
        "nombre": "cpu_pct", "dominio": "infraestructura", "valor": 62.5,
        "unidad": "%", "origen": "node-exporter-01"})
    assert r.status_code == 200 and r.json()["alertas_generadas"] == 0
    r = c.post("/api/v1/observability/metrics", json={
        "nombre": "cpu_pct", "dominio": "espacio", "valor": 1.0,
        "origen": "x"})
    assert r.status_code == 422
    r = c.post("/api/v1/observability/metrics", json={
        "nombre": "cpu_pct", "dominio": "infraestructura", "valor": 1.0,
        "origen": ""})
    assert r.status_code == 422  # origen obligatorio (55.12)
    ms = c.get("/api/v1/observability/metrics?dominio=infraestructura").json()
    assert len(ms) == 1 and ms[0]["origen"] == "node-exporter-01"


def test_logs_indexados_consulta_real(client):
    c = client
    c.post("/api/v1/observability/logs", json={
        "nivel": "ERROR", "servicio": "yield-engine", "origen": "microservicios",
        "mensaje": "fallo de conexión con NDS"})
    c.post("/api/v1/observability/logs", json={
        "nivel": "INFO", "servicio": "qc-engine", "origen": "microservicios",
        "mensaje": "lote liberado correctamente"})
    r = c.post("/api/v1/observability/logs", json={
        "nivel": "FATAL", "servicio": "x", "origen": "microservicios",
        "mensaje": "x"})
    assert r.status_code == 422
    errs = c.get("/api/v1/observability/logs?nivel=ERROR").json()
    assert len(errs) == 1 and "NDS" in errs[0]["mensaje"]
    txt = c.get("/api/v1/observability/logs?texto=conexión").json()
    assert len(txt) == 1


def test_trazas_reconstruidas_desde_spans_reales(client):
    c = client
    c.post("/api/v1/observability/traces/spans", json={
        "trace_id": "t-1", "servicio": "gateway", "operacion": "POST /yield",
        "inicio": "2026-08-11T10:00:00+00:00", "duracion_ms": 5.0})
    c.post("/api/v1/observability/traces/spans", json={
        "trace_id": "t-1", "servicio": "yield-engine", "operacion": "calcular",
        "inicio": "2026-08-11T10:00:01+00:00", "duracion_ms": 120.0,
        "error": "timeout solver"})
    tr = c.get("/api/v1/observability/traces/t-1").json()
    assert tr["servicios"] == ["gateway", "yield-engine"]
    assert tr["duracion_total_ms"] == pytest.approx(125.0)
    assert tr["errores"] == [{"servicio": "yield-engine", "error": "timeout solver"}]
    r = c.get("/api/v1/observability/traces/t-fantasma")
    assert r.status_code == 422  # nunca reconstruye sin spans reales


def test_alertas_solo_de_mediciones_reales(client):
    c = client
    r = c.post("/api/v1/observability/alerts/policies", json={
        "nombre": "cpu-alta", "metrica": "cpu_pct", "operador": ">",
        "umbral": 90.0, "prioridad": "alta", "escalamiento_a": "sre-guardia",
        "actor": "sre"})
    assert r.status_code == 200
    c.post("/api/v1/observability/metrics", json={
        "nombre": "cpu_pct", "dominio": "infraestructura", "valor": 70.0,
        "origen": "node-1"})
    assert c.get("/api/v1/observability/alerts").json() == []
    c.post("/api/v1/observability/metrics", json={
        "nombre": "cpu_pct", "dominio": "infraestructura", "valor": 95.0,
        "origen": "node-1"})
    alertas = c.get("/api/v1/observability/alerts?prioridad=alta").json()
    assert len(alertas) == 1
    a = alertas[0]
    assert a["valor"] == 95.0 and a["origen_medicion"] == "node-1"  # medición real
    r = c.post(f"/api/v1/observability/alerts/{a['alerta_id']}/cerrar", json={
        "actor": "sre-guardia", "motivo": "nodo reiniciado, CPU normalizada"})
    assert r.status_code == 200 and r.json()["estado"] == "cerrada"


def test_politicas_versionadas(client):
    c = client
    c.post("/api/v1/observability/alerts/policies", json={
        "nombre": "latencia", "metrica": "latencia_ms", "operador": ">",
        "umbral": 500, "prioridad": "media", "escalamiento_a": "sre",
        "actor": "sre"})
    r = c.post("/api/v1/observability/alerts/policies", json={
        "nombre": "latencia", "metrica": "latencia_ms", "operador": ">",
        "umbral": 300, "prioridad": "alta", "escalamiento_a": "sre",
        "actor": "sre"})
    assert r.json()["version"] == 2  # configurables y versionadas


def test_aiops_honesto_y_auditoria(client):
    c = client
    aiops = c.get("/api/v1/observability/aiops").json()
    assert aiops["aiops"] == "sin_modelos"  # 55.10 honesto
    c.post("/api/v1/observability/alerts/policies", json={
        "nombre": "p1", "metrica": "m1", "operador": ">", "umbral": 1,
        "prioridad": "baja", "escalamiento_a": "sre", "actor": "sre"})
    audit = c.get("/api/v1/observability/audit").json()
    assert any(a["accion"] == "politica_alerta" for a in audit)
    assert all("timestamp" in a and "version_motor" in a for a in audit)
