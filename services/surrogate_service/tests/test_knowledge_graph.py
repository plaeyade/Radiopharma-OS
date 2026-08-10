"""Tests del Knowledge Graph & Semantic Intelligence Engine (cap. 44).

Verifica: ontología versionada 44.6, Entity Registry con id semántico
único 44.7, relaciones trazables con evidencia 44.8, consulta
semántica 44.9, camino multi-dominio BFS, razonamiento transitivo
44.10 con justificación completa — nunca inferencia sin cadena —,
sincronización controlada 44.11 y auditoría.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.presentation.routers import graph_api


@pytest.fixture()
def client() -> TestClient:
    graph_api.init()
    c = TestClient(app)
    for tipo in ("radionuclido", "radiofarmaco", "lote", "equipo",
                 "documento"):
        assert c.post("/api/v1/graph/ontology", json={
            "nombre": tipo, "version": "1.0.0",
            "definicion": {"descripcion": tipo}}).status_code == 201
    for eid, tipo in (("F-18", "radionuclido"), ("FDG", "radiofarmaco"),
                      ("lote-42", "lote"), ("cyclo-1", "equipo"),
                      ("sop-qc-001", "documento")):
        assert c.post("/api/v1/graph/entities", json={
            "entidad_id": eid, "tipo": tipo}).status_code == 201
    return c


def _rel(c: TestClient, o: str, t: str, d: str, ev: str = "") -> int:
    return c.post("/api/v1/graph/relationships", json={
        "origen": o, "tipo": t, "destino": d, "evidencia": ev}).status_code


def test_ontologia_versionada(client: TestClient) -> None:
    assert client.post("/api/v1/graph/ontology", json={
        "nombre": "lote", "version": "1.0.0",
        "definicion": {}}).status_code == 422
    assert client.post("/api/v1/graph/ontology", json={
        "nombre": "lote", "version": "1.1.0",
        "definicion": {"ampliada": True}}).status_code == 201
    onto = client.get("/api/v1/graph/ontology").json()
    assert onto["lote"]["version_vigente"] == "1.1.0"
    assert onto["lote"]["n_versiones"] == 2


def test_entidad_tipo_debe_existir_en_ontologia(client: TestClient) -> None:
    r = client.post("/api/v1/graph/entities", json={
        "entidad_id": "x-1", "tipo": "tipo_inventado"})
    assert r.status_code == 422
    # id semántico único: nunca sobrescribe
    r2 = client.post("/api/v1/graph/entities", json={
        "entidad_id": "F-18", "tipo": "radionuclido"})
    assert r2.status_code == 422


def test_relaciones_trazables_y_unicas(client: TestClient) -> None:
    assert _rel(client, "cyclo-1", "produce", "F-18",
                "ye:production/run-1") == 201
    assert _rel(client, "F-18", "es_un", "radionuclido-err") == 422
    assert _rel(client, "cyclo-1", "produce", "F-18") == 422   # duplicada
    rels = client.get("/api/v1/graph/relationships",
                      params={"entidad_id": "F-18"}).json()
    assert rels[0]["evidencia"] == "ye:production/run-1"


def test_consulta_semantica(client: TestClient) -> None:
    _rel(client, "FDG", "utiliza", "F-18", "proc:fdg-synthesis")
    _rel(client, "lote-42", "contiene", "FDG", "ps:batch-42")
    sal = client.get("/api/v1/graph/query/FDG",
                     params={"tipo_relacion": "utiliza"}).json()
    assert sal == [{"tipo": "utiliza", "entidad": "F-18",
                    "evidencia": "proc:fdg-synthesis"}]
    ent = client.get("/api/v1/graph/query/F-18",
                     params={"direccion": "entrante"}).json()
    assert any(e["entidad"] == "FDG" for e in ent)


def test_camino_multi_dominio(client: TestClient) -> None:
    _rel(client, "cyclo-1", "produce", "F-18")
    _rel(client, "FDG", "utiliza", "F-18")
    _rel(client, "lote-42", "contiene", "FDG")
    _rel(client, "sop-qc-001", "valida", "lote-42", "qc:release-42")
    # camino dirigido desde el SOP hasta el radionúclido: 3 saltos
    p = client.get("/api/v1/graph/path", params={
        "origen": "sop-qc-001", "destino": "F-18"}).json()
    assert p["existe"] is True and p["saltos"] == 3
    # sin camino: honesto
    p2 = client.get("/api/v1/graph/path", params={
        "origen": "F-18", "destino": "sop-qc-001"}).json()
    assert p2["existe"] is False
    assert "honesto" in p2["nota"]


def test_razonamiento_transitivo_documentado(client: TestClient) -> None:
    client.post("/api/v1/graph/entities", json={
        "entidad_id": "emisor-beta-plus", "tipo": "radionuclido"})
    client.post("/api/v1/graph/entities", json={
        "entidad_id": "radionuclido-medico", "tipo": "radionuclido"})
    _rel(client, "F-18", "es_un", "emisor-beta-plus", "nds:decay/F-18")
    _rel(client, "emisor-beta-plus", "es_un", "radionuclido-medico",
         "taxonomia-institucional-v1")
    r = client.get("/api/v1/graph/reason/F-18").json()
    assert r["es_un"] == ["emisor-beta-plus", "radionuclido-medico"]
    # cadena de justificación completa: cada paso con evidencia
    assert len(r["justificacion"]) == 2
    assert r["justificacion"][0]["evidencia"] == "nds:decay/F-18"
    infs = client.get("/api/v1/graph/inferences").json()
    assert infs[-1]["entidad"] == "F-18"


def test_sincronizacion_controlada(client: TestClient) -> None:
    r = client.post("/api/v1/graph/sync", json={
        "origen": "qc_engine", "version": "qc-0.46.0",
        "entidades": [{"entidad_id": "hplc-1", "tipo": "equipo"}],
        "relaciones": [{"origen": "hplc-1", "tipo": "valida",
                        "destino": "lote-42"}]})
    assert r.status_code == 201
    assert r.json()["entidades_incorporadas"] == 1
    assert r.json()["relaciones_incorporadas"] == 1
    # segunda sincronización: no duplica (controlada)
    r2 = client.post("/api/v1/graph/sync", json={
        "origen": "qc_engine", "version": "qc-0.46.1",
        "entidades": [{"entidad_id": "hplc-1", "tipo": "equipo"}],
        "relaciones": [{"origen": "hplc-1", "tipo": "valida",
                        "destino": "lote-42"}]})
    assert r2.json()["entidades_incorporadas"] == 0
    assert r2.json()["relaciones_incorporadas"] == 0
    aud = client.get("/api/v1/graph/audit").json()
    assert sum(1 for a in aud if a["accion"] == "sincronizar") == 2
