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
from app.presentation.routers import (cyclotron_api, equipment_api, hpc_api,
                                      yield_api)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

app = FastAPI(
    title="Radiopharma OS - Yield Engine",
    version="0.3.0",
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
hpc_api.init()
app.include_router(hpc_api.router)
from app.domain.cyclotron import CiclotronRegistry
from app.domain.irradiation_profile import PerfilIrradiacionRegistry
from app.domain.target_cooling import CoolingRegistry
from app.infrastructure.stopping.pstar_stopping import PstarTables
from app.presentation.routers import irradiation_api

_ciclotrones = CiclotronRegistry()
_pstar = PstarTables(DATA_DIR / "stopping" / "pstar")
cyclotron_api.init(service, registry=_ciclotrones, pstar=_pstar)
app.include_router(cyclotron_api.router)
irradiation_api.init(service, _ciclotrones, CoolingRegistry(),
                     PerfilIrradiacionRegistry(), pstar=_pstar)
app.include_router(irradiation_api.router)

from app.domain.beamline import BeamlineRegistry
from app.domain.radiochemistry import ProcesoRadioquimicoRegistry
from app.domain.synthesis_module import ModuloSintesisRegistry
from app.infrastructure.stopping.external_tables import ExternalStoppingTables
from app.presentation.routers import (beamline_api, radiochemistry_api,
                                      stopping_tables_api)

_beamlines = BeamlineRegistry()
beamline_api.init(_beamlines)
app.include_router(beamline_api.router)
radiochemistry_api.init(service, ProcesoRadioquimicoRegistry(),
                        ModuloSintesisRegistry())
app.include_router(radiochemistry_api.router)
stopping_tables_api.init(ExternalStoppingTables(DATA_DIR / "stopping"
                                                / "external"), service)
app.include_router(stopping_tables_api.router)

from app.domain.beam_optics import LineaOpticaRegistry
from app.presentation.routers import beam_optics_api

beam_optics_api.init(LineaOpticaRegistry(), _beamlines)
app.include_router(beam_optics_api.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"service": "yield-engine", "status": "ok", "version": "0.2.0"}
