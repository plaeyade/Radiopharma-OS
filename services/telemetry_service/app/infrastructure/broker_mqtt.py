"""Puente REAL al broker MQTT para el Event Bus (EDS 52.6, fase 5).

Publica eventos en tópicos ``rpos/<topico>`` usando paho-mqtt. Cualquier
fallo real de red se propaga como excepción — el bus lo registra
honestamente (dead letter + estado fallo_conexion); nunca se declara
entregado un evento que el broker no aceptó.
"""
from __future__ import annotations


class PuenteMqtt:
    def __init__(self, endpoint: str) -> None:
        # endpoint: "mqtt://host:puerto"
        sin_esquema = endpoint.split("://", 1)[-1]
        host, _, puerto = sin_esquema.partition(":")
        self._host = host
        self._puerto = int(puerto or 1883)
        self._cliente = None

    def conectar(self) -> None:
        import paho.mqtt.client as mqtt

        cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        rc = cliente.connect(self._host, self._puerto, keepalive=10)
        if rc != 0:
            raise ConnectionError(f"MQTT connect rc={rc}")
        self._cliente = cliente

    def publicar(self, topico: str, mensaje: str) -> None:
        if self._cliente is None:
            raise RuntimeError("broker MQTT no conectado")
        info = self._cliente.publish(topico, mensaje, qos=1)
        info.wait_for_publish(timeout=5.0)
        if not info.is_published():
            raise ConnectionError(
                f"el broker no confirmó la publicación en {topico}")


def puente_mqtt_real(endpoint: str) -> PuenteMqtt:
    return PuenteMqtt(endpoint)
