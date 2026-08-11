"""Tests de DevSecOps & Platform Engineering (EDS cap. 56)."""

import base64

import pytest
from fastapi.testclient import TestClient

from app.domain.devsecops import DevsecopsEngine
from app.main import app
from app.presentation.routers import devsecops_api


@pytest.fixture()
def client():
    devsecops_api.init()
    return TestClient(app)


def _cambio(c: TestClient, cid: str = "chg-1"):
    r = c.post("/api/v1/devsecops/changes", json={
        "cambio_id": cid, "repositorio": "radiopharma-os", "rama": "master",
        "autor": "dev-1", "descripcion": "nueva funcionalidad",
        "hash_commit": "abc123def456"})
    assert r.status_code == 200
    return cid


def test_cambios_identificador_unico(client):
    c = client
    _cambio(c)
    r = c.post("/api/v1/devsecops/changes", json={
        "cambio_id": "chg-1", "repositorio": "otro", "rama": "x",
        "autor": "y", "descripcion": "z", "hash_commit": "999"})
    assert r.status_code == 422  # 56.6 unicidad
    hist = c.get("/api/v1/devsecops/changes?repositorio=radiopharma-os").json()
    assert len(hist) == 1 and hist[0]["autor"] == "dev-1"


def test_ci_sin_runner_no_se_declara(client):
    c = client
    _cambio(c)
    r = c.post("/api/v1/devsecops/ci/run", json={
        "cambio_id": "chg-1", "responsable": "ci-bot"})
    assert r.status_code == 422  # honesto: sin runner la ejecución NO se declara


def test_pipeline_completo_real():
    engine = DevsecopsEngine()
    devsecops_api.init(engine)
    c = TestClient(app)
    _cambio(c)
    engine.runner_ci = lambda cid: {
        "compilacion": "ok", "pruebas": {"total": 792, "fallidas": 0},
        "analisis_estatico": "ok", "artefactos": ["img-yield:0.55.0"]}
    r = c.post("/api/v1/devsecops/ci/run", json={
        "cambio_id": "chg-1", "responsable": "ci-bot"})
    assert r.status_code == 200
    ej = r.json()
    assert ej["estado"] == "exitosa" and ej["artefactos"] == ["img-yield:0.55.0"]
    # promoción bloqueada sin escaneo (56.9 forma parte de la validación)
    r = c.post("/api/v1/devsecops/cd/promote", json={
        "ejecucion_id": ej["ejecucion_id"], "entorno": "produccion",
        "estrategia": "rolling", "responsable": "sre"})
    assert r.status_code == 422
    # escaneo con crítico bloquea
    engine.scanner = lambda: [{"severidad": "critica", "detalle": "CVE-2026-0001"}]
    r = c.post("/api/v1/devsecops/security/scan", json={
        "ejecucion_id": ej["ejecucion_id"], "responsable": "sec-bot"})
    assert r.status_code == 200 and r.json()["apto_para_promocion"] is False
    r = c.post("/api/v1/devsecops/cd/promote", json={
        "ejecucion_id": ej["ejecucion_id"], "entorno": "produccion",
        "estrategia": "rolling", "responsable": "sre"})
    assert r.status_code == 422 and "críticos" in r.json()["detail"]
    # escaneo limpio permite promoción
    engine.scanner = lambda: [{"severidad": "baja", "detalle": "avisos menores"}]
    c.post("/api/v1/devsecops/security/scan", json={
        "ejecucion_id": ej["ejecucion_id"], "responsable": "sec-bot"})
    r = c.post("/api/v1/devsecops/cd/promote", json={
        "ejecucion_id": ej["ejecucion_id"], "entorno": "produccion",
        "estrategia": "blue_green", "responsable": "sre"})
    assert r.status_code == 200 and r.json()["estado"] == "promovido"


def test_ci_fallido_no_promueve():
    engine = DevsecopsEngine()
    devsecops_api.init(engine)
    c = TestClient(app)
    _cambio(c, "chg-2")
    engine.runner_ci = lambda cid: {"compilacion": "ok",
                                    "pruebas": {"total": 100, "fallidas": 3}}
    r = c.post("/api/v1/devsecops/ci/run", json={
        "cambio_id": "chg-2", "responsable": "ci-bot"})
    assert r.json()["estado"] == "fallida"
    r = c.post("/api/v1/devsecops/cd/promote", json={
        "ejecucion_id": r.json()["ejecucion_id"], "entorno": "produccion",
        "estrategia": "canary", "responsable": "sre"})
    assert r.status_code == 422


def test_artefactos_trazables_verificacion_real(client):
    c = client
    contenido = b"artefacto-binario-v1"
    r = c.post("/api/v1/devsecops/artifacts", json={
        "artefacto_id": "art-1", "tipo": "imagen", "version": "0.55.0",
        "contenido_b64": base64.b64encode(contenido).decode(),
        "ejecucion_origen": "ej-1", "responsable": "ci-bot"})
    assert r.status_code == 200
    r = c.post("/api/v1/devsecops/artifacts", json={
        "artefacto_id": "art-1", "tipo": "imagen", "version": "x",
        "contenido_b64": base64.b64encode(b"otro").decode(),
        "ejecucion_origen": "ej-2", "responsable": "x"})
    assert r.status_code == 422  # nunca sobrescrito (56.10)
    v = c.post("/api/v1/devsecops/artifacts/art-1/verify", json={
        "contenido_b64": base64.b64encode(contenido).decode()}).json()
    assert v["integro"] is True
    v = c.post("/api/v1/devsecops/artifacts/art-1/verify", json={
        "contenido_b64": base64.b64encode(b"manipulado").decode()}).json()
    assert v["integro"] is False  # verificación sha256 real


def test_auditoria_alcoa(client):
    c = client
    _cambio(c)
    audit = c.get("/api/v1/devsecops/audit").json()
    assert any(a["accion"] == "cambio_registrado" and a["actor"] == "dev-1"
               for a in audit)
    assert all("timestamp" in a and "version_motor" in a for a in audit)
