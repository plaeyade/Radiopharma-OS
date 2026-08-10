"""Router REST del Enterprise Governance Core (cap. 46).

  POST /api/v1/governance/policies               — Policy Manager 46.6
  POST /api/v1/governance/policies/{id}/publish  — validación 46.17
  POST /api/v1/governance/policies/{id}/retire
  GET  /api/v1/governance/policies
  POST /api/v1/governance/rules                  — Rule Manager 46.7
  POST /api/v1/governance/rules/{id}/deactivate
  POST /api/v1/governance/rules/{id}/evaluate    — evaluación desacoplada
  GET  /api/v1/governance/rules
  POST /api/v1/governance/architecture           — Architecture Mgr 46.9
  GET  /api/v1/governance/architecture
  GET  /api/v1/governance/architecture/{id}/dependencies
  GET  /api/v1/governance/registry               — registro oficial 46.10
  GET  /api/v1/governance/audit                  — auditoría 46.19
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.domain.governance import (ComponenteArquitectura, GobernanzaInvalida,
                                   GovernanceEngine, Politica, Regla)

router = APIRouter(prefix="/api/v1/governance", tags=["enterprise-governance"])

_engine: GovernanceEngine | None = None


def init(engine: GovernanceEngine | None = None) -> None:
    global _engine
    _engine = engine or GovernanceEngine()


def _guard(fn, *args):
    try:
        return fn(*args)
    except GobernanzaInvalida as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/policies", status_code=201)
def registrar_politica(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_engine.registrar_politica, Politica(**payload), usuario)


@router.post("/policies/{politica_id}/publish")
def publicar(politica_id: str, payload: dict) -> dict:
    return _guard(_engine.publicar_politica, politica_id,
                  payload.get("usuario", "sistema"))


@router.post("/policies/{politica_id}/retire")
def retirar(politica_id: str, payload: dict) -> dict:
    return _guard(_engine.retirar_politica, politica_id,
                  payload.get("usuario", "sistema"))


@router.get("/policies")
def politicas() -> list[dict]:
    return _engine.politicas()


@router.post("/rules", status_code=201)
def registrar_regla(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_engine.registrar_regla, Regla(**payload), usuario)


@router.post("/rules/{regla_id}/deactivate")
def desactivar(regla_id: str, payload: dict) -> dict:
    return _guard(_engine.desactivar_regla, regla_id,
                  payload.get("usuario", "sistema"))


@router.post("/rules/{regla_id}/evaluate")
def evaluar(regla_id: str, payload: dict) -> dict:
    return _guard(_engine.evaluar_regla, regla_id, payload["contexto"])


@router.get("/rules")
def reglas() -> list[dict]:
    return _engine.reglas()


@router.post("/architecture", status_code=201)
def registrar_componente(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_engine.registrar_componente,
                  ComponenteArquitectura(**payload), usuario)


@router.get("/architecture")
def arquitectura() -> list[dict]:
    return _engine.arquitectura()


@router.get("/architecture/{componente_id}/dependencies")
def dependencias(componente_id: str) -> dict:
    return _guard(_engine.dependencias_de, componente_id)


@router.get("/registry")
def registro() -> dict:
    return _engine.registro_oficial()


@router.get("/audit")
def auditoria() -> list[dict]:
    return _engine.auditoria()
