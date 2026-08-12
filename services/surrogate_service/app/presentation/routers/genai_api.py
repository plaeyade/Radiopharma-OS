"""API REST de los conectores GenAI — embeddings (45.8/45.9) y LLM (45.20)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...domain.genai_connector import (
    GENAI_VERSION,
    GenAiConnector,
    GenAiInvalido,
    SinProveedor,
)

router = APIRouter(prefix="/api/v1/genai", tags=["genai-connectors"])

_connector: GenAiConnector | None = None


def init(connector: GenAiConnector | None = None, **kwargs) -> None:
    global _connector
    _connector = connector or GenAiConnector(**kwargs)


def _con() -> GenAiConnector:
    if _connector is None:
        init()
    return _connector  # type: ignore[return-value]


def _guard(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except SinProveedor as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except GenAiInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))


class ProveedorIn(BaseModel):
    proveedor_id: str
    tipo: str
    endpoint: str
    modelo: str
    responsable: str


class EmbeddingIn(BaseModel):
    texto: str
    actor: str = "sistema"


class IndiceIn(BaseModel):
    actor: str


class BusquedaIn(BaseModel):
    consulta: str
    k: int = 5
    actor: str = "sistema"


class RespuestaIn(BaseModel):
    consulta: str
    documentos: list[str]
    usuario: str


@router.post("/providers", status_code=201)
def registrar_proveedor(body: ProveedorIn):
    p = _guard(_con().registrar_proveedor, body.proveedor_id, body.tipo,
               body.endpoint, body.modelo, body.responsable)
    return {"proveedor_id": p.proveedor_id, "version": p.version}


@router.get("/providers")
def proveedores():
    return _con().proveedores()


@router.get("/providers/{proveedor_id}/history")
def historial(proveedor_id: str):
    return _con().historial_proveedor(proveedor_id)


@router.post("/providers/{proveedor_id}/probe")
def sondear(proveedor_id: str, actor: str = "sistema"):
    return _guard(_con().sondear, proveedor_id, actor)


@router.post("/providers/{proveedor_id}/embed", status_code=201)
def generar_embedding(proveedor_id: str, body: EmbeddingIn):
    return _guard(_con().generar_embedding, proveedor_id, body.texto,
                  body.actor)


@router.post("/providers/{proveedor_id}/semantic-index", status_code=201)
def construir_indice(proveedor_id: str, body: IndiceIn):
    return _guard(_con().construir_indice_semantico, proveedor_id,
                  body.actor)


@router.post("/providers/{proveedor_id}/semantic-search")
def buscar_semantico(proveedor_id: str, body: BusquedaIn):
    return _guard(_con().buscar_semantico, proveedor_id, body.consulta,
                  body.k, body.actor)


@router.post("/providers/{proveedor_id}/rag-answer", status_code=201)
def respuesta_rag(proveedor_id: str, body: RespuestaIn):
    return _guard(_con().generar_respuesta_rag, proveedor_id,
                  body.consulta, body.documentos, body.usuario)


@router.get("/status")
def estado():
    return _con().estado()


@router.get("/audit")
def auditoria():
    return _con().auditoria()


@router.get("/meta")
def meta():
    return {"version_motor": GENAI_VERSION,
            "tipos_proveedor": ["embeddings", "llm"],
            "nota": ("embeddings neuronales (45.8/45.9) y generación RAG "
                     "con LLM real (45.20); sin conexión → 503 honesto.")}
