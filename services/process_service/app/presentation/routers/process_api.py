"""
Router REST del Process Twin.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.application.process_service import ProcessService
from app.domain.bottleneck import BottleneckResult
from app.domain.campaign import CampaignResult
from app.domain.dose_calendar import Appointment, CalendarResult
from app.domain.entities import ChainResult, Protocol
from app.domain.scheduling import ScheduleResult
from app.presentation.schemas import (AppointmentIn, BottleneckIn,
                                      BottleneckOut,
                                      CampaignBatchOut, CampaignIn,
                                      CampaignOut, DoseCalendarIn,
                                      DoseCalendarOut, DoseSlotOut,
                                      ProtocolOut, ProtocolStepOut,
                                      ProtocolSummaryOut, ScheduleIn,
                                      ScheduleOut, ScheduledStepOut,
                                      SimulateIn, SimulateOut,
                                      StepBottleneckOut, StepResultOut)

router = APIRouter(prefix="/api/v1/process", tags=["process-twin"])

_service: ProcessService | None = None


def init(service: ProcessService) -> None:
    global _service
    _service = service


def _summary_out(p: Protocol) -> ProtocolSummaryOut:
    return ProtocolSummaryOut(
        protocol_id=p.protocol_id,
        name=p.name,
        nuclide=p.nuclide,
        half_life_min=p.half_life_min,
        dose_per_patient_gbq=p.dose_per_patient_gbq,
        n_steps=len(p.steps),
        total_time_min=round(sum(s.duration_min for s in p.steps), 2),
        validated=p.validated)


def _protocol_out(p: Protocol) -> ProtocolOut:
    base = _summary_out(p).model_dump()
    return ProtocolOut(
        **base,
        source=p.source,
        steps=[ProtocolStepOut(name=s.name, duration_min=s.duration_min,
                               efficiency=s.efficiency) for s in p.steps])


def _chain_out(r: ChainResult) -> SimulateOut:
    return SimulateOut(
        protocol_id=r.protocol_id,
        nuclide=r.nuclide,
        half_life_min=r.half_life_min,
        eob_activity_gbq=round(r.eob_activity_gbq, 4),
        eos_activity_gbq=round(r.eos_activity_gbq, 4),
        total_time_min=round(r.total_time_min, 2),
        overall_decay_factor=round(r.overall_decay_factor, 6),
        overall_efficiency=round(r.overall_efficiency, 6),
        dose_per_patient_gbq=r.dose_per_patient_gbq,
        patient_doses=r.patient_doses,
        validated=r.validated,
        steps=[StepResultOut(
            name=s.name,
            duration_min=s.duration_min,
            efficiency=s.efficiency,
            activity_in_gbq=round(s.activity_in_gbq, 4),
            activity_after_decay_gbq=round(s.activity_after_decay_gbq, 4),
            activity_out_gbq=round(s.activity_out_gbq, 4)) for s in r.steps])


@router.get("/protocols", response_model=list[ProtocolSummaryOut])
def list_protocols() -> list[ProtocolSummaryOut]:
    return [_summary_out(p) for p in _service.list_protocols()]


@router.get("/protocols/{protocol_id}", response_model=ProtocolOut)
def get_protocol(protocol_id: str) -> ProtocolOut:
    try:
        return _protocol_out(_service.get_protocol(protocol_id))
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"protocolo '{protocol_id}' no encontrado")


@router.post("/simulate", response_model=SimulateOut)
def simulate(payload: SimulateIn) -> SimulateOut:
    try:
        result = _service.simulate(payload.protocol_id, payload.eob_activity_gbq)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"protocolo '{payload.protocol_id}' no encontrado")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _chain_out(result)


def _schedule_out(r: ScheduleResult) -> ScheduleOut:
    return ScheduleOut(
        protocol_id=r.protocol_id,
        nuclide=r.nuclide,
        eos_target_gbq=round(r.eos_target_gbq, 4),
        eob_required_gbq=round(r.eob_required_gbq, 4),
        dose_time=r.dose_time,
        beam_start=r.beam_start,
        setup_min=r.setup_min,
        irradiation_time_min=r.irradiation_time_min,
        eob_time=r.eob_time,
        total_lead_time_min=round(r.total_lead_time_min, 2),
        patient_doses=r.patient_doses,
        validated=r.validated,
        steps=[ScheduledStepOut(
            name=s.name, start=s.start, end=s.end,
            activity_out_gbq=round(s.activity_out_gbq, 4))
            for s in r.steps])


@router.post("/schedule", response_model=ScheduleOut)
def schedule(payload: ScheduleIn) -> ScheduleOut:
    try:
        result = _service.schedule(
            payload.protocol_id, payload.dose_time,
            payload.irradiation_time_min, payload.setup_min,
            payload.eos_target_gbq, payload.target_doses)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"protocolo '{payload.protocol_id}' no encontrado")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _schedule_out(result)


@router.post("/bottleneck", response_model=BottleneckOut)
def bottleneck(payload: BottleneckIn) -> BottleneckOut:
    try:
        r: BottleneckResult = _service.bottleneck(
            payload.protocol_id, payload.eob_activity_gbq)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"protocolo '{payload.protocol_id}' no encontrado")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return BottleneckOut(
        protocol_id=r.protocol_id,
        nuclide=r.nuclide,
        eob_activity_gbq=round(r.eob_activity_gbq, 4),
        eos_activity_gbq=round(r.eos_activity_gbq, 4),
        total_loss_gbq=round(r.total_loss_gbq, 4),
        dominant_loss_step=r.dominant_loss_step,
        steps=[StepBottleneckOut(
            name=s.name,
            loss_gbq=round(s.loss_gbq, 4),
            decay_loss_gbq=round(s.decay_loss_gbq, 4),
            efficiency_loss_gbq=round(s.efficiency_loss_gbq, 4),
            eos_gain_1min_faster_gbq=round(s.eos_gain_1min_faster_gbq, 4),
            eos_gain_1pp_efficiency_gbq=round(
                s.eos_gain_1pp_efficiency_gbq, 4)) for s in r.steps])


def _calendar_out(r: CalendarResult) -> DoseCalendarOut:
    return DoseCalendarOut(
        protocol_id=r.protocol_id,
        nuclide=r.nuclide,
        half_life_min=r.half_life_min,
        eos_activity_gbq=round(r.eos_activity_gbq, 4),
        eos_time=r.eos_time,
        required_eos_gbq=round(r.required_eos_gbq, 4),
        patients_served=r.patients_served,
        patients_total=r.patients_total,
        total_drawn_gbq=round(r.total_drawn_gbq, 4),
        remaining_after_last_gbq=round(r.remaining_after_last_gbq, 4),
        validated=r.validated,
        slots=[DoseSlotOut(
            label=s.label, time=s.time, dose_gbq=s.dose_gbq,
            inventory_before_gbq=round(s.inventory_before_gbq, 4),
            feasible=s.feasible,
            inventory_after_gbq=round(s.inventory_after_gbq, 4))
            for s in r.slots])


@router.post("/dose-calendar", response_model=DoseCalendarOut)
def calendar(payload: DoseCalendarIn) -> DoseCalendarOut:
    try:
        proto = _service.get_protocol(payload.protocol_id)
        appts = [Appointment(
            time=a.time,
            dose_gbq=(a.dose_gbq if a.dose_gbq is not None
                      else proto.dose_per_patient_gbq),
            label=a.label) for a in payload.appointments]
        result = _service.dose_calendar(
            payload.protocol_id, payload.eos_activity_gbq,
            payload.eos_time, appts)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"protocolo '{payload.protocol_id}' no encontrado")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _calendar_out(result)


def _campaign_out(protocol_id: str, r: CampaignResult) -> CampaignOut:
    return CampaignOut(
        protocol_id=protocol_id,
        half_life_min=r.half_life_min,
        capacity_gbq=r.capacity_gbq,
        prep_min=r.prep_min,
        turnaround_min=r.turnaround_min,
        batches=[CampaignBatchOut(
            index=b.index, eos_time=b.eos_time,
            required_eos_gbq=round(b.required_eos_gbq, 4),
            capacity_gbq=b.capacity_gbq,
            headroom_gbq=round(b.headroom_gbq, 4),
            utilization=round(b.utilization, 4),
            n_appointments=b.n_appointments,
            first_appointment=b.first_appointment,
            last_appointment=b.last_appointment,
            total_dose_gbq=round(b.total_dose_gbq, 4)) for b in r.batches],
        n_appointments=r.n_appointments,
        n_served=r.n_served,
        unserved=[AppointmentIn(time=a.time, dose_gbq=a.dose_gbq,
                                label=a.label) for a in r.unserved],
        total_required_eos_gbq=round(r.total_required_eos_gbq, 4),
        total_dose_gbq=round(r.total_dose_gbq, 4))


@router.post("/campaign", response_model=CampaignOut)
def campaign(payload: CampaignIn) -> CampaignOut:
    """Plan de campaña (F4): agrupa la demanda en el mínimo número de
    lotes viables según capacidad EOS, decaimiento entre administraciones
    y separación mínima entre lotes. Las citas no servibles se reportan
    explícitamente (honestidad operativa)."""
    try:
        proto = _service.get_protocol(payload.protocol_id)
        appts = [Appointment(
            time=a.time,
            dose_gbq=(a.dose_gbq if a.dose_gbq is not None
                      else proto.dose_per_patient_gbq),
            label=a.label) for a in payload.appointments]
        result = _service.campaign(
            payload.protocol_id, appts, payload.capacity_gbq,
            prep_min=payload.prep_min, turnaround_min=payload.turnaround_min)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"protocolo '{payload.protocol_id}' no encontrado")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _campaign_out(payload.protocol_id, result)
