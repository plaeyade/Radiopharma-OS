"""Router REST del Cybersecurity & Zero Trust Engine (cap. 48).

  POST /api/v1/security/policies            — ZT Policy Manager 48.6
  GET  /api/v1/security/policies
  POST /api/v1/security/endpoints           — Endpoint Manager 48.10
  POST /api/v1/security/endpoints/{id}/state
  POST /api/v1/security/verify-access       — verificación 48.4/48.1
  POST /api/v1/security/events              — Security Event Mgr 48.7
  GET  /api/v1/security/events
  GET  /api/v1/security/alerts              — Threat Detection 48.8
  POST /api/v1/security/network/segments    — segmentación 48.9
  GET  /api/v1/security/network/check       — default-deny
  POST /api/v1/security/incidents           — Incident Manager 48.11
  POST /api/v1/security/incidents/{id}/actions
  GET  /api/v1/security/incidents
  GET  /api/v1/security/audit
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.domain.zero_trust import (Endpoint, PoliticaZeroTrust,
                                   SeguridadInvalida, ZeroTrustEngine)

router = APIRouter(prefix="/api/v1/security", tags=["zero-trust"])

_engine: ZeroTrustEngine | None = None


def init(engine: ZeroTrustEngine | None = None) -> None:
    global _engine
    _engine = engine or ZeroTrustEngine()


def _guard(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except SeguridadInvalida as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/policies", status_code=201)
def registrar_politica(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_engine.registrar_politica, PoliticaZeroTrust(**payload),
                  usuario)


@router.get("/policies")
def politicas() -> list[dict]:
    return _engine.politicas()


@router.post("/endpoints", status_code=201)
def registrar_endpoint(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_engine.registrar_endpoint, Endpoint(**payload), usuario)


@router.post("/endpoints/{endpoint_id}/state")
def marcar_endpoint(endpoint_id: str, payload: dict) -> dict:
    return _guard(_engine.marcar_endpoint, endpoint_id, payload["estado"],
                  payload.get("usuario", "sistema"))


@router.post("/verify-access")
def verificar(payload: dict) -> dict:
    return _engine.verificar_acceso(
        payload.get("identidad", ""), payload.get("rol", ""),
        payload["recurso"], payload.get("endpoint_id", ""),
        payload.get("usuario", "sistema"))


@router.post("/events", status_code=201)
def registrar_evento(payload: dict) -> dict:
    return _guard(_engine.registrar_evento, payload["tipo"],
                  payload["origen"], payload["destino"],
                  payload["resultado"], payload.get("usuario", "sistema"))


@router.get("/events")
def eventos(tipo: str | None = Query(None)) -> list[dict]:
    return _engine.eventos(tipo)


@router.get("/alerts")
def alertas() -> list[dict]:
    return _engine.alertas()


@router.post("/network/segments", status_code=201)
def segmento(payload: dict) -> dict:
    return _guard(_engine.definir_segmento, payload["zona"],
                  payload["permitidas"], payload.get("usuario", "sistema"))


@router.get("/network/check")
def acceso_red(origen: str = Query(...), destino: str = Query(...)
               ) -> dict:
    return _engine.acceso_red(origen, destino)


@router.post("/incidents", status_code=201)
def abrir_incidente(payload: dict) -> dict:
    return _guard(_engine.abrir_incidente, payload["incidente_id"],
                  payload["severidad"], payload["descripcion"],
                  payload.get("alerta_id"),
                  payload.get("usuario", "sistema"))


@router.post("/incidents/{incidente_id}/actions")
def accion_incidente(incidente_id: str, payload: dict) -> dict:
    return _guard(_engine.accion_incidente, incidente_id, payload["accion"],
                  payload.get("usuario", "sistema"),
                  payload.get("nuevo_estado"))


@router.get("/incidents")
def incidentes() -> list[dict]:
    return _engine.incidentes()


@router.get("/audit")
def auditoria() -> list[dict]:
    return _engine.auditoria()
