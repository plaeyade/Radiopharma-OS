"""API REST del Enterprise Intelligence & AI Twin Core (EDS cap. 41)."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain.ei_core import EiCoreEngine, EiInvalido, SinRuntime
from app.presentation.routers import mlops_api

router = APIRouter(prefix="/api/v1/ei", tags=["enterprise-intelligence"])
_engine: EiCoreEngine | None = None


def _verificador_mlops(modelo_id: str, version: str) -> dict[str, Any] | None:
    """Consulta el Model Registry del cap. 42 (mismo proceso, 41.11)."""
    engine = getattr(mlops_api, "_engine", None)
    if engine is None:
        return None
    m = engine._modelos.get(modelo_id)
    if m is None or str(m["version"]) != str(version):
        return None
    return {"estado": m["estado"], "experimento_id": m["experimento_id"]}


def init(engine: EiCoreEngine | None = None) -> None:
    global _engine
    _engine = engine if engine is not None else EiCoreEngine(
        verificador_modelo=_verificador_mlops)


def _eng() -> EiCoreEngine:
    assert _engine is not None
    return _engine


def _guard(fn):
    try:
        return fn()
    except SinRuntime as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except EiInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))


class FeatureIn(BaseModel):
    feature_id: str
    twin_origen: str
    descripcion: str
    unidad: str = ""
    actor: str


class ValorIn(BaseModel):
    valor: float
    timestamp_dato: str
    fuente: str
    actor: str
    version_feature: int | None = None


class RuntimeIn(BaseModel):
    modelo_id: str
    version_modelo: str
    actor: str
    expresion: str  # expresión aritmética sobre las claves de `datos` (runtime declarativo)


class InferenciaIn(BaseModel):
    modelo_id: str
    version_modelo: str
    datos: dict[str, Any]
    usuario: str


class RecomendacionIn(BaseModel):
    area: str
    titulo: str
    detalle: str
    soporte: dict[str, Any]
    generada_por: str


class ResolucionIn(BaseModel):
    decision: str
    usuario: str
    motivo: str


_OPS = {"+", "-", "*", "/", "(", ")", ".", " "}


def _runtime_declarativo(expresion: str) -> Callable[[dict[str, Any]], Any]:
    """Runtime declarativo mínimo: evalúa una expresión aritmética real sobre
    las claves de `datos` (sin builtins). No es un modelo ML — es un runtime
    de cálculo declarado; sin él, la inferencia responde 503 honesto."""
    def _run(datos: dict[str, Any]) -> Any:
        entorno = {k: v for k, v in datos.items() if isinstance(v, (int, float))}
        return eval(expresion, {"__builtins__": {}}, entorno)  # noqa: S307 - entorno cerrado
    return _run


@router.post("/features")
def registrar_feature(body: FeatureIn):
    return _guard(lambda: _eng().registrar_feature(
        body.feature_id, body.twin_origen, body.descripcion, body.unidad, body.actor))


@router.get("/features")
def listar_features():
    return _guard(lambda: _eng().listar_features())


@router.get("/features/{feature_id}")
def obtener_feature(feature_id: str, version: int | None = None):
    return _guard(lambda: _eng().feature(feature_id, version))


@router.post("/features/{feature_id}/valores")
def registrar_valor(feature_id: str, body: ValorIn):
    return _guard(lambda: _eng().registrar_valor(
        feature_id, body.valor, body.timestamp_dato, body.fuente, body.actor,
        body.version_feature))


@router.get("/features/{feature_id}/valores")
def valores_feature(feature_id: str):
    return _guard(lambda: _eng().valores_feature(feature_id))


@router.post("/inference/runtimes")
def registrar_runtime(body: RuntimeIn):
    if not body.expresion or any(c not in _OPS and not (c.isalnum() or c == "_")
                                 for c in body.expresion):
        raise HTTPException(status_code=422, detail="expresion inválida")
    runtime = _runtime_declarativo(body.expresion)
    return _guard(lambda: _eng().registrar_runtime(
        body.modelo_id, body.version_modelo, runtime, body.actor))


@router.post("/inference/execute")
def ejecutar_inferencia(body: InferenciaIn):
    return _guard(lambda: _eng().ejecutar_inferencia(
        body.modelo_id, body.version_modelo, body.datos, body.usuario))


@router.get("/inference/history")
def historial_inferencias(modelo_id: str | None = None):
    return _guard(lambda: _eng().historial_inferencias(modelo_id))


@router.post("/recommendations")
def generar_recomendacion(body: RecomendacionIn):
    return _guard(lambda: _eng().generar_recomendacion(
        body.area, body.titulo, body.detalle, body.soporte, body.generada_por))


@router.get("/recommendations")
def listar_recomendaciones(area: str | None = None):
    return _guard(lambda: _eng().recomendaciones(area))


@router.post("/recommendations/{recomendacion_id}/resolver")
def resolver_recomendacion(recomendacion_id: str, body: ResolucionIn):
    return _guard(lambda: _eng().resolver_recomendacion(
        recomendacion_id, body.decision, body.usuario, body.motivo))


@router.get("/audit")
def auditoria():
    return _eng().auditoria()
