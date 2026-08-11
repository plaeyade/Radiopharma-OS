"""Tests del RTMSIL — SCADA Integration Layer (EDS cap. 31)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.domain.scada import ScadaEngine
from app.main import app
from app.presentation.routers import scada_api


class _ClienteFalso:
    """Cliente industrial de prueba inyectado (31.6/31.7/31.8)."""

    def __init__(self, endpoint, cfg, falla=False):
        self.endpoint = endpoint
        self.falla = falla
        self.conectado = False

    def conectar(self):
        if self.falla:
            raise ConnectionError("timeout real simulado por el cliente")
        self.conectado = True

    def leer(self, variable):
        if not self.conectado:
            raise RuntimeError("no conectado")
        return {"valor": 42.0, "variable": variable}


@pytest.fixture()
def engine():
    eng = ScadaEngine(fabricas_clientes={
        "opcua": lambda ep, cfg: _ClienteFalso(ep, cfg),
        "modbus_tcp": lambda ep, cfg: _ClienteFalso(ep, cfg, falla=True),
    })
    scada_api.init(eng)
    return eng


@pytest.fixture()
def client(engine):
    return TestClient(app)


def _conector(client, cid="plc-ciclotron", tipo="opcua",
              endpoint="opc.tcp://127.0.0.1:4840"):
    r = client.post("/api/v1/scada/connectors", json={
        "conector_id": cid, "tipo": tipo, "endpoint": endpoint,
        "configuracion": {"timeout_s": 2}, "responsable": "automatizacion"})
    assert r.status_code == 201
    return cid


def test_conector_versionado_y_endpoint_obligatorio(client):
    _conector(client)
    r = client.post("/api/v1/scada/connectors", json={
        "conector_id": "plc-ciclotron", "tipo": "opcua",
        "endpoint": "opc.tcp://127.0.0.1:4841", "configuracion": {},
        "responsable": "automatizacion"})
    assert r.status_code == 201 and r.json()["version"] == 2
    historial = client.get(
        "/api/v1/scada/connectors/plc-ciclotron/history").json()
    assert [h["version"] for h in historial] == [1, 2]
    r = client.post("/api/v1/scada/connectors", json={
        "conector_id": "x", "tipo": "opcua", "endpoint": "",
        "configuracion": {}, "responsable": "a"})
    assert r.status_code == 422  # sin endpoint sería simulación


def test_sondeo_real_exito_y_fallo_honesto(client):
    _conector(client)
    r = client.post("/api/v1/scada/connectors/plc-ciclotron/probe")
    assert r.json()["estado"] == "conectado"
    _conector(client, "plc-sintesis", "modbus_tcp",
              "modbus://127.0.0.1:502")
    r = client.post("/api/v1/scada/connectors/plc-sintesis/probe")
    cuerpo = r.json()
    assert cuerpo["estado"] == "fallo_conexion"
    assert "ConnectionError" in cuerpo["detalle"]
    # el fallo genera evento de pérdida de comunicación (31.11)
    eventos = client.get("/api/v1/scada/events").json()
    assert any(e["tipo"] == "perdida_comunicacion"
               and e["dispositivo"] == "plc-sintesis" for e in eventos)


def test_lectura_sin_conexion_503_y_con_conexion_real(client):
    _conector(client)
    r = client.post("/api/v1/scada/connectors/plc-ciclotron/read",
                    params={"variable": "ns://2;i=3"})
    assert r.status_code == 503  # honesto: sin conexión viva
    client.post("/api/v1/scada/connectors/plc-ciclotron/probe")
    r = client.post("/api/v1/scada/connectors/plc-ciclotron/read",
                    params={"variable": "ns://2;i=3"})
    assert r.status_code == 200
    assert r.json()["lectura"]["valor"] == 42.0


def test_adaptador_plc_traduccion_real(client):
    r = client.post("/api/v1/scada/adapters", json={
        "fabricante": "siemens-s7",
        "mapeo": {"DB1.TEMP": "temperatura", "DB1.PRES": "presion"},
        "responsable": "automatizacion"})
    assert r.status_code == 201
    r = client.post("/api/v1/scada/adapters/siemens-s7/translate",
                    json={"datos_externos": {
                        "DB1.TEMP": 63.5, "DB1.PRES": 101325,
                        "DB1.OTRO": 1}})
    assert r.json() == {"temperatura": 63.5, "presion": 101325}
    r = client.post("/api/v1/scada/adapters/abb/translate",
                    json={"datos_externos": {}})
    assert r.status_code == 422


def _medicion(valor, variable="temperatura", minutos=0):
    ts = (datetime.now(timezone.utc)
          - timedelta(minutes=minutos)).isoformat()
    return {"dispositivo": "modulo-sintesis-1", "variable": variable,
            "valor": valor, "unidad": "°C", "timestamp": ts,
            "origen": "plc-ciclotron", "calidad": "buena"}


def test_validacion_rango_y_evento_de_anomalia(client):
    client.post("/api/v1/scada/validations", json={
        "variable": "temperatura", "minimo": 0, "maximo": 120,
        "responsable": "automatizacion"})
    r = client.post("/api/v1/scada/measurements", json=_medicion(63.5))
    assert r.status_code == 201
    r = client.post("/api/v1/scada/measurements", json=_medicion(250.0))
    assert r.status_code == 422  # fuera de rango: NO se acepta (31.22)
    eventos = client.get("/api/v1/scada/events").json()
    assert any(e["tipo"] == "validacion" and "rango" in
               e["detalle"]["motivo"] for e in eventos)
    serie = client.get("/api/v1/scada/series/temperatura").json()
    assert len(serie) == 1  # la anomalía no entró en la serie


def test_consistencia_temporal_y_normalizacion_utc(client):
    r = client.post("/api/v1/scada/measurements", json=_medicion(60.0))
    assert r.status_code == 201
    assert r.json()["timestamp"].endswith("+00:00")  # 31.13
    # timestamp anterior a la última medición → rechazado (31.22)
    r = client.post("/api/v1/scada/measurements",
                    json=_medicion(61.0, minutos=10))
    assert r.status_code == 422
    # timestamp futuro → rechazado
    futuro = (datetime.now(timezone.utc)
              + timedelta(hours=1)).isoformat()
    m = _medicion(62.0)
    m["timestamp"] = futuro
    r = client.post("/api/v1/scada/measurements", json=m)
    assert r.status_code == 422


def test_alarmas_historial_completo(client):
    r = client.post("/api/v1/scada/alarms", json={
        "alarma_id": "alm-001", "criticidad": "alta",
        "origen": "celda-caliente-1", "responsable": "operador-1",
        "detalle": "presión fuera de rango"})
    assert r.status_code == 201
    client.post("/api/v1/scada/alarms/alm-001/transition", json={
        "estado": "reconocida", "actor": "operador-1"})
    r = client.post("/api/v1/scada/alarms/alm-001/transition", json={
        "estado": "cerrada", "actor": "supervisor",
        "detalle": "presión restablecida"})
    historial = r.json()["historial"]
    assert [h["estado"] for h in historial] == [
        "activa", "reconocida", "cerrada"]
    # una alarma cerrada no se reabre (31.12)
    r = client.post("/api/v1/scada/alarms/alm-001/transition", json={
        "estado": "reconocida", "actor": "x"})
    assert r.status_code == 422
    # duplicado → 422 (el historial nunca se reinicia)
    r = client.post("/api/v1/scada/alarms", json={
        "alarma_id": "alm-001", "criticidad": "baja", "origen": "x",
        "responsable": "y"})
    assert r.status_code == 422


def test_eventos_operativos_y_estado_honesto(client):
    r = client.post("/api/v1/scada/events", json={
        "tipo": "paro", "dispositivo": "ciclotron-1",
        "detalle": {"motivo": "interlock vacuum"}, "actor": "scada"})
    assert r.status_code == 201
    estado = client.get("/api/v1/scada/status").json()
    assert estado["persistencia_31_23"]["influxdb"] == "no_configurado"
    assert estado["bus_eventos"] == "no_inyectado"
    meta = client.get("/api/v1/scada/meta").json()
    assert set(meta["tipos_conector"]) == {
        "opcua", "mqtt", "modbus_tcp", "modbus_rtu"}
    audit = client.get("/api/v1/scada/audit").json()
    assert all("evento_id" in a and "resultado" in a for a in audit)
