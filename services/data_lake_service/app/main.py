"""
Radiopharma OS - Data Lake Service (Fase 1)
Punto de entrada FastAPI.

Persistencia de registros de lote con inmutabilidad ALCOA+:
PostgreSQL (metadatos) + MinIO/S3 (artefactos JSON).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.application.alert_service import AlertService
from app.application.analytics_service import AnalyticsService
from app.application.batch_service import BatchService
from app.application.ebr_service import EbrService
from app.application.simulation_service import SimulationService
from app.config import load_settings
from app.infrastructure.db.database import (build_engine,
                                            build_session_factory,
                                            create_schema)
from app.infrastructure.db.sql_alert_repository import SqlAlertRepository
from app.infrastructure.db.sql_audit_repository import SqlAuditEventRepository
from app.infrastructure.db.sql_batch_repository import SqlBatchRepository
from app.infrastructure.db.sql_qc_repository import SqlQcRepository
from app.infrastructure.db.sql_simulation_repository import SqlSimulationRepository
from app.infrastructure.db.sql_signature_repository import SqlSignatureRepository
from app.infrastructure.security.auth_client import AuthServiceClient
from app.presentation.routers import (alerts, analytics, batches, bcdr_api,
                                      platform_api,
                                        simulations)

settings = load_settings()


def _build_store():
    if settings.storage_backend == "minio":
        from app.infrastructure.storage.minio_object_store import MinioObjectStore
        return MinioObjectStore(settings.minio_endpoint,
                                settings.minio_access_key,
                                settings.minio_secret_key,
                                settings.minio_bucket)
    from app.infrastructure.storage.local_object_store import LocalObjectStore
    return LocalObjectStore(Path(settings.storage_dir))


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = build_engine(settings.database_url)
    await create_schema(engine)
    session_factory = build_session_factory(engine)
    batch_repo = SqlBatchRepository(session_factory)
    qc_repo = SqlQcRepository(session_factory)
    service = BatchService(batch_repo, _build_store(), qc_repo)
    ebr = EbrService(batch_repo, qc_repo,
                     SqlSignatureRepository(session_factory),
                     AuthServiceClient(),
                     audit_events=SqlAuditEventRepository(session_factory))
    alert_service = AlertService(SqlAlertRepository(session_factory),
                                 ebr=ebr,
                                 webhook_url=settings.alert_webhook_url)
    batches.init(service, ebr, alerts=alert_service)
    alerts.init(alert_service)
    analytics.init(AnalyticsService(batch_repo))
    simulations.init(SimulationService(SqlSimulationRepository(session_factory),
                                       _build_store()))
    yield
    await engine.dispose()


app = FastAPI(
    title="Radiopharma OS - Data Lake Service",
    version="0.1.0",
    description="Registros de lote inmutables (ALCOA+) + object store de artefactos.",
    lifespan=lifespan,
)
# CORS: la consola web (origen distinto) consume estas APIs desde el navegador
_cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(batches.router)
app.include_router(analytics.router)
app.include_router(alerts.router)
app.include_router(simulations.router)
bcdr_api.init()
app.include_router(bcdr_api.router)
platform_api.init()
app.include_router(platform_api.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"service": "data-lake-service", "status": "ok", "version": "0.1.0"}
