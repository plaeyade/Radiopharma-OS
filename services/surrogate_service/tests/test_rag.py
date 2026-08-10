"""Tests del Enterprise RAG & Scientific Knowledge Engine (cap. 45).

Verifica: Document Registry único 45.6, parser 45.7 con sha256 del
original y formatos honestamente pendientes, índice léxico TF-IDF
real versionado 45.8/45.9 — marcado honestamente como NO neuronal —,
recuperación por similitud coseno real con filtros y fuentes 45.10,
Citation Manager 45.11 y auditoría.
"""
import base64

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.presentation.routers import rag_api

DOC_QC = {"documento_id": "sop-qc-001", "titulo": "Pureza radioquímica FDG",
          "tipo": "procedimiento",
          "contenido_texto": "La pureza radioquímica del FDG se determina "
                             "por cromatografía HPLC. El criterio de "
                             "aceptación es pureza mayor o igual a 95%.",
          "version": "3.2", "autor": "dir-qc", "origen": "gd:sop/qc/001"}
DOC_PROD = {"documento_id": "man-cyclo-01", "titulo": "Irradiación H2-18O",
            "tipo": "manual",
            "contenido_texto": "El ciclotrón irradia el blanco de agua "
                               "enriquecida con protones de 16.5 MeV y "
                               "corriente de haz de 60 µA.",
            "version": "1.4", "origen": "gd:man/cyclo/01"}


@pytest.fixture()
def client() -> TestClient:
    rag_api.init()
    c = TestClient(app)
    for doc in (DOC_QC, DOC_PROD):
        assert c.post("/api/v1/rag/documents",
                      json={**doc, "usuario": "biblio-1"}
                      ).status_code == 201
    return c


def test_registry_unico_y_gestion_documental(client: TestClient) -> None:
    assert client.post("/api/v1/rag/documents",
                       json=DOC_QC).status_code == 422
    docs = client.get("/api/v1/rag/documents").json()
    assert docs[0]["version"] == "3.2" and docs[0]["estado"] == "vigente"
    client.post("/api/v1/rag/documents/sop-qc-001/obsolete", json={})
    docs2 = client.get("/api/v1/rag/documents").json()
    assert next(d for d in docs2
                if d["documento_id"] == "sop-qc-001")[
                    "estado"] == "obsoleto"


def test_parser_sha256_y_formatos_honestos(client: TestClient) -> None:
    html = base64.b64encode(
        b"<html><body><h1>Protocolo</h1><p>irradiacion de blanco</p>"
        b"</body></html>").decode()
    r = client.post("/api/v1/rag/documents/parse", json={
        "nombre_archivo": "protocolo.html", "contenido_b64": html})
    assert r.status_code == 201
    assert "<h1>" not in r.json()["texto"]
    assert len(r.json()["sha256_original"]) == 64
    # PDF: honestamente pendiente de runtime, nunca parseo ficticio
    r2 = client.post("/api/v1/rag/documents/parse", json={
        "nombre_archivo": "paper.pdf",
        "contenido_b64": base64.b64encode(b"%PDF-1.4 fake").decode()})
    assert r2.status_code == 422
    assert "pendientes" in r2.json()["detail"]


def test_recuperacion_coseno_real(client: TestClient) -> None:
    r = client.post("/api/v1/rag/retrieve", json={
        "consulta": "¿cuál es el criterio de pureza del FDG por HPLC?",
        "usuario": "ag-qc-1"})
    assert r.status_code == 200
    res = r.json()
    assert res["n_resultados"] >= 1
    top = res["resultados"][0]
    assert top["documento_id"] == "sop-qc-001"
    assert 0 < top["score"] <= 1.0
    assert top["fuente_original"] == "gd:sop/qc/001"    # 45.10
    # consulta sin relación léxica: honestamente sin resultados
    r2 = client.post("/api/v1/rag/retrieve", json={
        "consulta": "xyzzy qwvth kplmno"})
    assert r2.json()["n_resultados"] == 0


def test_recuperacion_con_filtros(client: TestClient) -> None:
    r = client.post("/api/v1/rag/retrieve", json={
        "consulta": "blanco protones haz",
        "filtros": {"tipo": "manual"}})
    docs = {x["documento_id"] for x in r.json()["resultados"]}
    assert docs <= {"man-cyclo-01"}
    # obsoletos excluidos de la recuperación
    client.post("/api/v1/rag/documents/sop-qc-001/obsolete", json={})
    r2 = client.post("/api/v1/rag/retrieve", json={
        "consulta": "pureza HPLC criterio aceptación"})
    assert all(x["documento_id"] != "sop-qc-001"
               for x in r2.json()["resultados"])


def test_indice_honesto_no_neuronal(client: TestClient) -> None:
    est = client.get("/api/v1/rag/index-status").json()
    assert est["embedding_neuronal"] is False
    assert est["indice_version"] == "lexical-tfidf-1.0.0"
    assert est["n_documentos"] == 2
    assert "honestamente pendiente" in est["nota"]


def test_citas_trazables(client: TestClient) -> None:
    r = client.post("/api/v1/rag/citations", json={
        "respuesta_id": "resp-conv-0007",
        "documentos": ["sop-qc-001"], "usuario": "ag-qc-1"})
    assert r.status_code == 201
    cita = r.json()
    assert cita["documentos"][0]["version"] == "3.2"
    assert cita["documentos"][0]["fuente_original"] == "gd:sop/qc/001"
    assert cita["indice_version"]
    assert client.post("/api/v1/rag/citations", json={
        "respuesta_id": "resp-conv-0007",
        "documentos": ["man-cyclo-01"]}).status_code == 422
    assert client.post("/api/v1/rag/citations", json={
        "respuesta_id": "resp-x",
        "documentos": ["doc-fantasma"]}).status_code == 422


def test_auditoria_rag(client: TestClient) -> None:
    client.post("/api/v1/rag/retrieve", json={"consulta": "FDG pureza"})
    aud = client.get("/api/v1/rag/audit").json()
    acciones = {a["accion"] for a in aud}
    assert {"registrar_documento", "recuperar"} <= acciones
    assert all(a["fecha"] for a in aud)
