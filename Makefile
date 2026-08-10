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
	python -m pytest pipelines/test_batch_cli.py pipelines/test_opcua.py pipelines/test_validation.py -q

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
