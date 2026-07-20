"""
Radiopharma OS - Yield Engine
Punto de entrada FastAPI.

Motor de rendimiento del Physics Twin: actividad a saturación y EOB para
blancos gruesos, integrando sigma(E) (IAEA/EXFOR) y S(E) (CATIMA/ATIMA).
"""
from __future__ import annotations

from pathlib import Path

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.application.calibration_service import (CalibrationService,
                                                 EquipmentCatalog)
from app.application.production_service import ProductionService
from app.infrastructure.repositories.factory import build_reaction_provider
from app.infrastructure.stopping.factory import build_stopping_provider
from app.presentation.routers import equipment_api, yield_api

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

app = FastAPI(
    title="Radiopharma OS - Yield Engine",
    version="0.2.0",
    description=(
        "Cálculo de rendimiento de blanco grueso para producción de "
        "radionúclidos PET (MVP: 18O(p,n)18F)."),
)

service = ProductionService(
    stopping=build_stopping_provider(DATA_DIR / "stopping"),
    rxn=build_reaction_provider(DATA_DIR),
)
yield_api.init(service)

calibration = CalibrationService(
    store_path=Path(os.environ.get("YE_CALIBRATION_STORE",
                                   DATA_DIR / "calibrations.json")),
    catalog=EquipmentCatalog(DATA_DIR / "equipment.json"),
)
equipment_api.init(service, calibration)
# CORS: la consola web (origen distinto) consume estas APIs desde el navegador
_cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(yield_api.router)
app.include_router(equipment_api.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"service": "yield-engine", "status": "ok", "version": "0.2.0"}
