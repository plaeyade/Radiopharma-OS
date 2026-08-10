"""MQTT Connector (EDS 31.7).

Suscripción real a topics MQTT del SCADA (cap. 31). Los payloads se
normalizan con el mapa de tags versionado (31.13). Patrón de
honestidad: sin broker alcanzable, el conector lo reporta (→ 503)
y nunca simula mensajes.
"""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass

from app.infrastructure.scada.normalization import TagMap, normalizar


class MqttUnavailable(RuntimeError):
    """Broker MQTT no configurado o inalcanzable (→ 503)."""


@dataclass
class MqttConfig:
    host: str | None
    port: int = 1883
    timeout_s: float = 5.0

    @staticmethod
    def from_env() -> "MqttConfig":
        return MqttConfig(
            host=os.environ.get("MQTT_HOST") or None,
            port=int(os.environ.get("MQTT_PORT", "1883")),
            timeout_s=float(os.environ.get("MQTT_TIMEOUT_S", "5.0")))


def mqtt_status(config: MqttConfig | None = None) -> dict:
    cfg = config or MqttConfig.from_env()
    try:
        import paho.mqtt.client  # noqa: F401
        lib = True
    except ImportError:
        lib = False
    return {"mqtt_configurado": bool(cfg.host), "host": cfg.host,
            "port": cfg.port, "paho_disponible": lib,
            "nota": "conector MQTT (31.7): suscripción real a topics; "
                    "sin broker se reporta honestamente (→ 503) y nunca "
                    "se simulan mensajes"}


async def suscribir_lecturas(topics: dict[str, str], tags: dict[str, TagMap],
                             config: MqttConfig | None = None,
                             esperar_s: float = 10.0) -> dict:
    """Escucha topics reales y normaliza el primer payload por serie.

    ``topics`` mapea serie → topic MQTT; cada payload debe ser JSON
    con campo ``value`` (número crudo del dispositivo).
    """
    cfg = config or MqttConfig.from_env()
    if not cfg.host:
        raise MqttUnavailable("MQTT_HOST no configurado")
    try:
        import paho.mqtt.client as mqtt
    except ImportError as exc:
        raise MqttUnavailable(f"paho-mqtt no instalada: {exc}")
    for serie in topics:
        if serie not in tags:
            raise MqttUnavailable(
                f"serie '{serie}' sin TagMap de normalización (31.13)")

    lecturas: dict = {}
    conectado = asyncio.Event()
    loop = asyncio.get_running_loop()

    def on_connect(client, userdata, flags, rc, properties=None):
        if rc == 0:
            for topic in topics.values():
                client.subscribe(topic)
            loop.call_soon_threadsafe(conectado.set)

    def on_message(client, userdata, msg):
        for serie, topic in topics.items():
            if msg.topic == topic and serie not in lecturas:
                try:
                    payload = json.loads(msg.payload.decode("utf-8"))
                    lecturas[serie] = normalizar(float(payload["value"]),
                                                 tags[serie])
                except Exception:
                    pass  # payload no normalizable: se ignora (6.23)

    cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    cliente.on_connect = on_connect
    cliente.on_message = on_message
    try:
        cliente.connect(cfg.host, cfg.port, keepalive=int(cfg.timeout_s))
        cliente.loop_start()
        await asyncio.wait_for(conectado.wait(), timeout=cfg.timeout_s)
        esperado = set(topics)
        restante = esperar_s
        while esperado - set(lecturas) and restante > 0:
            await asyncio.sleep(0.1)
            restante -= 0.1
        faltan = sorted(esperado - set(lecturas))
        return {"host": cfg.host, "lecturas": lecturas,
                "series_sin_mensaje": faltan,
                "fuente": "MQTT real (31.7) normalizado (31.13)"}
    except asyncio.TimeoutError:
        raise MqttUnavailable(
            f"broker MQTT no responde en {cfg.host}:{cfg.port}")
    except Exception as exc:
        raise MqttUnavailable(
            f"broker MQTT inalcanzable en {cfg.host}:{cfg.port}: {exc}")
    finally:
        try:
            cliente.loop_stop()
            cliente.disconnect()
        except Exception:
            pass
