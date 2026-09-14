#!/usr/bin/env python3
"""Corrida tipo IBA KIUBE (18 MeV, 300 µA) contra la plataforma viva.

Registra el ciclotrón con fuente citada (las specs del proveedor NUNCA se
inventan — las aporta el usuario con su referencia, 49.11) y ejecuta una
irradiación parametrizada (E, I, t) validada contra los límites reales de
la máquina. La actividad EOB la calcula el Yield Engine real (σ(E) IAEA ·
S(E) ATIMA) y es COTA SUPERIOR declarada: la degradación en ventana
(19.10, cadena SRIM/PSTAR) no se aplica todavía.

Uso:
  python3 scripts/corrida_tipo_kiube.py [--host localhost] \
      [--energia 18.0] [--corriente 300.0] [--tiempo-min 120]
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _req(method: str, url: str, body: dict | None = None):
    req = urllib.request.Request(
        url, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--energia", type=float, default=18.0)
    ap.add_argument("--corriente", type=float, default=300.0)
    ap.add_argument("--tiempo-min", type=float, default=120.0)
    a = ap.parse_args()
    ye = f"http://{a.host}:8002"

    # 1) ciclotrón: si ya está registrado se reutiliza (nunca duplicar);
    #    las specs son las públicas del fabricante, aportadas por el usuario
    existentes = _req("GET", f"{ye}/api/v1/cyclotrons")
    kiube = next((c for c in existentes
                  if c["fabricante"].upper() == "IBA"
                  and c["modelo"].upper() == "KIUBE"), None)
    if kiube is None:
        kiube = _req("POST", f"{ye}/api/v1/cyclotrons", {
            "fabricante": "IBA", "modelo": "KIUBE",
            "energia_max_mev": 18.0, "corriente_max_ua": 300.0,
            "estado_operativo": "proyectado",
            "fuente": ("especificación pública del fabricante aportada por "
                       "el usuario (18 MeV, 300 µA) — verificar contra "
                       "datasheet oficial antes de uso operativo"),
            "registrado_por": "calidad"})
        print(f"ciclotrón registrado: {kiube['ciclotron_id']} "
              f"(v{kiube['version']})")
    else:
        print(f"ciclotrón existente reutilizado: {kiube['ciclotron_id']} "
              f"(v{kiube['version']})")

    # 2) irradiación parametrizada, validada contra límites de la máquina
    irr = _req("POST",
               f"{ye}/api/v1/cyclotrons/{kiube['ciclotron_id']}/irradiations",
               {"energia_mev": a.energia, "corriente_ua": a.corriente,
                "tiempo_min": a.tiempo_min})
    print(json.dumps(irr, ensure_ascii=False, indent=2))

    # 3) estado honesto del poder de frenado (19.10)
    sp = _req("GET", f"{ye}/api/v1/stopping-power/status")
    informe = {"ciclotron": kiube, "irradiacion": irr, "stopping_power": sp}
    out = os.path.join(ROOT, "out", "corrida_kiube.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(informe, fh, ensure_ascii=False, indent=2)
    print(f"\ninforme: {out}")
    if "no_demostrable" in irr.get("eob", {}):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
