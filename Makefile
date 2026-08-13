# Radiopharma OS - comandos de desarrollo
.PHONY: test nds ye up down tel process

test:            ## corre todos los tests
	cd services/nuclear_data_service && PYTHONPATH=. python -m pytest tests/ -q
	cd services/yield_engine && PYTHONPATH=. python -m pytest tests/ -q
	cd services/data_lake_service && PYTHONPATH=. python -m pytest tests/ -q
	cd services/auth_service && PYTHONPATH=. python -m pytest tests/ -q
	cd services/qc_engine && PYTHONPATH=. python -m pytest tests/ -q
	cd services/telemetry_service && PYTHONPATH=. python -m pytest tests/ -q
	cd services/process_service && PYTHONPATH=. python -m pytest tests/ -q
	cd services/surrogate_service && PYTHONPATH=. python -m pytest tests/ -q
	python -m pytest pipelines/test_batch_cli.py pipelines/test_opcua.py pipelines/test_validation.py pipelines/test_airflow_dags.py pipelines/test_qualification.py pipelines/test_dashboards.py pipelines/test_artifacts.py pipelines/test_registro_rcae.py -q

validation:      ## reporte consolidado de validación (Fase 9, 18.13)
	python pipelines/validation_report.py --out validation_report.json

nds:             ## levanta Nuclear Data Service en :8001
	cd services/nuclear_data_service && PYTHONPATH=. uvicorn app.main:app --port 8001

ye:              ## levanta Yield Engine en :8002
	cd services/yield_engine && PYTHONPATH=. uvicorn app.main:app --port 8002

dl:              ## levanta Data Lake en :8003 (SQLite + filesystem)
	cd services/data_lake_service && PYTHONPATH=. uvicorn app.main:app --port 8003

auth:            ## levanta Auth Service en :8004
	cd services/auth_service && PYTHONPATH=. uvicorn app.main:app --port 8004

qc:              ## levanta QC Engine en :8005
	cd services/qc_engine && PYTHONPATH=. uvicorn app.main:app --port 8005

tel:             ## levanta Telemetry Service en :8006 (SQLite)
	cd services/telemetry_service && PYTHONPATH=. uvicorn app.main:app --port 8006

process:         ## levanta Process Service (Process Twin) en :8007
	cd services/process_service && PYTHONPATH=. uvicorn app.main:app --port 8007

surrogate:       ## levanta Surrogate Modeling Server (cap. 20) en :8008
	cd services/surrogate_service && PYTHONPATH=. uvicorn app.main:app --port 8008

up:              ## docker compose up
	docker compose up --build -d

down:
	docker compose down

demo:            ## demo de UN comando: docker compose o modo local + puerta de salud honesta
	./scripts/demo_un_comando.sh

demo-runtimes:   ## E2E real: TALYS/ElmerFEM/OpenGATE servidos vía HTTP (servicios vivos)
	python3 scripts/demo_runtimes_e2e.py localhost

registro-rcae:   ## Fase 8: registra la batería científica en DL + evidencia RCAE (49.8/49.13)
	python3 scripts/registrar_bateria_rcae.py localhost

qualification:   ## calificación DQ/IQ/OQ (Informe 14.9; PQ honestamente no iniciada)
	python pipelines/qualification.py --out qualification_report.json
