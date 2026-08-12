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


class OsrmUnavailable(RuntimeError):
    """Servidor OSRM no configurado o inalcanzable (→ 503 honesto)."""


class OsrmRoutingProvider:
    """Routing real vía servidor OSRM (HTTP, perfil driving).

    EDS: las rutas terrestres usan motores de routing reales en
    producción; el proveedor local solo es fallback offline. Sin
    servidor alcanzable, el proveedor lo reporta honestamente y
    nunca inventa tiempos.
    """

    name = "osrm-http"

    def __init__(self, base_url: str | None, timeout_s: float = 10.0,
                 speed_fallback_kmh: float = DEFAULT_SPEED_KMH) -> None:
        self._base = (base_url or "").rstrip("/")
        self._timeout = timeout_s
        self._speed = speed_fallback_kmh

    def _check(self) -> None:
        if not self._base:
            raise OsrmUnavailable("OSRM_URL no configurada")

    def road_time(self, origin: GeoPoint, dest: GeoPoint) -> tuple[float, float]:
        self._check()
        import httpx
        url = (f"{self._base}/route/v1/driving/"
               f"{origin.lon},{origin.lat};{dest.lon},{dest.lat}"
               "?overview=false")
        try:
            r = httpx.get(url, timeout=self._timeout)
            r.raise_for_status()
            datos = r.json()
            leg = datos["routes"][0]
            return leg["duration"] / 60.0, leg["distance"] / 1000.0
        except OsrmUnavailable:
            raise
        except Exception as exc:
            raise OsrmUnavailable(
                f"servidor OSRM inalcanzable en {self._base}: {exc}")

    def reachable_radius_km(self, origin: GeoPoint, minutes: float) -> float:
        # Las isócronas exactas requieren el plugin table de OSRM;
        # aquí se aproxima con la velocidad configurada (documentado).
        del origin
        return self._speed * (minutes / 60.0) / ROAD_FACTOR

class OsrmRoutingProvider:
    """Routing REAL contra un servidor OSRM (HTTP).

    Usa la API pública OSRM:
      - ``GET /route/v1/{perfil}/{lon},{lat};{lon},{lat}`` para tiempos y
        distancias por carretera reales;
      - ``GET /table/v1/{perfil}/{origen};{anillo}?sources=0`` para
        isócronas (radio alcanzable en N minutos).

    Cualquier fallo de red se propaga como excepción real — el Logistics
    Twin nunca sustituye silenciosamente el resultado por una estimación.
    """

    name = "osrm-http"

    def __init__(self, base_url: str, perfil: str = "driving",
                 http_factory=None, timeout_s: float = 10.0) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("base_url OSRM debe ser URL http(s)")
        self._base = base_url.rstrip("/")
        self._perfil = perfil
        self._http_factory = http_factory
        self._timeout_s = timeout_s

    def _http(self):
        if self._http_factory is not None:
            return self._http_factory()
        import httpx
        return httpx.Client(timeout=self._timeout_s)

    def road_time(self, origin: GeoPoint, dest: GeoPoint) -> tuple[float, float]:
        """(minutos, km) por carretera REAL según OSRM."""
        url = (f"{self._base}/route/v1/{self._perfil}/"
               f"{origin.lon},{origin.lat};{dest.lon},{dest.lat}"
               "?overview=false")
        with self._http() as http:
            resp = http.get(url)
        if resp.status_code >= 400:
            raise ConnectionError(f"OSRM HTTP {resp.status_code}")
        cuerpo = resp.json()
        if cuerpo.get("code") != "Ok" or not cuerpo.get("routes"):
            raise RuntimeError(
                f"OSRM sin ruta: {cuerpo.get('code', 'respuesta inválida')}")
        ruta = cuerpo["routes"][0]
        return ruta["duration"] / 60.0, ruta["distance"] / 1000.0

    def reachable_radius_km(self, origin: GeoPoint, minutes: float) -> float:
        """Radio real alcanzable en `minutes` vía OSRM table sobre un
        anillo de 12 puntos; devuelve la máxima distancia cuya duración
        OSRM real sea ≤ minutes."""
        if minutes <= 0:
            return 0.0
        import math
        # anillo estimado a velocidad de mensajería × margen vial
        radio_est_km = DEFAULT_SPEED_KMH * (minutes / 60.0) * 1.6
        puntos = []
        for k in range(12):
            ang = math.radians(k * 30)
            dlat = (radio_est_km / 111.32) * math.sin(ang)
            dlon = (radio_est_km / (111.32 *
                    max(0.01, math.cos(math.radians(origin.lat))))) \
                * math.cos(ang)
            puntos.append(GeoPoint(origin.lat + dlat, origin.lon + dlon))
        coords = ";".join(
            [f"{origin.lon},{origin.lat}"]
            + [f"{p.lon},{p.lat}" for p in puntos])
        url = (f"{self._base}/table/v1/{self._perfil}/{coords}"
               "?sources=0")
        with self._http() as http:
            resp = http.get(url)
        if resp.status_code >= 400:
            raise ConnectionError(f"OSRM HTTP {resp.status_code}")
        cuerpo = resp.json()
        if cuerpo.get("code") != "Ok" or not cuerpo.get("durations"):
            raise RuntimeError(
                f"OSRM table sin resultado: "
                f"{cuerpo.get('code', 'respuesta inválida')}")
        duraciones = cuerpo["durations"][0][1:]  # saltar origen-origen
        alcanzables = [haversine_km(origin, p)
                       for p, d in zip(puntos, duraciones)
                       if d is not None and d <= minutes * 60.0]
        return max(alcanzables) if alcanzables else 0.0

