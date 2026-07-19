#!/usr/bin/env python3
"""
Conector OPC-UA → Telemetry Service.

Cliente industrial que lee periódicamente los nodos del PLC del
ciclotrón (corriente de haz, presión del blanco, caudal de enfriamiento)
y empuja las muestras al Telemetry Service como telemetría de la corrida
del lote, autenticado con JWT de plataforma.

Contra el banco de pruebas:
    python pipelines/opcua_server_sim.py &
    python pipelines/opcua_connector.py --batch B-XXXX \
        --usuario operador.ciclotron --password '...' --duracion-min 1

Contra el PLC real solo cambian el endpoint (`--endpoint`) y, si el
árbol de nodos difiere, el mapa de tags (`--mapa tags.json`).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone

import httpx
from asyncua import Client

from opcua_server_sim import NAMESPACE, NODE_PATHS

TEL_URL = os.environ.get("TELEMETRY_URL", "http://localhost:8006")
AUTH_URL = os.environ.get("AUTH_URL", "http://localhost:8004")
_FLUSH_CADA = 500


class OpcUaSource:
    """Fuente de muestras: lectura periódica de nodos por browse path."""

    def __init__(self, endpoint: str, tag_map: dict[str, list[str]],
                 timeout_s: float = 10.0) -> None:
        self._endpoint = endpoint
        self._mapa = tag_map
        self._timeout = timeout_s
        self._client: Client | None = None
        self._nodos: dict[str, object] = {}

    async def connect(self) -> None:
        self._client = Client(self._endpoint, timeout=self._timeout)
        await self._client.connect()
        ns = await self._client.get_namespace_index(NAMESPACE)
        for serie, ruta in self._mapa.items():
            path = ["0:Objects"] + [f"{ns}:{p}" for p in ruta]
            self._nodos[serie] = await self._client.nodes.root.get_child(path)

    async def read_sample(self, batch_id: str) -> list[dict]:
        """Una lectura de todos los nodos → puntos de telemetría."""
        if self._client is None:
            raise RuntimeError("Fuente no conectada")
        ts = datetime.now(timezone.utc).isoformat()
        puntos = []
        for serie, nodo in self._nodos.items():
            valor = await nodo.read_value()
            puntos.append({"series": serie, "ts": ts,
                           "value": round(float(valor), 3),
                           "tags": {"batch_id": batch_id,
                                    "source": "opcua"}})
        return puntos

    async def close(self) -> None:
        if self._client is not None:
            await self._client.disconnect()
            self._client = None


def _login(usuario: str, password: str) -> str:
    r = httpx.post(f"{AUTH_URL}/api/v1/auth/login",
                   json={"username": usuario, "password": password},
                   timeout=15.0)
    r.raise_for_status()
    return r.json()["access_token"]


def _flush(puntos: list[dict], token: str) -> int:
    if not puntos:
        return 0
    r = httpx.post(f"{TEL_URL}/api/v1/telemetry/points",
                   json={"points": puntos}, timeout=30.0,
                   headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json()["written"]


async def run_connector(endpoint: str, tag_map: dict[str, list[str]],
                        batch_id: str, token: str, intervalo: float,
                        duracion_min: float) -> int:
    """Loop de adquisición: muestrea y empuja al Telemetry Service."""
    fuente = OpcUaSource(endpoint, tag_map)
    await fuente.connect()
    total = 0
    buffer: list[dict] = []
    t0 = asyncio.get_event_loop().time()
    try:
        while True:
            buffer.extend(await fuente.read_sample(batch_id))
            if len(buffer) >= _FLUSH_CADA:
                total += _flush(buffer, token)
                buffer = []
            if duracion_min > 0 and \
                    (asyncio.get_event_loop().time() - t0) >= duracion_min * 60:
                break
            await asyncio.sleep(intervalo)
    finally:
        total += _flush(buffer, token)
        await fuente.close()
    return total


def _cargar_mapa(ruta: str | None) -> dict[str, list[str]]:
    if ruta:
        with open(ruta, encoding="utf-8") as fh:
            return json.load(fh)
    return {serie: ["Ciclotron", *path] for serie, path in NODE_PATHS.items()}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Conector OPC-UA → Telemetry Service")
    ap.add_argument("--endpoint", default="opc.tcp://localhost:4840/rpos")
    ap.add_argument("--batch", required=True)
    ap.add_argument("--usuario", default="operador.ciclotron")
    ap.add_argument("--password", required=True)
    ap.add_argument("--intervalo", type=float, default=1.0,
                    help="periodo de muestreo (s)")
    ap.add_argument("--duracion-min", type=float, default=0.0,
                    help="0 = sin fin (producción)")
    ap.add_argument("--mapa", default=None,
                    help="JSON con el mapa serie → browse path de nodos")
    args = ap.parse_args()

    token = _login(args.usuario, args.password)
    print(f"Conectando a {args.endpoint} (lote {args.batch})…")
    n = asyncio.run(run_connector(
        args.endpoint, _cargar_mapa(args.mapa), args.batch, token,
        args.intervalo, args.duracion_min))
    print(f"Adquisición terminada: {n} puntos enviados a {TEL_URL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
