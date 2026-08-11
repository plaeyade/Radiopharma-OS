"""Tests de HPC & Scientific Computing Platform (EDS cap. 57)."""

import pytest
from fastapi.testclient import TestClient

from app.domain.hpc import HpcEngine
from app.main import app
from app.presentation.routers import hpc_api


@pytest.fixture()
def engine():
    e = HpcEngine(cpu_total=8, memoria_total_gb=32.0)
    hpc_api.init(e)
    return e


@pytest.fixture()
def client(engine):
    return TestClient(app)


def test_recursos_contabilidad_real(client, engine):
    disp = client.get("/api/v1/hpc/resources").json()
    assert disp["cpu_total"] == 8 and disp["cpu_libres"] == 8
    r = client.post("/api/v1/hpc/jobs", json={
        "usuario": "fisico1", "prioridad": 2, "cpu": 16, "memoria_gb": 4,
        "descripcion": "simulación MC grande"})
    tid = r.json()["trabajo_id"]
    r = client.post(f"/api/v1/hpc/jobs/{tid}/execute")
    assert r.status_code == 422  # 16 > 8: nunca se sobre-asigna (57.7)
    r = client.post("/api/v1/hpc/jobs", json={
        "usuario": "fisico1", "prioridad": 2, "cpu": 4, "memoria_gb": 8,
        "descripcion": "simulación MC"})
    tid = r.json()["trabajo_id"]
    r = client.post(f"/api/v1/hpc/jobs/{tid}/execute")
    assert r.status_code == 503  # sin runtime científico: NO se inventa (57.10)


def test_gpu_independiente_fabricante_y_asignacion(client, engine):
    r = client.post("/api/v1/hpc/gpus", json={
        "gpu_id": "gpu-1", "modelo": "A100", "fabricante": "nvidia",
        "memoria_gb": 80, "actor": "hpc-admin"})
    assert r.status_code == 200
    r = client.post("/api/v1/hpc/gpus", json={
        "gpu_id": "gpu-1", "modelo": "MI250", "fabricante": "amd",
        "memoria_gb": 128, "actor": "hpc-admin"})
    assert r.status_code == 422
    r = client.post("/api/v1/hpc/jobs", json={
        "usuario": "ml-1", "prioridad": 1, "cpu": 2, "gpu": 2,
        "memoria_gb": 16, "descripcion": "entrenamiento surrogate"})
    tid = r.json()["trabajo_id"]
    engine.runtimes = {tid: lambda: {"rmse": 1.7}}
    r = client.post(f"/api/v1/hpc/jobs/{tid}/execute")
    assert r.status_code == 422  # solo 1 GPU libre de 2 pedidas
    r = client.post("/api/v1/hpc/jobs", json={
        "usuario": "ml-1", "prioridad": 1, "cpu": 2, "gpu": 1,
        "memoria_gb": 16, "descripcion": "entrenamiento surrogate"})
    tid = r.json()["trabajo_id"]
    engine.runtimes = {tid: lambda: {"rmse": 1.7}}
    r = client.post(f"/api/v1/hpc/jobs/{tid}/execute")
    assert r.status_code == 200
    j = r.json()
    assert j["estado"] == "completado" and j["resultado"] == {"rmse": 1.7}
    assert j["duracion_s"] is not None and j["iniciado_en"] and j["finalizado_en"]
    gpus = client.get("/api/v1/hpc/gpus").json()
    assert gpus[0]["estado"] == "disponible"  # liberada al finalizar


def test_cola_por_prioridad(client):
    for prio, desc in [(4, "baja"), (1, "urgente"), (3, "media")]:
        client.post("/api/v1/hpc/jobs", json={
            "usuario": "u", "prioridad": prio, "cpu": 1, "descripcion": desc})
    cola = client.get("/api/v1/hpc/jobs/queue").json()
    assert [t["descripcion"] for t in cola] == ["urgente", "media", "baja"]


def test_workflow_topologico_real(client, engine):
    r = client.post("/api/v1/hpc/workflows", json={
        "flujo_id": "wf-f18", "actor": "fisico1", "etapas": [
            {"etapa": "irradiacion", "depende_de": []},
            {"etapa": "transporte", "depende_de": ["irradiacion"]},
            {"etapa": "sintesis", "depende_de": ["transporte"]},
            {"etapa": "qc", "depende_de": ["sintesis"]}]})
    assert r.status_code == 200
    assert r.json()["orden_ejecucion"] == ["irradiacion", "transporte",
                                           "sintesis", "qc"]
    r = client.post("/api/v1/hpc/workflows/wf-f18/execute", json={"actor": "fisico1"})
    assert r.status_code == 503  # sin runtimes: el flujo NO se simula
    orden_visto = []

    def mk(nombre):
        def _run(prev):
            orden_visto.append(nombre)
            return nombre.upper()
        return _run

    engine.runtimes_flujo = {"wf-f18": {n: mk(n) for n in
                                        ["irradiacion", "transporte", "sintesis", "qc"]}}
    r = client.post("/api/v1/hpc/workflows/wf-f18/execute", json={"actor": "fisico1"})
    assert r.status_code == 200
    assert orden_visto == ["irradiacion", "transporte", "sintesis", "qc"]
    hist = r.json()["historial"]
    assert hist[-1]["resultado"] == "QC"
    # cada etapa recibe los resultados de las anteriores (datos reales)
    assert engine._flujos["wf-f18"]["ejecuciones"]


def test_workflow_ciclo_rechazado(client):
    r = client.post("/api/v1/hpc/workflows", json={
        "flujo_id": "wf-ciclo", "actor": "x", "etapas": [
            {"etapa": "a", "depende_de": ["b"]},
            {"etapa": "b", "depende_de": ["a"]}]})
    assert r.status_code == 422  # dependencias cíclicas (57.11)
    r = client.post("/api/v1/hpc/workflows", json={
        "flujo_id": "wf-fantasma", "actor": "x", "etapas": [
            {"etapa": "a", "depende_de": ["inexistente"]}]})
    assert r.status_code == 422


def test_auditoria_alcoa(client):
    client.post("/api/v1/hpc/jobs", json={
        "usuario": "fisico1", "prioridad": 2, "cpu": 1, "descripcion": "t"})
    audit = client.get("/api/v1/hpc/audit").json()
    assert any(a["accion"] == "trabajo_planificado" and a["actor"] == "fisico1"
               for a in audit)
    assert all("timestamp" in a and "version_motor" in a for a in audit)
