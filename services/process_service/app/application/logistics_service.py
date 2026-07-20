"""
Servicio de aplicación del Logistics Twin.

Carga instalaciones (data/facilities.json, demo honesta) y aeropuertos
(data/airports.json, OpenFlights), y resuelve rutas terrestres y aéreas
con decaimiento de la carga, usando un RoutingProvider intercambiable.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.application.process_service import ProtocolCatalog
from app.domain.logistics import (DEFAULT_COURIER_MIN, DEFAULT_TDG_BUFFER_MIN,
                                  Facility, GeoPoint, Leg, RouteResult,
                                  build_air_route, decayed,
                                  max_delivery_minutes, nearest_airport,
                                  summarize_route)
from app.infrastructure.routing import (LocalRoutingProvider,
                                        RoutingProvider)

_DEFAULT_DATA = Path(__file__).resolve().parents[2] / "data"


@dataclass(frozen=True)
class ReachBand:
    """Una banda de tiempo de reparto: qué llega a tiempo."""
    minutes: float
    radius_km: float
    arrival_activity_gbq: float


@dataclass(frozen=True)
class FacilityReach:
    """Alcanzabilidad de una instalación concreta."""
    facility: Facility
    travel_minutes: float
    distance_km: float
    arrival_activity_gbq: float
    feasible_one_dose: bool


@dataclass(frozen=True)
class ReachabilityResult:
    origin: str
    nuclide: str
    eos_activity_gbq: float
    half_life_min: float
    max_delivery_minutes_one_dose: float
    bands: tuple[ReachBand, ...]
    facilities: tuple[FacilityReach, ...]
    routing_source: str
    validated: bool


def _load_facilities(path: Path) -> dict[str, Facility]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, Facility] = {}
    for f in raw.get("facilities", []):
        out[f["facility_id"]] = Facility(
            facility_id=f["facility_id"], name=f["name"], kind=f["kind"],
            point=GeoPoint(f["lat"], f["lon"]),
            validated=bool(f.get("validated", False)))
    if not out:
        raise ValueError(f"sin instalaciones en {path}")
    return out


def _load_airports(path: Path) -> list[Facility]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Facility(
        facility_id=a["facility_id"], name=a["name"], kind="airport",
        point=GeoPoint(a["lat"], a["lon"]), iata=a.get("iata", ""),
        validated=True)  # catálogo OpenFlights (dato abierto real)
        for a in raw.get("airports", [])]


class LogisticsService:
    """Casos de uso del Logistics Twin."""

    def __init__(self,
                 catalog: ProtocolCatalog | None = None,
                 routing: RoutingProvider | None = None,
                 data_dir: Path | None = None) -> None:
        self._catalog = catalog or ProtocolCatalog()
        data = data_dir or _DEFAULT_DATA
        self._facilities = _load_facilities(data / "facilities.json")
        self._airports = _load_airports(data / "airports.json")
        self._routing = routing or LocalRoutingProvider()

    @property
    def routing(self) -> RoutingProvider:
        return self._routing

    def list_facilities(self) -> list[Facility]:
        return list(self._facilities.values())

    def get_facility(self, facility_id: str) -> Facility:
        f = self._facilities.get(facility_id)
        if f is None:
            raise KeyError(facility_id)
        return f

    def route(self, origin_id: str, dest_id: str, protocol_id: str,
              eos_activity_gbq: float, mode: str = "road",
              tdg_buffer_min: float = DEFAULT_TDG_BUFFER_MIN,
              courier_min: float = DEFAULT_COURIER_MIN) -> RouteResult:
        """Ruta origen -> destino con decaimiento de la carga."""
        origin = self.get_facility(origin_id)
        dest = self.get_facility(dest_id)
        proto = self._catalog.get(protocol_id)
        if eos_activity_gbq <= 0:
            raise ValueError("eos_activity_gbq debe ser positivo")

        validated = origin.validated and dest.validated
        if mode == "road":
            minutes, km = self._routing.road_time(origin.point, dest.point)
            legs = (Leg("road", origin.name, dest.name, minutes, km),)
            source = self._routing.name
        elif mode == "air":
            o_apt, _ = nearest_airport(origin.point, self._airports)
            d_apt, _ = nearest_airport(dest.point, self._airports)
            g_min, g_km = self._routing.road_time(origin.point, o_apt.point)
            legs = build_air_route(origin, dest, o_apt, d_apt,
                                   g_min, g_km, courier_min, tdg_buffer_min)
            source = f"{self._routing.name}+openflights-haversine"
        else:
            raise ValueError(f"modo '{mode}' no soportado (road|air)")

        return summarize_route(
            mode, origin, dest, legs, eos_activity_gbq,
            proto.half_life_min, proto.dose_per_patient_gbq,
            source, validated)

    def reachability(self, origin_id: str, protocol_id: str,
                     eos_activity_gbq: float,
                     bands_minutes: tuple[float, ...] = (15, 30, 60, 90, 120)
                     ) -> ReachabilityResult:
        """Qué instalaciones entran en el presupuesto de decaimiento."""
        origin = self.get_facility(origin_id)
        proto = self._catalog.get(protocol_id)
        if eos_activity_gbq <= 0:
            raise ValueError("eos_activity_gbq debe ser positivo")
        if not bands_minutes or any(b <= 0 for b in bands_minutes):
            raise ValueError("bandas deben ser positivas")

        bands = tuple(ReachBand(
            minutes=b,
            radius_km=self._routing.reachable_radius_km(origin.point, b),
            arrival_activity_gbq=decayed(eos_activity_gbq, b,
                                         proto.half_life_min))
            for b in sorted(bands_minutes))

        reaches: list[FacilityReach] = []
        for f in self._facilities.values():
            if f.facility_id == origin_id or f.kind == "cyclotron":
                continue
            minutes, km = self._routing.road_time(origin.point, f.point)
            arrival = decayed(eos_activity_gbq, minutes, proto.half_life_min)
            reaches.append(FacilityReach(
                facility=f, travel_minutes=minutes, distance_km=km,
                arrival_activity_gbq=arrival,
                feasible_one_dose=arrival >= proto.dose_per_patient_gbq))
        reaches.sort(key=lambda r: r.travel_minutes)

        return ReachabilityResult(
            origin=origin.name,
            nuclide=proto.nuclide,
            eos_activity_gbq=eos_activity_gbq,
            half_life_min=proto.half_life_min,
            max_delivery_minutes_one_dose=max_delivery_minutes(
                eos_activity_gbq, proto.dose_per_patient_gbq,
                proto.half_life_min),
            bands=bands,
            facilities=tuple(reaches),
            routing_source=self._routing.name,
            validated=origin.validated)
