"""Tests del conector BentoML (EDS 20.10/20.11) y puente 41.8."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.domain.serving_connector import ServingConnector
from app.main import app
from app.presentation.routers import ei_api, mlops_api, serving_api
from tests.test_ei_core import _modelo_desplegado


class _Resp:
    def __init__(self, status_code=200, cuerpo=None):
        self.status_code = status_code
        self._cuerpo = cuerpo or {}

    def json(self):
        return self._cuerpo


class _HttpFalso:
    """Cliente HTTP inyectado; simula un BentoML accesible o caído."""

    def __init__(self, vivo=True):
        self.vivo = vivo
        self.peticiones = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url):
        self.peticiones.append(("GET", url))
        if not self.vivo:
            raise ConnectionError("connection refused")
        return _Resp(200)

    def post(self, url, json):
        self.peticiones.append(("POST", url, json))
        if not self.vivo:
            raise ConnectionError("connection refused")
        return _Resp(200, {"prediccion": 347.2, "unidad": "GBq"})


@pytest.fixture()
def conector_vivo():
    http = _HttpFalso(vivo=True)
    con = ServingConnector(fabrica_http=lambda: http)
    serving_api.init(con)
    mlops_api.init()
    ei_api.init()
    return con, http


@pytest.fixture()
def client(conector_vivo):
    return TestClient(app)


def _servidor(client, sid="bentoml-1", endpoint="http://bentoml.local:3000"):
    r = client.post("/api/v1/serving/servers", json={
        "servidor_id": sid, "endpoint": endpoint,
        "responsable": "mlops"})
    assert r.status_code == 201
    return sid


def test_servidor_versionado_y_endpoint_obligatorio(client):
    _servidor(client)
    r = client.post("/api/v1/serving/servers", json={
        "servidor_id": "bentoml-1", "endpoint": "http://bentoml2.local:3000",
        "responsable": "mlops"})
    assert r.status_code == 201 and r.json()["version"] == 2
    historial = client.get("/api/v1/serving/servers/bentoml-1/history").json()
    assert [h["version"] for h in historial] == [1, 2]
    r = client.post("/api/v1/serving/servers", json={
        "servidor_id": "x", "endpoint": "", "responsable": "a"})
    assert r.status_code == 422
    r = client.post("/api/v1/serving/servers", json={
        "servidor_id": "y", "endpoint": "bentoml.local", "responsable": "a"})
    assert r.status_code == 422  # URL http(s) obligatoria


def test_sonda_real_exito(client, conector_vivo):
    con, http = conector_vivo
    _servidor(client)
    r = client.post("/api/v1/serving/servers/bentoml-1/probe")
    assert r.json()["estado"] == "conectado"
    assert ("GET", "http://bentoml.local:3000/healthz") in http.peticiones


def test_sonda_fallo_honesto_y_503(client):
    serving_api.init(ServingConnector(
        fabrica_http=lambda: _HttpFalso(vivo=False)))
    _servidor(client)
    r = client.post("/api/v1/serving/servers/bentoml-1/probe")
    cuerpo = r.json()
    assert cuerpo["estado"] == "fallo_conexion"
    assert "ConnectionError" in cuerpo["detalle"]
    r = client.post("/api/v1/serving/servers/bentoml-1/infer", json={
        "ruta": "/predict", "datos": {"corriente_ua": 70},
        "modelo": "m-yield", "version_modelo": "1.0.0",
        "usuario": "fisico1"})
    assert r.status_code == 503  # el resultado NO se inventa


def test_inferencia_sin_sonda_503(client):
    _servidor(client)
    r = client.post("/api/v1/serving/servers/bentoml-1/infer", json={
        "ruta": "/predict", "datos": {"corriente_ua": 70},
        "modelo": "m-yield", "version_modelo": "1.0.0",
        "usuario": "fisico1"})
    assert r.status_code == 503


def test_inferencia_remota_real(client, conector_vivo):
    con, http = conector_vivo
    _servidor(client)
    client.post("/api/v1/serving/servers/bentoml-1/probe")
    r = client.post("/api/v1/serving/servers/bentoml-1/infer", json={
        "ruta": "/predict", "datos": {"corriente_ua": 70, "minutos": 120},
        "modelo": "m-yield", "version_modelo": "1.0.0",
        "usuario": "fisico1"})
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["prediccion"]["prediccion"] == 347.2
    assert cuerpo["ejecucion_id"]
    posts = [p for p in http.peticiones if p[0] == "POST"]
    assert posts[0][1] == "http://bentoml.local:3000/predict"
    assert posts[0][2]["version_modelo"] == "1.0.0"  # 20.11


def test_puente_runtime_inference_engine(client):
    _modelo_desplegado(client, "m-yield", "1.0.0")
    _servidor(client)
    client.post("/api/v1/serving/servers/bentoml-1/probe")
    # registra el runtime BentoML en ei_core (41.8) vía puente
    r = client.post("/api/v1/serving/bridge/runtime", json={
        "servidor_id": "bentoml-1", "ruta": "/predict",
        "modelo_id": "m-yield", "version_modelo": "1.0.0",
        "actor": "mlops"})
    assert r.status_code in (200, 201), r.text
    # inferencia a través del Inference Engine con trazabilidad completa
    r = client.post("/api/v1/ei/inference/execute", json={
        "modelo_id": "m-yield", "version_modelo": "1.0.0",
        "datos": {"corriente_ua": 70}, "usuario": "fisico1"})
    assert r.status_code in (200, 201), r.text
    assert r.json()["resultado"]["prediccion"] == 347.2


def test_puente_exige_modelo_desplegado(client):
    _servidor(client)  # modelo NO registrado en MLOps
    r = client.post("/api/v1/serving/bridge/runtime", json={
        "servidor_id": "bentoml-1", "ruta": "/predict",
        "modelo_id": "m-fantasma", "version_modelo": "9.9",
        "actor": "mlops"})
    assert r.status_code == 422  # 41.20: no validados no se usan


def test_estado_y_auditoria(client):
    _servidor(client)
    estado = client.get("/api/v1/serving/status").json()
    assert estado["servidores"][0]["estado"] == "no_sondeado"
    audit = client.get("/api/v1/serving/audit").json()
    assert all(k in audit[0] for k in ("evento_id", "accion", "actor",
                                       "resultado", "timestamp"))
    meta = client.get("/api/v1/serving/meta").json()
    assert "20.10" in meta["nota"]
