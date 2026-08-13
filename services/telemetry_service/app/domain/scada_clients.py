"""Clientes industriales reales del RTMSIL (EDS 31.6/31.7/31.8).

Cada fábrica devuelve un cliente con ``conectar()`` y ``leer(variable)``.
Cualquier fallo de librería o de red se propaga como excepción real —
la capa SCADA lo registra honestamente como ``fallo_conexion``.
"""
from __future__ import annotations

import asyncio


class _ClienteOpcua:
    """Cliente OPC UA real (asyncua) — 31.6."""

    def __init__(self, endpoint: str, configuracion: dict) -> None:
        self._endpoint = endpoint
        self._timeout = float(configuracion.get("timeout_s", 5.0))
        self._cliente = None

    def conectar(self) -> None:
        from asyncua import Client

        async def _con():
            cliente = Client(self._endpoint, timeout=self._timeout)
            await cliente.connect()
            return cliente

        self._cliente = asyncio.run(_con())

    def leer(self, variable: str) -> dict:
        if self._cliente is None:
            raise RuntimeError("cliente OPC UA no conectado")

        async def _leer():
            nodo = self._cliente.get_node(variable)
            valor = await nodo.read_value()
            return {"valor": valor, "nodo": variable}

        return asyncio.run(_leer())


class _ClienteMqtt:
    """Cliente MQTT real (paho-mqtt) — 31.7."""

    def __init__(self, endpoint: str, configuracion: dict) -> None:
        # endpoint: "mqtt://host:puerto"
        sin_esquema = endpoint.split("://", 1)[-1]
        host, _, puerto = sin_esquema.partition(":")
        self._host = host
        self._puerto = int(puerto or 1883)
        self._timeout = float(configuracion.get("timeout_s", 5.0))
        self._cliente = None

    def conectar(self) -> None:
        import paho.mqtt.client as mqtt

        cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        rc = cliente.connect(self._host, self._puerto,
                             keepalive=int(self._timeout))
        if rc != 0:
            raise ConnectionError(f"MQTT connect rc={rc}")
        self._cliente = cliente

    def leer(self, variable: str) -> dict:
        # MQTT es publish/subscribe: una "lectura" directa no existe;
        # se reporta honestamente que la variable se recibe por
        # suscripción (31.7), no por polling.
        raise RuntimeError(
            "MQTT es pub/sub (31.7): los datos llegan por suscripción "
            "al tópico, no por lectura directa")

    def suscribir(self, topico: str, callback) -> None:
        """Suscripción REAL al broker (31.7): cada mensaje publicado en
        el tópico invoca ``callback(topico, payload_texto)``. El hilo de
        red es el propio de paho (loop_start)."""
        if self._cliente is None:
            raise RuntimeError("cliente MQTT no conectado")

        def _al_mensaje(cliente, userdata, mensaje):
            callback(mensaje.topic,
                     mensaje.payload.decode("utf-8", errors="replace"))

        self._cliente.on_message = _al_mensaje
        resultado, _mid = self._cliente.subscribe(topico)
        if resultado != 0:
            raise ConnectionError(
                f"MQTT subscribe a {topico} falló rc={resultado}")
        self._cliente.loop_start()


class _ClienteModbus:
    """Cliente Modbus TCP/RTU real (pymodbus) — 31.8."""

    def __init__(self, tipo: str, endpoint: str,
                 configuracion: dict) -> None:
        self._tipo = tipo
        self._endpoint = endpoint
        self._cfg = configuracion
        self._cliente = None

    def conectar(self) -> None:
        if self._tipo == "modbus_tcp":
            from pymodbus.client import ModbusTcpClient
            sin_esquema = self._endpoint.split("://", 1)[-1]
            host, _, puerto = sin_esquema.partition(":")
            self._cliente = ModbusTcpClient(
                host, port=int(puerto or 502),
                timeout=float(self._cfg.get("timeout_s", 5.0)))
        else:
            from pymodbus.client import ModbusSerialClient
            self._cliente = ModbusSerialClient(
                self._endpoint,
                baudrate=int(self._cfg.get("baudrate", 9600)),
                timeout=float(self._cfg.get("timeout_s", 5.0)))
        if not self._cliente.connect():
            raise ConnectionError(f"Modbus {self._tipo} sin respuesta")

    def leer(self, variable: str) -> dict:
        # variable: "holding:<direccion>" o "input:<direccion>"
        if self._cliente is None:
            raise RuntimeError("cliente Modbus no conectado")
        tipo_reg, _, dir_txt = variable.partition(":")
        direccion = int(dir_txt)
        if tipo_reg == "holding":
            rr = self._cliente.read_holding_registers(direccion, 1)
        elif tipo_reg == "input":
            rr = self._cliente.read_input_registers(direccion, 1)
        else:
            raise ValueError(
                f"registro Modbus inválido: {variable} "
                "(use holding:<dir> o input:<dir>)")
        if rr.isError():
            raise RuntimeError(f"error Modbus leyendo {variable}")
        return {"valor": rr.registers[0], "registro": variable}


def cliente_opcua(endpoint: str, configuracion: dict) -> _ClienteOpcua:
    return _ClienteOpcua(endpoint, configuracion)


def cliente_mqtt(endpoint: str, configuracion: dict) -> _ClienteMqtt:
    return _ClienteMqtt(endpoint, configuracion)


def cliente_modbus(tipo: str, endpoint: str,
                   configuracion: dict) -> _ClienteModbus:
    return _ClienteModbus(tipo, endpoint, configuracion)
