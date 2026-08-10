"""Modbus Connector (EDS 31.8).

Lectura real de registros holding de dispositivos Modbus TCP del
SCADA (cap. 31). Las lecturas crudas se normalizan con el mapa de
tags versionado (31.13). Patrón de honestidad de plataforma: sin
dispositivo alcanzable, el conector lo reporta (→ 503) y nunca
simula registros.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from app.infrastructure.scada.normalization import TagMap, normalizar


class ModbusUnavailable(RuntimeError):
    """Dispositivo Modbus no configurado o inalcanzable (→ 503)."""


@dataclass
class ModbusConfig:
    host: str | None
    port: int = 502
    timeout_s: float = 3.0

    @staticmethod
    def from_env() -> "ModbusConfig":
        return ModbusConfig(
            host=os.environ.get("MODBUS_HOST") or None,
            port=int(os.environ.get("MODBUS_PORT", "502")),
            timeout_s=float(os.environ.get("MODBUS_TIMEOUT_S", "3.0")))


def modbus_status(config: ModbusConfig | None = None) -> dict:
    cfg = config or ModbusConfig.from_env()
    try:
        import pymodbus  # noqa: F401
        lib = True
    except ImportError:
        lib = False
    return {"modbus_configurado": bool(cfg.host), "host": cfg.host,
            "port": cfg.port, "pymodbus_disponible": lib,
            "nota": "conector Modbus TCP (31.8): lecturas reales; sin "
                    "dispositivo se reporta honestamente (→ 503) y nunca "
                    "se simulan registros"}


async def leer_registros(registros: dict[str, int], tags: dict[str, TagMap],
                         config: ModbusConfig | None = None,
                         unidad: int = 1) -> dict:
    """Lee registros holding reales y los normaliza (31.8/31.13).

    ``registros`` mapea serie → dirección de registro; ``tags``
    contiene el TagMap de normalización por serie.
    """
    cfg = config or ModbusConfig.from_env()
    if not cfg.host:
        raise ModbusUnavailable("MODBUS_HOST no configurado")
    try:
        from pymodbus.client import AsyncModbusTcpClient
    except ImportError as exc:
        raise ModbusUnavailable(f"pymodbus no instalada: {exc}")
    cliente = AsyncModbusTcpClient(cfg.host, port=cfg.port,
                                   timeout=cfg.timeout_s)
    try:
        if not await cliente.connect():
            raise ModbusUnavailable(
                f"sin conexión Modbus TCP a {cfg.host}:{cfg.port}")
        lecturas = {}
        for serie, direccion in registros.items():
            if serie not in tags:
                raise ModbusUnavailable(
                    f"serie '{serie}' sin TagMap de normalización (31.13)")
            rr = await cliente.read_holding_registers(
                direccion, count=1, device_id=unidad)
            if rr.isError():
                raise ModbusUnavailable(
                    f"error Modbus leyendo {serie} @ {direccion}: {rr}")
            lecturas[serie] = normalizar(float(rr.registers[0]),
                                         tags[serie])
        return {"host": cfg.host, "lecturas": lecturas,
                "fuente": "Modbus TCP real (31.8) normalizado (31.13)"}
    except ModbusUnavailable:
        raise
    except Exception as exc:
        raise ModbusUnavailable(
            f"dispositivo Modbus inalcanzable en {cfg.host}:{cfg.port}: "
            f"{exc}")
    finally:
        try:
            cliente.close()
        except Exception:
            pass
