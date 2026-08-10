"""Regulatory Compliance & Audit Engine (EDS cap. 49).

El RCAE administra EVIDENCIA de cumplimiento (49.3): no reemplaza a los
organismos reguladores ni a los sistemas oficiales de certificación.

- **Requirement Registry (49.6)**: catálogo de requisitos versionado;
  cada cambio es una revisión nueva (49.12), nunca se sobrescribe.
- **Compliance Manager (49.7)**: evaluaciones con estado, evidencia,
  responsable y fecha. El estado `no_demostrable` es el marcador
  honesto para requisitos cuya demostración exige entorno real (PQ,
  validación clínica, inspección regulatoria).
- **Evidence Manager (49.8/49.13)**: evidencias centralizadas, cada una
  vinculada a su origen (servicio/registro); nunca se eliminan.
- **Audit Manager (49.9)**: expedientes independientes de auditoría
  con hallazgos.
- **CAPA Manager (49.10)**: acciones correctivas/preventivas vinculadas
  al hallazgo que las originó, con seguimiento.
- **Inspection Manager (49.11)**: expediente de preparación que compila
  el estado real de cada requisito — la evidencia pendiente se marca
  explícitamente.
- **Validación (49.18)**: cerrar un requisito exige evidencia y
  aprobación; los incompletos permanecen abiertos.

Auditoría 49.20 en todas las operaciones.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

RCAE_VERSION = "rcae-1.0.0"

ESTADOS_CUMPLIMIENTO = ("cumple", "cumple_parcial", "no_cumple",
                        "no_demostrable", "pendiente")

TIPOS_AUDITORIA = ("interna", "externa")
SEVERIDADES = ("critica", "mayor", "menor", "observacion")
ESTADOS_CAPA = ("abierta", "en_curso", "cerrada_verificada")


class CumplimientoInvalido(ValueError):
    """Requisito, evidencia, auditoría o CAPA inválida (49.18)."""


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Requisito:
    """Requirement Registry (49.6)."""
    requisito_id: str
    fuente: str                     # GMP/GSR Part 3/21 CFR Part 11/...
    version: str
    vigencia_desde: str
    alcance: str
    descripcion: str = ""


@dataclass
class Evidencia:
    """Evidence Manager (49.8): vinculada a su origen (49.13)."""
    evidencia_id: str
    tipo: str                       # registro_electronico/reporte/
                                    # certificado/resultado_analitico/
                                    # registro_mantenimiento/bitacora
    origen: str                     # servicio:endpoint o registro origen
    referencia: str                 # id del registro origen
    hash_sha256: str = ""
    fecha: str = ""


class ComplianceEngine:
    """RCAE: evidencia organizada, trazable y verificable (49.3)."""

    def __init__(self) -> None:
        self._requisitos: dict[str, list[Requisito]] = {}  # versionado
        self._evaluaciones: dict[str, dict] = {}
        self._evidencias: dict[str, Evidencia] = {}
        self._vinculos: dict[str, list[str]] = {}   # requisito -> ev ids
        self._auditorias: dict[str, dict] = {}
        self._capas: dict[str, dict] = {}
        self._audit_trail: list[dict] = []

    # ------------------------------------------------------------ núcleo
    def _auditar(self, usuario: str, accion: str, detalle: str) -> None:
        self._audit_trail.append({"usuario": usuario, "accion": accion,
                                  "detalle": detalle, "fecha": _ahora()})

    def audit_trail(self) -> list[dict]:
        return list(self._audit_trail)

    # --------------------------------------------- requisitos 49.6/49.12
    def registrar_requisito(self, req: Requisito, usuario: str) -> dict:
        """Alta o nueva revisión de un requisito (49.6)."""
        if not req.fuente or not req.version or not req.vigencia_desde:
            raise CumplimientoInvalido(
                "fuente, versión y vigencia obligatorias (49.6)")
        versiones = self._requisitos.setdefault(req.requisito_id, [])
        if any(r.version == req.version for r in versiones):
            raise CumplimientoInvalido(
                f"versión ya registrada para {req.requisito_id}: "
                f"{req.version} (49.12: nunca se sobrescribe)")
        versiones.append(req)
        self._auditar(usuario, "registrar_requisito",
                      f"{req.requisito_id} v{req.version}")
        return {"requisito_id": req.requisito_id, "version": req.version,
                "n_revisiones": len(versiones)}

    def requisitos(self) -> list[dict]:
        out = []
        for rid, versiones in self._requisitos.items():
            vig = versiones[-1]
            out.append({"requisito_id": rid, "fuente": vig.fuente,
                        "version_vigente": vig.version,
                        "vigencia_desde": vig.vigencia_desde,
                        "alcance": vig.alcance, "descripcion": vig.descripcion,
                        "revisiones": [r.version for r in versiones],
                        "estado": self._evaluaciones.get(
                            rid, {}).get("estado", "pendiente")})
        return out

    # ----------------------------------------------- evidencias 49.8/13
    def registrar_evidencia(self, ev: Evidencia, usuario: str) -> dict:
        if ev.evidencia_id in self._evidencias:
            raise CumplimientoInvalido(
                f"evidencia ya registrada: {ev.evidencia_id}")
        if not ev.origen or not ev.referencia:
            raise CumplimientoInvalido(
                "toda evidencia permanece vinculada a su origen (49.13)")
        ev.fecha = ev.fecha or _ahora()
        self._evidencias[ev.evidencia_id] = ev   # nunca se elimina
        self._auditar(usuario, "registrar_evidencia", ev.evidencia_id)
        return {"evidencia_id": ev.evidencia_id}

    def vincular_evidencia(self, requisito_id: str, evidencia_id: str,
                           usuario: str) -> dict:
        if requisito_id not in self._requisitos:
            raise CumplimientoInvalido(
                f"requisito inexistente: {requisito_id}")
        if evidencia_id not in self._evidencias:
            raise CumplimientoInvalido(
                f"evidencia inexistente: {evidencia_id}")
        vinc = self._vinculos.setdefault(requisito_id, [])
        if evidencia_id not in vinc:
            vinc.append(evidencia_id)
        self._auditar(usuario, "vincular_evidencia",
                      f"{requisito_id} <- {evidencia_id}")
        return {"requisito_id": requisito_id, "evidencias": list(vinc)}

    def evidencias(self, requisito_id: str | None = None) -> list[dict]:
        ids = (self._vinculos.get(requisito_id, [])
               if requisito_id else list(self._evidencias))
        return [{"evidencia_id": e.evidencia_id, "tipo": e.tipo,
                 "origen": e.origen, "referencia": e.referencia,
                 "hash_sha256": e.hash_sha256, "fecha": e.fecha}
                for e in (self._evidencias[i] for i in ids)]

    # ------------------------------------------------ evaluación 49.7/18
    def evaluar(self, requisito_id: str, estado: str, responsable: str,
                usuario: str, nota: str = "") -> dict:
        if requisito_id not in self._requisitos:
            raise CumplimientoInvalido(
                f"requisito inexistente: {requisito_id}")
        if estado not in ESTADOS_CUMPLIMIENTO:
            raise CumplimientoInvalido(f"estado inválido: {estado}")
        # 49.18: declarar cumplimiento exige evidencia disponible
        if estado in ("cumple", "cumple_parcial") and not self._vinculos.get(
                requisito_id):
            raise CumplimientoInvalido(
                "no se puede declarar cumplimiento sin evidencia "
                "vinculada (49.18); el requisito permanece abierto")
        self._evaluaciones[requisito_id] = {
            "estado": estado, "responsable": responsable,
            "nota": nota, "fecha": _ahora(),
            "evidencias": list(self._vinculos.get(requisito_id, []))}
        self._auditar(usuario, "evaluar_requisito",
                      f"{requisito_id} -> {estado}")
        return {"requisito_id": requisito_id, "estado": estado}

    def tablero_cumplimiento(self) -> dict:
        """Estado real de la plataforma (49.7), sin inflar cifras."""
        total = len(self._requisitos)
        por_estado = {e: 0 for e in ESTADOS_CUMPLIMIENTO}
        for rid in self._requisitos:
            por_estado[self._evaluaciones.get(
                rid, {}).get("estado", "pendiente")] += 1
        demostrables = total - por_estado["no_demostrable"]
        return {"total_requisitos": total, "por_estado": por_estado,
                "cobertura_pct": (round(100.0 * por_estado["cumple"]
                                        / demostrables, 2)
                                  if demostrables else None),
                "nota": "la cobertura excluye los requisitos marcados "
                        "honestamente como no_demostrable (requieren "
                        "entorno real: PQ, clínica, inspección)"}

    # ------------------------------------------------- auditorías 49.9
    def abrir_auditoria(self, auditoria_id: str, tipo: str, alcance: str,
                        auditor: str, usuario: str) -> dict:
        if auditoria_id in self._auditorias:
            raise CumplimientoInvalido(
                f"auditoría ya registrada: {auditoria_id}")
        if tipo not in TIPOS_AUDITORIA:
            raise CumplimientoInvalido(f"tipo inválido: {tipo}")
        self._auditorias[auditoria_id] = {
            "auditoria_id": auditoria_id, "tipo": tipo, "alcance": alcance,
            "auditor": auditor, "estado": "abierta",
            "hallazgos": [], "apertura": _ahora(), "cierre": None}
        self._auditar(usuario, "abrir_auditoria", auditoria_id)
        return {"auditoria_id": auditoria_id, "estado": "abierta"}

    def registrar_hallazgo(self, auditoria_id: str, hallazgo_id: str,
                           severidad: str, descripcion: str,
                           requisito_id: str, usuario: str) -> dict:
        aud = self._auditorias.get(auditoria_id)
        if aud is None:
            raise CumplimientoInvalido(
                f"auditoría inexistente: {auditoria_id}")
        if aud["estado"] != "abierta":
            raise CumplimientoInvalido("auditoría cerrada")
        if severidad not in SEVERIDADES:
            raise CumplimientoInvalido(f"severidad inválida: {severidad}")
        if requisito_id not in self._requisitos:
            raise CumplimientoInvalido(
                f"requisito inexistente: {requisito_id}")
        if any(h["hallazgo_id"] == hallazgo_id for h in aud["hallazgos"]):
            raise CumplimientoInvalido(
                f"hallazgo duplicado: {hallazgo_id}")
        aud["hallazgos"].append({
            "hallazgo_id": hallazgo_id, "severidad": severidad,
            "descripcion": descripcion, "requisito_id": requisito_id,
            "fecha": _ahora(), "capas": []})
        self._auditar(usuario, "registrar_hallazgo",
                      f"{hallazgo_id} ({severidad}) en {auditoria_id}")
        return {"hallazgo_id": hallazgo_id}

    def cerrar_auditoria(self, auditoria_id: str, usuario: str) -> dict:
        aud = self._auditorias.get(auditoria_id)
        if aud is None:
            raise CumplimientoInvalido(
                f"auditoría inexistente: {auditoria_id}")
        # los hallazgos críticos/mayores exigen CAPA abierta (49.10)
        pendientes = []
        for h in aud["hallazgos"]:
            if h["severidad"] in ("critica", "mayor") and not h["capas"]:
                pendientes.append(h["hallazgo_id"])
        if pendientes:
            raise CumplimientoInvalido(
                f"hallazgos críticos/mayores sin CAPA: {pendientes}")
        aud["estado"] = "cerrada"
        aud["cierre"] = _ahora()
        self._auditar(usuario, "cerrar_auditoria", auditoria_id)
        return {"auditoria_id": auditoria_id, "estado": "cerrada"}

    def auditoria_expediente(self, auditoria_id: str) -> dict:
        if auditoria_id not in self._auditorias:
            raise CumplimientoInvalido(
                f"auditoría inexistente: {auditoria_id}")
        return self._auditorias[auditoria_id]

    # -------------------------------------------------------- CAPA 49.10
    def abrir_capa(self, capa_id: str, auditoria_id: str, hallazgo_id: str,
                   tipo: str, descripcion: str, responsable: str,
                   fecha_objetivo: str, usuario: str) -> dict:
        if capa_id in self._capas:
            raise CumplimientoInvalido(f"CAPA ya registrada: {capa_id}")
        if tipo not in ("correctiva", "preventiva"):
            raise CumplimientoInvalido(f"tipo CAPA inválido: {tipo}")
        aud = self._auditorias.get(auditoria_id)
        if aud is None:
            raise CumplimientoInvalido(
                f"auditoría inexistente: {auditoria_id}")
        hall = next((h for h in aud["hallazgos"]
                     if h["hallazgo_id"] == hallazgo_id), None)
        if hall is None:
            raise CumplimientoInvalido(
                f"hallazgo inexistente: {hallazgo_id} — cada CAPA "
                f"permanece vinculada al hallazgo que la originó (49.10)")
        self._capas[capa_id] = {
            "capa_id": capa_id, "auditoria_id": auditoria_id,
            "hallazgo_id": hallazgo_id, "tipo": tipo,
            "descripcion": descripcion, "responsable": responsable,
            "fecha_objetivo": fecha_objetivo, "estado": "abierta",
            "seguimiento": [], "apertura": _ahora()}
        hall["capas"].append(capa_id)
        self._auditar(usuario, "abrir_capa", f"{capa_id} <- {hallazgo_id}")
        return {"capa_id": capa_id, "estado": "abierta"}

    def seguir_capa(self, capa_id: str, nota: str, usuario: str,
                    nuevo_estado: str | None = None) -> dict:
        capa = self._capas.get(capa_id)
        if capa is None:
            raise CumplimientoInvalido(f"CAPA inexistente: {capa_id}")
        if nuevo_estado is not None:
            if nuevo_estado not in ESTADOS_CAPA:
                raise CumplimientoInvalido(
                    f"estado CAPA inválido: {nuevo_estado}")
            capa["estado"] = nuevo_estado
        capa["seguimiento"].append({"nota": nota, "usuario": usuario,
                                    "fecha": _ahora()})
        self._auditar(usuario, "seguir_capa", capa_id)
        return {"capa_id": capa_id, "estado": capa["estado"]}

    def capas(self) -> list[dict]:
        return list(self._capas.values())

    # ------------------------------------------------ inspección 49.11
    def preparar_inspeccion(self, usuario: str) -> dict:
        """Expediente de preparación: estado REAL por requisito; la
        evidencia pendiente se marca explícitamente (49.11/49.18)."""
        expediente = []
        for rid, versiones in self._requisitos.items():
            ev = self._evaluaciones.get(rid)
            evidencias = self._vinculos.get(rid, [])
            expediente.append({
                "requisito_id": rid, "fuente": versiones[-1].fuente,
                "version": versiones[-1].version,
                "estado": (ev or {}).get("estado", "pendiente"),
                "n_evidencias": len(evidencias),
                "evidencia_pendiente": not evidencias,
                "responsable": (ev or {}).get("responsable")})
        self._auditar(usuario, "preparar_inspeccion",
                      f"{len(expediente)} requisitos")
        return {"fecha": _ahora(), "requisitos": expediente,
                "n_requisitos": len(expediente),
                "n_sin_evidencia": sum(1 for e in expediente
                                       if e["evidencia_pendiente"]),
                "nota": "expediente compilado desde el estado real de la "
                        "plataforma; nada sustituye la verificación del "
                        "organismo regulador (49.3)"}
