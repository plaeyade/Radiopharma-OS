"""API REST del Qualification Engine (Informe 14.9)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...domain import qualification
from ...domain.qualification import (
    CalificacionInvalida,
    QualificationEngine,
)

router = APIRouter(prefix="/api/v1/qualification", tags=["qualification"])

_engine: QualificationEngine | None = None


def init(engine: QualificationEngine | None = None) -> None:
    global _engine
    _engine = engine or QualificationEngine()


def _eng() -> QualificationEngine:
    if _engine is None:
        init()
    return _engine  # type: ignore[return-value]


def _guard(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except CalificacionInvalida as exc:
        raise HTTPException(status_code=422, detail=str(exc))


class ComponenteIn(BaseModel):
    componente_id: str
    nombre: str
    tipo: str
    version: str
    responsable: str


class ProtocoloIn(BaseModel):
    etapa: str
    criterios: list[str] = Field(min_length=1)
    responsable: str
    motivo: str


class ResultadoIn(BaseModel):
    criterio: str
    cumple: bool
    detalle: str = ""
    evidencia_ref: str = ""


class EjecucionIn(BaseModel):
    etapa: str
    entorno: str
    ejecutor: str
    resultados: list[ResultadoIn]


@router.post("/components", status_code=201)
def registrar_componente(body: ComponenteIn):
    comp = _guard(_eng().registrar_componente, body.componente_id,
                  body.nombre, body.tipo, body.version, body.responsable)
    return {"componente_id": comp.componente_id,
            "registrado_en": comp.registrado_en}


@router.get("/components")
def listar_componentes():
    return [{"componente_id": c.componente_id, "nombre": c.nombre,
             "tipo": c.tipo, "version": c.version,
             "responsable": c.responsable}
            for c in _eng().componentes()]


@router.post("/components/{componente_id}/protocols", status_code=201)
def definir_protocolo(componente_id: str, body: ProtocoloIn):
    proto = _guard(_eng().definir_protocolo, componente_id, body.etapa,
                   body.criterios, body.responsable, body.motivo)
    return {"componente_id": proto.componente_id, "etapa": proto.etapa,
            "version": proto.version, "criterios": proto.criterios}


@router.get("/components/{componente_id}/protocols/{etapa}")
def historial_protocolo(componente_id: str, etapa: str):
    historial = _eng().historial_protocolo(componente_id, etapa.upper())
    return [{"version": p.version, "criterios": p.criterios,
             "responsable": p.responsable, "motivo": p.motivo,
             "definido_en": p.definido_en} for p in historial]


@router.post("/components/{componente_id}/executions", status_code=201)
def ejecutar_etapa(componente_id: str, body: EjecucionIn):
    ejec = _guard(_eng().ejecutar_etapa, componente_id, body.etapa.upper(),
                  body.entorno, body.ejecutor,
                  [r.model_dump() for r in body.resultados])
    return {"ejecucion_id": ejec.ejecucion_id, "etapa": ejec.etapa,
            "entorno": ejec.entorno, "estado": ejec.estado,
            "protocolo_version": ejec.protocolo_version,
            "resultados": [{"criterio": r.criterio, "cumple": r.cumple,
                            "detalle": r.detalle,
                            "evidencia_ref": r.evidencia_ref}
                           for r in ejec.resultados]}


@router.get("/components/{componente_id}/status")
def estado_calificacion(componente_id: str):
    return _guard(_eng().estado_calificacion, componente_id)


@router.get("/components/{componente_id}/dossier")
def expediente(componente_id: str):
    return _guard(_eng().expediente, componente_id)


@router.get("/audit")
def auditoria():
    return _eng().auditoria()


@router.get("/meta")
def meta():
    return {"version_motor": qualification.QUALIFICATION_VERSION,
            "etapas": list(qualification.ETAPAS),
            "entornos": list(qualification.ENTORNOS),
            "nota": ("PQ exige entorno 'condiciones_reales' (Informe "
                     "14.9); en entorno simulado la etapa queda "
                     "honestamente no superada.")}
