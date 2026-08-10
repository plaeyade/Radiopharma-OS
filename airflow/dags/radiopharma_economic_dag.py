"""DAG económico (EDS 8.19): integración con el Economic Digital Twin.

Airflow programa periódicamente (8.19): consolidación de costeos ABC
de los lotes del período, indicadores financieros y actualización de
KPIs económicos (38.12). Airflow coordina; el cálculo lo realiza el
servicio (8.7).
"""
from __future__ import annotations

import os

TASK_FLOW: list[dict] = [
    {"task": "collect_batch_costs", "endpoint": "PROCESS_URL",
     "path": "/api/v1/economics/costeos"},
    {"task": "aggregate_radiopharmaceutical", "endpoint": "PROCESS_URL",
     "path": "/api/v1/economics/radiofarmaco/FDG"},
    {"task": "financial_indicators", "endpoint": "PROCESS_URL",
     "path": "/api/v1/economics/kpis",
     "nota": "indicadores financieros programados (8.19)"},
]

SCHEDULE = "0 22 * * *"  # consolidación nocturna
DAG_ID = "radiopharma_economic"

_SERVICE_URLS = {
    "PROCESS_URL": os.environ.get("PROCESS_URL", "http://localhost:8007"),
}


def call_service(task: dict, payload: dict) -> dict:
    import httpx
    url = _SERVICE_URLS[task["endpoint"]] + task["path"]
    r = httpx.get(url, params=payload, timeout=60.0)
    r.raise_for_status()
    return r.json()


def build_dag():  # pragma: no cover - requiere runtime Airflow
    try:
        from airflow import DAG
        from airflow.operators.python import PythonOperator
    except ImportError as exc:
        raise RuntimeError(
            "runtime Airflow no instalado (cap. 8): estructura "
            "validable sin runtime") from exc
    from datetime import datetime

    with DAG(DAG_ID, schedule=SCHEDULE, start_date=datetime(2026, 1, 1),
             catchup=False, doc_md=__doc__) as dag:
        ops = [PythonOperator(task_id=t["task"],
                              python_callable=call_service,
                              op_kwargs={"task": t, "payload": {}})
               for t in TASK_FLOW]
        for a, b in zip(ops, ops[1:]):
            a >> b
    return dag


try:
    _dag = build_dag()
except RuntimeError:
    _dag = None
