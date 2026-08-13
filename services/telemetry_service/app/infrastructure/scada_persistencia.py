"""Almacenes REALES de persistencia SCADA (EDS 31.23) — fase 5.

InfluxDB vía su API HTTP (/api/v2/write, line protocol) y Redis vía
protocolo RESP sobre socket (LPUSH por variable). Cualquier fallo real de
red/escritura se propaga como excepción — la capa SCADA lo registra
honestamente como ``fallo_persistencia``; nunca se declara persistido lo
que no se escribió. Sin almacén configurado, ``estado_capa`` sigue
reportando ``no_configurado``.
"""
from __future__ import annotations

import json
import socket
import urllib.request
from datetime import datetime, timezone


def _ns(timestamp: str) -> int:
    ts = datetime.fromisoformat(timestamp)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return int(ts.timestamp() * 1_000_000_000)


class AlmacenInflux:
    """Escritura real en InfluxDB 2.x (line protocol, 31.23)."""

    nombre = "influxdb"

    def __init__(self, url: str, token: str, org: str, bucket: str,
                 timeout_s: float = 5.0) -> None:
        if not url.startswith(("http://", "https://")):
            raise ValueError("url InfluxDB debe ser http(s)")
        self._url = url.rstrip("/")
        self._token = token
        self._org = org
        self._bucket = bucket
        self._timeout = timeout_s

    def sondear(self) -> None:
        req = urllib.request.Request(f"{self._url}/health")
        with urllib.request.urlopen(req, timeout=self._timeout) as r:
            if r.status != 200:
                raise ConnectionError(f"InfluxDB health HTTP {r.status}")

    def escribir(self, medicion: dict) -> None:
        linea = (
            f"scada_medicion,dispositivo={medicion['dispositivo']},"
            f"variable={medicion['variable']},origen={medicion['origen']},"
            f"calidad={medicion['calidad']} "
            f"valor={float(medicion['valor'])} "
            f"{_ns(medicion['timestamp'])}"
        )
        req = urllib.request.Request(
            f"{self._url}/api/v2/write?org={self._org}"
            f"&bucket={self._bucket}&precision=ns",
            data=linea.encode("utf-8"), method="POST",
            headers={"Authorization": f"Token {self._token}",
                     "Content-Type": "text/plain; charset=utf-8"})
        with urllib.request.urlopen(req, timeout=self._timeout) as r:
            if r.status not in (200, 204):
                raise ConnectionError(f"InfluxDB write HTTP {r.status}")


class AlmacenRedis:
    """Escritura real en Redis (RESP sobre socket, LPUSH por variable)."""

    nombre = "redis"

    def __init__(self, host: str, puerto: int = 6379,
                 timeout_s: float = 5.0) -> None:
        self._host = host
        self._puerto = int(puerto)
        self._timeout = timeout_s

    def _comando(self, *args: str) -> str:
        partes = [f"*{len(args)}"]
        for a in args:
            b = str(a).encode("utf-8")
            partes.append(f"${len(b)}")
            partes.append(str(a))
        with socket.create_connection((self._host, self._puerto),
                                      timeout=self._timeout) as s:
            s.sendall(("\r\n".join(partes) + "\r\n").encode("utf-8"))
            resp = s.recv(4096).decode("utf-8", "replace")
        if resp.startswith("-"):
            raise ConnectionError(f"Redis error: {resp.strip()}")
        return resp.strip()

    def sondear(self) -> None:
        if not self._comando("PING").startswith("+PONG"):
            raise ConnectionError("Redis PING sin PONG")

    def escribir(self, medicion: dict) -> None:
        clave = f"scada:{medicion['variable']}"
        self._comando("RPUSH", clave, json.dumps(medicion,
                                                 ensure_ascii=False))
