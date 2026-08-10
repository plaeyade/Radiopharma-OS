"""Cliente OPC-UA del PLC del ciclotrón (EDS cap. 30; Fase 8).

Conexión real al PLC configurado por despliegue (variable
``PLC_OPCUA_URL``). Patrón de honestidad de plataforma: si el PLC
no está configurado o no responde, el servicio lo reporta (→ 503)
y nunca simula lecturas. El banco de pruebas OPC-UA de `pipelines/`
sigue disponible para validación de integración.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


class PlcUnavailable(RuntimeError):
    """PLC no configurado o inalcanzable (honestidad de plataforma)."""


@dataclass
class PlcConfig:
    endpoint: str | None
    namespace: str = "http://radiopharma.local/ciclotron"
    timeout_s: float = 5.0

    @staticmethod
    def from_env() -> "PlcConfig":
        return PlcConfig(
            endpoint=os.environ.get("PLC_OPCUA_URL") or None,
            namespace=os.environ.get(
                "PLC_OPCUA_NAMESPACE", "http://radiopharma.local/ciclotron"),
            timeout_s=float(os.environ.get("PLC_OPCUA_TIMEOUT_S", "5.0")))


def plc_status(config: PlcConfig | None = None) -> dict:
    """Estado honesto de la integración con el PLC (cap. 30)."""
    cfg = config or PlcConfig.from_env()
    if not cfg.endpoint:
        return {"plc_configurado": False, "plc_alcanzable": False,
                "nota": "PLC_OPCUA_URL no configurada: la integración se "
                        "reporta honestamente y nunca se simula (cap. 30)"}
    return {"plc_configurado": True, "endpoint": cfg.endpoint,
            "plc_alcanzable": None,
            "nota": "la alcanzabilidad se verifica en /plc/read"}


async def plc_read(series_paths: dict[str, list[str]],
                   config: PlcConfig | None = None) -> dict:
    """Lectura real de nodos del PLC vía OPC-UA.

    ``series_paths`` mapea nombre de serie → browse path bajo Objects.
    """
    cfg = config or PlcConfig.from_env()
    if not cfg.endpoint:
        raise PlcUnavailable("PLC_OPCUA_URL no configurada")
    try:
        from asyncua import Client
    except ImportError as exc:
        raise PlcUnavailable(f"asyncua no instalada: {exc}")
    client = Client(cfg.endpoint, timeout=cfg.timeout_s)
    try:
        await client.connect()
        ns = await client.get_namespace_index(cfg.namespace)
        lecturas = {}
        for serie, ruta in series_paths.items():
            path = ["0:Objects"] + [f"{ns}:{p}" for p in ruta]
            nodo = await client.nodes.root.get_child(path)
            lecturas[serie] = await nodo.read_value()
        return {"endpoint": cfg.endpoint, "lecturas": lecturas,
                "fuente": "PLC real vía OPC-UA (cap. 30)"}
    except PlcUnavailable:
        raise
    except Exception as exc:
        raise PlcUnavailable(
            f"PLC inalcanzable en {cfg.endpoint}: {exc}")
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
