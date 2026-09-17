"""
Radiopharma OS - Process Service (Process Twin, EDS Vol. V)
Punto de entrada FastAPI.

Gemelo de proceso radioquímico: continúa donde el Physics Twin concluye
(actividad al EOB) y simula la cascada post-proceso hasta el radiofármaco
listo para liberación clínica (EOS): transferencia, síntesis, purificación,
formulación, transporte — con decaimiento físico y eficiencias por paso.
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.application.logistics_service import LogisticsService
from app.application.process_service import ProcessService
from app.application.synthesis_service import SynthesisService
from app.presentation.routers import (beme_api, clinical_api, component_api,
                                  cost_api,
                                  vacuum_api,
                                  facility_api,
                                  osrm_api,
                                  financial_api,
                                  simulation_api,
                                  logistics_api,
                                  operations_api,
                                  process_api,
                                        synthesis_api)

app = FastAPI(
    title="Radiopharma OS - Process Service",
    version="0.5.0",
    description=(
        "Process Twin: cascada EOB -> EOS con decaimiento por paso, "
        "eficiencias de proceso y estimación de dosis por paciente. "
        "Logistics Twin: rutas terrestres/aéreas con decaimiento en tránsito."),
)

process_api.init(ProcessService())
logistics_api.init(LogisticsService())
osrm_api.init()
synthesis_api.init(SynthesisService())
operations_api.init()
clinical_api.init()
facility_api.init()
component_api.init(facility_api._twin)  # comparte el Asset Registry real
vacuum_api.init(facility_api._twin)     # mismo Asset Registry
from app.domain.cost_engine import CostEngine
cost_api.init(CostEngine("data/costos/corridas.json"))  # Fase 29
beme_api.init()
simulation_api.init()
financial_api.init()
# CORS: la consola web (origen distinto) consume estas APIs desde el navegador
_cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(process_api.router)
app.include_router(logistics_api.router)
app.include_router(osrm_api.router)
app.include_router(synthesis_api.router)
app.include_router(operations_api.router)
app.include_router(clinical_api.router)
app.include_router(facility_api.router)
app.include_router(beme_api.router)
app.include_router(simulation_api.router)
app.include_router(financial_api.router)
app.include_router(component_api.router)
app.include_router(vacuum_api.router)
app.include_router(cost_api.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"service": "process-service", "status": "ok", "version": "0.5.0"}
