"""
Radiopharma OS - Telemetry Service (Operational Twin, Fase 1)
Punto de entrada FastAPI.

Series temporales de la corrida de irradiación con backend conmutable:
SQLite (dev/test) o InfluxDB 2.x (despliegue), etiquetadas por batch_id.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.application.telemetry_service import TelemetryService
from app.config import load_settings
from app.presentation.routers import telemetry, events_api

settings = load_settings()


def _build_store():
    if settings.backend == "influx":
        from app.infrastructure.influx.influx_telemetry_store import (
            InfluxTelemetryStore)
        return InfluxTelemetryStore(settings.influx_url, settings.influx_token,
                                    settings.influx_org, settings.influx_bucket)
    from app.infrastructure.db.sqlite_telemetry_store import SqliteTelemetryStore
    return SqliteTelemetryStore(settings.database_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = _build_store()
    await store.create_schema()
    telemetry.init(TelemetryService(store))
    yield
    await store.dispose()


app = FastAPI(
    title="Radiopharma OS - Telemetry Service",
    version="0.1.0",
    description="Series de telemetría del gemelo operacional (SQLite/InfluxDB).",
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

app.include_router(telemetry.router)
events_api.init()
app.include_router(events_api.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"service": "telemetry-service", "status": "ok", "version": "0.1.0"}
