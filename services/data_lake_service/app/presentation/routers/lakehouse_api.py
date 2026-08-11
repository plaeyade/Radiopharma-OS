"""API REST del Data Lakehouse & Analytics Platform (EDS cap. 54)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain.lakehouse import LakehouseEngine, LakehouseInvalido

router = APIRouter(prefix="/api/v1/lakehouse", tags=["lakehouse"])
_engine: LakehouseEngine | None = None


def init(engine: LakehouseEngine | None = None) -> None:
    global _engine
    _engine = engine if engine is not None else LakehouseEngine()


def _eng() -> LakehouseEngine:
    assert _engine is not None
    return _engine


def _guard(fn):
    try:
        return fn()
    except LakehouseInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))


class DatasetIn(BaseModel):
    dataset_id: str
    propietario: str
    dominio: str
    esquema: list[str]
    clasificacion: str
    vigencia_desde: str
    actor: str


class VersionDatasetIn(BaseModel):
    esquema: list[str]
    clasificacion: str
    vigencia_desde: str
    actor: str


class IngestaIn(BaseModel):
    registros: list[dict[str, Any]]
    origen: str
    modo: str
    actor: str


class PoliticaIn(BaseModel):
    politica_id: str
    tipo: str
    contenido: str
    responsable: str


class CalidadIn(BaseModel):
    campo_clave: str
    evaluador: str


@router.post("/datasets")
def registrar_dataset(body: DatasetIn):
    return _guard(lambda: _eng().registrar_dataset(
        body.dataset_id, body.propietario, body.dominio, body.esquema,
        body.clasificacion, body.vigencia_desde, body.actor))


@router.get("/datasets")
def catalogo(dominio: str | None = None):
    return _eng().catalogo(dominio)


@router.post("/datasets/{dataset_id}/versions")
def publicar_version(dataset_id: str, body: VersionDatasetIn):
    return _guard(lambda: _eng().publicar_version_dataset(
        dataset_id, body.esquema, body.clasificacion, body.vigencia_desde, body.actor))


@router.post("/datasets/{dataset_id}/ingest")
def ingerir(dataset_id: str, body: IngestaIn):
    return _guard(lambda: _eng().ingerir(
        dataset_id, body.registros, body.origen, body.modo, body.actor))


@router.get("/datasets/{dataset_id}/records")
def registros(dataset_id: str):
    return _guard(lambda: _eng().registros(dataset_id))


@router.post("/datasets/{dataset_id}/quality")
def evaluar_calidad(dataset_id: str, body: CalidadIn):
    return _guard(lambda: _eng().evaluar_calidad(
        dataset_id, body.campo_clave, body.evaluador))


@router.get("/quality")
def evaluaciones(dataset_id: str | None = None):
    return _eng().evaluaciones(dataset_id)


@router.post("/policies")
def definir_politica(body: PoliticaIn):
    return _guard(lambda: _eng().definir_politica(
        body.politica_id, body.tipo, body.contenido, body.responsable))


@router.get("/policies")
def politicas(tipo: str | None = None):
    return _eng().politicas(tipo)


@router.get("/audit")
def auditoria():
    return _eng().auditoria()
