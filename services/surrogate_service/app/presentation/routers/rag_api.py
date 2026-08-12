"""Router REST del Enterprise RAG & Scientific Knowledge Engine
(cap. 45).

  POST /api/v1/rag/documents            — Document Registry 45.6
  POST /api/v1/rag/documents/parse      — Document Parser 45.7
  POST /api/v1/rag/documents/{id}/obsolete
  GET  /api/v1/rag/documents
  POST /api/v1/rag/retrieve             — Retrieval Engine 45.10
  POST /api/v1/rag/citations            — Citation Manager 45.11
  GET  /api/v1/rag/citations
  GET  /api/v1/rag/index-status         — estado honesto 45.8
  GET  /api/v1/rag/audit
"""
from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException

from app.domain.rag_engine import Documento, RagEngine, RagInvalido

router = APIRouter(prefix="/api/v1/rag", tags=["enterprise-rag"])

_engine: RagEngine | None = None


def init(engine: RagEngine | None = None) -> None:
    global _engine
    _engine = engine or RagEngine()


def _guard(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except RagInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/documents/parse", status_code=201)
def parsear(payload: dict) -> dict:
    """Body: {"nombre_archivo": ..., "contenido_b64": ...}."""
    contenido = base64.b64decode(payload["contenido_b64"])
    return _guard(_engine.parsear, payload["nombre_archivo"], contenido)


@router.post("/documents", status_code=201)
def registrar(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_engine.registrar_documento, Documento(**payload),
                  usuario)


@router.post("/documents/{documento_id}/obsolete")
def obsoleto(documento_id: str, payload: dict) -> dict:
    return _guard(_engine.marcar_obsoleto, documento_id,
                  payload.get("usuario", "sistema"))


@router.get("/documents")
def documentos() -> list[dict]:
    return _engine.documentos()


@router.post("/retrieve")
def recuperar(payload: dict) -> dict:
    return _guard(_engine.recuperar, payload["consulta"],
                  int(payload.get("k", 5)), payload.get("filtros"),
                  payload.get("usuario", "sistema"))


@router.post("/citations", status_code=201)
def citar(payload: dict) -> dict:
    return _guard(_engine.registrar_cita, payload["respuesta_id"],
                  payload["documentos"], payload.get("usuario", "sistema"))


@router.get("/extractor-status")
def estado_extractor():
    """Estado real del extractor documental (45.7): pypdf, Tesseract
    (idiomas instalados), poppler."""
    from app.domain.document_extractor import estado_extractor as _est
    return _est()


@router.get("/citations")
def citas() -> list[dict]:
    return _engine.citas()


@router.get("/index-status")
def estado() -> dict:
    return _engine.estado_indice()


@router.get("/audit")
def auditoria() -> list[dict]:
    return _engine.auditoria()
