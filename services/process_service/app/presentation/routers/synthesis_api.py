"""
Router REST del Process Twin químico (EDS Vol. II, caps. 22-24):

  POST /api/v1/synthesis/reaction      — Reaction Engine (cap. 22)
  POST /api/v1/synthesis/purification  — Purification Engine (cap. 23)
  POST /api/v1/synthesis/formulation   — Formulation Engine (caps. 21.13/24)
  POST /api/v1/synthesis/e2e           — cadena RE → PU → FE (22.17/23.17)
  GET  /api/v1/synthesis/protocols     — catálogo versionado (22.6/23.6/24.6)
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from app.application.synthesis_service import (ProtocoloNoEncontrado,
                                               SynthesisService)
from app.domain.formulation_engine import FormulacionInvalida
from app.domain.purification_engine import PurificacionInvalida
from app.domain.reaction_engine import ProtocoloInvalido
from app.presentation.schemas_synthesis import (
    FormulationIn, FormulationOut, PurificationIn, PurificationOut,
    ReactionIn, ReactionOut, SynthesisE2EIn, SynthesisProtocolSummaryOut)

router = APIRouter(prefix="/api/v1/synthesis", tags=["synthesis-twin"])

_service: SynthesisService | None = None


def init(service: SynthesisService) -> None:
    global _service
    _service = service


def _handle(exc: Exception) -> HTTPException:
    if isinstance(exc, ProtocoloNoEncontrado):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (ProtocoloInvalido, PurificacionInvalida,
                        FormulacionInvalida, ValueError)):
        # 22.22: las inconsistencias detienen la ejecución
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@router.get("/protocols", response_model=list[SynthesisProtocolSummaryOut])
def list_protocols() -> list[SynthesisProtocolSummaryOut]:
    c = _service.catalog
    out = [SynthesisProtocolSummaryOut(
        kind="reaction", protocol_id=p.protocol_id, version=p.version,
        radiopharmaceutical=p.radiopharmaceutical, validated=p.validated,
        source=p.source) for p in c.list_reaction()]
    out += [SynthesisProtocolSummaryOut(
        kind="purification", protocol_id=p.protocol_id, version=p.version,
        radiopharmaceutical=p.radiopharmaceutical, validated=p.validated,
        source=p.source) for p in c.list_purification()]
    out += [SynthesisProtocolSummaryOut(
        kind="formulation", protocol_id=p.protocol_id, version=p.version,
        radiopharmaceutical=p.radiopharmaceutical, validated=p.validated,
        source=p.source) for p in c.list_formulation()]
    return out


@router.post("/reaction", response_model=ReactionOut)
def reaction(payload: ReactionIn) -> ReactionOut:
    try:
        r = _service.reaction(payload.protocol_id, payload.eob_activity_gbq,
                              payload.incertidumbre_inicial_rel,
                              operador=payload.operador, motivo=payload.motivo,
                              lote=payload.lote, fecha_lote=payload.fecha_lote)
    except Exception as exc:
        raise _handle(exc)
    return ReactionOut(**asdict(r))


@router.post("/purification", response_model=PurificationOut)
def purification(payload: PurificationIn) -> PurificationOut:
    try:
        r = _service.purification(payload.protocol_id, payload.input_activity_gbq,
                                  payload.impurezas_iniciales,
                                  operador=payload.operador,
                                  motivo=payload.motivo, lote=payload.lote)
    except Exception as exc:
        raise _handle(exc)
    return PurificationOut(**asdict(r))


@router.post("/formulation", response_model=FormulationOut)
def formulation(payload: FormulationIn) -> FormulationOut:
    try:
        r = _service.formulation(payload.protocol_id, payload.input_activity_gbq,
                                 payload.input_volumen_ml,
                                 operador=payload.operador,
                                 motivo=payload.motivo, lote=payload.lote,
                                 fecha_lote=payload.fecha_lote)
    except Exception as exc:
        raise _handle(exc)
    return FormulationOut(**asdict(r))


@router.post("/e2e")
def synthesis_e2e(payload: SynthesisE2EIn) -> dict:
    try:
        return _service.synthesis_e2e(
            payload.reaction_id, payload.purification_id, payload.formulation_id,
            payload.eob_activity_gbq, payload.incertidumbre_inicial_rel,
            payload.volumen_crudo_ml, payload.impurezas_iniciales,
            operador=payload.operador, motivo=payload.motivo,
            lote=payload.lote, fecha_lote=payload.fecha_lote)
    except Exception as exc:
        raise _handle(exc)
