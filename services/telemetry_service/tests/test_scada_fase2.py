"""Tests fase 2 — cableado industrial: suscripción MQTT real (31.7) y
perfiles de adaptador PLC por fabricante (31.9)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.domain.scada import ScadaEngine
from app.main import app
from app.presentation.routers import scada_api


class _ClienteMqttFalso:
    """Cliente MQTT de prueba: guarda el callback y permite disparar
    mensajes como los entregaría el hilo de red real de paho."""

    def __init__(self, endpoint, cfg):
        self.endpoint = endpoint
        self.conectado = False
        self.callbacks = {}

    def conectar(self):
        self.conectado = True

    def leer(self, variable):
        raise RuntimeError("MQTT es pub/sub (31.7)")

    def suscribir(self, topico, callback):
        if not self.conectado:
            raise RuntimeError("no conectado")
        self.callbacks[topico] = callback

    def disparar(self, topico, payload):
        self.callbacks[topico](topico, payload)


@pytest.fixture()
def engine():
    eng = ScadaEngine(fabricas_clientes={
        "mqtt": lambda ep, cfg: _ClienteMqttFalso(ep, cfg),
    })
    scada_api.init(eng)
    return eng


@pytest.fixture()
def client(engine):
    return TestClient(app)


def _conector_mqtt_vivo(engine, conector_id="mqtt_planta"):
    engine.registrar_conector(conector_id, "mqtt", "mqtt://broker:1883",
                              {}, responsable="integrador")
    engine.sondear(conector_id)
    return engine._clientes_vivos[conector_id]


def test_suscripcion_mqtt_ingiere_mediciones_reales(engine):
    mqtt = _conector_mqtt_vivo(engine)
    engine.suscribir_mqtt("mqtt_planta", "ciclotron/haz", "cyclotron_main",
                          "corriente_haz_ua", "uA", responsable="integrador")
    mqtt.disparar("ciclotron/haz", "70.5")
    mqtt.disparar("ciclotron/haz", "71.2")
    serie = engine._series["corriente_haz_ua"]
    assert [m.valor for m in serie] == [70.5, 71.2]
    assert all(m.origen == "mqtt:ciclotron/haz" for m in serie)
    subs = engine.suscripciones()
    assert subs[0]["mensajes_ingestados"] == 2
    acciones = [a["accion"] for a in engine.auditoria()]
    assert "suscripcion_mqtt" in acciones


def test_payload_no_numerico_rechazado_honestamente(engine):
    mqtt = _conector_mqtt_vivo(engine)
    engine.suscribir_mqtt("mqtt_planta", "ciclotron/haz", "cyclotron_main",
                          "corriente_haz_ua", "uA", responsable="integrador")
    mqtt.disparar("ciclotron/haz", "no-es-un-numero")
    assert "corriente_haz_ua" not in engine._series
    eventos = [e for e in engine._eventos if e.tipo == "validacion"]
    assert eventos and "no numérico" in eventos[0].detalle.get("motivo", "")


def test_mensaje_fuera_de_rango_no_se_acepta(engine):
    mqtt = _conector_mqtt_vivo(engine)
    engine.definir_validacion("corriente_haz_ua", 0.0, 100.0,
                              responsable="metrologia")
    engine.suscribir_mqtt("mqtt_planta", "ciclotron/haz", "cyclotron_main",
                          "corriente_haz_ua", "uA", responsable="integrador")
    mqtt.disparar("ciclotron/haz", "150.0")
    assert engine._series.get("corriente_haz_ua") in (None, [])


def test_suscripcion_sin_conexion_viva_es_503(engine, client):
    engine.registrar_conector("mqtt_planta", "mqtt", "mqtt://broker:1883",
                              {}, responsable="integrador")
    r = client.post("/api/v1/scada/connectors/mqtt_planta/subscribe",
                    json={"topico": "a/b", "dispositivo": "d",
                          "variable": "v", "unidad": "uA",
                          "responsable": "integrador"})
    assert r.status_code == 503
    assert "sin conexión viva" in r.json()["detail"]


def test_suscripcion_en_conector_no_mqtt_es_422(engine):
    engine.registrar_conector("opc_plc", "opcua", "opc.tcp://plc:4840", {},
                              responsable="integrador")
    with pytest.raises(Exception, match="solo aplica a conectores mqtt"):
        engine.suscribir_mqtt("opc_plc", "a/b", "d", "v", "uA",
                              responsable="integrador")


def test_adaptador_desde_perfil_real(engine):
    adp = engine.registrar_adaptador_desde_perfil("siemens_s7_ciclotron",
                                                  responsable="integrador")
    assert adp.fabricante == "Siemens SIMATIC S7"
    traducido = engine.traducir("Siemens SIMATIC S7",
                                {"DB1_DBD0_corriente_haz": 70.5,
                                 "DB1_DBD4_vacio_camara": 1e-7,
                                 "campo_desconocido": 1})
    assert traducido == {"corriente_haz_ua": 70.5,
                         "vacio_camara_mbar": 1e-7}


def test_perfil_desconocido_error_honesto(engine):
    with pytest.raises(Exception, match="perfil PLC desconocido"):
        engine.registrar_adaptador_desde_perfil("siemens_inventado",
                                                responsable="integrador")


def test_api_perfiles_y_registro(engine, client):
    r = client.get("/api/v1/scada/adapter-profiles")
    assert r.status_code == 200
    ids = {p["perfil_id"] for p in r.json()}
    assert {"siemens_s7_ciclotron", "allen_bradley_ciclotron",
            "modbus_generico_ciclotron"} <= ids
    r2 = client.post("/api/v1/scada/adapters/from-profile",
                     json={"perfil_id": "modbus_generico_ciclotron",
                           "responsable": "integrador"})
    assert r2.status_code == 201
    r3 = client.post("/api/v1/scada/adapters/PLC genérico Modbus/translate",
                     json={"datos_externos": {"holding:0": 68.0,
                                              "holding:10": 1}})
    assert r3.json() == {"corriente_haz_ua": 68.0, "haz_activo": 1}


def test_estado_capa_reporta_suscripciones(engine):
    _conector_mqtt_vivo(engine)
    engine.suscribir_mqtt("mqtt_planta", "ciclotron/haz", "cyclotron_main",
                          "corriente_haz_ua", "uA", responsable="integrador")
    estado = engine.estado_capa()
    assert estado["suscripciones_mqtt"] == 1
    assert "mensajes_mqtt_ingestados" in estado
