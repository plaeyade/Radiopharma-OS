"""API REST de modelado radioquímico (Informe 19.14).

Procesos post-EOB versionados (síntesis → transferencia → purificación →
formulación), cada etapa con eficiencia registrada SOLO con fuente
citada. La actividad al EOS usa la λ REAL del núclido desde la
biblioteca nuclear configurada — nunca un valor tecleado ni inventado.
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.application.production_service import ProductionService
from app.domain.radiochemistry import (EtapaRadioquimica, ProcesoInvalido,
                                       ProcesoRadioquimicoRegistry,
                                       actividad_eos)

router = APIRouter(prefix="/api/v1/radiochemistry", tags=["radiochemistry"])

_service: ProductionService | None = None
_procesos: ProcesoRadioquimicoRegistry | None = None


def init(service: ProductionService,
         procesos: ProcesoRadioquimicoRegistry) -> None:
    global _service, _procesos
    _service, _procesos = service, procesos


class EtapaIn(BaseModel):
    tipo: str
    nombre: str
    eficiencia: float
    duracion_min: float
    fuente: str


class ProcesoIn(BaseModel):
    producto: str
    nucleido: str
    etapas: list[EtapaIn]
    registrado_por: str
    motivo_version: str = "registro inicial"


class EosIn(BaseModel):
    proceso_id: str
    eob_gbq: float
    version: int | None = None


def _proceso_dict(p) -> dict:
    d = asdict(p)
    d["etapas"] = [asdict(e) for e in p.etapas]
    return d


@router.post("/processes", status_code=201)
def registrar_proceso(body: ProcesoIn):
    assert _procesos is not None
    etapas = [EtapaRadioquimica(**e.model_dump()) for e in body.etapas]
    try:
        p = _procesos.registrar(
            producto=body.producto, nucleido=body.nucleido, etapas=etapas,
            registrado_por=body.registrado_por,
            motivo_version=body.motivo_version)
        return _proceso_dict(p)
    except ProcesoInvalido as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/processes")
def listar_procesos():
    assert _procesos is not None
    return {"procesos": [_proceso_dict(p) for p in _procesos.listar()]}


@router.get("/processes/{proceso_id}")
def obtener_proceso(proceso_id: str, version: int | None = None):
    assert _procesos is not None
    try:
        return _proceso_dict(_procesos.obtener(proceso_id, version=version))
    except ProcesoInvalido as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/processes/{proceso_id}/versions")
def versiones_proceso(proceso_id: str):
    assert _procesos is not None
    try:
        return {"versiones": [_proceso_dict(p)
                              for p in _procesos.versiones(proceso_id)]}
    except ProcesoInvalido as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/eos")
def calcular_eos(body: EosIn):
    """A_EOS = A_EOB · Π(eficiencias) · exp(−λ·t_total) — 19.14."""
    assert _procesos is not None and _service is not None
    try:
        p = _procesos.obtener(body.proceso_id, version=body.version)
    except ProcesoInvalido as exc:
        raise HTTPException(404, str(exc)) from exc
    lam = _service.decay_constant_s(p.nucleido)   # λ real de la biblioteca
    try:
        resultado = actividad_eos(p, body.eob_gbq, lam)
    except ProcesoInvalido as exc:
        raise HTTPException(422, str(exc)) from exc
    resultado["lambda_s"] = lam
    resultado["fuente_lambda"] = "biblioteca nuclear configurada (real)"
    return resultado
