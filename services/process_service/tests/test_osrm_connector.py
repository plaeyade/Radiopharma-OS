"""Tests del conector OSRM — routing terrestre real del Logistics Twin."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.application.logistics_service import LogisticsService
from app.domain.osrm_connector import OsrmConnector
from app.main import app
from app.presentation.routers import logistics_api, osrm_api


class _Resp:
    def __init__(self, status_code=200, cuerpo=None):
        self.status_code = status_code
        self._cuerpo = cuerpo or {}

    def json(self):
        return self._cuerpo


class _HttpOsrm:
    """HTTP inyectado que imita la API OSRM (route/table)."""

    def __init__(self, vivo=True):
        self.vivo = vivo
        self.gets = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url):
        self.gets.append(url)
        if not self.vivo:
            raise ConnectionError("connection refused")
        if "/route/v1/" in url:
            return _Resp(200, {"code": "Ok", "routes": [
                {"duration": 3240.0, "distance": 68500.0}]})
        if "/table/v1/" in url:
            # 12 destinos del anillo: 8 alcanzables en 30 min
            durs = [0.0] + [900.0] * 8 + [3600.0] * 4
            return _Resp(200, {"code": "Ok", "durations": [durs]})
        return _Resp(404)


@pytest.fixture()
def conector():
    http = _HttpOsrm()
    con = OsrmConnector(fabrica_http=lambda: http)
    osrm_api.init(con)
    logistics_api.init(LogisticsService())
    return con, http


@pytest.fixture()
def client(conector):
    return TestClient(app)


def _servidor(client, sid="osrm-1", endpoint="http://osrm.local:5000"):
    r = client.post("/api/v1/osrm/servers", json={
        "servidor_id": sid, "endpoint": endpoint,
        "responsable": "logistica"})
    assert r.status_code == 201
    return sid


def test_servidor_versionado_y_endpoint_obligatorio(client):
    _servidor(client)
    r = client.post("/api/v1/osrm/servers", json={
        "servidor_id": "osrm-1", "endpoint": "http://osrm2.local:5000",
        "responsable": "logistica"})
    assert r.json()["version"] == 2
    historial = client.get("/api/v1/osrm/servers/osrm-1/history").json()
    assert [h["version"] for h in historial] == [1, 2]
    r = client.post("/api/v1/osrm/servers", json={
        "servidor_id": "x", "endpoint": "", "responsable": "a"})
    assert r.status_code == 422
    r = client.post("/api/v1/osrm/servers", json={
        "servidor_id": "y", "endpoint": "osrm.local", "responsable": "a"})
    assert r.status_code == 422


def test_sonda_real_exito_y_fallo_honesto(client, conector):
    con, http = conector
    _servidor(client)
    r = client.post("/api/v1/osrm/servers/osrm-1/probe")
    assert r.json()["estado"] == "conectado"
    assert any("/route/v1/driving/13.388860,52.517037" in u for u in http.gets)
    http.vivo = False
    r = client.post("/api/v1/osrm/servers/osrm-1/probe")
    assert r.json()["estado"] == "fallo_conexion"
    assert "ConnectionError" in r.json()["detalle"]


def test_ruta_directa_real(client):
    _servidor(client)
    client.post("/api/v1/osrm/servers/osrm-1/probe")
    r = client.get("/api/v1/osrm/servers/osrm-1/route", params={
        "lon_o": -3.7038, "lat_o": 40.4168,
        "lon_d": -5.9845, "lat_d": 37.3891})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["minutos"] == 54.0      # 3240 s reales de la respuesta
    assert cuerpo["km"] == 68.5           # 68500 m reales
    assert cuerpo["routing_source"] == "osrm-http"


def test_ruta_sin_sonda_503(client):
    _servidor(client)
    r = client.get("/api/v1/osrm/servers/osrm-1/route", params={
        "lon_o": -3.7, "lat_o": 40.4, "lon_d": -5.9, "lat_d": 37.4})
    assert r.status_code == 503


def test_activacion_cambia_routing_del_twin(client):
    _servidor(client)
    # antes: proveedor local honesto
    r = client.post("/api/v1/logistics/route", json={
        "origin_id": "cyclotron_main", "dest_id": "hosp_norte",
        "protocol_id": "fdg_18f", "eos_activity_gbq": 66.7, "mode": "road"})
    assert r.json()["routing_source"] == "local-haversine"
    # activar sin sonda → 503 (nunca sustitución silenciosa)
    r = client.post("/api/v1/osrm/servers/osrm-1/activate",
                    json={"actor": "logistica"})
    assert r.status_code == 503
    client.post("/api/v1/osrm/servers/osrm-1/probe")
    r = client.post("/api/v1/osrm/servers/osrm-1/activate",
                    json={"actor": "logistica"})
    assert r.status_code == 200
    assert r.json()["routing_source_activo"] == "osrm-http"
    assert r.json()["proveedor_anterior"] == "local-haversine"
    # desde la activación, las rutas del twin usan OSRM y lo declaran
    r = client.post("/api/v1/logistics/route", json={
        "origin_id": "cyclotron_main", "dest_id": "hosp_norte",
        "protocol_id": "fdg_18f", "eos_activity_gbq": 66.7, "mode": "road"})
    cuerpo = r.json()
    assert cuerpo["routing_source"] == "osrm-http"
    pierna = cuerpo["legs"][0]
    assert pierna["duration_min"] == 54.0   # tiempo REAL de OSRM
    estado = client.get("/api/v1/osrm/status").json()
    assert estado["routing_source_vigente_twin"] == "osrm-http"


def test_desactivacion_auditada(client):
    _servidor(client)
    client.post("/api/v1/osrm/servers/osrm-1/probe")
    client.post("/api/v1/osrm/servers/osrm-1/activate",
                json={"actor": "logistica"})
    r = client.post("/api/v1/osrm/deactivate", json={"actor": "logistica"})
    assert r.json()["routing_source_activo"] == "local-haversine"
    assert r.json()["proveedor_anterior"] == "osrm-http"
    audit = client.get("/api/v1/osrm/audit").json()
    acciones = [a["accion"] for a in audit]
    assert "osrm_activado" in acciones and "osrm_desactivado" in acciones


def test_isocrona_real_osrm(client, conector):
    con, http = conector
    from app.infrastructure.routing import OsrmRoutingProvider
    from app.domain.logistics import GeoPoint
    prov = OsrmRoutingProvider("http://osrm.local:5000",
                               http_factory=lambda: http)
    radio = prov.reachable_radius_km(GeoPoint(40.4168, -3.7038), 30.0)
    assert radio > 0
    assert any("/table/v1/driving/" in u and "sources=0" in u
               for u in http.gets)
    # con todos los destinos fuera de tiempo → radio 0 honesto
    class _HttpLento(_HttpOsrm):
        def get(self, url):
            self.gets.append(url)
            return _Resp(200, {"code": "Ok",
                               "durations": [[0.0] + [99999.0] * 12]})
    prov2 = OsrmRoutingProvider("http://osrm.local:5000",
                                http_factory=lambda: _HttpLento())
    assert prov2.reachable_radius_km(GeoPoint(40.4168, -3.7038), 30.0) == 0.0


def test_meta_y_auditoria(client):
    _servidor(client)
    meta = client.get("/api/v1/osrm/meta").json()
    assert "routing_source" in meta["nota"]
    audit = client.get("/api/v1/osrm/audit").json()
    assert all(k in audit[0] for k in ("evento_id", "accion", "actor",
                                       "resultado", "timestamp"))
