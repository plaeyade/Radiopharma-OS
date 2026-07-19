#!/usr/bin/env python3
"""
Radiopharma OS - Pipeline de telemetría: simulación de corrida + resumen

Genera series sintéticas realistas de una corrida de irradiación (rampa de
corriente, presión de blanco, caudal de enfriamiento), las ingiere en el
Telemetry Service etiquetadas con el batch_id y muestra el resumen.

Uso:
    python pipelines/telemetry_cli.py --batch B-20260718-XXXX \
        --usuario operador.ciclotron --password *** \
        --duracion-min 30 --corriente 40 --puntos-por-min 6
    python pipelines/telemetry_cli.py --batch B-20260718-XXXX \
        --usuario operador.ciclotron --password *** --solo-resumen
"""
from __future__ import annotations

import argparse
import math
import os
import random
import sys
from datetime import datetime, timedelta, timezone

import httpx

TEL_URL = os.environ.get("TELEMETRY_URL", "http://localhost:8006")
AUTH_URL = os.environ.get("AUTH_URL", "http://localhost:8004")
TIMEOUT = httpx.Timeout(30.0)


def login(username: str, password: str) -> str:
    with httpx.Client(timeout=TIMEOUT) as http:
        r = http.post(f"{AUTH_URL}/api/v1/auth/login",
                      json={"username": username, "password": password})
        r.raise_for_status()
        return r.json()["access_token"]


def simulate_run(batch_id: str, duracion_min: float, corriente: float,
                 puntos_por_min: int, seed: int = 42,
                 excursion: bool = False) -> list[dict]:
    """Series sintéticas: rampa de haz + ruido + deriva térmica leve.

    Con `excursion=True` se inyecta una desviación de proceso realista en
    el 60-66 % de la corrida: el caudal de enfriamiento cae a ~8.5 lpm
    (fallo de bomba) y la presión del blanco sube ~+18 psi como
    consecuencia térmica — dos eventos detectables por deviation-check.
    """
    rng = random.Random(seed)
    n = max(2, int(duracion_min * puntos_por_min))
    t0 = datetime.now(timezone.utc) - timedelta(minutes=duracion_min)
    points = []
    for i in range(n):
        ts = t0 + timedelta(minutes=duracion_min * i / (n - 1))
        frac = i / (n - 1)
        rampa = min(1.0, frac / 0.05)                # rampa 5% inicial
        deriva = 1.0 - 0.01 * frac                   # caída térmica 1%
        corriente_i = corriente * rampa * deriva + rng.gauss(0, 0.15)
        presion_i = 320 + 25 * rampa + rng.gauss(0, 0.8)
        caudal_i = 12.0 + 0.4 * math.sin(frac * math.pi * 4) + rng.gauss(0, 0.05)
        if excursion and 0.60 <= frac <= 0.66:
            caudal_i = 8.5 + rng.gauss(0, 0.08)      # fallo de enfriamiento
            presion_i += 18.0 * math.sin((frac - 0.60) / 0.06 * math.pi)
        for serie, valor in [("beam_current_ua", corriente_i),
                             ("target_pressure_psi", presion_i),
                             ("cooling_flow_lpm", caudal_i)]:
            points.append({"series": serie, "ts": ts.isoformat(),
                           "value": round(valor, 3),
                           "tags": {"batch_id": batch_id}})
    return points


def ingest(points: list[dict], token: str, chunk: int = 500) -> int:
    headers = {"Authorization": f"Bearer {token}"}
    total = 0
    with httpx.Client(timeout=TIMEOUT) as http:
        for i in range(0, len(points), chunk):
            r = http.post(f"{TEL_URL}/api/v1/telemetry/points",
                          json={"points": points[i:i + chunk]}, headers=headers)
            r.raise_for_status()
            total += r.json()["written"]
    return total


def summary(batch_id: str, token: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=TIMEOUT) as http:
        r = http.get(f"{TEL_URL}/api/v1/telemetry/batches/{batch_id}/summary",
                     headers=headers)
        r.raise_for_status()
        return r.json()


def print_summary(s: dict) -> None:
    print(f"Resumen de telemetría · lote {s['batch_id']} · "
          f"{s['total_points']} puntos")
    for x in s["series"]:
        print(f"  {x['series']:22s} n={x['count']:4d}  "
              f"media={x['mean']:8.2f}  min={x['minimum']:8.2f}  "
              f"max={x['maximum']:8.2f}  σ={x['stddev']:.3f}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Pipeline de telemetría (simulador)")
    ap.add_argument("--batch", required=True)
    ap.add_argument("--usuario", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--duracion-min", type=float, default=30.0)
    ap.add_argument("--corriente", type=float, default=40.0)
    ap.add_argument("--puntos-por-min", type=int, default=6)
    ap.add_argument("--excursion", action="store_true",
                    help="inyectar desviación de proceso (fallo de "
                         "enfriamiento al 60-66 % de la corrida)")
    ap.add_argument("--solo-resumen", action="store_true")
    args = ap.parse_args()

    token = login(args.usuario, args.password)
    if not args.solo_resumen:
        points = simulate_run(args.batch, args.duracion_min, args.corriente,
                              args.puntos_por_min, excursion=args.excursion)
        n = ingest(points, token)
        print(f"Ingeridos {n} puntos en {TEL_URL}"
              + (" (con excursión inyectada)" if args.excursion else ""))
    print_summary(summary(args.batch, token))
    return 0


if __name__ == "__main__":
    sys.exit(main())
