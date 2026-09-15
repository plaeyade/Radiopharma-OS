"""API REST de neutrones de producción (EDS 19.12/19.14/19.24).

Fuente (TALYS real) y termalización (OpenGATE/Geant4 real) — ambos con
503 honesto sin runtime: la plataforma nunca inventa cuántos neutrones
rápidos o térmicos produce una irradiación.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.application.neutron_service import NeutronService
from app.infrastructure.gate.neutron_tally import (TallyGateError,
                                                   TallyGateUnavailable)
from app.infrastructure.talys_spectra import TalysError, TalysUnavailable

router = APIRouter(prefix="/api/v1/neutrons", tags=["neutrons"])

_service: NeutronService | None = None


def init(service: NeutronService) -> None:
    global _service
    _service = service


@router.get("/status")
def estado() -> dict:
    """Disponibilidad honesta de los runtimes (TALYS / OpenGATE+G4NDL)."""
    assert _service is not None
    return _service.status()


class ProduccionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reaccion_id: str
    blanco_id: str
    energia_mev: float = Field(gt=0)
    corriente_ua: float = Field(gt=0)
    paso_mev: float = Field(default=1.0, gt=0, le=5.0)


@router.post("/production")
def produccion_neutronica(body: ProduccionIn) -> dict:
    """Neutrones fuente por protón y tasa n/(µA·s) — TALYS real."""
    assert _service is not None
    try:
        return _service.produccion(body.reaccion_id, body.blanco_id,
                                   body.energia_mev, body.corriente_ua,
                                   body.paso_mev)
    except TalysUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except TalysError as exc:
        raise HTTPException(422, str(exc)) from exc


class BlindajeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    material_g4: str = Field(min_length=2, max_length=40)
    espesor_cm: float = Field(gt=0, le=100.0)


class TallyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reaccion_id: str
    blanco_id: str
    energia_mev: float = Field(gt=0)
    corriente_ua: float = Field(gt=0)
    radio_moderador_cm: float = Field(gt=0, le=200.0)
    n_histories: int = Field(default=2000, ge=100, le=200000)
    seed: int = 12345
    material_g4: str = "G4_WATER"
    blindajes: list[BlindajeIn] = Field(default_factory=list, max_length=5)


@router.post("/transport-tally")
def tally_termalizacion(body: TallyIn) -> dict:
    """Neutrones térmicos/epitérmicos/rápidos tras moderador (+blindaje)
    — MC real."""
    assert _service is not None
    try:
        return _service.tally(body.reaccion_id, body.blanco_id,
                              body.energia_mev, body.corriente_ua,
                              body.radio_moderador_cm, body.n_histories,
                              body.seed, body.material_g4,
                              [b.model_dump() for b in body.blindajes])
    except (TallyGateUnavailable, TalysUnavailable) as exc:
        raise HTTPException(503, str(exc)) from exc
    except (TallyGateError, TalysError) as exc:
        raise HTTPException(422, str(exc)) from exc
