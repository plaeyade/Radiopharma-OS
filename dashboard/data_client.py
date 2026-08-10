"""Cliente de datos del Dashboard (EDS 6.18).

Streamlit **no consulta directamente el PLC**: obtiene los datos
procesados desde las APIs de los microservicios (Operational Twin)
y de los almacenes (InfluxDB/PostgreSQL vía Telemetry/Data Lake),
evitando sobrecargar los sistemas industriales.

Todas las funciones son puras sobre ``httpx``: el runtime Streamlit
solo las invoca desde ``streamlit_app.py``.
"""
from __future__ import annotations

import os

import httpx

YE_URL = os.environ.get("YE_URL", "http://localhost:8002")
QC_URL = os.environ.get("QC_URL", "http://localhost:8005")
TEL_URL = os.environ.get("TEL_URL", "http://localhost:8006")
PROCESS_URL = os.environ.get("PROCESS_URL", "http://localhost:8007")
SURROGATE_URL = os.environ.get("SURROGATE_URL", "http://localhost:8008")

_TIMEOUT = 60.0


def produccion_ye(reaction_id: str, target_id: str, beam_energy_mev: float,
                  current_ua: float, irradiation_time_min: float) -> dict:
    r = httpx.post(f"{YE_URL}/api/v1/production", json={
        "reaction_id": reaction_id, "target_id": target_id,
        "beam_energy_mev": beam_energy_mev, "current_ua": current_ua,
        "irradiation_time_min": irradiation_time_min}, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def optimizacion_ye(reaction_id: str, target_id: str,
                    max_beam_power_w: float = 1500.0) -> dict:
    r = httpx.post(f"{YE_URL}/api/v1/production/optimize", json={
        "reaction_id": reaction_id, "target_id": target_id,
        "restricciones": {"max_beam_power_w": max_beam_power_w}},
        timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def qc_release(protocol_id: str, resultados: dict, operador: str) -> dict:
    r = httpx.post(f"{QC_URL}/api/v1/qc/release", json={
        "protocol_id": protocol_id, "resultados": resultados,
        "operador": operador, "motivo": "dashboard Fase 7"}, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def inventario_lotes() -> list[dict]:
    r = httpx.get(f"{PROCESS_URL}/api/v1/inventory/lotes", timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def kpis_operativos() -> dict:
    r = httpx.get(f"{PROCESS_URL}/api/v1/operations/kpis", timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def kpis_economicos(precio_dosis: float | None = None) -> dict:
    params = {"precio_dosis": precio_dosis} if precio_dosis else {}
    r = httpx.get(f"{PROCESS_URL}/api/v1/economics/kpis", params=params,
                  timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def telemetria_batch(batch_id: str) -> dict:
    """Series de un lote desde el Telemetry Service (que a su vez las
    obtiene de InfluxDB/SQLite): Streamlit nunca toca el PLC (6.18)."""
    r = httpx.get(f"{TEL_URL}/api/v1/telemetry/batches/{batch_id}/summary",
                  timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def estado_plataforma() -> dict:
    """Estado honesto de los solvers y runtimes de plataforma."""
    estados: dict = {}
    for nombre, url in [("yield_engine", YE_URL), ("telemetry", TEL_URL),
                        ("surrogate", SURROGATE_URL)]:
        try:
            r = httpx.get(f"{url}/health", timeout=10.0)
            estados[nombre] = r.json() if r.status_code == 200 else {
                "error": r.status_code}
        except Exception as exc:
            estados[nombre] = {"error": str(exc)}
    return estados
