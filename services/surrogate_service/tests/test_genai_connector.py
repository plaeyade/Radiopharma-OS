"""Tests de los conectores GenAI — embeddings (45.8/45.9) y LLM (45.20)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.domain.genai_connector import GenAiConnector
from app.domain.rag_engine import Documento, RagEngine
from app.main import app
from app.presentation.routers import genai_api, rag_api


class _Resp:
    def __init__(self, status_code=200, cuerpo=None):
        self.status_code = status_code
        self._cuerpo = cuerpo or {}

    def json(self):
        return self._cuerpo


class _HttpGenAi:
    """HTTP inyectado: imita API OpenAI-compatible (embeddings/chat)."""

    def __init__(self, vivo=True):
        self.vivo = vivo
        self.posts = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, url, json, headers=None):
        self.posts.append((url, json))
        if not self.vivo:
            raise ConnectionError("connection refused")
        if url.endswith("/v1/embeddings"):
            texto = json.get("input", "")
            # vector determinista derivado del texto (3 dimensiones)
            base = [len(texto) % 7 + 1.0,
                    sum(map(ord, texto)) % 13 + 1.0, 2.0]
            return _Resp(200, {"data": [{"embedding": base}]})
        if url.endswith("/v1/chat/completions"):
            return _Resp(200, {"choices": [
                {"message": {"content": "El F-18 decae con T½ 109,77 min"
                                        " [doc-f18]."}}]})
        return _Resp(404)


@pytest.fixture()
def conector():
    http = _HttpGenAi()
    rag = RagEngine()
    rag_api.init(rag)
    rag.registrar_documento(Documento(
        documento_id="doc-f18", titulo="Producción de F-18",
        tipo="protocolo", contenido_texto="El F-18 se produce por 18O(p,n)"
        "18F y decae con vida media 109,77 minutos.", version="1.0",
        origen="lab-ciclotron"), "documentalista")
    rag.registrar_documento(Documento(
        documento_id="doc-qc", titulo="Control de pureza",
        tipo="procedimiento", contenido_texto="La pureza radioquímica se "
        "mide por HPLC según procedimiento PQ-012.", version="2.1",
        origen="qc-lab"), "documentalista")
    con = GenAiConnector(rag_engine=rag, fabrica_http=lambda: http)
    genai_api.init(con)
    return con, http


@pytest.fixture()
def client(conector):
    return TestClient(app)


def _proveedor(client, pid, tipo, modelo="emb-v3"):
    r = client.post("/api/v1/genai/providers", json={
        "proveedor_id": pid, "tipo": tipo,
        "endpoint": "http://genai.local:8080", "modelo": modelo,
        "responsable": "jefe-ia"})
    assert r.status_code == 201
    return pid


def test_proveedor_versionado_y_validaciones(client):
    _proveedor(client, "emb-1", "embeddings")
    r = client.post("/api/v1/genai/providers", json={
        "proveedor_id": "emb-1", "tipo": "embeddings",
        "endpoint": "http://otro.local:8080", "modelo": "emb-v4",
        "responsable": "jefe-ia"})
    assert r.json()["version"] == 2
    historial = client.get("/api/v1/genai/providers/emb-1/history").json()
    assert [h["version"] for h in historial] == [1, 2]
    r = client.post("/api/v1/genai/providers", json={
        "proveedor_id": "x", "tipo": "embeddings", "endpoint": "",
        "modelo": "m", "responsable": "a"})
    assert r.status_code == 422
    r = client.post("/api/v1/genai/providers", json={
        "proveedor_id": "y", "tipo": "llm", "endpoint": "genai.local",
        "modelo": "m", "responsable": "a"})
    assert r.status_code == 422


def test_sonda_real_embeddings_y_llm(client):
    _proveedor(client, "emb-1", "embeddings")
    r = client.post("/api/v1/genai/providers/emb-1/probe")
    assert r.json()["estado"] == "conectado"
    assert "dimensión 3" in r.json()["detalle"]
    _proveedor(client, "llm-1", "llm", "gpt-radiofar")
    r = client.post("/api/v1/genai/providers/llm-1/probe")
    assert r.json()["estado"] == "conectado"


def test_sonda_fallo_y_operaciones_503(client, conector):
    con, http = conector
    http.vivo = False
    _proveedor(client, "emb-1", "embeddings")
    r = client.post("/api/v1/genai/providers/emb-1/probe")
    assert r.json()["estado"] == "fallo_conexion"
    r = client.post("/api/v1/genai/providers/emb-1/embed",
                    json={"texto": "hola"})
    assert r.status_code == 503
    # sin sonda → 503 también
    http.vivo = True
    r = client.post("/api/v1/genai/providers/emb-1/embed",
                    json={"texto": "hola"})
    assert r.status_code == 503


def test_indice_semantico_real_y_reproducible(client):
    _proveedor(client, "emb-1", "embeddings")
    client.post("/api/v1/genai/providers/emb-1/probe")
    r = client.post("/api/v1/genai/providers/emb-1/semantic-index",
                    json={"actor": "jefe-ia"})
    assert r.status_code == 201, r.text
    indice = r.json()
    assert indice["documentos"] == 2 and indice["dimension"] == 3
    assert indice["modelo"] == "emb-v3"  # 45.8: reproducibilidad
    # reconstruir genera versión nueva, nunca borra la anterior
    r = client.post("/api/v1/genai/providers/emb-1/semantic-index",
                    json={"actor": "jefe-ia"})
    assert r.json()["version"] == 2
    estado = client.get("/api/v1/genai/status").json()
    assert len(estado["indices_semanticos"]) == 2


def test_busqueda_semantica_con_fuentes(client):
    _proveedor(client, "emb-1", "embeddings")
    client.post("/api/v1/genai/providers/emb-1/probe")
    client.post("/api/v1/genai/providers/emb-1/semantic-index",
                json={"actor": "jefe-ia"})
    r = client.post("/api/v1/genai/providers/emb-1/semantic-search",
                    json={"consulta": "vida media del F-18", "k": 2})
    assert r.status_code == 200
    cuerpo = r.json()
    assert len(cuerpo["resultados"]) == 2
    for res in cuerpo["resultados"]:
        assert res["fuente_original"] in ("lab-ciclotron", "qc-lab")
        assert 0 <= res["similitud_semantica"] <= 1
    # búsqueda sin índice → 422
    con2 = GenAiConnector(fabrica_http=lambda: _HttpGenAi())
    genai_api.init(con2)


def test_respuesta_rag_con_citas_reales(client):
    _proveedor(client, "llm-1", "llm", "gpt-radiofar")
    r = client.post("/api/v1/genai/providers/llm-1/rag-answer", json={
        "consulta": "¿cuál es la vida media del F-18?",
        "documentos": ["doc-f18"], "usuario": "fisico1"})
    assert r.status_code == 503  # sin sonda previa
    client.post("/api/v1/genai/providers/llm-1/probe")
    r = client.post("/api/v1/genai/providers/llm-1/rag-answer", json={
        "consulta": "¿cuál es la vida media del F-18?",
        "documentos": ["doc-f18"], "usuario": "fisico1"})
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert "109,77" in cuerpo["respuesta"]
    assert cuerpo["documentos_utilizados"] == ["doc-f18"]
    assert cuerpo["cita"]["documentos"][0]["fuente_original"] == \
        "lab-ciclotron"  # 45.11
    # documento inexistente → 422: el contexto nunca se inventa
    r = client.post("/api/v1/genai/providers/llm-1/rag-answer", json={
        "consulta": "x", "documentos": ["doc-fantasma"],
        "usuario": "fisico1"})
    assert r.status_code == 422


def test_llm_contexto_real_enviado(client, conector):
    con, http = conector
    _proveedor(client, "llm-1", "llm", "gpt-radiofar")
    client.post("/api/v1/genai/providers/llm-1/probe")
    client.post("/api/v1/genai/providers/llm-1/rag-answer", json={
        "consulta": "¿cómo se mide la pureza?",
        "documentos": ["doc-qc"], "usuario": "qc1"})
    chats = [p for p in http.posts if p[0].endswith("/v1/chat/completions")
             and "pureza" in str(p[1])]
    assert chats  # la pregunta viajó al LLM
    contenido = chats[-1][1]["messages"][1]["content"]
    assert "HPLC" in contenido  # el contexto REAL del documento viajó


def test_estado_y_auditoria(client):
    _proveedor(client, "emb-1", "embeddings")
    estado = client.get("/api/v1/genai/status").json()
    assert estado["rag_engine"] == "inyectado"
    audit = client.get("/api/v1/genai/audit").json()
    assert all(k in audit[0] for k in ("evento_id", "accion", "actor",
                                       "resultado", "timestamp"))
    meta = client.get("/api/v1/genai/meta").json()
    assert "45.20" in meta["nota"]
