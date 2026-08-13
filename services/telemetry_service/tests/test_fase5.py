"""Tests fase 5 — persistencia real 31.23 y broker MQTT real 52.6."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.domain.event_bus import EventBusEngine
from app.domain.scada import ScadaEngine
from app.main import app
from app.presentation.routers import events_api, scada_api


# ------------------------------------------------- persistencia 31.23
class _AlmacenFalso:
    nombre = "influxdb"

    def __init__(self, vivo=True):
        self.vivo = vivo
        self.escritos = []

    def sondear(self):
        if not self.vivo:
            raise ConnectionError("influxdb caído")

    def escribir(self, doc):
        if not self.vivo:
            raise ConnectionError("write failed")
        self.escritos.append(doc)


@pytest.fixture()
def engine():
    eng = ScadaEngine(fabricas_clientes={})
    scada_api.init(eng)
    return eng


@pytest.fixture()
def client(engine):
    return TestClient(app)


def _medir(engine, variable="corriente_haz_ua", valor=70.5):
    from datetime import datetime, timezone
    return engine.registrar_medicion(
        "cyclotron_main", variable, valor, "uA",
        datetime.now(timezone.utc).isoformat(), "test")


def test_persistencia_configurada_escribe_real(engine):
    almacen = _AlmacenFalso()
    out = engine.configurar_persistencia("influxdb", almacen, "sre")
    assert out["estado"] == "configurado"
    _medir(engine)
    assert len(almacen.escritos) == 1
    assert almacen.escritos[0]["variable"] == "corriente_haz_ua"
    estado = engine.estado_capa()["persistencia_31_23"]
    assert estado["influxdb"] == "configurado"
    assert estado["redis"] == "no_configurado"  # honesto


def test_sondeo_fallido_no_configura_y_es_503(engine, client):
    r = client.post("/api/v1/scada/persistence", json={
        "backend": "influxdb", "responsable": "sre",
        "config": {"url": "http://influx-caido:8086", "token": "t",
                   "org": "o", "bucket": "b"}})
    assert r.status_code == 503
    assert "no responde" in r.json()["detail"]
    assert "influxdb" not in engine._almacenes
    acciones = [a["accion"] for a in engine.auditoria()]
    assert "persistencia_fallo_sondeo" in acciones


def test_fallo_de_escritura_auditado_honestamente(engine):
    almacen = _AlmacenFalso()
    engine.configurar_persistencia("influxdb", almacen, "sre")
    almacen.vivo = False  # caída posterior al sondeo
    med = _medir(engine)  # la medición se acepta en memoria…
    assert med.valor == 70.5
    fallos = [a for a in engine.auditoria()
              if a["accion"] == "fallo_persistencia"]
    assert fallos and "write failed" in fallos[0]["detalle"]["detalle"]


def test_backend_invalido_422(engine, client):
    r = client.post("/api/v1/scada/persistence", json={
        "backend": "minio", "responsable": "sre", "config": {}})
    assert r.status_code == 422
    assert "sin implementación" in r.json()["detail"]


# ------------------------------------------------------ broker real 52.6
class _PuenteFalso:
    def __init__(self, endpoint, vivo=True):
        self.endpoint = endpoint
        self.vivo = vivo
        self.publicados = []

    def conectar(self):
        if not self.vivo:
            raise ConnectionError("broker inalcanzable")

    def publicar(self, topico, mensaje):
        if not self.vivo:
            raise ConnectionError("publish failed")
        self.publicados.append((topico, mensaje))


@pytest.fixture()
def bus():
    b = EventBusEngine()
    events_api.init(b)
    b.crear_topico("monitoreo.scada", "monitoreo", "test")
    b.registrar_esquema("evento_industrial",
                        ["evento", "dispositivo", "detalle"], "test")
    return b


def _publicar(bus):
    return bus.publicar("evento_industrial", "monitoreo.scada",
                        productor="scada-rtmsil",
                        payload={"evento": "inicio", "dispositivo": "plc1",
                                 "detalle": {}})


def test_broker_conectado_publica_real(bus):
    puente = _PuenteFalso("mqtt://broker:1883")
    bus.conectar_broker("mqtt://broker:1883", "sre",
                        fabrica_broker=lambda ep: puente)
    ev = _publicar(bus)
    assert puente.publicados and puente.publicados[0][0] == \
        "rpos/monitoreo.scada"
    assert ev["evento_id"] in puente.publicados[0][1]
    estado = bus.estado_broker()
    assert estado["broker_externo"] == "conectado"
    assert estado["endpoint"] == "mqtt://broker:1883"


def test_broker_caido_declarado_honestamente(bus):
    out = bus.conectar_broker(
        "mqtt://broker-caido:1883", "sre",
        fabrica_broker=lambda ep: _PuenteFalso(ep, vivo=False))
    assert out["estado"] == "fallo_conexion"
    assert "inalcanzable" in out["detalle"]
    assert bus.estado_broker()["broker_externo"] == "fallo_conexion"


def test_fallo_de_publicacion_genera_dead_letter(bus):
    puente = _PuenteFalso("mqtt://broker:1883")
    bus.conectar_broker("mqtt://broker:1883", "sre",
                        fabrica_broker=lambda ep: puente)
    puente.vivo = False
    _publicar(bus)
    dls = bus._dead_letters
    assert dls and next(iter(dls.values())).servicio == "broker-mqtt"
    assert bus.estado_broker()["broker_externo"] == "fallo_conexion"


def test_sin_broker_estado_honesto_no_configurado(bus):
    assert bus.estado_broker()["broker_externo"] == "no_configurado"
    ev = _publicar(bus)  # bus en proceso sigue operativo
    assert ev["topico"] == "monitoreo.scada"


def test_api_broker_connect(bus):
    c = TestClient(app)
    r = c.post("/api/v1/events/broker/connect",
               json={"endpoint": "mqtt://broker-inexistente:1883",
                     "actor": "sre"})
    assert r.status_code == 200
    assert r.json()["estado"] in ("conectado", "fallo_conexion")
    assert "endpoint" in r.json()
