"""
Router REST del Logistics Twin.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.application.logistics_service import (LogisticsService,
                                               ReachabilityResult)
from app.domain.logistics import RouteResult
from app.presentation.schemas_logistics import (FacilityOut, FacilityReachOut,
                                                LegOut, ReachabilityIn,
                                                ReachabilityOut, ReachBandOut,
                                                RouteIn, RouteOut)

router = APIRouter(prefix="/api/v1/logistics", tags=["logistics-twin"])

_service: LogisticsService | None = None


def init(service: LogisticsService) -> None:
    global _service
    _service = service


def _route_out(r: RouteResult) -> RouteOut:
    return RouteOut(
        mode=r.mode, origin=r.origin, destination=r.destination,
        legs=[LegOut(kind=l.kind, origin=l.origin, destination=l.destination,
                     duration_min=round(l.duration_min, 2),
                     distance_km=round(l.distance_km, 2)) for l in r.legs],
        total_minutes=round(r.total_minutes, 2),
        total_distance_km=round(r.total_distance_km, 2),
        eos_activity_gbq=round(r.eos_activity_gbq, 4),
        arrival_activity_gbq=round(r.arrival_activity_gbq, 4),
        decay_factor=round(r.decay_factor, 6),
        patient_doses_on_arrival=r.patient_doses_on_arrival,
        routing_source=r.routing_source,
        validated=r.validated)


def _reach_out(r: ReachabilityResult) -> ReachabilityOut:
    return ReachabilityOut(
        origin=r.origin, nuclide=r.nuclide,
        eos_activity_gbq=round(r.eos_activity_gbq, 4),
        half_life_min=r.half_life_min,
        max_delivery_minutes_one_dose=round(r.max_delivery_minutes_one_dose, 2),
        bands=[ReachBandOut(
            minutes=b.minutes, radius_km=round(b.radius_km, 2),
            arrival_activity_gbq=round(b.arrival_activity_gbq, 4))
            for b in r.bands],
        facilities=[FacilityReachOut(
            facility_id=f.facility.facility_id, name=f.facility.name,
            kind=f.facility.kind, travel_minutes=round(f.travel_minutes, 2),
            distance_km=round(f.distance_km, 2),
            arrival_activity_gbq=round(f.arrival_activity_gbq, 4),
            feasible_one_dose=f.feasible_one_dose) for f in r.facilities],
        routing_source=r.routing_source,
        validated=r.validated)


@router.get("/facilities", response_model=list[FacilityOut])
def list_facilities() -> list[FacilityOut]:
    return [FacilityOut(
        facility_id=f.facility_id, name=f.name, kind=f.kind,
        lat=f.point.lat, lon=f.point.lon, validated=f.validated)
        for f in _service.list_facilities()]


@router.post("/route", response_model=RouteOut)
def route(payload: RouteIn) -> RouteOut:
    try:
        result = _service.route(
            payload.origin_id, payload.dest_id, payload.protocol_id,
            payload.eos_activity_gbq, payload.mode,
            payload.tdg_buffer_min, payload.courier_min)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"instalación/protocolo '{exc.args[0]}' no encontrado")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _route_out(result)


@router.post("/reachability", response_model=ReachabilityOut)
def reachability(payload: ReachabilityIn) -> ReachabilityOut:
    bands = (tuple(payload.bands_minutes) if payload.bands_minutes
             else (15.0, 30.0, 60.0, 90.0, 120.0))
    try:
        result = _service.reachability(
            payload.origin_id, payload.protocol_id,
            payload.eos_activity_gbq, bands)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"instalación/protocolo '{exc.args[0]}' no encontrado")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _reach_out(result)
