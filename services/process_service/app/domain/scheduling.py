"""
Planificación inversa del Process Twin (F2).

Dado un objetivo clínico (actividad EOS a una hora de administración),
resuelve la inversa de la cascada EOB -> EOS y construye la línea
temporal completa hacia atrás:

    EOB_necesaria = EOS_objetivo / (Π decay · Π η)
    fin_último_paso = hora_dosis
    inicio_paso_i   = fin_paso_i - duración_i
    EOB             = inicio del primer paso
    inicio_haz      = EOB - irradiación - preparación
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.domain.entities import Protocol
from app.domain.process_chain import simulate_chain


@dataclass(frozen=True)
class ScheduledStep:
    """Un paso de la cascada con su ventana temporal planificada."""
    name: str
    start: datetime
    end: datetime
    activity_out_gbq: float


@dataclass(frozen=True)
class ScheduleResult:
    """Plan de producción hacia atrás desde la hora de dosis."""
    protocol_id: str
    nuclide: str
    eos_target_gbq: float
    eob_required_gbq: float
    dose_time: datetime
    beam_start: datetime
    setup_min: float
    irradiation_time_min: float
    eob_time: datetime
    total_lead_time_min: float
    patient_doses: int
    validated: bool
    steps: tuple[ScheduledStep, ...]


def required_eob(protocol: Protocol, eos_target_gbq: float) -> float:
    """Actividad EOB necesaria para obtener eos_target_gbq al final."""
    if eos_target_gbq <= 0:
        raise ValueError("eos_target_gbq debe ser positivo")
    unitario = simulate_chain(protocol, 1.0)
    factor = unitario.overall_decay_factor * unitario.overall_efficiency
    return eos_target_gbq / factor


def backward_schedule(protocol: Protocol,
                      eos_target_gbq: float,
                      dose_time: datetime,
                      irradiation_time_min: float,
                      setup_min: float = 0.0) -> ScheduleResult:
    """Planifica hacia atrás desde dose_time.

    dose_time naive se interpreta como UTC.
    """
    if irradiation_time_min <= 0:
        raise ValueError("irradiation_time_min debe ser positivo")
    if setup_min < 0:
        raise ValueError("setup_min no puede ser negativo")
    if dose_time.tzinfo is None:
        dose_time = dose_time.replace(tzinfo=timezone.utc)

    eob_act = required_eob(protocol, eos_target_gbq)
    chain = simulate_chain(protocol, eob_act)

    # ventanas temporales hacia atrás desde la hora de dosis
    steps: list[ScheduledStep] = []
    end = dose_time
    for step_out in reversed(chain.steps):
        start = end - timedelta(minutes=step_out.duration_min)
        steps.append(ScheduledStep(
            name=step_out.name, start=start, end=end,
            activity_out_gbq=step_out.activity_out_gbq))
        end = start
    steps.reverse()

    eob_time = steps[0].start
    beam_start = eob_time - timedelta(
        minutes=irradiation_time_min + setup_min)
    lead = (dose_time - beam_start).total_seconds() / 60.0

    return ScheduleResult(
        protocol_id=protocol.protocol_id,
        nuclide=protocol.nuclide,
        eos_target_gbq=eos_target_gbq,
        eob_required_gbq=eob_act,
        dose_time=dose_time,
        beam_start=beam_start,
        setup_min=setup_min,
        irradiation_time_min=irradiation_time_min,
        eob_time=eob_time,
        total_lead_time_min=lead,
        patient_doses=chain.patient_doses,
        validated=protocol.validated,
        steps=tuple(steps))
