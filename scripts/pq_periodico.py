#!/usr/bin/env python3
"""PQ periódico programado (fase 5.4): re-ejecuta un protocolo PQ contra
los servicios vivos y anexa el resultado real a un histórico append-only
(out/pq_historico.jsonl) — evidencia de estado de control continuo
(Informe 14.9). El histórico nunca se reescribe.

Programación (cron del sistema o del orquestador):
  */15 * * * *  python3 /app/scripts/pq_periodico.py pq_deploy calidad

Uso:
  python3 scripts/pq_periodico.py <protocolo_id> <ejecutor> [--host localhost]
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from datetime import datetime, timezone

HISTORICO = "out/pq_historico.jsonl"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("protocolo_id")
    ap.add_argument("ejecutor")
    ap.add_argument("--host", default="localhost")
    a = ap.parse_args()

    url = (f"http://{a.host}:8005/api/v1/qualification/pq/protocols/"
           f"{a.protocolo_id}/run")
    req = urllib.request.Request(
        url, data=json.dumps({"ejecutor": a.ejecutor}).encode(),
        method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            resultado = json.loads(r.read().decode())
    except Exception as exc:
        # el fallo de ejecución también es evidencia — se anexa honesto
        resultado = {"protocolo_id": a.protocolo_id, "estado": "error",
                     "detalle": f"{type(exc).__name__}: {exc}"}

    os.makedirs(os.path.dirname(HISTORICO), exist_ok=True)
    with open(HISTORICO, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(
            {"timestamp": datetime.now(timezone.utc).isoformat(),
             **resultado}, ensure_ascii=False) + "\n")
    print(f"PQ {a.protocolo_id}: {resultado.get('estado')} "
          f"→ anexado a {HISTORICO}")
    raise SystemExit(0 if resultado.get("estado") == "superada" else 1)


if __name__ == "__main__":
    main()
