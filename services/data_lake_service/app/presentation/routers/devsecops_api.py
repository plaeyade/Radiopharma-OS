"""API REST de DevSecOps & Platform Engineering (EDS cap. 56).

Los runners de CI y los scanners de seguridad se inyectan en el motor
(entorno de build real); por REST, una ejecución sin runner responde 422
honesto — nunca se declara un pipeline sin ejecución real.
"""

from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain.devsecops import DevsecopsEngine, DevsecopsInvalido

router = APIRouter(prefix="/api/v1/devsecops", tags=["devsecops"])
_engine: DevsecopsEngine | None = None


def init(engine: DevsecopsEngine | None = None) -> None:
    global _engine
    _engine = engine if engine is not None else DevsecopsEngine()


def _eng() -> DevsecopsEngine:
    assert _engine is not None
    return _engine


def _guard(fn):
    try:
        return fn()
    except DevsecopsInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))


class CambioIn(BaseModel):
    cambio_id: str
    repositorio: str
    rama: str
    autor: str
    descripcion: str
    hash_commit: str


class EjecucionIn(BaseModel):
    cambio_id: str
    responsable: str


class EscaneoIn(BaseModel):
    ejecucion_id: str
    responsable: str


class PromocionIn(BaseModel):
    ejecucion_id: str
    entorno: str
    estrategia: str
    responsable: str


class ArtefactoIn(BaseModel):
    artefacto_id: str
    tipo: str
    version: str
    contenido_b64: str
    ejecucion_origen: str
    responsable: str


class VerificacionIn(BaseModel):
    contenido_b64: str


@router.post("/changes")
def registrar_cambio(body: CambioIn):
    return _guard(lambda: _eng().registrar_cambio(
        body.cambio_id, body.repositorio, body.rama, body.autor,
        body.descripcion, body.hash_commit))


@router.get("/changes")
def historial_cambios(repositorio: str | None = None):
    return _eng().historial_cambios(repositorio)


@router.post("/ci/run")
def ejecutar_ci(body: EjecucionIn):
    # runner real inyectado en el motor (entorno de build); sin runner → 422
    return _guard(lambda: _eng().ejecutar_ci(body.cambio_id, body.responsable,
                                             getattr(_eng(), "runner_ci", None)))


@router.get("/ci/executions")
def ejecuciones_ci():
    return _eng().ejecuciones_ci()


@router.post("/security/scan")
def registrar_escaneo(body: EscaneoIn):
    return _guard(lambda: _eng().registrar_escaneo(
        body.ejecucion_id, body.responsable, getattr(_eng(), "scanner", None)))


@router.post("/cd/promote")
def promover(body: PromocionIn):
    return _guard(lambda: _eng().promover(
        body.ejecucion_id, body.entorno, body.estrategia, body.responsable))


@router.get("/cd/deployments")
def despliegues():
    return _eng().despliegues()


@router.post("/artifacts")
def registrar_artefacto(body: ArtefactoIn):
    try:
        contenido = base64.b64decode(body.contenido_b64)
    except Exception:
        raise HTTPException(status_code=422, detail="contenido_b64 inválido")
    return _guard(lambda: _eng().registrar_artefacto(
        body.artefacto_id, body.tipo, body.version, contenido,
        body.ejecucion_origen, body.responsable))


@router.get("/artifacts")
def artefactos():
    return _eng().artefactos()


@router.post("/artifacts/{artefacto_id}/verify")
def verificar_artefacto(artefacto_id: str, body: VerificacionIn):
    try:
        contenido = base64.b64decode(body.contenido_b64)
    except Exception:
        raise HTTPException(status_code=422, detail="contenido_b64 inválido")
    return _guard(lambda: _eng().verificar_artefacto(artefacto_id, contenido))


@router.get("/audit")
def auditoria():
    return _eng().auditoria()
