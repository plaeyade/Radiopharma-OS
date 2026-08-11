"""API REST del Identity & Access Management (EDS cap. 47)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain.iam import AccesoDenegado, IamEngine, IamInvalido

router = APIRouter(prefix="/api/v1/iam", tags=["iam"])
_engine: IamEngine | None = None


def init(engine: IamEngine | None = None) -> None:
    global _engine
    _engine = engine if engine is not None else IamEngine()


def _eng() -> IamEngine:
    assert _engine is not None
    return _engine


def _guard(fn):
    try:
        return fn()
    except AccesoDenegado as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except IamInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))


class IdentidadIn(BaseModel):
    identidad_id: str
    tipo: str
    nombre: str
    roles: list[str] = []
    actor: str
    metadatos: dict[str, Any] = {}


class EstadoIdentidadIn(BaseModel):
    estado: str
    actor: str
    motivo: str


class RolIn(BaseModel):
    rol: str
    descripcion: str
    permisos: list[dict[str, str]] = []
    actor: str


class SesionIn(BaseModel):
    identidad_id: str
    origen: str = ""


class AccesoIn(BaseModel):
    sesion_id: str
    recurso: str
    accion: str
    contexto: dict[str, Any] = {}


@router.post("/identities")
def registrar_identidad(body: IdentidadIn):
    return _guard(lambda: _eng().registrar_identidad(
        body.identidad_id, body.tipo, body.nombre, body.roles, body.actor, body.metadatos))


@router.get("/identities")
def listar_identidades(tipo: str | None = None):
    return _guard(lambda: _eng().identidades(tipo))


@router.post("/identities/{identidad_id}/estado")
def cambiar_estado(identidad_id: str, body: EstadoIdentidadIn):
    return _guard(lambda: _eng().cambiar_estado_identidad(
        identidad_id, body.estado, body.actor, body.motivo))


@router.post("/roles")
def definir_rol(body: RolIn):
    return _guard(lambda: _eng().definir_rol(
        body.rol, body.descripcion, body.permisos, body.actor))


@router.get("/roles")
def listar_roles():
    return _guard(lambda: _eng().listar_roles())


@router.get("/roles/{rol}")
def obtener_rol(rol: str, version: int | None = None):
    return _guard(lambda: _eng().rol(rol, version))


@router.post("/sessions")
def iniciar_sesion(body: SesionIn):
    return _guard(lambda: _eng().iniciar_sesion(body.identidad_id, body.origen))


@router.get("/sessions")
def listar_sesiones(identidad_id: str | None = None):
    return _guard(lambda: _eng().sesiones(identidad_id))


@router.post("/sessions/{sesion_id}/renovar")
def renovar_sesion(sesion_id: str):
    return _guard(lambda: _eng().renovar_sesion(sesion_id))


@router.post("/sessions/{sesion_id}/cerrar")
def cerrar_sesion(sesion_id: str):
    return _guard(lambda: _eng().cerrar_sesion(sesion_id))


@router.post("/pep/verificar")
def verificar_acceso(body: AccesoIn):
    return _guard(lambda: _eng().verificar_acceso(
        body.sesion_id, body.recurso, body.accion, body.contexto))


@router.get("/pep/decisiones")
def decisiones(identidad_id: str | None = None):
    return _guard(lambda: _eng().decisiones(identidad_id))


@router.get("/audit")
def auditoria():
    return _eng().auditoria()
