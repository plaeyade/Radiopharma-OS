"""Conector OSRM — routing terrestre REAL para el Logistics Twin.

El Logistics Twin calcula tiempos terrestres con un proveedor de routing
(`RoutingProvider`); este conector gestiona servidores OSRM externos:

- Servidores versionados: la configuración nunca se sobrescribe; el
  endpoint http(s) es obligatorio.
- Sonda REAL: petición a `/route/v1/{perfil}/0,0;0,0` (o la ruta de
  salud configurada); el fallo se registra honestamente como
  ``fallo_conexion`` con el error real.
- Activación REAL: ``activar`` construye un ``OsrmRoutingProvider`` y lo
  inyecta en el ``LogisticsService`` — a partir de ese momento todas las
  rutas e isócronas terrestres usan OSRM y el campo ``routing_source``
  de cada resultado lo declara (``osrm-http``).
- Sin conexión viva → 503; nunca se sustituye silenciosamente por el
  proveedor local.

Auditoría ALCOA+ en todas las operaciones.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

OSRM_VERSION = "osrm-connector-1.0.0"


class OsrmInvalido(ValueError):
    """Servidor o solicitud inválida."""


class SinOsrm(RuntimeError):
    """Sin servidor OSRM conectado → 503 honesto."""


@dataclass
class ServidorOsrm:
    servidor_id: str
    endpoint: str
    perfil: str
    version: int
    responsable: str
    registrado_en: str


class OsrmConnector:
    """Gestión de servidores OSRM y activación en el Logistics Twin."""

    def __init__(self, fabrica_http=None, timeout_s: float = 10.0) -> None:
        self._fabrica_http = fabrica_http
        self._timeout_s = timeout_s
        self._servidores: dict[str, list[ServidorOsrm]] = {}
        self._vivos: dict[str, ServidorOsrm] = {}
        self._ultimo_estado: dict[str, dict] = {}
        self._proveedor_activo: str | None = None
        self._auditoria: list[dict] = []

    # ------------------------------------------------------------ núcleo
    def _ahora(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _auditar(self, accion: str, detalle: dict, actor: str,
                 resultado: str = "ok") -> None:
        self._auditoria.append({
            "evento_id": str(uuid.uuid4()),
            "accion": accion,
            "detalle": detalle,
            "actor": actor,
            "resultado": resultado,
            "timestamp": self._ahora(),
            "version_motor": OSRM_VERSION,
        })

    def auditoria(self) -> list[dict]:
        return list(self._auditoria)

    def _http(self):
        if self._fabrica_http is not None:
            return self._fabrica_http()
        import httpx
        return httpx.Client(timeout=self._timeout_s)

    # ------------------------------------------------------ servidores
    def registrar_servidor(self, servidor_id: str, endpoint: str,
                           responsable: str,
                           perfil: str = "driving") -> ServidorOsrm:
        """Alta o nueva versión de la configuración; nunca se sobrescribe."""
        if not servidor_id or not endpoint or not responsable:
            raise OsrmInvalido(
                "servidor_id, endpoint y responsable obligatorios; sin "
                "endpoint el routing sería una simulación")
        if not endpoint.startswith(("http://", "https://")):
            raise OsrmInvalido(
                "endpoint debe ser URL http(s) del servidor OSRM")
        versiones = self._servidores.setdefault(servidor_id, [])
        srv = ServidorOsrm(servidor_id, endpoint.rstrip("/"), perfil,
                           len(versiones) + 1, responsable, self._ahora())
        versiones.append(srv)
        self._vivos.pop(servidor_id, None)
        self._auditar("servidor_registrado",
                      {"servidor_id": servidor_id, "endpoint": endpoint,
                       "perfil": perfil, "version": srv.version},
                      responsable)
        return srv

    def servidores(self) -> list[dict]:
        return [{"servidor_id": v[-1].servidor_id,
                 "endpoint": v[-1].endpoint, "perfil": v[-1].perfil,
                 "version": v[-1].version,
                 "estado": self._ultimo_estado.get(
                     v[-1].servidor_id, {}).get("estado", "no_sondeado")}
                for v in self._servidores.values()]

    def historial_servidor(self, servidor_id: str) -> list[dict]:
        return [{"version": s.version, "endpoint": s.endpoint,
                 "perfil": s.perfil, "responsable": s.responsable,
                 "registrado_en": s.registrado_en}
                for s in self._servidores.get(servidor_id, [])]

    def _vigente(self, servidor_id: str) -> ServidorOsrm:
        versiones = self._servidores.get(servidor_id)
        if not versiones:
            raise OsrmInvalido(f"servidor desconocido: {servidor_id}")
        return versiones[-1]

    def sondear(self, servidor_id: str, actor: str = "sistema") -> dict:
        """Sonda REAL: auto-ruta sobre un punto transitable (un punto en el océano como 0,0 devuelve NoRoute en servidores reales)."""
        srv = self._vigente(servidor_id)
        try:
            # auto-ruta sobre un punto transitable (Berlín, ejemplo de
            # referencia de la API OSRM): 0,0 está en el océano y los
            # servidores reales responden NoRoute/400
            url = (f"{srv.endpoint}/route/v1/{srv.perfil}/"
                   "13.388860,52.517037;13.388860,52.517037"
                   "?overview=false")
            with self._http() as http:
                resp = http.get(url)
            if resp.status_code >= 400:
                raise ConnectionError(f"HTTP {resp.status_code}")
            cuerpo = resp.json()
            if cuerpo.get("code") != "Ok":
                raise ConnectionError(
                    f"respuesta OSRM no Ok: {cuerpo.get('code')}")
            self._vivos[servidor_id] = srv
            estado = {"estado": "conectado",
                      "detalle": f"perfil {srv.perfil} operativo",
                      "sondeado_en": self._ahora()}
            resultado = "ok"
        except Exception as exc:
            self._vivos.pop(servidor_id, None)
            estado = {"estado": "fallo_conexion",
                      "detalle": f"{type(exc).__name__}: {exc}",
                      "sondeado_en": self._ahora()}
            resultado = "fallo"
        self._ultimo_estado[servidor_id] = estado
        self._auditar("servidor_sondeado",
                      {"servidor_id": servidor_id,
                       "estado": estado["estado"],
                       "detalle": estado["detalle"]}, actor, resultado)
        return {"servidor_id": servidor_id, **estado}

    # ------------------------------------------ routing directo (prueba real)
    def ruta(self, servidor_id: str, lon_o: float, lat_o: float,
             lon_d: float, lat_d: float, actor: str = "sistema") -> dict:
        """Ruta REAL OSRM entre dos coordenadas (sin pasar por el twin)."""
        if servidor_id not in self._vivos:
            raise SinOsrm(
                f"servidor {servidor_id} sin conexión viva; sondee "
                "primero")
        from ..infrastructure.routing import OsrmRoutingProvider
        from .logistics import GeoPoint
        prov = OsrmRoutingProvider(
            self._vivos[servidor_id].endpoint,
            perfil=self._vivos[servidor_id].perfil,
            http_factory=self._fabrica_http,
            timeout_s=self._timeout_s)
        try:
            minutos, km = prov.road_time(GeoPoint(lat_o, lon_o),
                                         GeoPoint(lat_d, lon_d))
        except Exception as exc:
            self._auditar("ruta_osrm_fallida",
                          {"servidor_id": servidor_id,
                           "detalle": f"{type(exc).__name__}: {exc}"},
                          actor, "fallo")
            raise SinOsrm(
                f"fallo OSRM: {type(exc).__name__}: {exc}") from exc
        self._auditar("ruta_osrm",
                      {"servidor_id": servidor_id,
                       "origen": [lon_o, lat_o], "destino": [lon_d, lat_d],
                       "minutos": minutos, "km": km}, actor)
        return {"servidor_id": servidor_id, "minutos": minutos, "km": km,
                "routing_source": prov.name,
                "calculada_en": self._ahora()}

    # ------------------------------------------------- activación en el twin
    def activar(self, servidor_id: str, logistics_service,
                actor: str) -> dict:
        """Inyecta el OsrmRoutingProvider REAL en el LogisticsService;
        desde entonces routing_source de cada ruta declara 'osrm-http'."""
        if servidor_id not in self._vivos:
            self._auditar("activacion_rechazada",
                          {"servidor_id": servidor_id,
                           "motivo": "sin conexión viva"}, actor, "fallo")
            raise SinOsrm(
                f"servidor {servidor_id} sin conexión viva; sondee "
                "primero — nunca se sustituye silenciosamente por el "
                "proveedor local")
        from ..infrastructure.routing import OsrmRoutingProvider
        srv = self._vivos[servidor_id]
        prov = OsrmRoutingProvider(srv.endpoint, perfil=srv.perfil,
                                   http_factory=self._fabrica_http,
                                   timeout_s=self._timeout_s)
        anterior = getattr(logistics_service.routing, "name", "desconocido")
        logistics_service.set_routing(prov)
        self._proveedor_activo = servidor_id
        self._auditar("osrm_activado",
                      {"servidor_id": servidor_id,
                       "proveedor_anterior": anterior,
                       "proveedor_nuevo": prov.name}, actor)
        return {"servidor_id": servidor_id,
                "routing_source_activo": prov.name,
                "proveedor_anterior": anterior,
                "nota": ("todas las rutas terrestres del Logistics Twin "
                         "usan OSRM real a partir de este momento; el "
                         "campo routing_source lo declara en cada "
                         "resultado")}

    def desactivar(self, logistics_service, actor: str) -> dict:
        """Vuelve explícitamente al proveedor local (decisión auditada)."""
        from ..infrastructure.routing import LocalRoutingProvider
        anterior = getattr(logistics_service.routing, "name", "desconocido")
        logistics_service.set_routing(LocalRoutingProvider())
        self._proveedor_activo = None
        self._auditar("osrm_desactivado",
                      {"proveedor_anterior": anterior,
                       "proveedor_nuevo": "local-haversine"}, actor)
        return {"routing_source_activo": "local-haversine",
                "proveedor_anterior": anterior}

    def estado(self) -> dict:
        return {"version_motor": OSRM_VERSION,
                "servidores": self.servidores(),
                "proveedor_activo": (self._proveedor_activo
                                     or "local-haversine (por defecto)"),
                "nota": ("routing terrestre real vía OSRM; sin conexión "
                         "viva las operaciones devuelven 503 y nunca se "
                         "sustituye silenciosamente por el proveedor "
                         "local")}
