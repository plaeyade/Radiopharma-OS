"""Pruebas de los conectores SCADA (EDS 31.7/31.8/31.13).

Modbus se verifica con roundtrip real de protocolo contra un
servidor Modbus TCP real en proceso; MQTT se verifica con
honestidad de plataforma (sin broker en el sandbox).
"""
from __future__ import annotations

import asyncio
import sys
import warnings
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.infrastructure.scada.modbus_connector import (  # noqa: E402
    ModbusConfig, ModbusUnavailable, leer_registros, modbus_status)
from app.infrastructure.scada.mqtt_connector import (  # noqa: E402
    MqttConfig, MqttUnavailable, mqtt_status, suscribir_lecturas)
from app.infrastructure.scada.normalization import (  # noqa: E402
    NormalizacionInvalida, TagMap, normalizar)
from app.main import app  # noqa: E402
from tests.test_jwt_guard import auth_headers  # noqa: E402

warnings.filterwarnings("ignore", category=DeprecationWarning)


# ------------------------------------------------------- normalización 31.13
def test_normalizacion_escala_offset():
    tag = TagMap(serie="target_temperature", unidad="C", escala=0.1,
                 offset=-40.0, rango_min=-40.0, rango_max=150.0)
    r = normalizar(250.0, tag)  # 250 crudo → -15.0 °C... escala 0.1
    assert r["valor"] == pytest.approx(250.0 * 0.1 - 40.0)
    assert r["unidad"] == "C"
    assert "31.13" in r["fuente"]


def test_normalizacion_fuera_de_rango_rechazada():
    tag = TagMap(serie="beam_current", unidad="uA", rango_max=100.0)
    with pytest.raises(NormalizacionInvalida, match="6.23"):
        normalizar(250.0, tag)


# ---------------------------------------------------------- Modbus 31.8
async def _roundtrip_modbus() -> dict:
    from pymodbus.datastore import (ModbusDeviceContext,
                                    ModbusSequentialDataBlock,
                                    ModbusServerContext)
    from pymodbus.server import StartAsyncTcpServer
    dev = ModbusDeviceContext(hr=ModbusSequentialDataBlock(1, [0] * 100))
    ctx = ModbusServerContext(devices=dev, single=True)
    task = asyncio.create_task(
        StartAsyncTcpServer(context=ctx, address=("127.0.0.1", 15030)))
    await asyncio.sleep(1.0)
    try:
        from pymodbus.client import AsyncModbusTcpClient
        c = AsyncModbusTcpClient("127.0.0.1", port=15030, timeout=2)
        await c.connect()
        await c.write_register(10, 250, device_id=1)  # 25.0 °C con escala 0.1
        c.close()
        cfg = ModbusConfig(host="127.0.0.1", port=15030, timeout_s=2.0)
        tag = TagMap(serie="target_temperature", unidad="C", escala=0.1,
                     rango_min=-40.0, rango_max=150.0)
        return await leer_registros({"target_temperature": 10},
                                    {"target_temperature": tag}, config=cfg)
    finally:
        task.cancel()


def test_modbus_roundtrip_real():
    res = asyncio.run(_roundtrip_modbus())
    lectura = res["lecturas"]["target_temperature"]
    assert lectura["valor"] == pytest.approx(25.0)
    assert "31.8" in res["fuente"]


def test_modbus_inalcanzable_503_honesto():
    async def _run():
        cfg = ModbusConfig(host="127.0.0.1", port=19999, timeout_s=0.5)
        with pytest.raises(ModbusUnavailable):
            await leer_registros({"x": 1},
                                 {"x": TagMap(serie="x", unidad="u")},
                                 config=cfg)
    asyncio.run(_run())


def test_modbus_sin_configurar():
    async def _run():
        with pytest.raises(ModbusUnavailable, match="MODBUS_HOST"):
            await leer_registros({"x": 1},
                                 {"x": TagMap(serie="x", unidad="u")},
                                 config=ModbusConfig(host=None))
    asyncio.run(_run())


# ------------------------------------------------------------- MQTT 31.7
def test_mqtt_status_honesto(monkeypatch):
    monkeypatch.delenv("MQTT_HOST", raising=False)
    st = mqtt_status()
    assert st["mqtt_configurado"] is False
    assert "nunca" in st["nota"]


def test_mqtt_broker_inalcanzable():
    async def _run():
        cfg = MqttConfig(host="127.0.0.1", port=19998, timeout_s=0.5)
        with pytest.raises(MqttUnavailable):
            await suscribir_lecturas(
                {"beam_current": "ciclotron/beam_current"},
                {"beam_current": TagMap(serie="beam_current", unidad="uA")},
                config=cfg)
    asyncio.run(_run())


# ------------------------------------------------------------ endpoints
def test_endpoint_scada_status():
    client = TestClient(app)
    r = client.get("/api/v1/telemetry/scada/status", headers=auth_headers())
    assert r.status_code == 200
    cuerpo = r.json()
    assert set(cuerpo) >= {"opc_ua", "modbus", "mqtt"}


def test_endpoint_modbus_sin_config_503(monkeypatch):
    monkeypatch.delenv("MODBUS_HOST", raising=False)
    client = TestClient(app)
    r = client.post("/api/v1/telemetry/scada/modbus/read",
                    json={"registros": {"t": 1},
                          "tags": {"t": {"serie": "t", "unidad": "C"}}},
                    headers=auth_headers("operador", "operador.ciclotron"))
    assert r.status_code == 503
