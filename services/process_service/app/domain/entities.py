"""
Entidades de dominio del Process Twin (EDS Vol. V).

Cadena de proceso radioquímico EOB -> EOS: cada paso aplica
decaimiento físico durante su duración y una eficiencia de
transferencia/rendimiento propia.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProtocolStep:
    """Un paso del proceso post-EOB (transferencia, síntesis, ...)."""
    name: str
    duration_min: float
    efficiency: float  # fracción de actividad que sobrevive al paso (0-1]


@dataclass(frozen=True)
class Protocol:
    """Protocolo de proceso para un radiofármaco."""
    protocol_id: str
    name: str
    nuclide: str
    half_life_min: float
    dose_per_patient_gbq: float
    validated: bool
    source: str
    steps: tuple[ProtocolStep, ...]


@dataclass(frozen=True)
class StepResult:
    """Resultado de simular un paso individual."""
    name: str
    duration_min: float
    efficiency: float
    activity_in_gbq: float
    activity_after_decay_gbq: float
    activity_out_gbq: float


@dataclass(frozen=True)
class ChainResult:
    """Resultado de la cascada completa EOB -> EOS."""
    protocol_id: str
    nuclide: str
    half_life_min: float
    eob_activity_gbq: float
    eos_activity_gbq: float
    total_time_min: float
    overall_decay_factor: float
    overall_efficiency: float
    dose_per_patient_gbq: float
    patient_doses: int
    validated: bool
    steps: tuple[StepResult, ...]
