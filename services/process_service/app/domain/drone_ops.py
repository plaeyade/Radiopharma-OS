"""
Pierna con dron del Logistics Twin.

Modelo: operación punto a punto ciclotrón -> hospital sin pasar por
aeropuerto. Piernas:
    preflight: preparación del bulto Tipo A + operaciones de vuelo UAS
               (por defecto 20 min, configurable);
    drone_flight: distancia ortodrómica / velocidad crucero.

Restricciones duras del catálogo: alcance y payload (blindaje de FDG a
granel = 15-30 kg + contenedor ~2 kg).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.logistics import Facility, GeoPoint, Leg, haversine_km

DEFAULT_PREFLIGHT_MIN = 20.0   # bulto Tipo A + ops UAS
CONTAINER_KG = 2.0             # contenedor Tipo A (sin blindaje)

DRONE_REGULATORY_NOTES: tuple[str, ...] = (
    "Operación UAS Clase 7: categoría 'specific' EASA (SORA) + ICAO TI/IATA DGR.",
    "Bulto Tipo A requerido (IAEA SSR-6) con aprobación del operador UAS.",
)


@dataclass(frozen=True)
class DroneModel:
    """Una clase de dron del catálogo (parámetros de referencia)."""
    drone_id: str
    name: str
    drone_class: str
    cruise_kmh: float
    range_km: float
    max_payload_kg: float
    validated: bool
    note: str
    source: str


def package_mass_kg(shielding_kg: float,
                    container_kg: float = CONTAINER_KG) -> float:
    """Masa del bulto: blindaje + contenedor Tipo A."""
    if shielding_kg < 0 or container_kg < 0:
        raise ValueError("masas no pueden ser negativas")
    return shielding_kg + container_kg


def check_drone_feasibility(drone: DroneModel, distance_km: float,
                            package_kg: float) -> None:
    """Restricciones duras: alcance y payload."""
    if distance_km <= 0:
        raise ValueError("distance_km debe ser positiva")
    if package_kg <= 0:
        raise ValueError("package_kg debe ser positivo")
    if distance_km > drone.range_km:
        raise ValueError(
            f"fuera de alcance: {distance_km:.1f} km > {drone.range_km} km "
            f"del dron '{drone.name}'")
    if package_kg > drone.max_payload_kg:
        raise ValueError(
            f"payload excedido: {package_kg:.1f} kg > "
            f"{drone.max_payload_kg} kg del dron '{drone.name}' "
            f"({drone.note})")


def build_drone_route(origin: Facility, destination: Facility,
                      drone: DroneModel, shielding_kg: float,
                      preflight_min: float = DEFAULT_PREFLIGHT_MIN
                      ) -> tuple[Leg, ...]:
    """Cadena con dron: ops de vuelo -> vuelo directo."""
    if preflight_min < 0:
        raise ValueError("preflight_min no puede ser negativo")
    distance = haversine_km(origin.point, destination.point)
    package = package_mass_kg(shielding_kg)
    check_drone_feasibility(drone, distance, package)
    flight_min = distance / drone.cruise_kmh * 60.0
    return (
        Leg("preflight", origin.name, origin.name, preflight_min, 0.0),
        Leg("drone_flight", origin.name, destination.name,
            flight_min, distance))


def drone_notes(drone: DroneModel, shielding_kg: float) -> list[str]:
    """Notas regulatorias y de operación para la respuesta."""
    return [
        *DRONE_REGULATORY_NOTES,
        f"Bulto: blindaje {shielding_kg:.0f} kg + contenedor "
        f"{CONTAINER_KG:.0f} kg = {package_mass_kg(shielding_kg):.0f} kg; "
        f"{drone.note}",
        f"Parámetros del dron: {drone.source}",
    ]
