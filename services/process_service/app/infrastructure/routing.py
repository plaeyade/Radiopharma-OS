"""
Proveedores de routing terrestre para el Logistics Twin.

Interfaz única `RoutingProvider` con dos implementaciones:
  - LocalRoutingProvider: determinista, sin red (tests y fallback
    offline): distancia ortodrómica × factor vial / velocidad media.
  - OsmnxRoutingProvider: grafo vial real de OpenStreetMap vía OSMnx
    (import perezoso; solo en producción con red).

Cuando exista telemetría GPS real de transportistas, la capa GNN
(city2graph) se enchufa aquí como tercer proveedor para predicción
de tiempos aprendida — roadmap Logistics F2.
"""
from __future__ import annotations

from typing import Protocol

from app.domain.logistics import GeoPoint, haversine_km

ROAD_FACTOR = 1.3        # circunvalación típica red vial vs ortodromia
DEFAULT_SPEED_KMH = 50.0 # velocidad media interurbana de mensajería


class RoutingProvider(Protocol):
    """Contrato de tiempos de ruta terrestre."""

    name: str

    def road_time(self, origin: GeoPoint, dest: GeoPoint) -> tuple[float, float]:
        """(minutos, km) por carretera entre dos puntos."""
        ...

    def reachable_radius_km(self, origin: GeoPoint, minutes: float) -> float:
        """Radio aproximado alcanzable en `minutes` (para isócronas)."""
        ...


class LocalRoutingProvider:
    """Routing determinista sin red: haversine × factor vial / velocidad."""

    name = "local-haversine"

    def __init__(self, speed_kmh: float = DEFAULT_SPEED_KMH,
                 road_factor: float = ROAD_FACTOR) -> None:
        if speed_kmh <= 0:
            raise ValueError("speed_kmh debe ser positivo")
        self._speed = speed_kmh
        self._factor = road_factor

    def road_time(self, origin: GeoPoint, dest: GeoPoint) -> tuple[float, float]:
        km = haversine_km(origin, dest) * self._factor
        return km / self._speed * 60.0, km

    def reachable_radius_km(self, origin: GeoPoint, minutes: float) -> float:
        del origin
        return self._speed * (minutes / 60.0) / self._factor


class OsmnxRoutingProvider:
    """Routing real sobre OpenStreetMap (osmnx + networkx).

    Descarga y cachea el grafo vial alrededor del primer origen usado.
    Requiere red (Overpass API). Si osmnx no está instalado, falla en
    construcción con instrucción clara.
    """

    name = "osmnx-osm"

    def __init__(self, center: GeoPoint, dist_m: int = 60000,
                 speed_kmh: float = DEFAULT_SPEED_KMH) -> None:
        try:
            import osmnx as ox  # noqa: F401
            import networkx as nx  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "OsmnxRoutingProvider requiere `pip install osmnx networkx`"
            ) from exc
        self._ox = ox
        self._nx = nx
        self._speed = speed_kmh
        self._graph = ox.graph_from_point(
            (center.lat, center.lon), dist=dist_m,
            network_type="drive", simplify=True)

    def road_time(self, origin: GeoPoint, dest: GeoPoint) -> tuple[float, float]:
        ox, nx = self._ox, self._nx
        g = self._graph
        o = ox.nearest_nodes(g, X=origin.lon, Y=origin.lat)
        d = ox.nearest_nodes(g, X=dest.lon, Y=dest.lat)
        km = nx.shortest_path_length(g, o, d, weight="length") / 1000.0
        return km / self._speed * 60.0, km

    def reachable_radius_km(self, origin: GeoPoint, minutes: float) -> float:
        """Radio del 80-percentil de nodos alcanzables en `minutes`."""
        ox, nx = self._ox, self._nx
        g = self._graph
        o = ox.nearest_nodes(g, X=origin.lon, Y=origin.lat)
        max_m = self._speed * (minutes / 60.0) * 1000.0
        lengths = nx.single_source_dijkstra_path_length(g, o, cutoff=max_m,
                                                        weight="length")
        dists = sorted(lengths.values())
        if not dists:
            return 0.0
        p80 = dists[int(0.8 * (len(dists) - 1))]
        return p80 / 1000.0


def default_provider(center: GeoPoint | None = None) -> RoutingProvider:
    """Proveedor por defecto: OSM real si hay osmnx y red; si no, local."""
    if center is not None:
        try:
            return OsmnxRoutingProvider(center)
        except Exception:
            pass
    return LocalRoutingProvider()
