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
NDS_URL = os.environ.get("NDS_URL", "http://localhost:8001")
DL_URL = os.environ.get("DL_URL", "http://localhost:8003")

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


# ------------------------------------------------------ fase 4: producción
# clínica — paneles alimentados SOLO desde las APIs; cada fallo se muestra
# honestamente (nunca se maquilla un servicio caído).

def _consulta(url: str, timeout: float = 10.0, **kw) -> dict:
    """GET real con resultado honesto: datos o error real."""
    try:
        r = httpx.get(url, timeout=timeout, **kw)
        if r.status_code == 200:
            return {"ok": True, "datos": r.json()}
        return {"ok": False, "error": f"HTTP {r.status_code}",
                "detalle": r.text[:300]}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def estado_conectores() -> dict:
    """Estado REAL de los conectores externos (fases 1-2): nuclear
    (EXFOR/SRIM/NNDC), SCADA/MQTT, OSRM, BentoML serving, GenAI y
    extractor documental. Cada bloque muestra sus marcadores honestos."""
    return {
        "nuclear_exfor_srim_nndc":
            _consulta(f"{NDS_URL}/api/v1/connectors/status"),
        "scada_rtmsil_mqtt":
            _consulta(f"{TEL_URL}/api/v1/scada/status"),
        "osrm_logistica":
            _consulta(f"{PROCESS_URL}/api/v1/osrm/status"),
        "bentoml_serving":
            _consulta(f"{SURROGATE_URL}/api/v1/serving/status"),
        "genai_embeddings_llm":
            _consulta(f"{SURROGATE_URL}/api/v1/genai/status"),
        "extractor_documental":
            _consulta(f"{SURROGATE_URL}/api/v1/rag/extractor-status"),
    }


def protocolos_pq() -> dict:
    """Protocolos PQ definidos (Informe 14.9) — fase 3."""
    return _consulta(f"{QC_URL}/api/v1/qualification/pq/protocols")


def estado_calificacion(componente_id: str) -> dict:
    """Estado real DQ/IQ/OQ/PQ de un componente (14.9)."""
    return _consulta(
        f"{QC_URL}/api/v1/qualification/components/{componente_id}/status")


def lotes_clinicos(token: str) -> dict:
    """Lotes de producción clínica (Data Lake, cap. 32/33). Requiere JWT
    real: sin token se muestra honestamente el 401 — el dashboard nunca
    elude la autenticación (cap. 47/48)."""
    if not token:
        return {"ok": False, "error": "autenticacion_requerida",
                "detalle": "introduzca un JWT válido del auth-service "
                           "(47.10); el dashboard nunca elude la "
                           "autenticación"}
    return _consulta(f"{DL_URL}/api/v1/batches",
                     headers={"Authorization": f"Bearer {token}"})


def verificar_ebr(batch_id: str, token: str) -> dict:
    """Verificación de integridad del eBR (hash real, cadena de firma).
    La conformidad PDF/A se valida con veraPDF (perfil calidad del
    compose) — el panel muestra el resultado real, nunca lo declara."""
    if not token:
        return {"ok": False, "error": "autenticacion_requerida",
                "detalle": "introduzca un JWT válido del auth-service"}
    return _consulta(f"{DL_URL}/api/v1/batches/{batch_id}/ebr/verify",
                     headers={"Authorization": f"Bearer {token}"})
