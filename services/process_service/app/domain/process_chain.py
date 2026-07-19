"""
Motor de cascada del Process Twin (EDS Vol. V).

Matemática por paso:
    a_decay = a_in * 0.5 ** (duration_min / half_life_min)
    a_out   = a_decay * efficiency

Cierre de cadena:
    EOS   = EOB * Π(0.5^(t_i/T½)) * Π(η_i)
    dosis = floor(EOS / dosis_por_paciente)
"""
from __future__ import annotations

import math

from app.domain.entities import ChainResult, Protocol, StepResult


def decay_factor(duration_min: float, half_life_min: float) -> float:
    """Fracción de actividad que queda tras duration_min de decaimiento."""
    if half_life_min <= 0:
        raise ValueError("half_life_min debe ser positivo")
    if duration_min < 0:
        raise ValueError("duration_min no puede ser negativo")
    return 0.5 ** (duration_min / half_life_min)


def simulate_chain(protocol: Protocol, eob_activity_gbq: float) -> ChainResult:
    """Simula la cascada EOB -> EOS para un protocolo y actividad EOB."""
    if eob_activity_gbq <= 0:
        raise ValueError("eob_activity_gbq debe ser positivo")
    if not protocol.steps:
        raise ValueError("el protocolo no tiene pasos")

    activity = eob_activity_gbq
    results: list[StepResult] = []
    total_time = 0.0
    prod_decay = 1.0
    prod_eff = 1.0

    for step in protocol.steps:
        if step.duration_min < 0:
            raise ValueError(f"duración negativa en paso '{step.name}'")
        if not 0 < step.efficiency <= 1:
            raise ValueError(
                f"eficiencia fuera de rango (0-1] en paso '{step.name}'")
        f = decay_factor(step.duration_min, protocol.half_life_min)
        after_decay = activity * f
        after_step = after_decay * step.efficiency
        results.append(StepResult(
            name=step.name,
            duration_min=step.duration_min,
            efficiency=step.efficiency,
            activity_in_gbq=activity,
            activity_after_decay_gbq=after_decay,
            activity_out_gbq=after_step))
        activity = after_step
        total_time += step.duration_min
        prod_decay *= f
        prod_eff *= step.efficiency

    eos = activity
    doses = math.floor(eos / protocol.dose_per_patient_gbq)
    return ChainResult(
        protocol_id=protocol.protocol_id,
        nuclide=protocol.nuclide,
        half_life_min=protocol.half_life_min,
        eob_activity_gbq=eob_activity_gbq,
        eos_activity_gbq=eos,
        total_time_min=total_time,
        overall_decay_factor=prod_decay,
        overall_efficiency=prod_eff,
        dose_per_patient_gbq=protocol.dose_per_patient_gbq,
        patient_doses=doses,
        validated=protocol.validated,
        steps=tuple(results))
