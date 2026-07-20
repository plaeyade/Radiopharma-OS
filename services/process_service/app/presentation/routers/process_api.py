"""
Router REST del Process Twin.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.application.process_service import ProcessService
from app.domain.bottleneck import BottleneckResult
from app.domain.entities import ChainResult, Protocol
from app.domain.scheduling import ScheduleResult
from app.presentation.schemas import (BottleneckIn, BottleneckOut,
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
