#!/usr/bin/env python3
"""
Servidor OPC-UA simulado del ciclotrón (banco de pruebas del conector).

Expone los mismos nodos que publicaría el PLC del acelerador:

    Ciclotron/
      Beam/     Current_uA, Energy_MeV
      Target/   Pressure_psi
      Cooling/  Flow_lpm

con el modelo de proceso del simulador de telemetría (rampa de haz,
deriva térmica, ruido gaussiano, oscilación del caudal) y excursión
opcional de enfriamiento. Sirve para probar el conector OPC-UA →
Telemetry Service sin hardware; contra el PLC real solo cambian el
endpoint y el mapa de tags.

Uso:
    python pipelines/opcua_server_sim.py [--port 4840] [--excursion]
"""
from __future__ import annotations

import argparse
import asyncio
import math
import random

from asyncua import Server

NAMESPACE = "urn:radiopharma-os:cyclotron"
# serie de telemetría → ruta de nodo (browse path bajo Objects/Ciclotron)
NODE_PATHS = {
    "beam_current_ua": ("Beam", "Current_uA"),
    "beam_energy_mev": ("Beam", "Energy_MeV"),
    "target_pressure_psi": ("Target", "Pressure_psi"),
    "cooling_flow_lpm": ("Cooling", "Flow_lpm"),
}


class CyclotronModel:
    """Estado del proceso: meseta a `corriente` µA con rampa y ruido."""

    def __init__(self, corriente: float = 40.0, energia: float = 16.5,
                 excursion: bool = False, periodo_min: float = 60.0,
                 seed: int = 42) -> None:
        self.corriente = corriente
        self.energia = energia
        self.excursion = excursion
        self.periodo_min = periodo_min
        self._rng = random.Random(seed)
        self._t = 0.0  # segundos de corrida simulada

    def step(self, dt_s: float) -> dict[str, float]:
        self._t = (self._t + dt_s) % (self.periodo_min * 60.0)
        frac = self._t / (self.periodo_min * 60.0)
        rampa = min(1.0, frac / 0.05)
        deriva = 1.0 - 0.01 * frac
        g = self._rng.gauss
        corriente = self.corriente * rampa * deriva + g(0, 0.15)
        presion = 320 + 25 * rampa + g(0, 0.8)
        caudal = 12.0 + 0.4 * math.sin(frac * math.pi * 4) + g(0, 0.05)
        if self.excursion and 0.60 <= frac <= 0.66:
            caudal = 8.5 + g(0, 0.08)
            presion += 18.0 * math.sin((frac - 0.60) / 0.06 * math.pi)
        return {
            "beam_current_ua": round(corriente, 3),
            "beam_energy_mev": self.energia,
            "target_pressure_psi": round(presion, 3),
            "cooling_flow_lpm": round(caudal, 3),
        }


async def crear_servidor(port: int, modelo: CyclotronModel) -> tuple[Server, dict]:
    """Crea el servidor con el árbol de nodos; devuelve (server, nodos)."""
    server = Server()
    await server.init()
    server.set_endpoint(f"opc.tcp://0.0.0.0:{port}/rpos")
    server.set_server_name("Radiopharma OS — Ciclotrón (simulado)")
    idx = await server.register_namespace(NAMESPACE)
    ciclo = await server.nodes.objects.add_object(idx, "Ciclotron")
    nodos: dict[str, object] = {}
    for serie, (grupo, nombre) in NODE_PATHS.items():
        obj = await ciclo.add_object(idx, grupo)
        var = await obj.add_variable(idx, nombre, 0.0)
        await var.set_writable()
        nodos[serie] = var
    return server, nodos


async def _main(args: argparse.Namespace) -> None:
    modelo = CyclotronModel(corriente=args.corriente, energia=args.energia,
                            excursion=args.excursion,
                            periodo_min=args.periodo_min, seed=args.seed)
    server, nodos = await crear_servidor(args.port, modelo)
    async with server:
        print(f"Servidor OPC-UA simulado en opc.tcp://0.0.0.0:{args.port}/rpos")
        print(f"namespace: {NAMESPACE}")
        for serie, (g, n) in NODE_PATHS.items():
            print(f"  Ciclotron/{g}/{n:<14s} ← {serie}")
        print("Ctrl+C para detener.")
        while True:
            muestra = modelo.step(args.intervalo)
            for serie, valor in muestra.items():
                await nodos[serie].set_value(valor)
            await asyncio.sleep(args.intervalo)


def main() -> None:
    ap = argparse.ArgumentParser(description="Servidor OPC-UA simulado del ciclotrón")
    ap.add_argument("--port", type=int, default=4840)
    ap.add_argument("--corriente", type=float, default=40.0)
    ap.add_argument("--energia", type=float, default=16.5)
    ap.add_argument("--intervalo", type=float, default=1.0,
                    help="periodo de actualización de los nodos (s)")
    ap.add_argument("--periodo-min", type=float, default=60.0,
                    help="duración del ciclo de corrida simulada (min)")
    ap.add_argument("--excursion", action="store_true",
                    help="inyectar fallo de enfriamiento al 60-66 % del ciclo")
    ap.add_argument("--seed", type=int, default=42)
    asyncio.run(_main(ap.parse_args()))


if __name__ == "__main__":
    main()
