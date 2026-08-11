"""EDS cap. 58 — Digital Thread & Traceability Engine.

Digital Thread Manager 58.6 (hilo por entidad con continuidad durante
todo el ciclo de vida; los eventos se anexan — nunca se reescriben),
Data Lineage Engine 58.7 (origen, transformaciones, consumidores y
versiones de cada conjunto de datos), Product Genealogy Manager 58.8
(genealogía completa: materias primas → síntesis → purificación →
formulación → liberación → distribución, secuencia estricta), Event
Correlation Engine 58.9 (relación de eventos de múltiples dominios por
entidad — correlaciones registradas), Historical Reconstruction Engine
58.10 (estado de cualquier entidad en un instante, reconstruido SOLO
desde eventos reales del hilo — reproducible) y Provenance Registry
58.11 (origen verificable de datos, documentos, modelos, resultados y
simulaciones con hash opcional).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

THREAD_VERSION = "1.0.0"
TIPOS_ENTIDAD = ("lote", "radiofarmaco", "equipo", "documento", "usuario",
                 "simulacion", "modelo_ia")
DOMINIOS_EVENTO = ("produccion", "calidad", "logistica", "mantenimiento",
                   "inteligencia_artificial", "regulatorio")
ETAPAS_GENEALOGIA = ("materias_primas", "sintesis", "purificacion", "formulacion",
                     "liberacion", "distribucion")
TIPOS_PROCEDENCIA = ("dato", "documento", "modelo", "resultado", "simulacion")


class HiloInvalido(ValueError):
    pass


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class EventoHilo:
    evento_id: str
    dominio: str
    tipo: str
    datos: dict[str, Any]
    timestamp: str
    actor: str


@dataclass
class Hilo:
    entidad_id: str
    tipo_entidad: str
    eventos: list[EventoHilo] = field(default_factory=list)
    creado_en: str = ""


class DigitalThreadEngine:
    """Hilo digital y trazabilidad integral (cap. 58)."""

    def __init__(self) -> None:
        self._hilos: dict[str, Hilo] = {}
        self._linajes: dict[str, dict[str, Any]] = {}
        self._genealogias: dict[str, list[dict[str, Any]]] = {}
        self._correlaciones: list[dict[str, Any]] = []
        self._procedencia: dict[str, dict[str, Any]] = {}
        self._auditoria: list[dict[str, Any]] = []

    # ---------------- auditoría ALCOA+ ----------------
    def _auditar(self, accion: str, detalle: dict[str, Any], actor: str) -> None:
        self._auditoria.append({
            "evento_id": str(uuid.uuid4()),
            "accion": accion,
            "detalle": detalle,
            "actor": actor,
            "timestamp": _ahora(),
            "version_motor": THREAD_VERSION,
        })

    def auditoria(self) -> list[dict[str, Any]]:
        return list(self._auditoria)

    # ---------------- Digital Thread Manager 58.6 ----------------
    def abrir_hilo(self, entidad_id: str, tipo_entidad: str, actor: str) -> dict[str, Any]:
        if not entidad_id or not actor:
            raise HiloInvalido("entidad_id y actor son obligatorios")
        if tipo_entidad not in TIPOS_ENTIDAD:
            raise HiloInvalido(f"tipo_entidad debe ser uno de {TIPOS_ENTIDAD}")
        if entidad_id in self._hilos:
            raise HiloInvalido(f"hilo ya abierto para {entidad_id} — continuidad, "
                               "nunca duplicado (58.6)")
        self._hilos[entidad_id] = Hilo(entidad_id, tipo_entidad, [], _ahora())
        self._auditar("hilo_abierto", {"entidad_id": entidad_id,
                                       "tipo_entidad": tipo_entidad}, actor)
        return {"entidad_id": entidad_id, "tipo_entidad": tipo_entidad}

    def registrar_evento(self, entidad_id: str, dominio: str, tipo: str,
                         datos: dict[str, Any], actor: str,
                         timestamp: str | None = None) -> dict[str, Any]:
        hilo = self._hilo(entidad_id)
        if dominio not in DOMINIOS_EVENTO:
            raise HiloInvalido(f"dominio debe ser uno de {DOMINIOS_EVENTO}")
        if not tipo or not actor:
            raise HiloInvalido("tipo y actor son obligatorios")
        ev = EventoHilo(str(uuid.uuid4()), dominio, tipo, dict(datos or {}),
                        timestamp or _ahora(), actor)
        hilo.eventos.append(ev)  # se anexa — nunca se reescribe (58.6)
        self._auditar("evento_hilo", {"entidad_id": entidad_id, "dominio": dominio,
                                      "tipo": tipo}, actor)
        return {"evento_id": ev.evento_id, "entidad_id": entidad_id,
                "timestamp": ev.timestamp}

    def hilo(self, entidad_id: str) -> dict[str, Any]:
        hilo = self._hilo(entidad_id)
        return {"entidad_id": entidad_id, "tipo_entidad": hilo.tipo_entidad,
                "creado_en": hilo.creado_en, "n_eventos": len(hilo.eventos),
                "eventos": [{"evento_id": e.evento_id, "dominio": e.dominio,
                             "tipo": e.tipo, "datos": e.datos,
                             "timestamp": e.timestamp, "actor": e.actor}
                            for e in hilo.eventos]}

    def _hilo(self, entidad_id: str) -> Hilo:
        hilo = self._hilos.get(entidad_id)
        if hilo is None:
            raise HiloInvalido(f"hilo no registrado para la entidad: {entidad_id}")
        return hilo

    # ---------------- Data Lineage Engine 58.7 ----------------
    def registrar_linaje(self, dataset_id: str, origen: str, actor: str,
                         transformaciones: list[str] | None = None,
                         consumidores: list[str] | None = None) -> dict[str, Any]:
        if not dataset_id or not origen or not actor:
            raise HiloInvalido("dataset_id, origen y actor son obligatorios (58.7)")
        lin = self._linajes.setdefault(dataset_id, {
            "dataset_id": dataset_id, "origen": origen,
            "transformaciones": [], "consumidores": [], "versiones": 1,
            "registrado_en": _ahora()})
        if transformaciones:
            for t in transformaciones:
                if t not in lin["transformaciones"]:
                    lin["transformaciones"].append(t)
        if consumidores:
            for cons in consumidores:
                if cons not in lin["consumidores"]:
                    lin["consumidores"].append(cons)
        self._auditar("linaje_registrado", {"dataset_id": dataset_id,
                      "origen": origen}, actor)
        return dict(lin)

    def nueva_version_linaje(self, dataset_id: str, actor: str) -> dict[str, Any]:
        lin = self._linajes.get(dataset_id)
        if lin is None:
            raise HiloInvalido(f"linaje no registrado: {dataset_id}")
        lin["versiones"] += 1  # todo el linaje permanece disponible
        self._auditar("linaje_version", {"dataset_id": dataset_id,
                                         "versiones": lin["versiones"]}, actor)
        return dict(lin)

    def linaje(self, dataset_id: str) -> dict[str, Any]:
        lin = self._linajes.get(dataset_id)
        if lin is None:
            raise HiloInvalido(f"linaje no registrado: {dataset_id}")
        return dict(lin)

    # ---------------- Product Genealogy Manager 58.8 ----------------
    def registrar_etapa_producto(self, lote_id: str, etapa: str, datos: dict[str, Any],
                                 actor: str) -> dict[str, Any]:
        if etapa not in ETAPAS_GENEALOGIA:
            raise HiloInvalido(f"etapa debe ser una de {ETAPAS_GENEALOGIA}")
        if not actor:
            raise HiloInvalido("actor obligatorio")
        etapas = self._genealogias.setdefault(lote_id, [])
        completadas = [e["etapa"] for e in etapas]
        esperada = ETAPAS_GENEALOGIA[len(completadas)] if len(completadas) < len(ETAPAS_GENEALOGIA) else None
        if etapa in completadas:
            raise HiloInvalido(f"etapa {etapa} ya registrada para {lote_id} — la "
                               "genealogía no se reescribe")
        if etapa != esperada:
            raise HiloInvalido(f"secuencia genealógica: tras {completadas or ['(inicio)']} "
                               f"corresponde '{esperada}', no '{etapa}' (58.8)")
        etapas.append({"etapa": etapa, "datos": dict(datos or {}), "actor": actor,
                       "registrada_en": _ahora()})
        self._auditar("etapa_producto", {"lote_id": lote_id, "etapa": etapa}, actor)
        return {"lote_id": lote_id, "etapa": etapa,
                "completitud": f"{len(etapas)}/{len(ETAPAS_GENEALOGIA)}"}

    def genealogia(self, lote_id: str) -> dict[str, Any]:
        etapas = self._genealogias.get(lote_id)
        if etapas is None:
            raise HiloInvalido(f"genealogía no registrada para el lote: {lote_id}")
        return {"lote_id": lote_id, "etapas": list(etapas),
                "completa": len(etapas) == len(ETAPAS_GENEALOGIA)}

    # ---------------- Event Correlation Engine 58.9 ----------------
    def correlacionar(self, entidad_id: str, actor: str) -> dict[str, Any]:
        """Correlación REAL: agrupa los eventos del hilo por dominio."""
        hilo = self._hilo(entidad_id)
        if not hilo.eventos:
            raise HiloInvalido(f"entidad {entidad_id} sin eventos: no hay correlación "
                               "que declarar")
        por_dominio: dict[str, int] = {}
        for e in hilo.eventos:
            por_dominio[e.dominio] = por_dominio.get(e.dominio, 0) + 1
        correlacion = {"correlacion_id": str(uuid.uuid4()), "entidad_id": entidad_id,
                       "dominios": sorted(por_dominio),
                       "eventos_por_dominio": por_dominio,
                       "n_eventos": len(hilo.eventos), "generada_en": _ahora()}
        self._correlaciones.append(correlacion)  # correlaciones registradas (58.9)
        self._auditar("correlacion_generada", {"entidad_id": entidad_id,
                      "dominios": sorted(por_dominio)}, actor)
        return dict(correlacion)

    def correlaciones(self, entidad_id: str | None = None) -> list[dict[str, Any]]:
        return [dict(c) for c in self._correlaciones
                if entidad_id is None or c["entidad_id"] == entidad_id]

    # ---------------- Historical Reconstruction Engine 58.10 ----------------
    def reconstruir(self, entidad_id: str, instante: str) -> dict[str, Any]:
        """Estado en un instante, SOLO desde eventos reales del hilo."""
        hilo = self._hilo(entidad_id)
        if not instante:
            raise HiloInvalido("instante obligatorio")
        eventos = [e for e in hilo.eventos if e.timestamp <= instante]
        reconstruccion = {"entidad_id": entidad_id, "instante": instante,
                          "tipo_entidad": hilo.tipo_entidad,
                          "n_eventos_hasta_instante": len(eventos),
                          "eventos": [{"dominio": e.dominio, "tipo": e.tipo,
                                       "datos": e.datos, "timestamp": e.timestamp}
                                      for e in eventos],
                          "reproducible": True,
                          "nota": "reconstrucción exclusivamente desde eventos "
                                  "reales del hilo (58.10)"}
        self._auditar("reconstruccion", {"entidad_id": entidad_id, "instante": instante,
                                         "n_eventos": len(eventos)}, "thread-engine")
        return reconstruccion

    # ---------------- Provenance Registry 58.11 ----------------
    def registrar_procedencia(self, elemento_id: str, tipo: str, origen: str,
                              actor: str, hash_sha256: str | None = None,
                              metadatos: dict[str, Any] | None = None) -> dict[str, Any]:
        if not elemento_id or not origen or not actor:
            raise HiloInvalido("elemento_id, origen y actor son obligatorios")
        if tipo not in TIPOS_PROCEDENCIA:
            raise HiloInvalido(f"tipo debe ser uno de {TIPOS_PROCEDENCIA}")
        if elemento_id in self._procedencia:
            raise HiloInvalido(f"procedencia ya registrada: {elemento_id} — nunca "
                               "sobrescrita (58.11)")
        self._procedencia[elemento_id] = {
            "elemento_id": elemento_id, "tipo": tipo, "origen": origen,
            "hash_sha256": hash_sha256, "metadatos": dict(metadatos or {}),
            "registrado_por": actor, "registrado_en": _ahora()}
        self._auditar("procedencia_registrada", {"elemento_id": elemento_id,
                      "tipo": tipo, "origen": origen}, actor)
        return dict(self._procedencia[elemento_id])

    def procedencia(self, elemento_id: str) -> dict[str, Any]:
        p = self._procedencia.get(elemento_id)
        if p is None:
            raise HiloInvalido(f"procedencia no registrada: {elemento_id}")
        return dict(p)
