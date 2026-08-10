"""Pruebas de estructura de los DAGs Airflow (cap. 8) sin runtime.

Airflow no ejecuta cálculos científicos (8.7): las pruebas verifican
que las tareas solo invocan endpoints HTTP y que el flujo canónico
de orquestación (8.17/8.19) se respeta.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

AIRFLOW_DIR = Path(__file__).resolve().parents[1] / "airflow" / "dags"


def _cargar(nombre: str):
    spec = importlib.util.spec_from_file_location(
        nombre, AIRFLOW_DIR / f"{nombre}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = mod
    spec.loader.exec_module(mod)
    return mod


def test_flujo_canonico_produccion():
    dag = _cargar("radiopharma_production_dag")
    orden = [t["task"] for t in dag.TASK_FLOW]
    assert orden == ["yield_production", "synthesis_reaction",
                     "synthesis_purification", "synthesis_formulation",
                     "qc_release", "inventory_register",
                     "update_indicators"]
    assert dag.SCHEDULE
    assert dag.DAG_ID == "radiopharma_production"


def test_airflow_no_calcula_ciencia():
    """8.7: las tareas solo invocan endpoints; no hay motores
    científicos importados en el DAG."""
    dag = _cargar("radiopharma_production_dag")
    for t in dag.TASK_FLOW:
        assert t["path"].startswith("/api/v1/")
    fuente = (AIRFLOW_DIR / "radiopharma_production_dag.py").read_text()
    assert "YieldCalculator" not in fuente
    assert "import scipy" not in fuente and "import numpy" not in fuente
    assert "no ejecuta" in fuente and "cálculos científicos" in fuente


def test_dag_economico_8_19():
    dag = _cargar("radiopharma_economic_dag")
    orden = [t["task"] for t in dag.TASK_FLOW]
    assert orden == ["collect_batch_costs", "aggregate_radiopharmaceutical",
                     "financial_indicators"]
    assert dag.SCHEDULE


def test_build_dag_sin_runtime_es_honesto():
    dag = _cargar("radiopharma_production_dag")
    import importlib
    try:
        import airflow  # noqa: F401
        tiene_runtime = True
    except ImportError:
        tiene_runtime = False
    if not tiene_runtime:
        assert dag._dag is None
        import pytest
        with pytest.raises(RuntimeError, match="runtime Airflow"):
            dag.build_dag()
