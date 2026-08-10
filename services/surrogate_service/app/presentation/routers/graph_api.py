"""Router REST del Knowledge Graph & Semantic Intelligence Engine
(cap. 44).

  POST /api/v1/graph/ontology              — Ontology Manager 44.6
  GET  /api/v1/graph/ontology
  POST /api/v1/graph/entities              — Entity Registry 44.7
  GET  /api/v1/graph/entities
  POST /api/v1/graph/relationships         — Relationship Manager 44.8
  GET  /api/v1/graph/relationships
  GET  /api/v1/graph/query/{entidad_id}    — Semantic Query 44.9
  GET  /api/v1/graph/path                  — camino multi-dominio (BFS)
  GET  /api/v1/graph/reason/{entidad_id}   — Reasoning 44.10 documentado
  GET  /api/v1/graph/inferences
  POST /api/v1/graph/sync                  — Knowledge Synchronizer 44.11
  GET  /api/v1/graph/audit                 — auditoría 44.21
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.domain.knowledge_graph import (Entidad, GrafoInvalido,
                                        KnowledgeGraph, Relacion)

router = APIRouter(prefix="/api/v1/graph", tags=["knowledge-graph"])

_graph: KnowledgeGraph | None = None


def init(graph: KnowledgeGraph | None = None) -> None:
    global _graph
    _graph = graph or KnowledgeGraph()


def _guard(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except GrafoInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/ontology", status_code=201)
def registrar_tipo(payload: dict) -> dict:
    return _guard(_graph.registrar_tipo, payload["nombre"],
                  payload["version"], payload["definicion"],
                  payload.get("usuario", "sistema"))


@router.get("/ontology")
def ontologia() -> dict:
    return _graph.ontologia()


@router.post("/entities", status_code=201)
def registrar_entidad(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_graph.registrar_entidad, Entidad(**payload), usuario)


@router.get("/entities")
def entidades(tipo: str | None = Query(None)) -> list[dict]:
    return _graph.entidades(tipo)


@router.post("/relationships", status_code=201)
def registrar_relacion(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_graph.registrar_relacion, Relacion(
        origen_id=payload["origen"], tipo=payload["tipo"],
        destino_id=payload["destino"],
        evidencia=payload.get("evidencia", "")), usuario)


@router.get("/relationships")
def relaciones(entidad_id: str | None = Query(None)) -> list[dict]:
    return _graph.relaciones(entidad_id)


@router.get("/query/{entidad_id}")
def consultar(entidad_id: str, tipo_relacion: str | None = Query(None),
              direccion: str = Query("saliente")) -> list[dict]:
    return _guard(_graph.consultar, entidad_id, tipo_relacion, direccion)


@router.get("/path")
def camino(origen: str = Query(...), destino: str = Query(...),
           max_saltos: int = Query(6, ge=1, le=20)) -> dict:
    return _guard(_graph.camino, origen, destino, max_saltos)


@router.get("/reason/{entidad_id}")
def razonar(entidad_id: str) -> dict:
    return _guard(_graph.inferir_jerarquia, entidad_id)


@router.get("/inferences")
def inferencias() -> list[dict]:
    return _graph.inferencias()


@router.post("/sync", status_code=201)
def sincronizar(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_graph.sincronizar, payload, usuario)


@router.get("/audit")
def auditoria() -> list[dict]:
    return _graph.auditoria()
