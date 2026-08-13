#!/usr/bin/env python3
"""Expediente de inspección RCAE/GMP — compilado REAL desde los servicios
vivos (fase 5.3).

Reúne, de fuentes reales y citadas: estado de calificación DQ/IQ/OQ/PQ de
cada componente, historial de ejecuciones PQ, estado de conectores
externos, persistencia SCADA, broker de eventos y trazas de auditoría.
Lo que no responde se marca honestamente ``sin_evidencia`` — el
expediente nunca declara lo que no puede demostrar (49.11).

Uso:
  python3 scripts/expediente_inspeccion.py [--host localhost] \
      [--componente plataforma_rpos] [--out out/expediente_inspeccion.json]
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime, timezone

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get(url: str, token: str | None = None):
    try:
        req = urllib.request.Request(url)
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=8) as r:
            return {"ok": True, "datos": json.loads(r.read().decode())}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--componente", default="plataforma_rpos")
    ap.add_argument("--out", default="out/expediente_inspeccion.json")
    ap.add_argument("--token", default=None,
                    help="JWT para fuentes autenticadas (p. ej. simulaciones "
                         "del Data Lake); sin él se marcan sin_evidencia")
    a = ap.parse_args()
    h = a.host

    exp = {
        "expediente_id": f"INSPEC-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}",
        "compilado_en": datetime.now(timezone.utc).isoformat(),
        "fuentes": {},
    }
    puntos = {
        "calificacion_componente":
            f"http://{h}:8005/api/v1/qualification/components/{a.componente}/status",
        "expediente_rcae":
            f"http://{h}:8005/api/v1/qualification/components/{a.componente}/dossier",
        "protocolos_pq":
            f"http://{h}:8005/api/v1/qualification/pq/protocols",
        "auditoria_pq":
            f"http://{h}:8005/api/v1/qualification/pq/audit",
        "conectores_nucleares":
            f"http://{h}:8001/api/v1/connectors/status",
        "scada_rtmsil":
            f"http://{h}:8006/api/v1/scada/status",
        "broker_eventos":
            f"http://{h}:8006/api/v1/events/broker",
        "osrm_logistica":
            f"http://{h}:8007/api/v1/osrm/status",
        "serving_bentoml":
            f"http://{h}:8008/api/v1/serving/status",
        "genai":
            f"http://{h}:8008/api/v1/genai/status",
        "cumplimiento_rcae":
            f"http://{h}:8005/api/v1/compliance/dashboard",
        "simulaciones_cientificas":
            f"http://{h}:8003/api/v1/simulations",
    }
    for nombre, url in puntos.items():
        r = _get(url, token=a.token)
        exp["fuentes"][nombre] = (r if r["ok"] else {
            "sin_evidencia": True, "motivo": r["error"], "url": url})

    # Historial PQ periódico (out/pq_historico.jsonl) — evidencia de estado
    # de control continuo generada por scripts/pq_periodico.py.
    pq_path = os.path.join(ROOT, "out", "pq_historico.jsonl")
    try:
        with open(pq_path, encoding="utf-8") as fh:
            lineas = [json.loads(ln) for ln in fh if ln.strip()]
        exp["fuentes"]["pq_historico"] = {
            "ok": True,
            "datos": {
                "ejecuciones": len(lineas),
                "ultima": lineas[-1] if lineas else None,
                "archivo": "out/pq_historico.jsonl",
            },
        }
    except Exception as exc:
        exp["fuentes"]["pq_historico"] = {
            "sin_evidencia": True,
            "motivo": f"{type(exc).__name__}: {exc}",
            "archivo": "out/pq_historico.jsonl",
        }

    sin_evidencia = [k for k, v in exp["fuentes"].items() if not v.get("ok")]
    exp["resumen"] = {
        "fuentes_consultadas": len(puntos),
        "fuentes_sin_evidencia": sin_evidencia,
        "nota": ("expediente compilado solo desde evidencia real; las "
                 "fuentes sin evidencia se declaran, nunca se suplen "
                 "(49.11/49.18 — marcador no_demostrable)"),
    }
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(exp, fh, ensure_ascii=False, indent=2)
    print(f"expediente: {a.out}")
    print(f"fuentes sin evidencia: {sin_evidencia or 'ninguna'}")


if __name__ == "__main__":
    main()
