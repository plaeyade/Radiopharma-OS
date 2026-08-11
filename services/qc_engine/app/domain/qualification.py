"""Qualification Engine — calificación DQ/IQ/OQ/PQ de componentes (Informe 14.9).

Principios canónicos:
- **14.9**: cada componente debe superar, en orden estricto, Design
  Qualification (DQ), Installation Qualification (IQ), Operational
  Qualification (OQ) y Performance Qualification (PQ).
- **PQ bajo condiciones reales (14.9)**: la etapa PQ exige entorno
  declarado como ``condiciones_reales``; en entorno simulado la etapa
  NO puede marcarse como superada — queda honestamente pendiente.
- **14.8**: la calificación forma parte del ciclo de validación
  estructurado; cada etapa genera documentación específica (protocolo
  versionado + resultados por criterio).
- **Protocolos versionados (14.12)**: un protocolo nunca se sobrescribe;
  toda modificación genera una versión nueva con motivo.
- **Nada se declara sin evidencia**: una etapa sólo se supera cuando
  TODOS sus criterios tienen resultado real registrado y cumplido.
- Auditoría ALCOA+ en todas las operaciones (evento_id, acción, detalle,
  actor, timestamp, versión del motor).
- El expediente de calificación queda estructurado para su ingesta como
  evidencia en el RCAE (EDS 49.8/49.13: vinculada a su origen).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

QUALIFICATION_VERSION = "qualification-1.0.0"

ETAPAS = ("DQ", "IQ", "OQ", "PQ")
ENTORNOS = ("condiciones_reales", "simulado", "laboratorio")
ESTADOS_ETAPA = ("pendiente", "superada", "no_superada")


class CalificacionInvalida(ValueError):
    """Componente, protocolo, etapa o resultado inválido (14.8/14.9)."""


@dataclass
class Componente:
    componente_id: str
    nombre: str
    tipo: str
    version: str
    responsable: str
    registrado_en: str


@dataclass
class Protocolo:
    """Protocolo de una etapa (14.8: documentación específica por fase)."""
    componente_id: str
    etapa: str
    version: int
    criterios: list[str]
    responsable: str
    motivo: str
    definido_en: str


@dataclass
class ResultadoCriterio:
    criterio: str
    cumple: bool
    detalle: str
    evidencia_ref: str


@dataclass
class EjecucionEtapa:
    ejecucion_id: str
    componente_id: str
    etapa: str
    protocolo_version: int
    entorno: str
    ejecutor: str
    resultados: list[ResultadoCriterio]
    estado: str  # superada | no_superada
    ejecutada_en: str


class QualificationEngine:
    """Motor de calificación DQ/IQ/OQ/PQ (Informe 14.9)."""

    def __init__(self) -> None:
        self._componentes: dict[str, Componente] = {}
        self._protocolos: dict[tuple[str, str], list[Protocolo]] = {}
        self._ejecuciones: dict[str, list[EjecucionEtapa]] = {}
        self._auditoria: list[dict] = []

    # ----------------------------------------------------------- utilidades
    def _ahora(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _auditar(self, accion: str, detalle: dict, actor: str) -> None:
        self._auditoria.append({
            "evento_id": str(uuid.uuid4()),
            "accion": accion,
            "detalle": detalle,
            "actor": actor,
            "timestamp": self._ahora(),
            "version_motor": QUALIFICATION_VERSION,
        })

    def auditoria(self) -> list[dict]:
        return list(self._auditoria)

    def _componente(self, componente_id: str) -> Componente:
        comp = self._componentes.get(componente_id)
        if comp is None:
            raise CalificacionInvalida(
                f"componente desconocido: {componente_id}")
        return comp

    # ------------------------------------------------- componentes (14.9)
    def registrar_componente(self, componente_id: str, nombre: str,
                             tipo: str, version: str,
                             responsable: str) -> Componente:
        if not all([componente_id, nombre, tipo, version, responsable]):
            raise CalificacionInvalida(
                "id, nombre, tipo, versión y responsable obligatorios")
        if componente_id in self._componentes:
            raise CalificacionInvalida(
                f"el componente {componente_id} ya existe; "
                "registre una versión nueva como componente distinto")
        comp = Componente(componente_id, nombre, tipo, version,
                          responsable, self._ahora())
        self._componentes[componente_id] = comp
        self._auditar("componente_registrado",
                      {"componente_id": componente_id, "tipo": tipo,
                       "version": version}, responsable)
        return comp

    def componentes(self) -> list[Componente]:
        return list(self._componentes.values())

    # ---------------------------------------------- protocolos (14.8/14.12)
    def definir_protocolo(self, componente_id: str, etapa: str,
                          criterios: list[str], responsable: str,
                          motivo: str) -> Protocolo:
        """Alta o nueva versión del protocolo de una etapa (nunca se
        sobrescribe — 14.12 gestión de cambios)."""
        self._componente(componente_id)
        if etapa not in ETAPAS:
            raise CalificacionInvalida(
                f"etapa inválida {etapa}; etapas: {list(ETAPAS)} (14.9)")
        if not criterios:
            raise CalificacionInvalida(
                "el protocolo exige al menos un criterio de aceptación")
        if not responsable or not motivo:
            raise CalificacionInvalida(
                "responsable y motivo obligatorios (14.12)")
        key = (componente_id, etapa)
        versiones = self._protocolos.setdefault(key, [])
        version = len(versiones) + 1
        proto = Protocolo(componente_id, etapa, version, list(criterios),
                          responsable, motivo, self._ahora())
        versiones.append(proto)
        self._auditar("protocolo_definido",
                      {"componente_id": componente_id, "etapa": etapa,
                       "version": version, "criterios": len(criterios),
                       "motivo": motivo}, responsable)
        return proto

    def protocolo_vigente(self, componente_id: str, etapa: str) -> Protocolo:
        versiones = self._protocolos.get((componente_id, etapa), [])
        if not versiones:
            raise CalificacionInvalida(
                f"sin protocolo para {componente_id}/{etapa} "
                "(14.8: cada fase genera documentación específica)")
        return versiones[-1]

    def historial_protocolo(self, componente_id: str,
                            etapa: str) -> list[Protocolo]:
        return list(self._protocolos.get((componente_id, etapa), []))

    # ------------------------------------------------ ejecución (14.9)
    def _etapa_superada(self, componente_id: str, etapa: str) -> bool:
        return any(e.etapa == etapa and e.estado == "superada"
                   for e in self._ejecuciones.get(componente_id, []))

    def ejecutar_etapa(self, componente_id: str, etapa: str, entorno: str,
                       ejecutor: str,
                       resultados: list[dict]) -> EjecucionEtapa:
        """Ejecuta una etapa con resultados REALES por criterio.

        ``resultados``: lista de dicts {criterio, cumple, detalle,
        evidencia_ref}. La etapa se supera sólo si todos los criterios
        del protocolo vigente tienen resultado cumplido. PQ exige
        ``entorno == "condiciones_reales"`` (14.9); en cualquier otro
        entorno la ejecución se registra honestamente pero la etapa
        permanece no superada.
        """
        self._componente(componente_id)
        if etapa not in ETAPAS:
            raise CalificacionInvalida(
                f"etapa inválida {etapa}; etapas: {list(ETAPAS)} (14.9)")
        if entorno not in ENTORNOS:
            raise CalificacionInvalida(
                f"entorno inválido {entorno}; entornos: {list(ENTORNOS)}")
        if not ejecutor:
            raise CalificacionInvalida("ejecutor obligatorio (ALCOA+)")
        # orden estricto DQ → IQ → OQ → PQ (14.9)
        idx = ETAPAS.index(etapa)
        for previa in ETAPAS[:idx]:
            if not self._etapa_superada(componente_id, previa):
                raise CalificacionInvalida(
                    f"la etapa {previa} debe superarse antes de {etapa} "
                    "(14.9: orden estricto DQ/IQ/OQ/PQ)")
        proto = self.protocolo_vigente(componente_id, etapa)
        por_criterio = {r.get("criterio"): r for r in (resultados or [])}
        faltantes = [c for c in proto.criterios if c not in por_criterio]
        if faltantes:
            raise CalificacionInvalida(
                f"faltan resultados reales para criterios: {faltantes}; "
                "nada se declara sin evidencia")
        res: list[ResultadoCriterio] = []
        for c in proto.criterios:
            r = por_criterio[c]
            res.append(ResultadoCriterio(
                criterio=c,
                cumple=bool(r.get("cumple")),
                detalle=str(r.get("detalle", "")),
                evidencia_ref=str(r.get("evidencia_ref", "")),
            ))
        todos_cumplen = all(r.cumple for r in res)
        if etapa == "PQ" and entorno != "condiciones_reales":
            # 14.9: PQ es verificación bajo condiciones reales; en otro
            # entorno se registra la ejecución pero NO se declara superada.
            estado = "no_superada"
        else:
            estado = "superada" if todos_cumplen else "no_superada"
        ejec = EjecucionEtapa(
            ejecucion_id=str(uuid.uuid4()),
            componente_id=componente_id, etapa=etapa,
            protocolo_version=proto.version, entorno=entorno,
            ejecutor=ejecutor, resultados=res, estado=estado,
            ejecutada_en=self._ahora())
        self._ejecuciones.setdefault(componente_id, []).append(ejec)
        self._auditar("etapa_ejecutada",
                      {"componente_id": componente_id, "etapa": etapa,
                       "protocolo_version": proto.version,
                       "entorno": entorno, "estado": estado,
                       "ejecucion_id": ejec.ejecucion_id,
                       "pq_nota": ("PQ bajo condiciones reales exigida "
                                   "(14.9)" if etapa == "PQ" else None)},
                      ejecutor)
        return ejec

    # ------------------------------------------------------ estado/expediente
    def estado_calificacion(self, componente_id: str) -> dict:
        """Estado real por etapa; el componente está calificado sólo con
        las cuatro etapas superadas, PQ incluida (14.9)."""
        comp = self._componente(componente_id)
        etapas = {}
        for e in ETAPAS:
            ejecs = [x for x in self._ejecuciones.get(componente_id, [])
                     if x.etapa == e]
            if not ejecs:
                etapas[e] = {"estado": "pendiente", "ejecuciones": 0}
            else:
                ultima = ejecs[-1]
                etapas[e] = {
                    "estado": ("superada" if self._etapa_superada(
                        componente_id, e) else ultima.estado),
                    "ejecuciones": len(ejecs),
                    "ultima_ejecucion": ultima.ejecucion_id,
                    "entorno": ultima.entorno,
                }
        calificado = all(self._etapa_superada(componente_id, e)
                         for e in ETAPAS)
        siguiente = next((e for e in ETAPAS
                          if not self._etapa_superada(componente_id, e)),
                         None)
        return {
            "componente_id": componente_id,
            "nombre": comp.nombre,
            "version_componente": comp.version,
            "etapas": etapas,
            "siguiente_etapa": siguiente,
            "calificado": calificado,
            "nota": ("calificación completa DQ/IQ/OQ/PQ (14.9)"
                     if calificado else
                     f"pendiente: {siguiente}"),
        }

    def expediente(self, componente_id: str) -> dict:
        """Expediente completo, estructurado como evidencia RCAE
        (EDS 49.8/49.13: toda evidencia vinculada a su origen)."""
        self._componente(componente_id)
        return {
            "origen": "qualification_engine",
            "tipo_evidencia": "expediente_calificacion",
            "componente_id": componente_id,
            "estado": self.estado_calificacion(componente_id),
            "protocolos": {
                etapa: [
                    {"version": p.version, "criterios": p.criterios,
                     "responsable": p.responsable, "motivo": p.motivo,
                     "definido_en": p.definido_en}
                    for p in self.historial_protocolo(componente_id, etapa)
                ] for etapa in ETAPAS
                if self.historial_protocolo(componente_id, etapa)},
            "ejecuciones": [
                {"ejecucion_id": e.ejecucion_id, "etapa": e.etapa,
                 "protocolo_version": e.protocolo_version,
                 "entorno": e.entorno, "ejecutor": e.ejecutor,
                 "estado": e.estado, "ejecutada_en": e.ejecutada_en,
                 "resultados": [
                     {"criterio": r.criterio, "cumple": r.cumple,
                      "detalle": r.detalle,
                      "evidencia_ref": r.evidencia_ref}
                     for r in e.resultados]}
                for e in self._ejecuciones.get(componente_id, [])],
            "generado_en": self._ahora(),
            "version_motor": QUALIFICATION_VERSION,
        }
