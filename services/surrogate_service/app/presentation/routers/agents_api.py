"""Router REST del Multi-Agent Decision Support Engine (cap. 43).

  POST /api/v1/agents/register             — Agent Registry 43.6
  GET  /api/v1/agents
  POST /api/v1/agents/consult              — Orchestrator + Consenso 43.8/9
  GET  /api/v1/agents/conversations        — Conversation Manager 43.11
  GET  /api/v1/agents/conversations/{id}
  GET  /api/v1/agents/audit                — trazabilidad de inferencias

Toda salida es RECOMENDACIÓN de soporte a la decisión (43.3/41.9):
el motor nunca decide. Los agentes sin runtime quedan honestamente
omitidos — nunca se inventa su contribución.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.domain.agents import (Agente, AgentesInvalido, MultiAgentEngine)

router = APIRouter(prefix="/api/v1/agents", tags=["multi-agent-decision"])

_engine: MultiAgentEngine | None = None


def init(engine: MultiAgentEngine | None = None) -> None:
    global _engine
    _engine = engine or MultiAgentEngine()


def _guard(fn, *args):
    try:
        return fn(*args)
    except AgentesInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/register", status_code=201)
def registrar(payload: dict) -> dict:
    """Alta declarativa. Las contribuciones ejecutables se registran
    desde código (callable); vía API el agente queda `sin_runtime`
    hasta que su contribución esté disponible — honesto."""
    usuario = payload.pop("usuario", "sistema")
    return _guard(_engine.registrar_agente, Agente(**payload), None,
                  usuario)


@router.get("")
def agentes() -> list[dict]:
    return _engine.agentes()


@router.post("/consult", status_code=201)
def consultar(payload: dict) -> dict:
    return _guard(_engine.consultar, payload["problema"],
                  payload["dominios"], payload.get("contexto", {}),
                  payload.get("usuario", "sistema"))


@router.get("/conversations")
def conversaciones() -> list[dict]:
    return _engine.conversaciones()


@router.get("/conversations/{conversacion_id}")
def conversacion(conversacion_id: str) -> dict:
    try:
        return _engine.conversacion(conversacion_id)
    except AgentesInvalido as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/audit")
def auditoria() -> list[dict]:
    return _engine.auditoria()
