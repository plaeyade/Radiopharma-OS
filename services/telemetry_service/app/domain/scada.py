"""Real-Time Monitoring & SCADA Integration Layer (EDS cap. 31).

Capa de adquisición y normalización de datos industriales (31.3):
los sistemas industriales NUNCA interactúan directamente con los Gemelos
Digitales — toda comunicación pasa por esta capa.

Componentes (31.5):
- **OPC UA Client (31.6)**, **MQTT Connector (31.7)** y
  **Modbus Connector (31.8)**: conectores reales (asyncua / paho-mqtt /
  pymodbus). Sin endpoint configurado o sin conexión viva, el estado se
  reporta honestamente (``no_configurado`` / ``fallo_conexion``) y las
  lecturas devuelven 503 — nunca se inventan mediciones.
- **PLC Adapter Manager (31.9)**: un adaptador independiente por
  fabricante que traduce campos externos al modelo interno.
- **Time-Series Collector (31.10/31.21)**: cada dato registra timestamp,
  origen, calidad, versión y dispositivo.
- **Event Processor (31.11)**: detecta inicio/paro/alarma/cambio de
  estado/pérdida de comunicación a partir de mediciones reales.
- **Alarmas (31.12)**: historial completo, nunca se borran.
- **Normalización (31.13)**: timestamps a UTC, metadatos completos.
- **Validation Engine (31.22)**: antes de aceptar una medición se
  verifica formato, rango permitido y consistencia temporal; las
  anomalías generan eventos de validación y la medición NO se acepta.

Persistencia 31.23 (InfluxDB/Redis/MinIO): se reporta honestamente como
``no_configurado`` en este entorno. Auditoría 31.24 en todo.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

SCADA_VERSION = "scada-rtmsil-1.0.0"

TIPOS_CONECTOR = ("opcua", "mqtt", "modbus_tcp", "modbus_rtu")
TIPOS_EVENTO = ("inicio", "paro", "alarma", "cambio_estado",
                "perdida_comunicacion", "validacion")
CRITICIDADES = ("baja", "media", "alta", "critica")
ESTADOS_ALARMA = ("activa", "reconocida", "cerrada")
CALIDADES = ("buena", "incierta", "mala")


class ScadaInvalido(ValueError):
    """Conector, medición, validación o alarma inválida (31.22)."""


class SinCanal(RuntimeError):
    """Sin endpoint configurado o sin conexión viva → 503 honesto."""


@dataclass
class Conector:
    conector_id: str
    tipo: str
    endpoint: str
    configuracion: dict
    version: int
    responsable: str
    registrado_en: str


@dataclass
class AdaptadorPLC:
    """Traduce campos del PLC al modelo interno (31.9)."""
    fabricante: str
    mapeo: dict  # campo_externo -> campo_interno
    version: int
    responsable: str


@dataclass
class Medicion:
    medicion_id: str
    dispositivo: str
    variable: str
    valor: float
    unidad: str
    timestamp: str          # normalizado a UTC (31.13)
    origen: str             # conector_id o "manual"
    calidad: str
    version: str
    dispositivo_id: str


@dataclass
class EventoIndustrial:
    evento_id: str
    tipo: str
    dispositivo: str
    detalle: dict
    timestamp: str


@dataclass
class Alarma:
    alarma_id: str
    criticidad: str
    origen: str
    estado: str
    responsable: str
    historial: list = field(default_factory=list)
    registrada_en: str = ""


class ScadaEngine:
    """RTMSIL — adquisición continua de datos industriales (cap. 31)."""

    def __init__(self, fabricas_clientes: dict | None = None,
                 bus_eventos=None) -> None:
        # fabricas_clientes: {tipo: callable(endpoint, configuracion)}
        # que devuelve un cliente con .conectar()/.leer(variable).
        # Inyectable para pruebas; en producción se usan las librerías
        # reales (asyncua, paho-mqtt, pymodbus) vía _fabrica_real.
        self._fabricas = fabricas_clientes or {}
        self._bus = bus_eventos  # EventBusEngine inyectado (31.11)
        self._conectores: dict[str, list[Conector]] = {}
        self._adaptadores: dict[str, list[AdaptadorPLC]] = {}
        self._series: dict[str, list[Medicion]] = {}
        self._validaciones: dict[str, dict] = {}
        self._eventos: list[EventoIndustrial] = []
        self._alarmas: dict[str, Alarma] = {}
        self._clientes_vivos: dict[str, object] = {}
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
            "actor": actor,               # usuario cuando aplique (31.24)
            "resultado": resultado,
            "timestamp": self._ahora(),
            "version_motor": SCADA_VERSION,
        })

    def auditoria(self) -> list[dict]:
        return list(self._auditoria)

    # ------------------------------------- conectores 31.6/31.7/31.8
    def registrar_conector(self, conector_id: str, tipo: str,
                           endpoint: str, configuracion: dict,
                           responsable: str) -> Conector:
        """Alta o nueva versión de la configuración de un conector;
        nunca se sobrescribe (31.7: suscripción administrada por
        configuración)."""
        if tipo not in TIPOS_CONECTOR:
            raise ScadaInvalido(
                f"tipo inválido {tipo}; tipos: {list(TIPOS_CONECTOR)}")
        if not endpoint:
            raise ScadaInvalido(
                "endpoint obligatorio; sin endpoint el conector sería "
                "una simulación")
        if not responsable:
            raise ScadaInvalido("responsable obligatorio (31.24)")
        versiones = self._conectores.setdefault(conector_id, [])
        version = len(versiones) + 1
        con = Conector(conector_id, tipo, endpoint,
                       dict(configuracion or {}), version, responsable,
                       self._ahora())
        versiones.append(con)
        # una nueva versión invalida cualquier cliente vivo anterior
        self._clientes_vivos.pop(conector_id, None)
        self._auditar("conector_registrado",
                      {"conector_id": conector_id, "tipo": tipo,
                       "endpoint": endpoint, "version": version},
                      responsable)
        return con

    def conectores(self) -> list[dict]:
        out = []
        for versiones in self._conectores.values():
            c = versiones[-1]
            out.append({"conector_id": c.conector_id, "tipo": c.tipo,
                        "endpoint": c.endpoint, "version": c.version,
                        "estado": self._ultimo_estado.get(
                            c.conector_id, {}).get("estado",
                                                   "no_sondeado")})
        return out

    def historial_conector(self, conector_id: str) -> list[Conector]:
        return list(self._conectores.get(conector_id, []))

    def _conector_vigente(self, conector_id: str) -> Conector:
        versiones = self._conectores.get(conector_id)
        if not versiones:
            raise ScadaInvalido(f"conector desconocido: {conector_id}")
        return versiones[-1]

    def _fabrica(self, tipo: str):
        if tipo in self._fabricas:
            return self._fabricas[tipo]
        return _fabrica_real(tipo)

    def sondear(self, conector_id: str, actor: str = "sistema") -> dict:
        """Intento REAL de conexión (31.6/31.7/31.8). El resultado,
        incluido el fallo, se registra honestamente (31.24)."""
        con = self._conector_vigente(conector_id)
        try:
            cliente = self._fabrica(con.tipo)(con.endpoint,
                                              con.configuracion)
            cliente.conectar()
            self._clientes_vivos[conector_id] = cliente
            estado = {"estado": "conectado", "detalle": "",
                      "sondeado_en": self._ahora()}
            resultado = "ok"
        except Exception as exc:  # fallo real de conexión
            self._clientes_vivos.pop(conector_id, None)
            estado = {"estado": "fallo_conexion",
                      "detalle": f"{type(exc).__name__}: {exc}",
                      "sondeado_en": self._ahora()}
            resultado = "fallo"
            self._emitir_evento("perdida_comunicacion", conector_id,
                                {"detalle": estado["detalle"]})
        self._ultimo_estado[conector_id] = estado
        self._auditar("conector_sondeado",
                      {"conector_id": conector_id, "tipo": con.tipo,
                       "estado": estado["estado"],
                       "detalle": estado["detalle"]}, actor, resultado)
        return {"conector_id": conector_id, **estado}

    def leer_variable(self, conector_id: str, variable: str,
                      actor: str = "sistema") -> dict:
        """Lectura real a través del conector; sin conexión viva →
        SinCanal (503 honesto). Jamás se inventa una medición."""
        con = self._conector_vigente(conector_id)
        cliente = self._clientes_vivos.get(conector_id)
        if cliente is None:
            self._auditar("lectura_rechazada",
                          {"conector_id": conector_id,
                           "variable": variable,
                           "motivo": "sin conexión viva"},
                          actor, "fallo")
            raise SinCanal(
                f"conector {conector_id} sin conexión viva; sondee "
                "primero (POST .../probe)")
        try:
            lectura = cliente.leer(variable)
        except Exception as exc:
            self._clientes_vivos.pop(conector_id, None)
            self._emitir_evento("perdida_comunicacion", conector_id,
                                {"detalle": f"{type(exc).__name__}: {exc}"})
            raise SinCanal(
                f"fallo de lectura en {conector_id}: "
                f"{type(exc).__name__}: {exc}") from exc
        self._auditar("lectura_realizada",
                      {"conector_id": conector_id, "variable": variable},
                      actor)
        return {"conector_id": conector_id, "variable": variable,
                "lectura": lectura, "tipo": con.tipo,
                "leido_en": self._ahora()}

    # --------------------------------------------- adaptadores PLC (31.9)
    def registrar_adaptador(self, fabricante: str, mapeo: dict,
                            responsable: str) -> AdaptadorPLC:
        if not fabricante or not mapeo or not responsable:
            raise ScadaInvalido(
                "fabricante, mapeo y responsable obligatorios (31.9)")
        versiones = self._adaptadores.setdefault(fabricante, [])
        adp = AdaptadorPLC(fabricante, dict(mapeo),
                           len(versiones) + 1, responsable)
        versiones.append(adp)
        self._auditar("adaptador_registrado",
                      {"fabricante": fabricante, "campos": len(mapeo),
                       "version": adp.version}, responsable)
        return adp

    def traducir(self, fabricante: str, datos_externos: dict) -> dict:
        """Traducción real campo externo → modelo interno (31.9)."""
        versiones = self._adaptadores.get(fabricante)
        if not versiones:
            raise ScadaInvalido(
                f"sin adaptador para fabricante {fabricante} (31.9)")
        mapeo = versiones[-1].mapeo
        return {mapeo[k]: v for k, v in datos_externos.items()
                if k in mapeo}

    # -------------------------------------- colector de series (31.10)
    def definir_validacion(self, variable: str, minimo: float,
                           maximo: float, responsable: str) -> dict:
        """Rango permitido por variable (31.22); versionado."""
        if minimo >= maximo:
            raise ScadaInvalido("minimo debe ser menor que maximo")
        reglas = self._validaciones.setdefault(variable, [])
        reglas.append({"minimo": minimo, "maximo": maximo,
                       "version": len(reglas) + 1,
                       "responsable": responsable,
                       "definida_en": self._ahora()})
        self._auditar("validacion_definida",
                      {"variable": variable, "minimo": minimo,
                       "maximo": maximo}, responsable)
        return reglas[-1]

    def registrar_medicion(self, dispositivo: str, variable: str,
                           valor: float, unidad: str,
                           timestamp: str, origen: str,
                           calidad: str = "buena") -> Medicion:
        """Acepta una medición sólo tras validación real (31.22):
        formato (valor numérico), rango permitido (si hay regla) y
        consistencia temporal (no futura, no anterior a la última de la
        serie). Las anomalías generan evento de validación y la medición
        NO se acepta."""
        if not dispositivo or not variable or not unidad or not origen:
            raise ScadaInvalido(
                "dispositivo, variable, unidad y origen obligatorios "
                "(31.21)")
        if not isinstance(valor, (int, float)) or isinstance(valor, bool):
            self._rechazo(dispositivo, variable, "formato no numérico")
        if calidad not in CALIDADES:
            raise ScadaInvalido(
                f"calidad inválida {calidad}; calidades: {list(CALIDADES)}")
        try:
            ts = datetime.fromisoformat(timestamp)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            ts_utc = ts.astimezone(timezone.utc)  # normalización 31.13
        except (ValueError, TypeError):
            raise ScadaInvalido(f"timestamp inválido: {timestamp}")
        ahora = datetime.now(timezone.utc)
        if ts_utc > ahora:
            self._rechazo(dispositivo, variable,
                          "timestamp en el futuro")
        serie = self._series.setdefault(variable, [])
        if serie:
            ultimo = datetime.fromisoformat(serie[-1].timestamp)
            if ts_utc < ultimo:
                self._rechazo(dispositivo, variable,
                              "inconsistencia temporal: anterior a la "
                              "última medición de la serie")
        reglas = self._validaciones.get(variable, [])
        if reglas:
            r = reglas[-1]
            if not (r["minimo"] <= valor <= r["maximo"]):
                self._rechazo(
                    dispositivo, variable,
                    f"fuera de rango [{r['minimo']}, {r['maximo']}]")
        med = Medicion(
            medicion_id=str(uuid.uuid4()),
            dispositivo=dispositivo, variable=variable, valor=float(valor),
            unidad=unidad, timestamp=ts_utc.isoformat(), origen=origen,
            calidad=calidad, version=SCADA_VERSION,
            dispositivo_id=dispositivo)
        serie.append(med)
        self._auditar("medicion_registrada",
                      {"dispositivo": dispositivo, "variable": variable,
                       "valor": valor, "unidad": unidad,
                       "origen": origen, "calidad": calidad},
                      origen)
        return med

    def _rechazo(self, dispositivo: str, variable: str, motivo: str):
        # 31.22: las anomalías generan eventos de validación
        self._emitir_evento("validacion", dispositivo,
                            {"variable": variable, "motivo": motivo})
        self._auditar("medicion_rechazada",
                      {"dispositivo": dispositivo, "variable": variable,
                       "motivo": motivo}, dispositivo, "fallo")
        raise ScadaInvalido(f"medición rechazada (31.22): {motivo}")

    def serie(self, variable: str) -> list[dict]:
        return [{"medicion_id": m.medicion_id, "valor": m.valor,
                 "unidad": m.unidad, "timestamp": m.timestamp,
                 "origen": m.origen, "calidad": m.calidad,
                 "dispositivo": m.dispositivo}
                for m in self._series.get(variable, [])]

    # ---------------------------------------- procesador de eventos 31.11
    def _emitir_evento(self, tipo: str, dispositivo: str,
                       detalle: dict) -> EventoIndustrial:
        ev = EventoIndustrial(str(uuid.uuid4()), tipo, dispositivo,
                              detalle, self._ahora())
        self._eventos.append(ev)
        if self._bus is not None:
            # distribución real al bus de mensajería (31.11)
            try:
                self._bus.publicar("evento_industrial",
                                   "monitoreo.scada",
                                   productor="scada-rtmsil",
                                   payload={"evento": tipo,
                                            "dispositivo": dispositivo,
                                            "detalle": detalle})
            except Exception:
                pass  # el bus reporta su propio estado honesto
        return ev

    def registrar_evento_operativo(self, tipo: str, dispositivo: str,
                                   detalle: dict, actor: str) -> dict:
        """Eventos operativos 31.11: inicio/paro/alarma/cambio_estado/
        pérdida_comunicacion, reportados por el equipo o el conector."""
        if tipo not in TIPOS_EVENTO:
            raise ScadaInvalido(
                f"tipo inválido {tipo}; tipos: {list(TIPOS_EVENTO)}")
        ev = self._emitir_evento(tipo, dispositivo, dict(detalle or {}))
        self._auditar("evento_registrado",
                      {"tipo": tipo, "dispositivo": dispositivo}, actor)
        return {"evento_id": ev.evento_id, "tipo": tipo,
                "dispositivo": dispositivo, "timestamp": ev.timestamp}

    def eventos(self, dispositivo: str | None = None) -> list[dict]:
        return [{"evento_id": e.evento_id, "tipo": e.tipo,
                 "dispositivo": e.dispositivo, "detalle": e.detalle,
                 "timestamp": e.timestamp}
                for e in self._eventos
                if dispositivo is None or e.dispositivo == dispositivo]

    # ------------------------------------------------- alarmas (31.12)
    def registrar_alarma(self, alarma_id: str, criticidad: str,
                         origen: str, responsable: str,
                         detalle: str) -> Alarma:
        if criticidad not in CRITICIDADES:
            raise ScadaInvalido(
                f"criticidad inválida {criticidad}; "
                f"criticidades: {list(CRITICIDADES)}")
        if not all([alarma_id, origen, responsable]):
            raise ScadaInvalido(
                "alarma_id, origen y responsable obligatorios (31.12)")
        if alarma_id in self._alarmas:
            raise ScadaInvalido(
                f"la alarma {alarma_id} ya existe; el historial nunca "
                "se reinicia (31.12)")
        ahora = self._ahora()
        al = Alarma(alarma_id, criticidad, origen, "activa", responsable,
                    historial=[{"estado": "activa", "timestamp": ahora,
                                "actor": responsable,
                                "detalle": detalle}],
                    registrada_en=ahora)
        self._alarmas[alarma_id] = al
        self._emitir_evento("alarma", origen,
                            {"alarma_id": alarma_id,
                             "criticidad": criticidad})
        self._auditar("alarma_registrada",
                      {"alarma_id": alarma_id, "criticidad": criticidad,
                       "origen": origen}, responsable)
        return al

    def cambiar_estado_alarma(self, alarma_id: str, estado: str,
                              actor: str, detalle: str = "") -> Alarma:
        al = self._alarmas.get(alarma_id)
        if al is None:
            raise ScadaInvalido(f"alarma desconocida: {alarma_id}")
        if estado not in ("reconocida", "cerrada"):
            raise ScadaInvalido(
                "transición inválida; estados: reconocida/cerrada")
        if al.estado == "cerrada":
            raise ScadaInvalido(
                "una alarma cerrada no se reabre; registre una nueva "
                "(31.12: historial completo)")
        al.estado = estado
        al.historial.append({"estado": estado,
                             "timestamp": self._ahora(),
                             "actor": actor, "detalle": detalle})
        self._auditar("alarma_actualizada",
                      {"alarma_id": alarma_id, "estado": estado}, actor)
        return al

    def alarmas(self) -> list[dict]:
        return [{"alarma_id": a.alarma_id, "criticidad": a.criticidad,
                 "origen": a.origen, "estado": a.estado,
                 "responsable": a.responsable,
                 "historial": a.historial,
                 "registrada_en": a.registrada_en}
                for a in self._alarmas.values()]

    # -------------------------------------------------- estado honesto
    def estado_capa(self) -> dict:
        return {
            "version_motor": SCADA_VERSION,
            "conectores": self.conectores(),
            "persistencia_31_23": {
                "influxdb": "no_configurado",
                "redis": "no_configurado",
                "minio": "no_configurado",
                "nota": ("series almacenadas en memoria del proceso; "
                         "la persistencia externa se activa al "
                         "configurar la infraestructura real")},
            "bus_eventos": ("inyectado" if self._bus is not None
                            else "no_inyectado"),
            "mediciones": sum(len(s) for s in self._series.values()),
            "eventos": len(self._eventos),
            "alarmas_activas": sum(
                1 for a in self._alarmas.values()
                if a.estado == "activa"),
        }


def _fabrica_real(tipo: str):
    """Fábricas de clientes reales por protocolo (31.6/31.7/31.8)."""
    if tipo == "opcua":
        from .scada_clients import cliente_opcua
        return cliente_opcua
    if tipo == "mqtt":
        from .scada_clients import cliente_mqtt
        return cliente_mqtt
    if tipo in ("modbus_tcp", "modbus_rtu"):
        from .scada_clients import cliente_modbus
        return lambda endpoint, cfg: cliente_modbus(tipo, endpoint, cfg)
    raise ScadaInvalido(f"tipo de conector sin fábrica: {tipo}")
