"""
Radiopharma OS - QC Engine (Quality Control Twin, EDS Vol. IV)
Punto de entrada FastAPI.

Control de calidad físico del radiofármaco: corrección por decaimiento,
verificación de vida media y criterios de aceptación configurables.
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.application.qc_release_service import QcReleaseService
from app.application.qc_service import QcService
from app.presentation.routers import compliance_api, qc_api

app = FastAPI(
    title="Radiopharma OS - QC Engine",
    version="0.2.0",
    description=(
        "Control de calidad físico: decay correction, half-life fit "
        "(pureza radionuclídica) y reglas de aceptación."),
)

qc_api.init(QcService())
qc_api.init_release(QcReleaseService())
qc_api.init_instruments()
qc_api.init_dosimetry()
compliance_api.init()
# CORS: la consola web (origen distinto) consume estas APIs desde el navegador
_cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(qc_api.router)
app.include_router(compliance_api.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"service": "qc-engine", "status": "ok", "version": "0.2.0"}
