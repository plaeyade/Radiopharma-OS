"""
Plan de campaña del Process Twin (F4): de la demanda de pacientes a los
lotes necesarios.

Dado un calendario de citas (instante + dosis) y la capacidad EOS por
lote, agrupa las citas en el **mínimo número de lotes** viables con una
estrategia voraz cronológica:

1.  Las citas se ordenan en el tiempo. Cada lote nace en la primera cita
    sin servir: su EOS se programa `prep_min` antes de esa cita (tiempo
    de dispensación/transporte interno), respetando la separación mínima
    `turnaround_min` respecto al lote anterior (haz + síntesis + QC del
    lote previo).
2.  El lote crece absorbiendo citas mientras la **EOS requerida exacta**
    (inversa de `required_eos_for_calendar`, con decaimiento entre
    administraciones) no supere la capacidad.
3.  Lo que no cabe es honesto: si un lote no puede servir ni su primera
    cita (dosis con decaimiento > capacidad), o si el turnaround empuja
    la EOS más allá de la cita, la cita queda **no servida** y se
    reporta como tal — nunca se maquilla.

Propiedades (verificadas en tests):
    * la EOS requerida de cada lote servida por `dose_calendar` deja
      inventario remanente ≈ 0 (inversa exacta);
    * capacidad mayor → mismo o menos lotes (monotonía);
    * eos_time de lotes consecutivos separados ≥ turnaround_min;
    * toda cita servida cumple cita ≥ eos_time de su lote.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.domain.dose_calendar import Appointment, required_eos_for_calendar
from app.domain.entities import Protocol

_EPS: float = 1e-9


@dataclass(frozen=True)
class CampaignBatch:
    """Un lote del plan de campaña."""
    index: int
    eos_time: datetime
    required_eos_gbq: float      # EOS mínima exacta para su grupo de citas
    capacity_gbq: float
    headroom_gbq: float          # capacidad − requerida
    utilization: float           # requerida / capacidad
    n_appointments: int
    first_appointment: datetime
    last_appointment: datetime
    total_dose_gbq: float


@dataclass(frozen=True)
class CampaignResult:
    """Resultado agregado del plan de campaña."""
    half_life_min: float
    capacity_gbq: float
    prep_min: float
    turnaround_min: float
    batches: tuple[CampaignBatch, ...]
    n_appointments: int
    n_served: int
    unserved: tuple[Appointment, ...]
    total_required_eos_gbq: float
    total_dose_gbq: float


def plan_campaign(protocol: Protocol,
                  appointments: list[Appointment],
                  capacity_gbq: float,
                  prep_min: float = 30.0,
                  turnaround_min: float = 240.0) -> CampaignResult:
    """Agrupa las citas en el mínimo número de lotes viables (voraz)."""
    if capacity_gbq <= 0.0:
        raise ValueError("capacity_gbq debe ser positivo")
    if prep_min < 0.0:
        raise ValueError("prep_min debe ser >= 0")
    if turnaround_min < 0.0:
        raise ValueError("turnaround_min debe ser >= 0")
    if not appointments:
        raise ValueError("la campaña no tiene citas")

    norm: list[Appointment] = []
    for a in appointments:
        t = a.time if a.time.tzinfo is not None else a.time.replace(
            tzinfo=timezone.utc)
        if a.dose_gbq <= 0.0:
            raise ValueError("dosis de cita no positiva")
        norm.append(Appointment(time=t, dose_gbq=a.dose_gbq, label=a.label))
    norm.sort(key=lambda a: a.time)

    batches: list[CampaignBatch] = []
    unserved: list[Appointment] = []
    prev_eos: datetime | None = None
    i = 0
    n = len(norm)
    while i < n:
        first = norm[i]
        eos_time = first.time - timedelta(minutes=prep_min)
        if prev_eos is not None:
            earliest = prev_eos + timedelta(minutes=turnaround_min)
            eos_time = max(eos_time, earliest)
        if eos_time > first.time + _EPS_timedelta():
            # El turnaround empuja la EOS más allá de la cita: no servible
            unserved.append(first)
            i += 1
            continue
        # Crece el grupo mientras la EOS requerida quepa en la capacidad
        j = i
        group: list[Appointment] = []
        required = 0.0
        while j < n:
            tentative = group + [norm[j]]
            req = required_eos_for_calendar(protocol, eos_time, tentative)
            if req > capacity_gbq + _EPS:
                break
            group = tentative
            required = req
            j += 1
        if not group:
            # Ni su primera cita cabe (dosis con decaimiento > capacidad)
            unserved.append(first)
            i += 1
            continue
        batches.append(CampaignBatch(
            index=len(batches) + 1, eos_time=eos_time,
            required_eos_gbq=required, capacity_gbq=capacity_gbq,
            headroom_gbq=capacity_gbq - required,
            utilization=required / capacity_gbq,
            n_appointments=len(group),
            first_appointment=group[0].time,
            last_appointment=group[-1].time,
            total_dose_gbq=sum(a.dose_gbq for a in group)))
        prev_eos = eos_time
        i = j

    return CampaignResult(
        half_life_min=protocol.half_life_min, capacity_gbq=capacity_gbq,
        prep_min=prep_min, turnaround_min=turnaround_min,
        batches=tuple(batches), n_appointments=n,
        n_served=sum(b.n_appointments for b in batches),
        unserved=tuple(unserved),
        total_required_eos_gbq=sum(b.required_eos_gbq for b in batches),
        total_dose_gbq=sum(a.dose_gbq for a in norm))


def _EPS_timedelta() -> timedelta:
    return timedelta(seconds=max(_EPS * 60.0, 1e-6))
