"""Pruebas del conector PLC OPC-UA (cap. 30): roundtrip real de protocolo
con un servidor OPC-UA real en proceso + honestidad de plataforma."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "pipelines"))
from app.infrastructure.opcua.plc_client import (PlcConfig, PlcUnavailable,  # noqa: E402,E501
                                                 plc_read, plc_status)
from app.main import app  # noqa: E402
from tests.test_jwt_guard import auth_headers  # noqa: E402

NAMESPACE = "urn:radiopharma-os:cyclotron"


async def _servidor_real(port: int):
    """Servidor OPC-UA real (asyncua) con un nodo de corriente de haz."""
    from asyncua import Server
    server = Server()
    await server.init()
    server.set_endpoint(f"opc.tcp://127.0.0.1:{port}")
    idx = await server.register_namespace(NAMESPACE)
    ciclo = await server.nodes.objects.add_object(idx, "Ciclotron")
    var = await ciclo.add_variable(idx, "BeamCurrent", 37.5)
    await var.set_writable(False)
    await server.start()
    return server


def test_status_honesto_sin_configuracion(monkeypatch):
    monkeypatch.delenv("PLC_OPCUA_URL", raising=False)
    st = plc_status()
    assert st["plc_configurado"] is False
    assert "nunca se simula" in st["nota"]


def test_roundtrip_real_opcua():
    """Lectura real por protocolo OPC-UA contra un servidor real."""
    async def _run():
        server = await _servidor_real(14845)
        try:
            cfg = PlcConfig(endpoint="opc.tcp://127.0.0.1:14845",
                            namespace=NAMESPACE)
            res = await plc_read({"beam_current": ["Ciclotron", "BeamCurrent"]},
                                 config=cfg)
            return res
        finally:
            await server.stop()
    res = asyncio.run(_run())
    assert res["lecturas"]["beam_current"] == pytest.approx(37.5)
    assert "PLC real" in res["fuente"]


def test_plc_inalcanzable_es_503_honesto():
    async def _run():
        cfg = PlcConfig(endpoint="opc.tcp://127.0.0.1:19999",
                        namespace=NAMESPACE, timeout_s=1.0)
        with pytest.raises(PlcUnavailable, match="inalcanzable"):
            await plc_read({"beam_current": ["Ciclotron", "BeamCurrent"]},
                           config=cfg)
    asyncio.run(_run())


def test_endpoint_plc_sin_configurar_503(monkeypatch):
    monkeypatch.delenv("PLC_OPCUA_URL", raising=False)
    client = TestClient(app)
    r = client.get("/api/v1/telemetry/plc/status", headers=auth_headers())
    assert r.status_code == 200
    assert r.json()["plc_configurado"] is False
    r2 = client.post("/api/v1/telemetry/plc/read",
                     json={"series": {"beam_current": ["Ciclotron",
                                                       "BeamCurrent"]}},
                     headers=auth_headers("operador", "operador.ciclotron"))
    assert r2.status_code == 503
