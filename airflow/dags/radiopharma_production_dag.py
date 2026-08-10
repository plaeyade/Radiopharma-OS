"""DAG de producción radioquímica (EDS cap. 8; Informe 18.12).

Airflow es el orquestador oficial (8.4): coordina la cadena
producción → síntesis → purificación → formulación → QC →
inventario → indicadores (8.17-8.19). **Airflow no ejecuta
cálculos científicos** (8.7/8.16): cada tarea invoca los
endpoints de los microservicios, que son quienes calculan; las
simulaciones pesadas (TALYS/Elmer/Geant4) corren fuera de Airflow
(8.16) y Airflow únicamente supervisa (8.16).

El DAG es importable sin el runtime de Airflow (tests de
estructura): el grafo se declara en TASK_FLOW y las tareas usan
HTTP contra los servicios.
"""
from __future__ import annotations

import os

# Grafo canónico de la orquestación (8.17): orden y endpoints.
TASK_FLOW: list[dict] = [
    {"task": "yield_production", "endpoint": "YE_URL",
     "path": "/api/v1/production",
     "nota": "cálculo físico en el Yield Engine, no en Airflow (8.7)"},
    {"task": "synthesis_reaction", "endpoint": "PROCESS_URL",
     "path": "/api/v1/synthesis/reaction"},
    {"task": "synthesis_purification", "endpoint": "PROCESS_URL",
     "path": "/api/v1/synthesis/purification"},
    {"task": "synthesis_formulation", "endpoint": "PROCESS_URL",
     "path": "/api/v1/synthesis/formulation"},
    {"task": "qc_release", "endpoint": "QC_URL",
     "path": "/api/v1/qc/release",
     "nota": "recomendación técnica 25.12; la liberación final sigue "
             "el flujo organizativo"},
    {"task": "inventory_register", "endpoint": "PROCESS_URL",
     "path": "/api/v1/inventory/lotes"},
    {"task": "update_indicators", "endpoint": "PROCESS_URL",
     "path": "/api/v1/operations/kpis",
     "nota": "actualización de indicadores (8.17)"},
]

SCHEDULE = "0 4 * * *"  # corrida madrugada previa a la campaña clínica
DAG_ID = "radiopharma_production"

_SERVICE_URLS = {
    "YE_URL": os.environ.get("YE_URL", "http://localhost:8002"),
    "PROCESS_URL": os.environ.get("PROCESS_URL", "http://localhost:8007"),
    "QC_URL": os.environ.get("QC_URL", "http://localhost:8005"),
}


def call_service(task: dict, payload: dict) -> dict:
    """Invocación HTTP al microservicio (nunca cálculo local, 8.7)."""
    import httpx
    url = _SERVICE_URLS[task["endpoint"]] + task["path"]
    r = httpx.post(url, json=payload, timeout=120.0)
    r.raise_for_status()
    return r.json()


def build_dag():  # pragma: no cover - requiere runtime Airflow
    """Construcción del DAG cuando el runtime Airflow está disponible."""
    try:
        from airflow import DAG
        from airflow.operators.python import PythonOperator
    except ImportError as exc:
        raise RuntimeError(
            "runtime Airflow no instalado: el DAG se declara para el "
            "despliegue orquestado (cap. 8); la estructura se valida "
            "sin runtime en pipelines/test_airflow_dags.py") from exc
    from datetime import datetime

    with DAG(DAG_ID, schedule=SCHEDULE, start_date=datetime(2026, 1, 1),
             catchup=False,
             doc_md=__doc__) as dag:
        ops = []
        for t in TASK_FLOW:
            ops.append(PythonOperator(
                task_id=t["task"], python_callable=call_service,
                op_kwargs={"task": t, "payload": {}}))
        for a, b in zip(ops, ops[1:]):
            a >> b
    return dag


try:
    _dag = build_dag()  # registro cuando Airflow importa el fichero
except RuntimeError:
    _dag = None  # entorno sin Airflow: estructura validable igualmente
