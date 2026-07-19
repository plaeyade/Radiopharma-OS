"""
Radiopharma OS - Nuclear Data Service
Punto de entrada FastAPI.

Servicio de datos nucleares del Physics Twin: funciones de excitación
(EXFOR/IAEA) y esquemas de decaimiento (LiveChart/DDEP), con trazabilidad
de procedencia por dataset (ALCOA+).
"""
from __future__ import annotations

from pathlib import Path

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.application.queries import NuclearDataQueries
from app.infrastructure.repositories.csv_cross_section_repository import CsvCrossSectionRepository
from app.infrastructure.repositories.json_decay_repository import JsonDecayRepository
from app.presentation.routers import nuclear_data

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

app = FastAPI(
    title="Radiopharma OS - Nuclear Data Service",
    version="0.1.0",
    description=(
        "Datos nucleares abiertos y versionados para el Physics Twin: "
        "secciones eficaces (IAEA/EXFOR) y decaimiento (LiveChart/DDEP)."),
)

queries = NuclearDataQueries(
    xs_repo=CsvCrossSectionRepository(DATA_DIR),
    decay_repo=JsonDecayRepository(DATA_DIR),
)
nuclear_data.init(queries, DATA_DIR)
# CORS: la consola web (origen distinto) consume estas APIs desde el navegador
_cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(nuclear_data.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"service": "nuclear-data-service", "status": "ok", "version": "0.1.0"}
