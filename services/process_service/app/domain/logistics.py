"""
Logistics Twin (F1): rutas de distribución del radiofármaco con
decaimiento en tránsito.

Modelos:
  - terrestre: tiempo de ruta por carretera (proveedor de routing:
    local determinista u OSMnx/OpenStreetMap en producción);
  - aéreo: pierna terrestre al aeropuerto origen + buffer TDG
    (inspección mercancías peligrosas Clase 7, típ. 60-120 min) +
    vuelo (haversine / velocidad crucero + overhead) + mensajería
    terrestre en destino (referencia operativa: puerta a puerta
    5-6 h para 18F-FDG interurbano).

El decaimiento es continuo sobre la cadena completa:
    A_llegada = EOS · 0.5 ** (t_total / T½)
"""
from __future__ import annotations

import math
from dataclasses import dataclass

EARTH_R_KM = 6371.0
DEFAULT_CRUISE_KMH = 800.0
DEFAULT_FLIGHT_OVERHEAD_MIN = 30.0   # rodaje, ascenso, aproximación
DEFAULT_TDG_BUFFER_MIN = 90.0        # inspección Clase 7 (60-120 min)
DEFAULT_COURIER_MIN = 30.0           # mensajería terrestre en destino


@dataclass(frozen=True)
class GeoPoint:
    lat: float
    lon: float


@dataclass(frozen=True)
class Facility:
    """Instalación del mapa logístico (ciclotrón, hospital, aeropuerto)."""
    facility_id: str
    name: str
    kind: str            # cyclotron | hospital | airport
    point: GeoPoint
    iata: str = ""
    validated: bool = False


@dataclass(frozen=True)
class Leg:
    """Una pierna de la ruta."""
    kind: str            # road | tdg_buffer | flight | courier
    origin: str
    destination: str
    duration_min: float
    distance_km: float


@dataclass(frozen=True)
class RouteResult:
    """Ruta completa con decaimiento de la carga."""
    mode: str            # road | air
    origin: str
    destination: str
    legs: tuple[Leg, ...]
    total_minutes: float
    total_distance_km: float
    eos_activity_gbq: float
    arrival_activity_gbq: float
    decay_factor: float
    patient_doses_on_arrival: int
    routing_source: str  # qué proveedor calculó los tiempos terrestres
    validated: bool


def haversine_km(a: GeoPoint, b: GeoPoint) -> float:
    """Distancia ortodrómica en km."""
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp = p2 - p1
    dl = math.radians(b.lon - a.lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R_KM * math.asin(math.sqrt(h))


def flight_time_min(distance_km: float,
                    cruise_kmh: float = DEFAULT_CRUISE_KMH,
                    overhead_min: float = DEFAULT_FLIGHT_OVERHEAD_MIN) -> float:
    """Tiempo de vuelo: distancia / crucero + overhead fijo."""
    if distance_km <= 0:
        raise ValueError("distance_km debe ser positivo")
    return distance_km / cruise_kmh * 60.0 + overhead_min


def decayed(activity_gbq: float, minutes: float, half_life_min: float) -> float:
    """Actividad tras `minutes` de decaimiento."""
    if half_life_min <= 0:
        raise ValueError("half_life_min debe ser positivo")
    return activity_gbq * 0.5 ** (minutes / half_life_min)


def build_air_route(origin: Facility, destination: Facility,
                    origin_airport: Facility, dest_airport: Facility,
                    ground_to_airport_min: float,
                    ground_to_airport_km: float,
                    courier_min: float = DEFAULT_COURIER_MIN,
                    tdg_buffer_min: float = DEFAULT_TDG_BUFFER_MIN
                    ) -> tuple[Leg, ...]:
    """Cadena aérea: carretera -> buffer TDG -> vuelo -> mensajería."""
    if tdg_buffer_min < 0 or courier_min < 0:
        raise ValueError("buffer/mensajería no pueden ser negativos")
    if origin_airport.facility_id == dest_airport.facility_id:
        raise ValueError(
            "origen y destino comparten aeropuerto: use modo terrestre")
    flight_km = haversine_km(origin_airport.point, dest_airport.point)
    flight_min = flight_time_min(flight_km)
    courier_km = haversine_km(dest_airport.point, destination.point) * 1.3
    return (
        Leg("road", origin.name, origin_airport.name,
            ground_to_airport_min, ground_to_airport_km),
        Leg("tdg_buffer", origin_airport.name, origin_airport.name,
            tdg_buffer_min, 0.0),
        Leg("flight", origin_airport.name, dest_airport.name,
            flight_min, flight_km),
        Leg("courier", dest_airport.name, destination.name,
            courier_min, courier_km))


def summarize_route(mode: str, origin: Facility, destination: Facility,
                    legs: tuple[Leg, ...], eos_activity_gbq: float,
                    half_life_min: float, dose_per_patient_gbq: float,
                    routing_source: str, validated: bool) -> RouteResult:
    """Cierra la ruta con el decaimiento de la carga y las dosis a llegada."""
    if eos_activity_gbq <= 0:
        raise ValueError("eos_activity_gbq debe ser positivo")
    total_min = sum(l.duration_min for l in legs)
    total_km = sum(l.distance_km for l in legs)
    arrival = decayed(eos_activity_gbq, total_min, half_life_min)
    doses = math.floor(arrival / dose_per_patient_gbq + 1e-9)
    return RouteResult(
        mode=mode,
        origin=origin.name,
        destination=destination.name,
        legs=legs,
        total_minutes=total_min,
        total_distance_km=total_km,
        eos_activity_gbq=eos_activity_gbq,
        arrival_activity_gbq=arrival,
        decay_factor=0.5 ** (total_min / half_life_min),
        patient_doses_on_arrival=doses,
        routing_source=routing_source,
        validated=validated)


def max_delivery_minutes(eos_activity_gbq: float, required_gbq: float,
                         half_life_min: float) -> float:
    """Presupuesto de tiempo: cuánto puede durar la entrega para llegar
    con al menos `required_gbq`."""
    if required_gbq <= 0 or eos_activity_gbq <= 0:
        raise ValueError("actividades deben ser positivas")
    if required_gbq >= eos_activity_gbq:
        return 0.0
    return half_life_min * math.log2(eos_activity_gbq / required_gbq)


def nearest_airport(point: GeoPoint,
                    airports: list[Facility]) -> tuple[Facility, float]:
    """Aeropuerto más cercano y distancia ortodrómica."""
    if not airports:
        raise ValueError("sin aeropuertos en el catálogo")
    best = min(airports, key=lambda a: haversine_km(point, a.point))
    return best, haversine_km(point, best.point)
