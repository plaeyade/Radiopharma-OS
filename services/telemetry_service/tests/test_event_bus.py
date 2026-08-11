"""Tests del Event Bus & Message Broker (EDS cap. 52)."""

import pytest
from fastapi.testclient import TestClient

from app.domain.event_bus import EventBusEngine
from app.main import app
from app.presentation.routers import events_api


@pytest.fixture()
def client():
    events_api.init()
    return TestClient(app)


def _topico_y_esquema(c: TestClient):
    assert c.post("/api/v1/events/topics", json={
        "topico": "produccion.lotes", "dominio": "produccion",
        "actor": "integrador"}).status_code == 200
    assert c.post("/api/v1/events/schemas", json={
        "tipo": "lote_producido", "campos_requeridos": ["lote_id", "actividad_gbqe"],
        "actor": "integrador"}).status_code == 200


def test_topicos_por_dominio_y_unicidad(client):
    c = client
    _topico_y_esquema(c)
    r = c.post("/api/v1/events/topics", json={
        "topico": "produccion.lotes", "dominio": "produccion", "actor": "x"})
    assert r.status_code == 422  # duplicado
    r = c.post("/api/v1/events/topics", json={
        "topico": "finanzas.x", "dominio": "finanzas", "actor": "x"})
    assert r.status_code == 422  # dominio fuera del catálogo 52.7
    tops = c.get("/api/v1/events/topics").json()
    assert tops[0]["dominio"] == "produccion"


def test_schema_registry_versionado_compatible(client):
    c = client
    _topico_y_esquema(c)
    r = c.post("/api/v1/events/schemas", json={
        "tipo": "lote_producido",
        "campos_requeridos": ["lote_id", "actividad_gbqe", "rendimiento_pct"],
        "actor": "integrador"})
    assert r.json()["version"] == 2  # compatible: conserva los anteriores
    r = c.post("/api/v1/events/schemas", json={
        "tipo": "lote_producido", "campos_requeridos": ["lote_id"],
        "actor": "integrador"})
    assert r.status_code == 422  # incompatible: retira campos requeridos (52.10)
    v1 = c.get("/api/v1/events/schemas/lote_producido?version=1").json()
    assert v1["campos_requeridos"] == ["lote_id", "actividad_gbqe"]
    vigente = c.get("/api/v1/events/schemas/lote_producido").json()
    assert vigente["versiones_disponibles"] == 2  # toda versión permanece


def test_publicar_valida_esquema(client):
    c = client
    _topico_y_esquema(c)
    r = c.post("/api/v1/events/publish", json={
        "tipo": "lote_producido", "topico": "produccion.lotes",
        "productor": "process-service", "payload": {"lote_id": "L-1"}})
    assert r.status_code == 422  # falta actividad_gbqe: nunca enruta inválidos
    r = c.post("/api/v1/events/publish", json={
        "tipo": "lote_producido", "topico": "produccion.lotes",
        "productor": "process-service",
        "payload": {"lote_id": "L-1", "actividad_gbqe": 148.0}})
    assert r.status_code == 200
    assert r.json()["version_esquema"] == 1


def test_enrutamiento_desacoplado_y_sin_canal_honesto(client):
    c = client
    _topico_y_esquema(c)
    c.post("/api/v1/events/subscriptions", json={
        "topico": "produccion.lotes", "servicio": "analytics-service",
        "actor": "integrador"})
    r = c.post("/api/v1/events/publish", json={
        "tipo": "lote_producido", "topico": "produccion.lotes",
        "productor": "process-service",
        "payload": {"lote_id": "L-2", "actividad_gbqe": 150.0}}).json()
    assert r["entregas"][0]["estado"] == "sin_canal"  # NUNCA declara entregado
    assert "no_configurado" in r["entregas"][0]["causa"]
    broker = c.get("/api/v1/events/broker").json()
    assert broker["broker_externo"] == "no_configurado"  # honestidad 52.6


def test_entrega_real_y_dead_letter_con_causa_real():
    engine = EventBusEngine()
    events_api.init(engine)
    c = TestClient(app)
    _topico_y_esquema(c)
    recibidos = []
    engine.suscribir("produccion.lotes", "kpi-service", "test",
                     canal=lambda e: recibidos.append(e))

    def canal_roto(_e):
        raise RuntimeError("conexión rechazada por el consumidor")

    engine.suscribir("produccion.lotes", "alerts-service", "test", canal=canal_roto)
    r = c.post("/api/v1/events/publish", json={
        "tipo": "lote_producido", "topico": "produccion.lotes",
        "productor": "process-service",
        "payload": {"lote_id": "L-3", "actividad_gbqe": 152.5}}).json()
    estados = {e["destino"]: e["estado"] for e in r["entregas"]}
    assert estados["kpi-service"] == "entregado"
    assert recibidos[0]["payload"]["lote_id"] == "L-3"  # entrega real 52.9
    assert estados["alerts-service"] == "fallido"
    dls = c.get("/api/v1/events/dead-letters").json()
    assert len(dls) == 1
    assert "conexión rechazada" in dls[0]["causa"]  # causa REAL (52.11)
    assert dls[0]["estado"] == "pendiente" and dls[0]["servicio"] == "alerts-service"


def test_reprocesamiento_dead_letter():
    engine = EventBusEngine()
    events_api.init(engine)
    c = TestClient(app)
    _topico_y_esquema(c)
    fallos = {"n": 1}
    recibidos = []

    def canal_inestable(e):
        if fallos["n"] > 0:
            fallos["n"] -= 1
            raise ConnectionError("caída temporal")
        recibidos.append(e)

    engine.suscribir("produccion.lotes", "replay-service", "test",
                     canal=canal_inestable)
    c.post("/api/v1/events/publish", json={
        "tipo": "lote_producido", "topico": "produccion.lotes",
        "productor": "process-service",
        "payload": {"lote_id": "L-4", "actividad_gbqe": 140.0}})
    dl = c.get("/api/v1/events/dead-letters").json()[0]
    r = c.post(f"/api/v1/events/dead-letters/{dl['dead_letter_id']}/reprocesar",
               json={"actor": "sre"})
    assert r.status_code == 200 and r.json()["estado"] == "reprocesado"
    assert recibidos[0]["payload"]["lote_id"] == "L-4"  # reprocesado real
    r = c.post(f"/api/v1/events/dead-letters/{dl['dead_letter_id']}/reprocesar",
               json={"actor": "sre"})
    assert r.status_code == 422  # ya reprocesado: no se repite


def test_historial_y_auditoria(client):
    c = client
    _topico_y_esquema(c)
    c.post("/api/v1/events/publish", json={
        "tipo": "lote_producido", "topico": "produccion.lotes",
        "productor": "process-service",
        "payload": {"lote_id": "L-5", "actividad_gbqe": 99.0}})
    hist = c.get("/api/v1/events/history?topico=produccion.lotes").json()
    assert hist[0]["productor"] == "process-service" and hist[0]["publicado_en"]
    cat = c.get("/api/v1/events/catalog").json()
    assert cat[0]["tipo"] == "lote_producido" and cat[0]["publicaciones"] == 1
    audit = c.get("/api/v1/events/audit").json()
    assert any(a["accion"] == "evento_publicado" for a in audit)
    assert all("timestamp" in a and "version_motor" in a for a in audit)
