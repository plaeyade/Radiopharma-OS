"""Tests de los conectores EXFOR/SRIM/NNDC (Informe 19.10-19.13)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.domain.nuclear_connectors import NuclearDataConnectors
from app.main import app
from app.presentation.routers import connectors_api, library_api


class _Resp:
    def __init__(self, status_code=200, cuerpo=None):
        self.status_code = status_code
        self._cuerpo = cuerpo or {}

    def json(self):
        return self._cuerpo


EXFOR_OK = {
    "tipo": "seccion_eficaz",
    "metadatos": {"referencia": "EXFOR-D0419", "version": "2024-03",
                  "fecha": "2024-03-15"},
    "datos": [{"energia_mev": 10.0, "seccion_eficaz_mb": 512.0},
              {"energia_mev": 15.0, "seccion_eficaz_mb": 380.0}],
}


class _HttpFalso:
    def __init__(self, vivo=True, cuerpo=None):
        self.vivo = vivo
        self.cuerpo = cuerpo if cuerpo is not None else EXFOR_OK
        self.gets = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url):
        self.gets.append(url)
        if not self.vivo:
            raise ConnectionError("connection refused")
        return _Resp(200, self.cuerpo)


@pytest.fixture()
def conector(tmp_path):
    srim_dir = tmp_path / "srim"
    srim_dir.mkdir()
    (srim_dir / "o18_stopping.csv").write_text(
        "energia_mev,stopping_power\n5.0,92.1\n10.0,61.3\n15.0,45.7\n")
    http = _HttpFalso()
    con = NuclearDataConnectors(biblioteca=library_api._engine,
                                fabrica_http=lambda: http)
    connectors_api.init(con)
    return con, http, str(srim_dir)


@pytest.fixture()
def client(conector):
    return TestClient(app)


def test_fuente_versionada_y_validaciones(client):
    r = client.post("/api/v1/connectors/sources", json={
        "fuente_id": "exfor-iaea", "tipo": "exfor",
        "endpoint": "https://www-nds.iaea.org/exfor",
        "responsable": "fisico-nuclear"})
    assert r.status_code == 201
    r = client.post("/api/v1/connectors/sources", json={
        "fuente_id": "exfor-iaea", "tipo": "exfor",
        "endpoint": "https://mirror.exfor.org", "responsable": "fisico"})
    assert r.json()["version"] == 2
    historial = client.get(
        "/api/v1/connectors/sources/exfor-iaea/history").json()
    assert [h["version"] for h in historial] == [1, 2]
    r = client.post("/api/v1/connectors/sources", json={
        "fuente_id": "x", "tipo": "exfor", "endpoint": "sin-esquema",
        "responsable": "a"})
    assert r.status_code == 422
    r = client.post("/api/v1/connectors/sources", json={
        "fuente_id": "y", "tipo": "talys", "endpoint": "http://x",
        "responsable": "a"})
    assert r.status_code == 422  # tipo inválido


def test_sonda_exfor_exito_y_fallo_honesto(client, conector):
    con, http, _ = conector
    client.post("/api/v1/connectors/sources", json={
        "fuente_id": "exfor-iaea", "tipo": "exfor",
        "endpoint": "https://www-nds.iaea.org/exfor",
        "responsable": "fisico"})
    r = client.post("/api/v1/connectors/sources/exfor-iaea/probe")
    assert r.json()["estado"] == "conectada"
    # fuente caída → fallo honesto
    http.vivo = False
    r = client.post("/api/v1/connectors/sources/exfor-iaea/probe")
    assert r.json()["estado"] == "fallo_conexion"
    assert "ConnectionError" in r.json()["detalle"]


def test_importacion_exfor_registra_en_biblioteca(client):
    client.post("/api/v1/connectors/sources", json={
        "fuente_id": "exfor-iaea", "tipo": "exfor",
        "endpoint": "https://www-nds.iaea.org/exfor",
        "responsable": "fisico"})
    client.post("/api/v1/connectors/sources/exfor-iaea/probe")
    r = client.post("/api/v1/connectors/sources/exfor-iaea/exfor/import",
                    json={"nuclide": "f18",
                          "ruta_consulta": "/api/dataset?reaction=18O(p,n)18F",
                          "autor": "fisico-nuclear"})
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert "prevalece sobre modelos teóricos" in cuerpo["prioridad"]
    reg = cuerpo["registro"]
    assert reg["referencia"] == "EXFOR-D0419"
    assert reg["fuente"].startswith("EXFOR — https://")
    # consultable desde la biblioteca (19.12)
    datos = client.get("/api/v1/library/nuclides/f18/experimental").json()
    assert any(d["referencia"] == "EXFOR-D0419" for d in datos)


def test_importacion_sin_sonda_503(client):
    client.post("/api/v1/connectors/sources", json={
        "fuente_id": "exfor-iaea", "tipo": "exfor",
        "endpoint": "https://www-nds.iaea.org/exfor",
        "responsable": "fisico"})
    r = client.post("/api/v1/connectors/sources/exfor-iaea/exfor/import",
                    json={"nuclide": "f18", "ruta_consulta": "/api/x",
                          "autor": "fisico"})
    assert r.status_code == 503


def test_respuesta_exfor_sin_metadatos_rechazada(client, conector):
    con, http, _ = conector
    http.cuerpo = {"datos": [{"e": 1}]}  # sin referencia/versión/fecha
    client.post("/api/v1/connectors/sources", json={
        "fuente_id": "exfor-iaea", "tipo": "exfor",
        "endpoint": "https://www-nds.iaea.org/exfor",
        "responsable": "fisico"})
    client.post("/api/v1/connectors/sources/exfor-iaea/probe")
    r = client.post("/api/v1/connectors/sources/exfor-iaea/exfor/import",
                    json={"nuclide": "f18", "ruta_consulta": "/api/x",
                          "autor": "fisico"})
    assert r.status_code == 422  # 19.12: metadatos obligatorios


def test_importacion_srim_real_con_hash(client, conector):
    _, _, srim_dir = conector
    client.post("/api/v1/connectors/sources", json={
        "fuente_id": "srim-local", "tipo": "srim", "endpoint": srim_dir,
        "responsable": "fisico"})
    r = client.post("/api/v1/connectors/sources/srim-local/probe")
    assert r.json()["estado"] == "conectada"
    r = client.post("/api/v1/connectors/sources/srim-local/srim/import",
                    json={"material": "o18_enriquecido",
                          "archivo": "o18_stopping.csv",
                          "autor": "fisico"})
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["puntos"] == 3 and len(cuerpo["sha256"]) == 64
    assert cuerpo["alimenta_yield_engine"] is False  # honesto: sin cargador
    # duplicado idéntico → rechazado (nunca se sobrescribe)
    r = client.post("/api/v1/connectors/sources/srim-local/srim/import",
                    json={"material": "o18_enriquecido",
                          "archivo": "o18_stopping.csv",
                          "autor": "fisico"})
    assert r.status_code == 422
    # archivo inexistente → 422, no se inventa
    r = client.post("/api/v1/connectors/sources/srim-local/srim/import",
                    json={"material": "o18_enriquecido",
                          "archivo": "fantasma.csv", "autor": "fisico"})
    assert r.status_code == 422


def test_srim_alimenta_yield_engine_inyectado(tmp_path):
    recibidas = []
    srim_dir = tmp_path / "srim"
    srim_dir.mkdir()
    (srim_dir / "t.csv").write_text(
        "energia_mev,stopping_power\n5.0,92.1\n")
    con = NuclearDataConnectors(
        biblioteca=library_api._engine,
        fabrica_http=lambda: _HttpFalso(),
        cargador_yield=lambda mat, tabla, meta: recibidas.append(
            (mat, tabla, meta)))
    connectors_api.init(con)
    c = TestClient(app)
    c.post("/api/v1/connectors/sources", json={
        "fuente_id": "srim-local", "tipo": "srim", "endpoint": str(srim_dir),
        "responsable": "fisico"})
    c.post("/api/v1/connectors/sources/srim-local/probe")
    r = c.post("/api/v1/connectors/sources/srim-local/srim/import",
               json={"material": "h2o", "archivo": "t.csv",
                     "autor": "fisico"})
    assert r.json()["alimenta_yield_engine"] is True  # 19.10
    assert recibidas[0][0] == "h2o"
    assert recibidas[0][1][0]["energia_mev"] == 5.0
    assert len(recibidas[0][2]["sha256"]) == 64


def test_nndc_consulta_real_y_estado(client, conector):
    con, http, _ = conector
    http.cuerpo = {"vida_media_s": 6586.2, "emisiones": ["beta+"]}
    client.post("/api/v1/connectors/sources", json={
        "fuente_id": "nndc-bnl", "tipo": "nndc",
        "endpoint": "https://www.nndc.bnl.gov", "responsable": "fisico"})
    r = client.get("/api/v1/connectors/sources/nndc-bnl/nndc/f18")
    assert r.status_code == 503  # sin sonda previa
    client.post("/api/v1/connectors/sources/nndc-bnl/probe")
    r = client.get("/api/v1/connectors/sources/nndc-bnl/nndc/f18")
    assert r.status_code == 200
    assert r.json()["constantes"]["vida_media_s"] == 6586.2
    estado = client.get("/api/v1/connectors/status").json()
    assert estado["biblioteca"] == "inyectada"
    audit = client.get("/api/v1/connectors/audit").json()
    assert all("evento_id" in a for a in audit)
