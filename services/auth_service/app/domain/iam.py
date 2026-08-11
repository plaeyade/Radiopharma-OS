"""EDS cap. 47 — Identity & Access Management.

Identity Registry 47.6 (usuarios, aplicaciones, servicios, dispositivos y
agentes inteligentes — cada identidad con identificador único; el registro
nunca sobrescribe), Role Manager 47.9 (perfiles institucionales
completamente configurables y versionados), Authorization Manager 47.8
(decisión por rol/recurso/acción/contexto — TODA decisión registrada),
Session Manager 47.10 (inicio, expiración, renovación y cierre con
trazabilidad completa) y Policy Enforcement Point 47.11 (punto único y
centralizado donde se aplican las decisiones antes del acceso).
Gestión temporal 47.12 y auditoría 47.19 ALCOA+.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

IAM_VERSION = "1.0.0"
TIPOS_IDENTIDAD = ("usuario", "aplicacion", "servicio", "dispositivo", "agente_inteligente")
ESTADOS_SESION = ("activa", "renovada", "cerrada", "expirada")


class IamInvalido(ValueError):
    pass


class AccesoDenegado(PermissionError):
    pass


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


@dataclass
class Identidad:
    identidad_id: str
    tipo: str
    nombre: str
    roles: list[str]
    estado: str  # activa/suspendida/revocada
    registrada_en: str
    metadatos: dict[str, Any] = field(default_factory=dict)


@dataclass
class VersionRol:
    version: int
    descripcion: str
    permisos: list[dict[str, str]]  # {recurso, accion}
    registrada_en: str


@dataclass
class Sesion:
    sesion_id: str
    identidad_id: str
    estado: str
    iniciada_en: str
    expira_en: str
    renovaciones: int = 0
    cerrada_en: str | None = None
    origen: str = ""


class IamEngine:
    """Motor IAM formal del cap. 47."""

    def __init__(self, ttl_sesion_min: int = 60, max_renovaciones: int = 12):
        self._ttl = ttl_sesion_min
        self._max_renov = max_renovaciones
        self._identidades: dict[str, Identidad] = {}
        self._roles: dict[str, list[VersionRol]] = {}
        self._sesiones: dict[str, Sesion] = {}
        self._decisiones: list[dict[str, Any]] = []
        self._auditoria: list[dict[str, Any]] = []

    # ---------------- auditoría ALCOA+ (47.19) ----------------
    def _auditar(self, accion: str, detalle: dict[str, Any], actor: str) -> None:
        self._auditoria.append({
            "evento_id": str(uuid.uuid4()),
            "accion": accion,
            "detalle": detalle,
            "actor": actor,
            "timestamp": _iso(_ahora()),
            "version_motor": IAM_VERSION,
        })

    def auditoria(self) -> list[dict[str, Any]]:
        return list(self._auditoria)

    # ---------------- Identity Registry 47.6 ----------------
    def registrar_identidad(self, identidad_id: str, tipo: str, nombre: str,
                            roles: list[str] | None = None, actor: str = "",
                            metadatos: dict[str, Any] | None = None) -> dict[str, Any]:
        if not identidad_id or not nombre or not actor:
            raise IamInvalido("identidad_id, nombre y actor son obligatorios")
        if tipo not in TIPOS_IDENTIDAD:
            raise IamInvalido(f"tipo debe ser uno de {TIPOS_IDENTIDAD}: {tipo}")
        if identidad_id in self._identidades:
            raise IamInvalido(f"identidad ya registrada: {identidad_id} — el registro "
                              "nunca sobrescribe (47.6)")
        roles = roles or []
        for r in roles:
            if r not in self._roles:
                raise IamInvalido(f"rol no definido: {r} — los roles deben existir en el "
                                  "Role Manager (47.9)")
        self._identidades[identidad_id] = Identidad(
            identidad_id, tipo, nombre, list(roles), "activa", _iso(_ahora()),
            dict(metadatos or {}))
        self._auditar("identidad_registrada", {"identidad_id": identidad_id, "tipo": tipo,
                                               "roles": roles}, actor)
        return self._dto_identidad(self._identidades[identidad_id])

    def cambiar_estado_identidad(self, identidad_id: str, estado: str,
                                 actor: str, motivo: str) -> dict[str, Any]:
        ide = self._identidad(identidad_id)
        if estado not in ("activa", "suspendida", "revocada"):
            raise IamInvalido("estado debe ser activa/suspendida/revocada")
        if not motivo:
            raise IamInvalido("motivo obligatorio para cambiar el estado de una identidad")
        ide.estado = estado
        self._auditar("identidad_estado", {"identidad_id": identidad_id, "estado": estado,
                                           "motivo": motivo}, actor)
        return self._dto_identidad(ide)

    def identidades(self, tipo: str | None = None) -> list[dict[str, Any]]:
        return [self._dto_identidad(i) for i in self._identidades.values()
                if tipo is None or i.tipo == tipo]

    def _identidad(self, identidad_id: str) -> Identidad:
        ide = self._identidades.get(identidad_id)
        if ide is None:
            raise IamInvalido(f"identidad no registrada: {identidad_id}")
        return ide

    @staticmethod
    def _dto_identidad(i: Identidad) -> dict[str, Any]:
        return {"identidad_id": i.identidad_id, "tipo": i.tipo, "nombre": i.nombre,
                "roles": list(i.roles), "estado": i.estado, "registrada_en": i.registrada_en,
                "metadatos": i.metadatos}

    # ---------------- Role Manager 47.9 ----------------
    def definir_rol(self, rol: str, descripcion: str,
                    permisos: list[dict[str, str]], actor: str) -> dict[str, Any]:
        if not rol or not descripcion or not actor:
            raise IamInvalido("rol, descripcion y actor son obligatorios")
        for p in permisos:
            if not p.get("recurso") or not p.get("accion"):
                raise IamInvalido("cada permiso requiere recurso y accion")
        versiones = self._roles.setdefault(rol, [])
        version = len(versiones) + 1  # versionado: la definición nunca se sobrescribe
        versiones.append(VersionRol(version, descripcion,
                                    [dict(p) for p in permisos], _iso(_ahora())))
        self._auditar("rol_definido", {"rol": rol, "version": version,
                                       "permisos": len(permisos)}, actor)
        return {"rol": rol, "version": version}

    def rol(self, rol: str, version: int | None = None) -> dict[str, Any]:
        versiones = self._roles.get(rol)
        if not versiones:
            raise IamInvalido(f"rol no definido: {rol}")
        v = versiones[-1] if version is None else next(
            (x for x in versiones if x.version == version), None)
        if v is None:
            raise IamInvalido(f"versión {version} no registrada para el rol {rol}")
        return {"rol": rol, "version": v.version, "descripcion": v.descripcion,
                "permisos": [dict(p) for p in v.permisos], "registrada_en": v.registrada_en,
                "revisiones": len(versiones)}

    def listar_roles(self) -> list[dict[str, Any]]:
        return [self.rol(r) for r in sorted(self._roles)]

    # ---------------- Session Manager 47.10 ----------------
    def iniciar_sesion(self, identidad_id: str, origen: str = "") -> dict[str, Any]:
        ide = self._identidad(identidad_id)
        if ide.estado != "activa":
            raise AccesoDenegado(f"identidad {identidad_id} en estado '{ide.estado}': "
                                 "no puede iniciar sesión")
        ahora = _ahora()
        ses = Sesion(str(uuid.uuid4()), identidad_id, "activa", _iso(ahora),
                     _iso(ahora + timedelta(minutes=self._ttl)), 0, None, origen)
        self._sesiones[ses.sesion_id] = ses
        self._auditar("sesion_iniciada", {"sesion_id": ses.sesion_id,
                      "identidad_id": identidad_id, "origen": origen}, identidad_id)
        return self._dto_sesion(ses)

    def renovar_sesion(self, sesion_id: str) -> dict[str, Any]:
        ses = self._sesion_vigente(sesion_id)
        if ses.renovaciones >= self._max_renov:
            raise IamInvalido(f"límite de renovaciones alcanzado ({self._max_renov})")
        ses.renovaciones += 1
        ses.estado = "renovada"
        ses.expira_en = _iso(_ahora() + timedelta(minutes=self._ttl))
        self._auditar("sesion_renovada", {"sesion_id": sesion_id,
                                          "renovaciones": ses.renovaciones}, ses.identidad_id)
        return self._dto_sesion(ses)

    def cerrar_sesion(self, sesion_id: str) -> dict[str, Any]:
        ses = self._sesiones.get(sesion_id)
        if ses is None:
            raise IamInvalido(f"sesión no registrada: {sesion_id}")
        if ses.estado in ("cerrada", "expirada"):
            raise IamInvalido(f"sesión ya {ses.estado}")
        ses.estado = "cerrada"
        ses.cerrada_en = _iso(_ahora())
        self._auditar("sesion_cerrada", {"sesion_id": sesion_id}, ses.identidad_id)
        return self._dto_sesion(ses)

    def sesiones(self, identidad_id: str | None = None) -> list[dict[str, Any]]:
        return [self._dto_sesion(s) for s in self._sesiones.values()
                if identidad_id is None or s.identidad_id == identidad_id]

    def _sesion_vigente(self, sesion_id: str) -> Sesion:
        ses = self._sesiones.get(sesion_id)
        if ses is None:
            raise IamInvalido(f"sesión no registrada: {sesion_id}")
        if ses.estado == "cerrada":
            raise AccesoDenegado("sesión cerrada")
        if datetime.fromisoformat(ses.expira_en) <= _ahora():
            ses.estado = "expirada"  # expiración registrada, nunca silenciosa (47.10)
            self._auditar("sesion_expirada", {"sesion_id": sesion_id}, ses.identidad_id)
            raise AccesoDenegado("sesión expirada")
        return ses

    @staticmethod
    def _dto_sesion(s: Sesion) -> dict[str, Any]:
        return {"sesion_id": s.sesion_id, "identidad_id": s.identidad_id,
                "estado": s.estado, "iniciada_en": s.iniciada_en, "expira_en": s.expira_en,
                "renovaciones": s.renovaciones, "cerrada_en": s.cerrada_en, "origen": s.origen}

    # ---------------- Authorization Manager 47.8 + PEP 47.11 ----------------
    def _permisos_vigentes(self, identidad: Identidad) -> list[dict[str, str]]:
        permisos: list[dict[str, str]] = []
        for r in identidad.roles:
            versiones = self._roles.get(r, [])
            if versiones:
                permisos.extend(versiones[-1].permisos)
        return permisos

    def verificar_acceso(self, sesion_id: str, recurso: str, accion: str,
                         contexto: dict[str, Any] | None = None) -> dict[str, Any]:
        """Policy Enforcement Point 47.11: punto ÚNICO y centralizado.

        Toda decisión — permitida o denegada — permanece registrada (47.8).
        """
        if not recurso or not accion:
            raise IamInvalido("recurso y accion son obligatorios")
        motivo = ""
        permitido = False
        identidad_id = ""
        try:
            ses = self._sesion_vigente(sesion_id)
            identidad_id = ses.identidad_id
            ide = self._identidad(identidad_id)
            if ide.estado != "activa":
                motivo = f"identidad en estado '{ide.estado}'"
            else:
                permisos = self._permisos_vigentes(ide)
                permitido = any(
                    (p["recurso"] == recurso or p["recurso"] == "*") and
                    (p["accion"] == accion or p["accion"] == "*")
                    for p in permisos)
                motivo = "permiso vigente" if permitido else \
                    f"sin permiso para {accion} sobre {recurso} (default-deny)"
        except AccesoDenegado as exc:
            motivo = str(exc)
        except IamInvalido as exc:
            motivo = str(exc)
        decision = {"decision_id": str(uuid.uuid4()), "sesion_id": sesion_id,
                    "identidad_id": identidad_id, "recurso": recurso, "accion": accion,
                    "contexto": dict(contexto or {}), "permitido": permitido,
                    "motivo": motivo, "decidida_en": _iso(_ahora())}
        self._decisiones.append(decision)
        self._auditar("decision_acceso", {"decision_id": decision["decision_id"],
                      "recurso": recurso, "accion": accion, "permitido": permitido},
                      identidad_id or "anonimo")
        return decision

    def decisiones(self, identidad_id: str | None = None) -> list[dict[str, Any]]:
        return [d for d in self._decisiones
                if identidad_id is None or d["identidad_id"] == identidad_id]
