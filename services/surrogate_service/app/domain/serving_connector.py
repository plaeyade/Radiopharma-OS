"""Conector BentoML — BentoML Runtime real (EDS 20.10) e Inference API (20.11).

El Surrogate Modeling Server usa BentoML como plataforma oficial de
despliegue (20.10): cada modelo se publica como servicio independiente
con interfaz uniforme. Este conector habla HTTP REAL con un servidor
BentoML externo:

- Sin endpoint configurado o sin sonda exitosa, el servidor queda
  honestamente ``no_configurado``/``fallo_conexion`` y las inferencias
  devuelven 503 — el resultado NUNCA se inventa.
- La sonda es un GET real a ``/healthz`` (o la ruta configurada).
- La inferencia es un POST real con parámetros de entrada y versión del
  modelo (20.11); la respuesta incorpora predicción, versión y metadatos.
- Puente con el Inference Engine (41.8): ``runtime_bentoml`` devuelve un
  callable registrable en ``EiCoreEngine.registrar_runtime``, de modo
  que un modelo validado y desplegado (41.20/42.8) pueda ejecutar
  inferencias contra el servidor BentoML real con trazabilidad completa.

El cliente HTTP es inyectable (pruebas); en producción se usa httpx.
Auditoría ALCOA+ en todas las operaciones.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

SERVING_VERSION = "bentoml-connector-1.0.0"


class ServingInvalido(ValueError):
    """Servidor, servicio o solicitud de inferencia inválida."""


class SinServidor(RuntimeError):
    """Sin servidor BentoML configurado/conectado → 503 honesto."""


@dataclass
class ServidorBentoML:
    servidor_id: str
    endpoint: str
    ruta_salud: str
    version: int
    responsable: str
    registrado_en: str


class ServingConnector:
    """Conector al BentoML Runtime externo (20.10)."""

    def __init__(self, fabrica_http=None, timeout_s: float = 5.0) -> None:
        # fabrica_http: inyectable en pruebas; None → httpx real
        self._fabrica_http = fabrica_http
        self._timeout_s = timeout_s
        self._servidores: dict[str, list[ServidorBentoML]] = {}
        self._vivos: dict[str, object] = {}
        self._ultimo_estado: dict[str, dict] = {}
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
            "version_motor": SERVING_VERSION,
        })

    def auditoria(self) -> list[dict]:
        return list(self._auditoria)

    def _http(self):
        if self._fabrica_http is not None:
            return self._fabrica_http()
        import httpx
        return httpx.Client(timeout=self._timeout_s)

    # ------------------------------------------- servidores (20.10)
    def registrar_servidor(self, servidor_id: str, endpoint: str,
                           responsable: str,
                           ruta_salud: str = "/healthz") -> ServidorBentoML:
        """Alta o nueva versión de la configuración del servidor;
        nunca se sobrescribe."""
        if not servidor_id or not endpoint or not responsable:
            raise ServingInvalido(
                "servidor_id, endpoint y responsable obligatorios; sin "
                "endpoint el serving sería una simulación")
        if not endpoint.startswith(("http://", "https://")):
            raise ServingInvalido(
                "endpoint debe ser una URL http(s) del servidor BentoML")
        versiones = self._servidores.setdefault(servidor_id, [])
        srv = ServidorBentoML(servidor_id, endpoint.rstrip("/"),
                              ruta_salud, len(versiones) + 1, responsable,
                              self._ahora())
        versiones.append(srv)
        self._vivos.pop(servidor_id, None)
        self._auditar("servidor_registrado",
                      {"servidor_id": servidor_id, "endpoint": endpoint,
                       "version": srv.version}, responsable)
        return srv

    def servidores(self) -> list[dict]:
        return [{"servidor_id": v[-1].servidor_id,
                 "endpoint": v[-1].endpoint, "version": v[-1].version,
                 "estado": self._ultimo_estado.get(
                     v[-1].servidor_id, {}).get("estado", "no_sondeado")}
                for v in self._servidores.values()]

    def historial_servidor(self, servidor_id: str) -> list[dict]:
        return [{"version": s.version, "endpoint": s.endpoint,
                 "ruta_salud": s.ruta_salud, "responsable": s.responsable,
                 "registrado_en": s.registrado_en}
                for s in self._servidores.get(servidor_id, [])]

    def _vigente(self, servidor_id: str) -> ServidorBentoML:
        versiones = self._servidores.get(servidor_id)
        if not versiones:
            raise ServingInvalido(f"servidor desconocido: {servidor_id}")
        return versiones[-1]

    def sondear(self, servidor_id: str, actor: str = "sistema") -> dict:
        """Sonda REAL de salud del servidor BentoML (GET ruta_salud)."""
        srv = self._vigente(servidor_id)
        try:
            with self._http() as http:
                resp = http.get(srv.endpoint + srv.ruta_salud)
            if resp.status_code >= 400:
                raise ConnectionError(f"HTTP {resp.status_code}")
            self._vivos[servidor_id] = srv
            estado = {"estado": "conectado", "detalle": "",
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

    # ------------------------------------------- inferencia (20.11)
    def inferir(self, servidor_id: str, ruta: str, datos: dict,
                modelo: str, version_modelo: str,
                usuario: str) -> dict:
        """POST real al servicio BentoML (20.11): la solicitud incluye
        parámetros de entrada y versión del modelo; la respuesta incluye
        predicción y metadatos. Sin conexión viva → 503 honesto."""
        srv = self._vigente(servidor_id)
        if not ruta or not isinstance(datos, dict) or not datos:
            raise ServingInvalido(
                "ruta del servicio y datos de entrada obligatorios "
                "(20.11)")
        if not usuario:
            raise ServingInvalido(
                "usuario obligatorio: toda inferencia registra quién la "
                "ejecutó")
        if servidor_id not in self._vivos:
            self._auditar("inferencia_remota_rechazada",
                          {"servidor_id": servidor_id, "ruta": ruta,
                           "motivo": "sin conexión viva"},
                          usuario, "fallo")
            raise SinServidor(
                f"servidor {servidor_id} sin conexión viva; sondee "
                "primero (POST .../probe)")
        ejecucion_id = str(uuid.uuid4())
        try:
            with self._http() as http:
                resp = http.post(
                    srv.endpoint + ruta,
                    json={"ejecucion_id": ejecucion_id,
                          "modelo": modelo,
                          "version_modelo": version_modelo,
                          "parametros": datos})
            if resp.status_code >= 400:
                raise ConnectionError(f"HTTP {resp.status_code}")
            cuerpo = resp.json()
        except SinServidor:
            raise
        except Exception as exc:
            self._vivos.pop(servidor_id, None)
            self._auditar("inferencia_remota_fallida",
                          {"servidor_id": servidor_id, "ruta": ruta,
                           "detalle": f"{type(exc).__name__}: {exc}"},
                          usuario, "fallo")
            raise SinServidor(
                f"fallo de inferencia en {servidor_id}: "
                f"{type(exc).__name__}: {exc}") from exc
        self._auditar("inferencia_remota_ejecutada",
                      {"servidor_id": servidor_id, "ruta": ruta,
                       "modelo": modelo, "version_modelo": version_modelo,
                       "ejecucion_id": ejecucion_id}, usuario)
        return {"ejecucion_id": ejecucion_id, "servidor_id": servidor_id,
                "modelo": modelo, "version_modelo": version_modelo,
                "prediccion": cuerpo,
                "ejecutada_en": self._ahora(),
                "nota": ("inferencia ejecutada en el servidor BentoML "
                         "real (20.10); coexiste con la simulación "
                         "física completa (20.3)")}

    def runtime_bentoml(self, servidor_id: str, ruta: str,
                        modelo: str, version_modelo: str,
                        usuario: str = "serving-bridge"):
        """Callable registrable en EiCoreEngine.registrar_runtime
        (41.8): ejecuta la inferencia contra el BentoML real."""
        def _runtime(datos: dict):
            return self.inferir(servidor_id, ruta, datos, modelo,
                                version_modelo, usuario)["prediccion"]
        return _runtime

    def estado(self) -> dict:
        return {"version_motor": SERVING_VERSION,
                "servidores": self.servidores(),
                "nota": ("BentoML externo real (20.10); sin servidor "
                         "configurado/conectado las inferencias "
                         "devuelven 503 y el resultado nunca se "
                         "inventa")}
