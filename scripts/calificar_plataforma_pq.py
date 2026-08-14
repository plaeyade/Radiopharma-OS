#!/usr/bin/env python3
"""Calificación DQ/IQ/OQ de la plataforma + PQ periódico (fase 10, 14.9).

El orden DQ → IQ → OQ → PQ es estricto y lo impone el qc_engine. Este
script ejecuta las etapas previas declarando «cumple» SOLO cuando lo
verifica en el momento:

- DQ: el diseño está documentado (README + docs/ del repositorio).
- IQ: los 8 servicios responden /health 200 AHORA (verificación real;
      si alguno cae, el criterio se declara no cumplido — nunca se
      afirma una instalación no verificada).
- OQ: la batería de tests de pipelines se ejecuta de verdad
      (subproceso pytest) y solo «cumple» si termina en verde.

Después dispara una ejecución del protocolo PQ periódico
(``scripts/pq_periodico.py pq_deploy``), cuyo resultado real se anexa al
histórico append-only ``out/pq_historico.jsonl`` (nunca se reescribe).

Uso:
  python3 scripts/calificar_plataforma_pq.py [--host localhost]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SERVICIOS = {  # nombre → puerto (los 8 microservicios del MVP)
    "nuclear_data": 8001, "yield_engine": 8002, "data_lake": 8003,
    "auth": 8004, "qc_engine": 8005, "telemetry": 8006,
    "process": 8007, "surrogate": 8008,
}
COMPONENTE = "plataforma_rpos"


class Http:
    """Cliente mínimo (inyectable en tests)."""

    def __init__(self, host: str):
        self.base = f"http://{host}"

    def _req(self, method: str, path: str, body: dict | None = None):
        req = urllib.request.Request(
            self.base + path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode())

    def post(self, path: str, body: dict):
        return self._req("POST", path, body)

    def get(self, path: str):
        return self._req("GET", path)


def health_200(http: Http, puerto: int) -> tuple[bool, str]:
    """Verificación REAL de /health — devuelve (ok, detalle medido)."""
    import time
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(f"{http.base}:{puerto}/health")
        with urllib.request.urlopen(req, timeout=5) as r:
            ms = (time.perf_counter() - t0) * 1000
            return r.status == 200, f"GET :{puerto}/health → {r.status} en {ms:.1f} ms"
    except Exception as exc:
        return False, f":{puerto}/health FALLO: {type(exc).__name__}: {exc}"


def ejecutar_bateria_tests() -> tuple[bool, str]:
    """OQ real: ejecuta los tests de pipelines y solo cumple si pasan."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "pipelines", "-q"],
        cwd=ROOT, capture_output=True, text=True, timeout=900)
    ultima = (proc.stdout.strip().splitlines() or ["sin salida"])[-1]
    return proc.returncode == 0, f"pytest pipelines → {ultima}"


def asegurar_componente(http: Http) -> None:
    _, comps = http.get("/api/v1/qualification/components")
    if not any(c["componente_id"] == COMPONENTE for c in comps):
        http.post("/api/v1/qualification/components", {
            "componente_id": COMPONENTE, "nombre": "Plataforma Radiopharma OS MVP",
            "tipo": "plataforma",
            "version": open(os.path.join(ROOT, "VERSION")).read().strip()
            if os.path.exists(os.path.join(ROOT, "VERSION")) else "mvp",
            "responsable": "calidad"})


def etapa(http: Http, nombre: str, criterio: str, motivo: str,
          verificar, evidencia_ref: str) -> dict:
    """Define protocolo y ejecuta la etapa con verificación real previa.

    «cumple» refleja EXCLUSIVAMENTE el resultado de ``verificar()`` —
    un criterio no verificado jamás se declara superado (49.11).
    """
    http.post(f"/api/v1/qualification/components/{COMPONENTE}/protocols",
              {"etapa": nombre, "criterios": [criterio],
               "responsable": "calidad", "motivo": motivo})
    ok, detalle = verificar()
    _, ejec = http.post(
        f"/api/v1/qualification/components/{COMPONENTE}/executions",
        {"etapa": nombre, "entorno": "laboratorio", "ejecutor": "calidad",
         "resultados": [{"criterio": criterio, "cumple": ok,
                         "detalle": detalle, "evidencia_ref": evidencia_ref}]})
    return {"etapa": nombre, "estado": ejec["estado"], "verificado": ok,
            "detalle": detalle}


def definir_pq_deploy(qc: Http, base: Http) -> None:
    """Protocolo PQ de despliegue: /health real de los 8 servicios.

    ``qc`` apunta al qc_engine (puerto 8005); ``base`` es la base sin
    puerto usada para construir las URLs de health de cada servicio.
    """
    qc.post("/api/v1/qualification/pq/protocols", {
        "protocolo_id": "pq_deploy", "componente_id": COMPONENTE,
        "responsable": "calidad",
        "motivo": "PQ periódico de estado de control continuo (14.9)",
        "criterios": [{"criterio": f"{n}_health",
                       "url": f"{base.base}:{p}/health"}
                      for n, p in SERVICIOS.items()]})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    a = ap.parse_args()

    qc = Http(f"{a.host}:8005")          # API del qc_engine
    http = Http(a.host)                  # base sin puerto: /health por servicio
    informe: dict = {"componente": COMPONENTE, "etapas": []}

    asegurar_componente(qc)

    informe["etapas"].append(etapa(
        qc, "DQ", "diseno_documentado_eds",
        "DQ: diseño documentado en especificación canónica",
        lambda: (os.path.exists(os.path.join(ROOT, "README.md"))
                 and os.path.isdir(os.path.join(ROOT, "docs")),
                 "README.md + docs/ presentes en el repositorio"),
        "ESPECIFICACIÓN TÉCNICA DEL MVP INDUSTRIAL (doc canónico)"))

    def verificar_iq():
        resultados = [health_200(http, p) for p in SERVICIOS.values()]
        ok = all(r[0] for r in resultados)
        return ok, "; ".join(d for _, d in resultados)

    informe["etapas"].append(etapa(
        qc, "IQ", "servicios_instalados_health_200",
        "IQ: 8 servicios instalados responden /health 200",
        verificar_iq, "verificación /health en vivo (este script)"))

    informe["etapas"].append(etapa(
        qc, "OQ", "bateria_tests_verde",
        "OQ: suite de tests de pipelines en verde",
        ejecutar_bateria_tests, "pytest pipelines (ejecutado por este script)"))

    definir_pq_deploy(qc, http)  # API en qc:8005; URLs health sin puerto fijo
    pq = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "pq_periodico.py"),
         "pq_deploy", "calidad", "--host", a.host],
        cwd=ROOT, capture_output=True, text=True, timeout=300)
    informe["pq"] = {"salida": pq.stdout.strip(), "exit": pq.returncode}

    # las etapas no verificadas se reportan honestamente; el PQ periódico
    # es quien decide si el orden DQ/IQ/OQ permite ejecutar (14.9)
    informe["nota"] = ("cumple declarado solo tras verificación real; "
                       "histórico PQ append-only en out/pq_historico.jsonl")
    out = os.path.join(ROOT, "out", "calificacion_plataforma.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(informe, fh, ensure_ascii=False, indent=2)
    print(json.dumps(informe, ensure_ascii=False, indent=2))
    raise SystemExit(0 if informe["pq"]["exit"] == 0 else 1)


if __name__ == "__main__":
    main()
