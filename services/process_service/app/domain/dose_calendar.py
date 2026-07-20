"""
Calendario multi-paciente del Process Twin (F3).

Fracciona la actividad EOS en dosis individuales con decaimiento entre
administraciones. El inventario decae continuamente desde eos_time; cada
dosis es viable si el inventario en su instante la cubre, y se descuenta
en el momento de la administración.

También resuelve la inversa exacta: la EOS mínima que serviría TODAS las
citas del calendario (trabajando hacia atrás desde la última dosis).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain.entities import Protocol


@dataclass(frozen=True)
class Appointment:
    """Una cita de administración: instante y dosis prevista."""
    time: datetime
    dose_gbq: float
    label: str = ""


@dataclass(frozen=True)
class DoseSlotResult:
    """Resultado de una cita del calendario."""
    label: str
    time: datetime
    dose_gbq: float
    inventory_before_gbq: float
    feasible: bool
    inventory_after_gbq: float


@dataclass(frozen=True)
class CalendarResult:
    """Resultado del calendario completo."""
    protocol_id: str
    nuclide: str
    half_life_min: float
    eos_activity_gbq: float
    eos_time: datetime
    required_eos_gbq: float
    patients_served: int
    patients_total: int
    total_drawn_gbq: float
    remaining_after_last_gbq: float
    validated: bool
    slots: tuple[DoseSlotResult, ...]


def _decay(activity: float, minutes: float, half_life_min: float) -> float:
    return activity * 0.5 ** (minutes / half_life_min)


def required_eos_for_calendar(protocol: Protocol,
                              eos_time: datetime,
                              appointments: list[Appointment]) -> float:
    """EOS mínima para servir TODAS las citas (inversa exacta, hacia atrás)."""
    need = 0.0  # inventario necesario tras la última cita
    for i in range(len(appointments) - 1, -1, -1):
        need += appointments[i].dose_gbq
        t_anchor = eos_time if i == 0 else appointments[i - 1].time
        dt_min = (appointments[i].time - t_anchor).total_seconds() / 60.0
        need = need / 0.5 ** (dt_min / protocol.half_life_min)
    return need


def dose_calendar(protocol: Protocol,
                  eos_activity_gbq: float,
                  eos_time: datetime,
                  appointments: list[Appointment]) -> CalendarResult:
    """Fracciona la EOS entre las citas con decaimiento entre administraciones.

    Las citas se ordenan por instante; deben ser >= eos_time.
    """
    if eos_activity_gbq <= 0:
        raise ValueError("eos_activity_gbq debe ser positivo")
    if not appointments:
        raise ValueError("el calendario no tiene citas")
    if eos_time.tzinfo is None:
        eos_time = eos_time.replace(tzinfo=timezone.utc)

    norm: list[Appointment] = []
    for a in appointments:
        t = a.time if a.time.tzinfo is not None else a.time.replace(
            tzinfo=timezone.utc)
        if a.dose_gbq <= 0:
            raise ValueError("dosis de cita no positiva")
        norm.append(Appointment(time=t, dose_gbq=a.dose_gbq, label=a.label))
    norm.sort(key=lambda a: a.time)
    if norm[0].time < eos_time:
        raise ValueError("hay citas anteriores a eos_time")

    # hacia delante: decaimiento del inventario y descuento de dosis viables
    slots: list[DoseSlotResult] = []
    inventory = eos_activity_gbq
    anchor = eos_time
    served = 0
    drawn = 0.0
    for appt in norm:
        dt_min = (appt.time - anchor).total_seconds() / 60.0
        inventory = _decay(inventory, dt_min, protocol.half_life_min)
        feasible = inventory + 1e-12 >= appt.dose_gbq
        after = inventory - appt.dose_gbq if feasible else inventory
        slots.append(DoseSlotResult(
            label=appt.label, time=appt.time, dose_gbq=appt.dose_gbq,
            inventory_before_gbq=inventory, feasible=feasible,
            inventory_after_gbq=after))
        if feasible:
            served += 1
            drawn += appt.dose_gbq
            inventory = after
        anchor = appt.time

    required = required_eos_for_calendar(protocol, eos_time, norm)

    return CalendarResult(
        protocol_id=protocol.protocol_id,
        nuclide=protocol.nuclide,
        half_life_min=protocol.half_life_min,
        eos_activity_gbq=eos_activity_gbq,
        eos_time=eos_time,
        required_eos_gbq=required,
        patients_served=served,
        patients_total=len(norm),
        total_drawn_gbq=drawn,
        remaining_after_last_gbq=inventory,
        validated=protocol.validated,
        slots=tuple(slots))
