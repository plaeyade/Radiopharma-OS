#!/bin/sh
# Suite canónica completa de Radiopharma OS (estilo Makefile, Fase 40 OQ).
# Uso: sh scripts/suite_canonica.sh   → imprime totales por servicio.
set -e
cd "$(dirname "$0")/.."
TOT=0
for s in nuclear_data_service yield_engine data_lake_service auth_service qc_engine telemetry_service process_service surrogate_service; do
  R=$(cd services/$s && PYTHONPATH=. python3 -m pytest tests/ -q 2>&1 | tail -1)
  echo "$s: $R"
done
R=$(python3 -m pytest pipelines/test_batch_cli.py pipelines/test_opcua.py pipelines/test_validation.py pipelines/test_airflow_dags.py pipelines/test_qualification.py pipelines/test_dashboards.py pipelines/test_artifacts.py pipelines/test_registro_rcae.py pipelines/test_calificacion_pq.py pipelines/test_verificar_datasets.py -q 2>&1 | tail -1)
echo "pipelines: $R"
