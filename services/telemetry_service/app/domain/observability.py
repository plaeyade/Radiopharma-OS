"""EDS cap. 55 — Observability & Monitoring Platform.

Metrics Manager 55.6 (métricas organizadas por dominio con timestamp,
origen y categoría 55.12), Log Management Platform 55.7 (registros
centralizados e indexados para consulta — búsqueda real por texto,
nivel, servicio y ventana), Distributed Tracing Engine 55.8 (recorrido
completo de una solicitud reconstruido desde spans reales con tiempos,
dependencias y errores) y Alert Manager 55.9 (umbrales, prioridades y
escalamiento configurables — las alertas solo nacen de mediciones reales,
NUNCA inventadas). AIOps 55.10 asiste la operación: sin modelos
registrados se reporta honestamente `sin_modelos`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

OBSERVABILITY_VERSION = "1.0.0"
DOMINIOS_METRICA = ("infraestructura", "aplicaciones", "servicios", "gemelos", "ia")
NIVELES_LOG = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
ORIGENES_LOG = ("microservicios", "infraestructura", "aplicaciones", "seguridad",
                "industrial")
PRIORIDADES_ALERTA = ("baja", "media", "alta", "critica")
OPERADORES_UMBRAL = (">", ">=", "<", "<=")


class ObservabilidadInvalida(ValueError):
    pass


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Metrica:
    metrica_id: str
    nombre: str
    dominio: str
    valor: float
    unidad: str
    origen: str
    timestamp: str


@dataclass
class RegistroLog:
    log_id: str
    nivel: str
    servicio: str
    origen: str
    mensaje: str
    timestamp: str
    contexto: dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    span_id: str
    trace_id: str
    servicio: str
    operacion: str
    inicio: str
    duracion_ms: float
    span_padre: str | None
    error: str | None


@dataclass
class PoliticaAlerta:
    nombre: str
    metrica: str
    operador: str
    umbral: float
    prioridad: str
    escalamiento_a: str
    version: int


class ObservabilityEngine:
    """Plataforma de observabilidad (cap. 55)."""

    def __init__(self) -> None:
        self._metricas: list[Metrica] = []
        self._logs: list[RegistroLog] = []
        self._spans: list[Span] = []
        self._politicas: dict[str, list[PoliticaAlerta]] = {}
        self._alertas: list[dict[str, Any]] = []
        self._auditoria: list[dict[str, Any]] = []

    # ---------------- auditoría ALCOA+ ----------------
    def _auditar(self, accion: str, detalle: dict[str, Any], actor: str) -> None:
        self._auditoria.append({
            "evento_id": str(uuid.uuid4()),
            "accion": accion,
            "detalle": detalle,
            "actor": actor,
            "timestamp": _ahora(),
            "version_motor": OBSERVABILITY_VERSION,
        })

    def auditoria(self) -> list[dict[str, Any]]:
        return list(self._auditoria)

    def estado_aiops(self) -> dict[str, Any]:
        """55.10: honestidad — sin modelos AIOps registrados, no se declara
        análisis inteligente."""
        return {"aiops": "sin_modelos",
                "nota": "los modelos AIOps (anomalías/tendencias) requieren modelos "
                        "registrados en el Model Registry; el análisis nunca se inventa"}

    # ---------------- Metrics Manager 55.6 ----------------
    def registrar_metrica(self, nombre: str, dominio: str, valor: float,
                          unidad: str, origen: str) -> dict[str, Any]:
        if dominio not in DOMINIOS_METRICA:
            raise ObservabilidadInvalida(f"dominio debe ser uno de {DOMINIOS_METRICA}")
        if not nombre or not origen:
            raise ObservabilidadInvalida("nombre y origen son obligatorios (55.12)")
        m = Metrica(str(uuid.uuid4()), nombre, dominio, float(valor), unidad,
                    origen, _ahora())
        self._metricas.append(m)
        alertas = self._evaluar_politicas(m)
        return {"metrica_id": m.metrica_id, "nombre": nombre, "dominio": dominio,
                "valor": m.valor, "unidad": unidad, "origen": origen,
                "timestamp": m.timestamp, "alertas_generadas": len(alertas)}

    def metricas(self, nombre: str | None = None,
                 dominio: str | None = None) -> list[dict[str, Any]]:
        return [{"metrica_id": m.metrica_id, "nombre": m.nombre, "dominio": m.dominio,
                 "valor": m.valor, "unidad": m.unidad, "origen": m.origen,
                 "timestamp": m.timestamp}
                for m in self._metricas
                if (nombre is None or m.nombre == nombre)
                and (dominio is None or m.dominio == dominio)]

    # ---------------- Log Management Platform 55.7 ----------------
    def registrar_log(self, nivel: str, servicio: str, origen: str,
                      mensaje: str, contexto: dict[str, Any] | None = None) -> dict[str, Any]:
        if nivel not in NIVELES_LOG:
            raise ObservabilidadInvalida(f"nivel debe ser uno de {NIVELES_LOG}")
        if origen not in ORIGENES_LOG:
            raise ObservabilidadInvalida(f"origen debe ser uno de {ORIGENES_LOG}")
        if not servicio or not mensaje:
            raise ObservabilidadInvalida("servicio y mensaje son obligatorios")
        log = RegistroLog(str(uuid.uuid4()), nivel, servicio, origen, mensaje,
                          _ahora(), dict(contexto or {}))
        self._logs.append(log)
        return {"log_id": log.log_id, "timestamp": log.timestamp}

    def consultar_logs(self, texto: str | None = None, nivel: str | None = None,
                       servicio: str | None = None) -> list[dict[str, Any]]:
        """Consulta real sobre los registros indexados (55.7)."""
        return [{"log_id": l.log_id, "nivel": l.nivel, "servicio": l.servicio,
                 "origen": l.origen, "mensaje": l.mensaje, "timestamp": l.timestamp,
                 "contexto": l.contexto}
                for l in self._logs
                if (texto is None or texto.lower() in l.mensaje.lower())
                and (nivel is None or l.nivel == nivel)
                and (servicio is None or l.servicio == servicio)]

    # ---------------- Distributed Tracing Engine 55.8 ----------------
    def registrar_span(self, trace_id: str, servicio: str, operacion: str,
                       inicio: str, duracion_ms: float,
                       span_padre: str | None = None,
                       error: str | None = None) -> dict[str, Any]:
        if not trace_id or not servicio or not operacion or not inicio:
            raise ObservabilidadInvalida("trace_id, servicio, operacion e inicio son "
                                         "obligatorios")
        if duracion_ms < 0:
            raise ObservabilidadInvalida("duracion_ms no puede ser negativa")
        span = Span(str(uuid.uuid4()), trace_id, servicio, operacion, inicio,
                    float(duracion_ms), span_padre, error)
        self._spans.append(span)
        return {"span_id": span.span_id, "trace_id": trace_id}

    def reconstruir_traza(self, trace_id: str) -> dict[str, Any]:
        """Recorrido completo reconstruido desde spans REALES (55.8)."""
        spans = [s for s in self._spans if s.trace_id == trace_id]
        if not spans:
            raise ObservabilidadInvalida(f"traza no registrada: {trace_id}")
        return {"trace_id": trace_id,
                "servicios": [s.servicio for s in spans],
                "duracion_total_ms": round(sum(s.duracion_ms for s in spans), 4),
                "spans": [{"span_id": s.span_id, "servicio": s.servicio,
                           "operacion": s.operacion, "inicio": s.inicio,
                           "duracion_ms": s.duracion_ms, "span_padre": s.span_padre,
                           "error": s.error} for s in spans],
                "errores": [{"servicio": s.servicio, "error": s.error}
                            for s in spans if s.error]}

    # ---------------- Alert Manager 55.9 ----------------
    def definir_politica_alerta(self, nombre: str, metrica: str, operador: str,
                                umbral: float, prioridad: str,
                                escalamiento_a: str, actor: str) -> dict[str, Any]:
        if not nombre or not metrica or not escalamiento_a or not actor:
            raise ObservabilidadInvalida("nombre, metrica, escalamiento_a y actor son "
                                         "obligatorios")
        if operador not in OPERADORES_UMBRAL:
            raise ObservabilidadInvalida(f"operador debe ser uno de {OPERADORES_UMBRAL}")
        if prioridad not in PRIORIDADES_ALERTA:
            raise ObservabilidadInvalida(f"prioridad debe ser una de {PRIORIDADES_ALERTA}")
        versiones = self._politicas.setdefault(nombre, [])
        version = len(versiones) + 1  # políticas configurables y versionadas
        versiones.append(PoliticaAlerta(nombre, metrica, operador, float(umbral),
                                        prioridad, escalamiento_a, version))
        self._auditar("politica_alerta", {"nombre": nombre, "version": version}, actor)
        return {"nombre": nombre, "version": version}

    def _evaluar_politicas(self, m: Metrica) -> list[dict[str, Any]]:
        nuevas = []
        for versiones in self._politicas.values():
            p = versiones[-1]
            if p.metrica != m.nombre:
                continue
            disparada = {">": m.valor > p.umbral, ">=": m.valor >= p.umbral,
                         "<": m.valor < p.umbral, "<=": m.valor <= p.umbral}[p.operador]
            if not disparada:
                continue
            alerta = {"alerta_id": str(uuid.uuid4()), "politica": p.nombre,
                      "version_politica": p.version, "metrica": m.nombre,
                      "valor": m.valor, "umbral": f"{p.operador} {p.umbral}",
                      "prioridad": p.prioridad, "escalamiento_a": p.escalamiento_a,
                      "origen_medicion": m.origen, "generada_en": _ahora(),
                      "estado": "abierta"}
            self._alertas.append(alerta)  # solo de mediciones REALES
            self._auditar("alerta_generada", {"alerta_id": alerta["alerta_id"],
                          "politica": p.nombre, "valor": m.valor}, "alert-manager")
            nuevas.append(alerta)
        return nuevas

    def alertas(self, prioridad: str | None = None) -> list[dict[str, Any]]:
        return [dict(a) for a in self._alertas
                if prioridad is None or a["prioridad"] == prioridad]

    def cerrar_alerta(self, alerta_id: str, actor: str, motivo: str) -> dict[str, Any]:
        alerta = next((a for a in self._alertas if a["alerta_id"] == alerta_id), None)
        if alerta is None:
            raise ObservabilidadInvalida(f"alerta no registrada: {alerta_id}")
        if not actor or not motivo:
            raise ObservabilidadInvalida("actor y motivo son obligatorios")
        if alerta["estado"] != "abierta":
            raise ObservabilidadInvalida(f"alerta ya {alerta['estado']}")
        alerta["estado"] = "cerrada"
        alerta["cerrada_por"] = actor
        alerta["motivo_cierre"] = motivo
        self._auditar("alerta_cerrada", {"alerta_id": alerta_id, "motivo": motivo}, actor)
        return dict(alerta)
