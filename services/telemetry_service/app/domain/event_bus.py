"""EDS cap. 52 — Event Bus & Message Broker.

Topic Manager 52.7 (canales por dominio), Schema Registry 52.10 (toda
versión del esquema permanece disponible; la evolución exige
compatibilidad hacia atrás — nunca se retira una versión), Event Registry
52.8 (catálogo oficial versionado: identificador, productor, consumidor
esperado, esquema), Event Router 52.9 (distribución hacia los servicios
suscritos, completamente desacoplada del productor) y Dead Letter Manager
52.11 (eventos no procesados con causa real, fecha, servicio y estado —
reprocesables).

Honestidad de plataforma: el broker EXTERNO (Kafka/RabbitMQ) se reporta
`no_configurado`; el bus en proceso entrega realmente a los suscriptores
registrados con canal invocable — una suscripción sin canal nunca se
declara entregada (`sin_canal`).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

EVENT_BUS_VERSION = "1.0.0"
DOMINIOS_TOPICO = ("produccion", "calidad", "logistica", "mantenimiento",
                   "seguridad", "monitoreo", "inteligencia_artificial")
ESTADOS_ENTREGA = ("entregado", "sin_canal", "fallido")


class EventoInvalido(ValueError):
    pass


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class VersionEsquema:
    version: int
    campos_requeridos: list[str]
    registrada_en: str


@dataclass
class Suscripcion:
    suscripcion_id: str
    topico: str
    servicio: str
    canal: Callable[[dict[str, Any]], None] | None
    registrada_en: str


@dataclass
class Evento:
    evento_id: str
    tipo: str
    version_esquema: int
    topico: str
    productor: str
    payload: dict[str, Any]
    publicado_en: str


@dataclass
class Entrega:
    entrega_id: str
    evento_id: str
    destino: str
    estado: str
    timestamp: str
    causa: str | None = None


@dataclass
class DeadLetter:
    dead_letter_id: str
    evento_id: str
    servicio: str
    causa: str
    fecha: str
    estado: str  # pendiente/reprocesado/descartado
    reintentos: int = 0


class EventBusEngine:
    """Bus de eventos de la plataforma (cap. 52)."""

    def __init__(self) -> None:
        self._topicos: dict[str, dict[str, Any]] = {}
        self._esquemas: dict[str, list[VersionEsquema]] = {}
        self._suscripciones: dict[str, Suscripcion] = {}
        self._eventos: list[Evento] = []
        self._entregas: list[Entrega] = []
        self._dead_letters: dict[str, DeadLetter] = {}
        self._auditoria: list[dict[str, Any]] = []

    # ---------------- auditoría ALCOA+ (52.20) ----------------
    def _auditar(self, accion: str, detalle: dict[str, Any], actor: str) -> None:
        self._auditoria.append({
            "evento_id": str(uuid.uuid4()),
            "accion": accion,
            "detalle": detalle,
            "actor": actor,
            "timestamp": _ahora(),
            "version_motor": EVENT_BUS_VERSION,
        })

    def auditoria(self) -> list[dict[str, Any]]:
        return list(self._auditoria)

    def estado_broker(self) -> dict[str, Any]:
        """52.6: la implementación tecnológica permanece desacoplada; el
        broker externo se declara honestamente."""
        return {"broker_externo": "no_configurado",
                "bus_en_proceso": "operativo",
                "nota": "la entrega externa requiere un broker real; nunca se "
                        "declara entregado un evento sin canal"}

    # ---------------- Topic Manager 52.7 ----------------
    def crear_topico(self, topico: str, dominio: str, actor: str) -> dict[str, Any]:
        if not topico or not actor:
            raise EventoInvalido("topico y actor son obligatorios")
        if dominio not in DOMINIOS_TOPICO:
            raise EventoInvalido(f"dominio debe ser uno de {DOMINIOS_TOPICO}: {dominio}")
        if topico in self._topicos:
            raise EventoInvalido(f"tópico ya registrado: {topico}")
        self._topicos[topico] = {"topico": topico, "dominio": dominio,
                                 "creado_en": _ahora()}
        self._auditar("topico_creado", {"topico": topico, "dominio": dominio}, actor)
        return dict(self._topicos[topico])

    def topicos(self) -> list[dict[str, Any]]:
        return [dict(t) for t in self._topicos.values()]

    # ---------------- Schema Registry 52.10 ----------------
    def registrar_esquema(self, tipo: str, campos_requeridos: list[str],
                          actor: str) -> dict[str, Any]:
        if not tipo or not campos_requeridos or not actor:
            raise EventoInvalido("tipo, campos_requeridos y actor son obligatorios")
        versiones = self._esquemas.setdefault(tipo, [])
        if versiones:
            anterior = set(versiones[-1].campos_requeridos)
            if not anterior.issubset(set(campos_requeridos)):
                raise EventoInvalido(
                    f"esquema incompatible: la nueva versión debe conservar los campos "
                    f"requeridos de la anterior {sorted(anterior)} (52.10 — compatibilidad "
                    "entre productores y consumidores)")
        version = len(versiones) + 1  # toda versión permanece disponible
        versiones.append(VersionEsquema(version, list(campos_requeridos), _ahora()))
        self._auditar("esquema_registrado", {"tipo": tipo, "version": version}, actor)
        return {"tipo": tipo, "version": version}

    def esquema(self, tipo: str, version: int | None = None) -> dict[str, Any]:
        versiones = self._esquemas.get(tipo)
        if not versiones:
            raise EventoInvalido(f"esquema no registrado: {tipo}")
        v = versiones[-1] if version is None else next(
            (x for x in versiones if x.version == version), None)
        if v is None:
            raise EventoInvalido(f"versión {version} no registrada para el esquema {tipo}")
        return {"tipo": tipo, "version": v.version,
                "campos_requeridos": list(v.campos_requeridos),
                "registrada_en": v.registrada_en, "versiones_disponibles": len(versiones)}

    # ---------------- Event Registry 52.8 ----------------
    def catalogo_eventos(self) -> list[dict[str, Any]]:
        catalogo: dict[str, dict[str, Any]] = {}
        for e in self._eventos:
            entrada = catalogo.setdefault(e.tipo, {
                "tipo": e.tipo, "productor": e.productor, "topico": e.topico,
                "versiones": [], "publicaciones": 0})
            entrada["publicaciones"] += 1
            if e.version_esquema not in entrada["versiones"]:
                entrada["versiones"].append(e.version_esquema)
        return list(catalogo.values())

    # ---------------- Event Router 52.9 ----------------
    def suscribir(self, topico: str, servicio: str, actor: str,
                  canal: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
        if topico not in self._topicos:
            raise EventoInvalido(f"tópico no registrado: {topico}")
        if not servicio or not actor:
            raise EventoInvalido("servicio y actor son obligatorios")
        sus = Suscripcion(str(uuid.uuid4()), topico, servicio, canal, _ahora())
        self._suscripciones[sus.suscripcion_id] = sus
        self._auditar("suscripcion_registrada", {"topico": topico, "servicio": servicio,
                      "con_canal": canal is not None}, actor)
        return {"suscripcion_id": sus.suscripcion_id, "topico": topico,
                "servicio": servicio, "con_canal": canal is not None}

    def suscripciones(self, topico: str | None = None) -> list[dict[str, Any]]:
        return [{"suscripcion_id": s.suscripcion_id, "topico": s.topico,
                 "servicio": s.servicio, "con_canal": s.canal is not None,
                 "registrada_en": s.registrada_en}
                for s in self._suscripciones.values()
                if topico is None or s.topico == topico]

    def publicar(self, tipo: str, topico: str, productor: str,
                 payload: dict[str, Any]) -> dict[str, Any]:
        if topico not in self._topicos:
            raise EventoInvalido(f"tópico no registrado: {topico}")
        if not productor or not isinstance(payload, dict):
            raise EventoInvalido("productor y payload son obligatorios")
        esq = self.esquema(tipo)  # valida existencia del esquema (52.8/52.10)
        faltantes = [c for c in esq["campos_requeridos"] if c not in payload]
        if faltantes:
            raise EventoInvalido(f"payload incompleto para el esquema {tipo} "
                                 f"v{esq['version']}: faltan {faltantes} — nunca se "
                                 "enruta un evento inválido")
        ev = Evento(str(uuid.uuid4()), tipo, esq["version"], topico, productor,
                    dict(payload), _ahora())
        self._eventos.append(ev)
        entregas: list[dict[str, Any]] = []
        for sus in self._suscripciones.values():
            if sus.topico != topico:
                continue  # enrutamiento desacoplado del productor (52.9)
            entregas.append(self._entregar(ev, sus))
        self._auditar("evento_publicado", {"evento_id": ev.evento_id, "tipo": tipo,
                      "topico": topico, "entregas": len(entregas)}, productor)
        return {"evento_id": ev.evento_id, "tipo": tipo,
                "version_esquema": ev.version_esquema, "topico": topico,
                "publicado_en": ev.publicado_en, "entregas": entregas}

    def _entregar(self, ev: Evento, sus: Suscripcion) -> dict[str, Any]:
        if sus.canal is None:
            estado, causa = "sin_canal", "suscripción declarativa sin canal: el broker " \
                "externo está no_configurado — nunca se declara entregado"
        else:
            try:
                sus.canal({"evento_id": ev.evento_id, "tipo": ev.tipo,
                           "payload": dict(ev.payload), "publicado_en": ev.publicado_en})
                estado, causa = "entregado", None
            except Exception as exc:  # causa REAL del fallo (52.11)
                estado, causa = "fallido", f"{type(exc).__name__}: {exc}"
                dl = DeadLetter(str(uuid.uuid4()), ev.evento_id, sus.servicio,
                                causa, _ahora(), "pendiente")
                self._dead_letters[dl.dead_letter_id] = dl
                self._auditar("dead_letter_registrado", {"dead_letter_id": dl.dead_letter_id,
                              "evento_id": ev.evento_id, "servicio": sus.servicio,
                              "causa": causa}, "event-bus")
        ent = Entrega(str(uuid.uuid4()), ev.evento_id, sus.servicio, estado,
                      _ahora(), causa)
        self._entregas.append(ent)
        return {"entrega_id": ent.entrega_id, "destino": ent.destino,
                "estado": ent.estado, "timestamp": ent.timestamp, "causa": ent.causa}

    # ---------------- Dead Letter Manager 52.11 ----------------
    def dead_letters(self, estado: str | None = None) -> list[dict[str, Any]]:
        return [{"dead_letter_id": d.dead_letter_id, "evento_id": d.evento_id,
                 "servicio": d.servicio, "causa": d.causa, "fecha": d.fecha,
                 "estado": d.estado, "reintentos": d.reintentos}
                for d in self._dead_letters.values()
                if estado is None or d.estado == estado]

    def reprocesar_dead_letter(self, dead_letter_id: str, actor: str) -> dict[str, Any]:
        dl = self._dead_letters.get(dead_letter_id)
        if dl is None:
            raise EventoInvalido(f"dead letter no registrado: {dead_letter_id}")
        if dl.estado != "pendiente":
            raise EventoInvalido(f"dead letter en estado '{dl.estado}': no reprocesable")
        if not actor:
            raise EventoInvalido("actor obligatorio")
        ev = next((e for e in self._eventos if e.evento_id == dl.evento_id), None)
        if ev is None:
            raise EventoInvalido("evento original no disponible para reprocesar")
        sus = next((s for s in self._suscripciones.values()
                    if s.topico == ev.topico and s.servicio == dl.servicio), None)
        dl.reintentos += 1
        if sus is None or sus.canal is None:
            self._auditar("dead_letter_reproceso_fallido",
                          {"dead_letter_id": dead_letter_id,
                           "motivo": "sin canal suscrito"}, actor)
            raise EventoInvalido("sin canal suscrito para reprocesar: el evento NO se "
                                 "declara reprocesado")
        try:
            sus.canal({"evento_id": ev.evento_id, "tipo": ev.tipo,
                       "payload": dict(ev.payload), "publicado_en": ev.publicado_en})
        except Exception as exc:
            dl.causa = f"{type(exc).__name__}: {exc}"
            self._auditar("dead_letter_reproceso_fallido",
                          {"dead_letter_id": dead_letter_id, "causa": dl.causa}, actor)
            raise EventoInvalido(f"reprocesamiento falló de nuevo: {dl.causa}")
        dl.estado = "reprocesado"
        self._auditar("dead_letter_reprocesado", {"dead_letter_id": dead_letter_id,
                      "reintentos": dl.reintentos}, actor)
        return {"dead_letter_id": dead_letter_id, "estado": "reprocesado",
                "reintentos": dl.reintentos}

    def historial_eventos(self, topico: str | None = None) -> list[dict[str, Any]]:
        """Gestión temporal 52.12: timestamp/origen/versión/estado de cada evento."""
        return [{"evento_id": e.evento_id, "tipo": e.tipo,
                 "version_esquema": e.version_esquema, "topico": e.topico,
                 "productor": e.productor, "publicado_en": e.publicado_en}
                for e in self._eventos if topico is None or e.topico == topico]
