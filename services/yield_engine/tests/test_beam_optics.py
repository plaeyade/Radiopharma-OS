"""Tests de óptica de haz (TraceWin) + calibración de tablas externas
(Fase 17 — EDS 5.9 / 19.10)."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def beamline_id(client):
    r = client.post("/api/v1/beamlines", json={
        "ciclotron_id": "CYC-OPT", "nombre": "linea-opt",
        "transmision": 0.97,
        "fuente_transmision": "ficha proveedor — test",
        "registrado_por": "op"})
    assert r.status_code == 201
    return r.json()["beamline_id"]


LINEA = {"elementos": [
    {"tipo": "drift", "nombre": "drift extracción", "longitud_m": 0.5,
     "parametros": {}, "fuente": "diseño del proveedor, plano P-101"},
    {"tipo": "cuadrupolo", "nombre": "Q1", "longitud_m": 0.2,
     "parametros": {"gradiente_t_m": 8.5},
     "fuente": "medición en comisionado, informe COM-2024-01"},
    {"tipo": "drift", "nombre": "drift al blanco", "longitud_m": 0.8,
     "parametros": {}, "fuente": "diseño del proveedor, plano P-101"},
]}


def test_registrar_linea_optica(client, beamline_id):
    r = client.post(f"/api/v1/beamlines/{beamline_id}/optics",
                    json={**LINEA, "registrado_por": "físico"})
    assert r.status_code == 201
    lo = r.json()
    assert lo["version"] == 1
    assert len(lo["elementos"]) == 3


def test_elemento_sin_fuente_rechazado(client, beamline_id):
    mal = {"elementos": [{"tipo": "drift", "nombre": "d", "longitud_m": 1.0,
                          "parametros": {}, "fuente": ""}],
           "registrado_por": "op"}
    r = client.post(f"/api/v1/beamlines/{beamline_id}/optics", json=mal)
    assert r.status_code == 422
    assert "49.11" in r.json()["detail"]


def test_tipo_elemento_invalido(client, beamline_id):
    mal = {"elementos": [{"tipo": "imán mágico", "nombre": "x",
                          "longitud_m": 1.0, "parametros": {},
                          "fuente": "ficha"}],
           "registrado_por": "op"}
    r = client.post(f"/api/v1/beamlines/{beamline_id}/optics", json=mal)
    assert r.status_code == 422


def test_transporte_sin_runtime_503_honesto(client, beamline_id):
    r = client.post(f"/api/v1/beamlines/{beamline_id}/transport",
                    json={"energia_mev": 18.0, "corriente_ma": 0.3})
    assert r.status_code == 503            # sin TraceWin instalado
    detalle = r.json()["detail"]
    assert detalle["estado"] == "sin_runtime"
    assert "nunca simula" in detalle["nota"]


def test_transporte_sin_linea_404(client):
    r = client.post("/api/v1/beamlines/BL-9999/transport",
                    json={"energia_mev": 18.0, "corriente_ma": 0.3})
    assert r.status_code == 404
    assert "no_demostrable" in r.json()["detail"]


def test_calibracion_tabla_externa(client):
    # registra tabla con valores cercanos a ATIMA (agua) y calibra
    r = client.post("/api/v1/stopping-power/external-tables", json={
        "material": "agua", "ejecutado_en": "test",
        "fuente": "tabla de prueba con fuente citada",
        "filas": [[4.5, 85.0], [10.0, 45.0], [16.0, 30.0]],
        "registrado_por": "físico"})
    assert r.status_code == 201
    v = r.json()["version"]   # puede coexistir con tablas ya versionadas
    c = client.post(
        f"/api/v1/stopping-power/external-tables/agua/versions/{v}/calibrate",
        json={"criterio_max_pct": 25.0,
              "motivo": "verificación inicial vs ATIMA versionado",
              "registrado_por": "físico"})
    assert c.status_code == 201
    d = c.json()
    assert d["calibracion"]["veredicto"] in ("calibrada", "rechazada")
    assert d["calibracion"]["comparacion"]["n_puntos"] == 3
    assert "referencia" in d["calibracion"]["comparacion"]
    # append-only: segunda calibración no borra la primera
    c2 = client.post(
        f"/api/v1/stopping-power/external-tables/agua/versions/{v}/calibrate",
        json={"criterio_max_pct": 1.0, "motivo": "criterio estricto",
              "registrado_por": "físico"})
    assert len(c2.json()["tabla"]["calibraciones"]) == 2


def test_calibracion_material_sin_mapeo(client):
    client.post("/api/v1/stopping-power/external-tables", json={
        "material": "titanio", "ejecutado_en": "test",
        "fuente": "tabla de prueba con fuente citada",
        "filas": [[5.0, 40.0], [10.0, 22.0]], "registrado_por": "op"})
    r = client.post(
        "/api/v1/stopping-power/external-tables/titanio/versions/1/calibrate",
        json={"criterio_max_pct": 10.0, "motivo": "intento",
              "registrado_por": "op"})
    assert r.status_code == 422
    assert "no_demostrable" in r.json()["detail"]
