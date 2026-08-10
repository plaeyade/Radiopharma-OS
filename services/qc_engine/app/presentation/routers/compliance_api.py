"""Router REST del Regulatory Compliance & Audit Engine (cap. 49).

  POST /api/v1/compliance/requirements             — Requirement Reg. 49.6
  GET  /api/v1/compliance/requirements
  POST /api/v1/compliance/evidences                — Evidence Manager 49.8
  POST /api/v1/compliance/requirements/{id}/link   — vínculo 49.13
  GET  /api/v1/compliance/evidences
  POST /api/v1/compliance/requirements/{id}/assess — evaluación 49.7/49.18
  GET  /api/v1/compliance/dashboard                — tablero real 49.7
  POST /api/v1/compliance/audits                   — Audit Manager 49.9
  POST /api/v1/compliance/audits/{id}/findings
  POST /api/v1/compliance/audits/{id}/close
  GET  /api/v1/compliance/audits/{id}
  POST /api/v1/compliance/capas                    — CAPA Manager 49.10
  POST /api/v1/compliance/capas/{id}/follow
  GET  /api/v1/compliance/capas
  GET  /api/v1/compliance/inspection               — preparación 49.11
  GET  /api/v1/compliance/audit-trail              — auditoría 49.20
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.domain.compliance import (ComplianceEngine, CumplimientoInvalido,
                                   Evidencia, Requisito)

router = APIRouter(prefix="/api/v1/compliance", tags=["regulatory-compliance"])

_engine: ComplianceEngine | None = None


def init(engine: ComplianceEngine | None = None) -> None:
    global _engine
    _engine = engine or ComplianceEngine()


def _guard(fn, *args):
    try:
        return fn(*args)
    except CumplimientoInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/requirements", status_code=201)
def registrar_requisito(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_engine.registrar_requisito, Requisito(**payload), usuario)


@router.get("/requirements")
def requisitos() -> list[dict]:
    return _engine.requisitos()


@router.post("/evidences", status_code=201)
def registrar_evidencia(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_engine.registrar_evidencia, Evidencia(**payload), usuario)


@router.get("/evidences")
def evidencias(requisito_id: str | None = Query(None)) -> list[dict]:
    return _engine.evidencias(requisito_id)


@router.post("/requirements/{requisito_id}/link", status_code=201)
def vincular(requisito_id: str, payload: dict) -> dict:
    return _guard(_engine.vincular_evidencia, requisito_id,
                  payload["evidencia_id"], payload.get("usuario", "sistema"))


@router.post("/requirements/{requisito_id}/assess")
def evaluar(requisito_id: str, payload: dict) -> dict:
    return _guard(_engine.evaluar, requisito_id, payload["estado"],
                  payload["responsable"], payload.get("usuario", "sistema"),
                  payload.get("nota", ""))


@router.get("/dashboard")
def tablero() -> dict:
    return _engine.tablero_cumplimiento()


@router.post("/audits", status_code=201)
def abrir_auditoria(payload: dict) -> dict:
    return _guard(_engine.abrir_auditoria, payload["auditoria_id"],
                  payload["tipo"], payload["alcance"], payload["auditor"],
                  payload.get("usuario", "sistema"))


@router.post("/audits/{auditoria_id}/findings", status_code=201)
def hallazgo(auditoria_id: str, payload: dict) -> dict:
    return _guard(_engine.registrar_hallazgo, auditoria_id,
                  payload["hallazgo_id"], payload["severidad"],
                  payload["descripcion"], payload["requisito_id"],
                  payload.get("usuario", "sistema"))


@router.post("/audits/{auditoria_id}/close")
def cerrar_auditoria(auditoria_id: str, payload: dict) -> dict:
    return _guard(_engine.cerrar_auditoria, auditoria_id,
                  payload.get("usuario", "sistema"))


@router.get("/audits/{auditoria_id}")
def expediente(auditoria_id: str) -> dict:
    return _guard(_engine.auditoria_expediente, auditoria_id)


@router.post("/capas", status_code=201)
def abrir_capa(payload: dict) -> dict:
    return _guard(_engine.abrir_capa, payload["capa_id"],
                  payload["auditoria_id"], payload["hallazgo_id"],
                  payload["tipo"], payload["descripcion"],
                  payload["responsable"], payload["fecha_objetivo"],
                  payload.get("usuario", "sistema"))


@router.post("/capas/{capa_id}/follow")
def seguir_capa(capa_id: str, payload: dict) -> dict:
    return _guard(_engine.seguir_capa, capa_id, payload["nota"],
                  payload.get("usuario", "sistema"),
                  payload.get("nuevo_estado"))


@router.get("/capas")
def capas() -> list[dict]:
    return _engine.capas()


@router.get("/inspection")
def inspeccion() -> dict:
    return _engine.preparar_inspeccion("sistema")


@router.get("/audit-trail")
def audit_trail() -> list[dict]:
    return _engine.audit_trail()
