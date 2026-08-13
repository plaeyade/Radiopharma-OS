"""Tests del ejecutor PQ real (Informe 14.9) — fase 3."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.domain.pq_runner import EjecutorPQ
from app.domain.qualification import QualificationEngine
from app.main import app
from app.presentation.routers import pq_api, qualification_api


class _Resp:
    def __init__(self, status_code=200, text="ok"):
        self.status_code = status_code
        self.text = text


class _HttpFalso:
    """HTTP de prueba: responde según un mapa real de URLs; las URLs no
    registradas fallan como lo haría un servicio caído."""

    def __init__(self, mapa):
        self._mapa = mapa

    def get(self, url):
        if url not in self._mapa:
            raise ConnectionError(f"connection refused: {url}")
        resp = self._mapa[url]
        if isinstance(resp, Exception):
            raise resp
        return resp


@pytest.fixture()
def engine():
    eng = QualificationEngine()
    qualification_api.init(eng)
    return eng


@pytest.fixture()
def runner(engine):
    mapa = {
        "http://svc-a:8001/health": _Resp(200, "healthy"),
        "http://svc-b:8002/health": _Resp(200, "healthy"),
    }
    run = EjecutorPQ(engine, fabrica_http=lambda: _HttpFalso(mapa))
    pq_api.init(run)
    return run


@pytest.fixture()
def client(runner):
    return TestClient(app)


def _componente_con_dq_iq_oq(engine, componente_id="plataforma_base"):
    engine.registrar_componente(componente_id, "Plataforma base",
                                "sistema", "1.0.0", "calidad")
    for etapa in ("DQ", "IQ", "OQ"):
        engine.definir_protocolo(componente_id, etapa, ["criterio_base"],
                                 "calidad", f"protocolo {etapa}")
        engine.ejecutar_etapa(
            componente_id, etapa, "condiciones_reales", "calidad",
            [{"criterio": "criterio_base", "cumple": True,
              "detalle": "verificado", "evidencia_ref": "doc"}])


def test_pq_superado_con_servicios_vivos(engine, runner):
    _componente_con_dq_iq_oq(engine)
    runner.definir_protocolo(
        "pq_base", "plataforma_base",
        [{"criterio": "salud_svc_a", "url": "http://svc-a:8001/health",
          "contiene": "healthy", "umbral_ms": 5000},
         {"criterio": "salud_svc_b", "url": "http://svc-b:8002/health"}],
        "calidad", "PQ inicial de plataforma")
    res = runner.ejecutar("pq_base", "calidad")
    assert res["estado"] == "superada"
    assert all(r["cumple"] for r in res["resultados"])
    assert all("ms" in r["detalle"] for r in res["resultados"])
    assert engine.estado_calificacion("plataforma_base")["calificado"]


def test_servicio_caido_no_supera_y_no_se_inventa(engine, runner):
    _componente_con_dq_iq_oq(engine)
    runner.definir_protocolo(
        "pq_base", "plataforma_base",
        [{"criterio": "salud_svc_a", "url": "http://svc-a:8001/health"},
         {"criterio": "salud_svc_c",
          "url": "http://svc-caido:8003/health"}],
        "calidad", "PQ con servicio caído")
    res = runner.ejecutar("pq_base", "calidad")
    assert res["estado"] == "no_superada"
    caido = next(r for r in res["resultados"]
                 if r["criterio"] == "salud_svc_c")
    assert not caido["cumple"]
    assert "ConnectionError" in caido["detalle"]
    assert "NO responde" in caido["detalle"]
    assert not engine.estado_calificacion("plataforma_base")["calificado"]


def test_status_incorrecto_no_cumple(engine, runner):
    _componente_con_dq_iq_oq(engine)
    runner.definir_protocolo(
        "pq_estricto", "plataforma_base",
        [{"criterio": "status_imposible", "url": "http://svc-a:8001/health",
          "status_esperado": 503}],   # el servicio real responde 200
        "calidad", "status esperado distinto del real")
    res = runner.ejecutar("pq_estricto", "calidad")
    assert res["estado"] == "no_superada"
    assert "status 200 != 503" in res["resultados"][0]["detalle"]


def test_protocolo_versionado_nunca_sobrescrito(engine, runner):
    _componente_con_dq_iq_oq(engine)
    runner.definir_protocolo("pq_base", "plataforma_base",
                             [{"criterio": "c1",
                               "url": "http://svc-a:8001/health"}],
                             "calidad", "v1")
    proto2 = runner.definir_protocolo(
        "pq_base", "plataforma_base",
        [{"criterio": "c1", "url": "http://svc-a:8001/health"},
         {"criterio": "c2", "url": "http://svc-b:8002/health"}],
        "calidad", "v2: se añade criterio")
    assert proto2["version"] == 2
    assert len(runner._protocolos["pq_base"]) == 2
    # el espejo en el motor también queda versionado
    historial = engine.historial_protocolo("plataforma_base", "PQ")
    assert [p.version for p in historial] == [1, 2]


def test_criterio_sin_url_rechazado(engine, runner):
    _componente_con_dq_iq_oq(engine)
    with pytest.raises(Exception, match="url real"):
        runner.definir_protocolo("pq_vacio", "plataforma_base",
                                 [{"criterio": "declarativo", "url": ""}],
                                 "calidad", "criterio sin comprobación")


def test_api_flujo_completo(engine, runner, client):
    _componente_con_dq_iq_oq(engine)
    r = client.post("/api/v1/qualification/pq/protocols", json={
        "protocolo_id": "pq_api", "componente_id": "plataforma_base",
        "criterios": [{"criterio": "salud_a",
                       "url": "http://svc-a:8001/health",
                       "status_esperado": 200}],
        "responsable": "calidad", "motivo": "PQ vía API"})
    assert r.status_code == 201 and r.json()["version"] == 1
    r2 = client.post("/api/v1/qualification/pq/protocols/pq_api/run",
                     json={"ejecutor": "calidad"})
    assert r2.status_code == 201
    assert r2.json()["estado"] == "superada"
    # el expediente RCAE del motor refleja la ejecución PQ real
    r3 = client.get("/api/v1/qualification/components/plataforma_base/status")
    assert r3.json()["calificado"] is True
    r4 = client.get("/api/v1/qualification/pq/audit")
    assert any(a["accion"] == "pq_ejecutado" for a in r4.json())


def test_run_sin_protocolo_es_422(runner, client):
    r = client.post("/api/v1/qualification/pq/protocols/inexistente/run",
                    json={"ejecutor": "calidad"})
    assert r.status_code == 422


def test_meta_reporta_estado_real(runner, client):
    r = client.get("/api/v1/qualification/pq/meta")
    assert r.json()["fabrica_http"] == "inyectada"
