"""Tests del Qualification Engine (Informe 14.9) — DQ/IQ/OQ/PQ."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.domain.qualification import QualificationEngine
from app.main import app
from app.presentation.routers import qualification_api


@pytest.fixture()
def engine():
    eng = QualificationEngine()
    qualification_api.init(eng)
    return eng


@pytest.fixture()
def client(engine):
    return TestClient(app)


def _componente(client, cid="cyclotron-01"):
    r = client.post("/api/v1/qualification/components", json={
        "componente_id": cid, "nombre": "Ciclotrón 18 MeV",
        "tipo": "acelerador", "version": "1.0",
        "responsable": "calidad"})
    assert r.status_code == 201
    return cid


def _protocolo(client, cid, etapa, criterios, motivo="protocolo inicial"):
    return client.post(f"/api/v1/qualification/components/{cid}/protocols",
                       json={"etapa": etapa, "criterios": criterios,
                             "responsable": "calidad", "motivo": motivo})


def _ejecuta(client, cid, etapa, entorno, resultados):
    return client.post(
        f"/api/v1/qualification/components/{cid}/executions",
        json={"etapa": etapa, "entorno": entorno, "ejecutor": "operador-1",
              "resultados": resultados})


def test_registro_componente_y_unicidad(client):
    _componente(client)
    r = client.post("/api/v1/qualification/components", json={
        "componente_id": "cyclotron-01", "nombre": "dup",
        "tipo": "acelerador", "version": "1.0", "responsable": "x"})
    assert r.status_code == 422
    comps = client.get("/api/v1/qualification/components").json()
    assert len(comps) == 1 and comps[0]["tipo"] == "acelerador"


def test_protocolo_versionado_nunca_sobrescribe(client):
    cid = _componente(client)
    assert _protocolo(client, cid, "DQ", ["diseño documentado"]).status_code == 201
    r = _protocolo(client, cid, "DQ",
                   ["diseño documentado", "riesgos evaluados"],
                   motivo="ampliar criterios (14.12)")
    assert r.status_code == 201 and r.json()["version"] == 2
    historial = client.get(
        f"/api/v1/qualification/components/{cid}/protocols/DQ").json()
    assert [h["version"] for h in historial] == [1, 2]
    assert historial[0]["criterios"] == ["diseño documentado"]


def test_orden_estricto_etapas(client):
    cid = _componente(client)
    _protocolo(client, cid, "IQ", ["instalación verificada"])
    r = _ejecuta(client, cid, "IQ", "laboratorio",
                 [{"criterio": "instalación verificada", "cumple": True}])
    assert r.status_code == 422
    assert "DQ" in r.json()["detail"]


def test_etapa_superada_solo_con_evidencia_completa(client):
    cid = _componente(client)
    _protocolo(client, cid, "DQ", ["diseño documentado", "riesgos"])
    # falta un criterio → 422 (nada se declara sin evidencia)
    r = _ejecuta(client, cid, "DQ", "laboratorio",
                 [{"criterio": "diseño documentado", "cumple": True}])
    assert r.status_code == 422
    # criterio no cumplido → etapa no_superada, permanece pendiente
    r = _ejecuta(client, cid, "DQ", "laboratorio", [
        {"criterio": "diseño documentado", "cumple": True,
         "evidencia_ref": "doc-001"},
        {"criterio": "riesgos", "cumple": False, "detalle": "pendiente"},
    ])
    assert r.status_code == 201 and r.json()["estado"] == "no_superada"
    estado = client.get(
        f"/api/v1/qualification/components/{cid}/status").json()
    assert estado["calificado"] is False
    assert estado["siguiente_etapa"] == "DQ"
    # segunda ejecución con todo cumplido → superada
    r = _ejecuta(client, cid, "DQ", "laboratorio", [
        {"criterio": "diseño documentado", "cumple": True},
        {"criterio": "riesgos", "cumple": True},
    ])
    assert r.json()["estado"] == "superada"


def test_pq_exige_condiciones_reales(client):
    cid = _componente(client)
    for etapa in ("DQ", "IQ", "OQ"):
        _protocolo(client, cid, etapa, [f"criterio-{etapa}"])
        r = _ejecuta(client, cid, etapa, "laboratorio",
                     [{"criterio": f"criterio-{etapa}", "cumple": True}])
        assert r.json()["estado"] == "superada"
    _protocolo(client, cid, "PQ", ["rendimiento bajo carga real"])
    # PQ en entorno simulado → se registra pero NO se declara superada
    r = _ejecuta(client, cid, "PQ", "simulado",
                 [{"criterio": "rendimiento bajo carga real",
                   "cumple": True}])
    assert r.status_code == 201 and r.json()["estado"] == "no_superada"
    estado = client.get(
        f"/api/v1/qualification/components/{cid}/status").json()
    assert estado["calificado"] is False
    assert estado["siguiente_etapa"] == "PQ"


def test_flujo_completo_califica_componente(client):
    cid = _componente(client)
    entornos = {"DQ": "laboratorio", "IQ": "condiciones_reales",
                "OQ": "condiciones_reales", "PQ": "condiciones_reales"}
    for etapa in ("DQ", "IQ", "OQ", "PQ"):
        _protocolo(client, cid, etapa, [f"criterio-{etapa}"])
        r = _ejecuta(client, cid, etapa, entornos[etapa],
                     [{"criterio": f"criterio-{etapa}", "cumple": True,
                       "evidencia_ref": f"ev-{etapa}"}])
        assert r.json()["estado"] == "superada", etapa
    estado = client.get(
        f"/api/v1/qualification/components/{cid}/status").json()
    assert estado["calificado"] is True
    assert estado["siguiente_etapa"] is None
    assert estado["etapas"]["PQ"]["entorno"] == "condiciones_reales"


def test_expediente_estructurado_para_rcae(client):
    cid = _componente(client)
    _protocolo(client, cid, "DQ", ["diseño documentado"])
    _ejecuta(client, cid, "DQ", "laboratorio",
             [{"criterio": "diseño documentado", "cumple": True,
               "evidencia_ref": "doc-001"}])
    exp = client.get(
        f"/api/v1/qualification/components/{cid}/dossier").json()
    assert exp["origen"] == "qualification_engine"
    assert exp["tipo_evidencia"] == "expediente_calificacion"
    assert exp["protocolos"]["DQ"][0]["criterios"] == ["diseño documentado"]
    assert exp["ejecuciones"][0]["estado"] == "superada"
    # la evidencia del expediente es integrable al RCAE del mismo servicio
    r = client.post("/api/v1/compliance/evidences", json={
        "evidencia_id": "ev-dq-cyclotron-01",
        "tipo": "registro_electronico",
        "origen": exp["origen"],
        "referencia": "dossier:cyclotron-01"})
    assert r.status_code == 201


def test_auditoria_alcoa_y_meta(client):
    cid = _componente(client)
    _protocolo(client, cid, "DQ", ["diseño documentado"])
    audit = client.get("/api/v1/qualification/audit").json()
    acciones = [a["accion"] for a in audit]
    assert acciones == ["componente_registrado", "protocolo_definido"]
    for a in audit:
        assert all(k in a for k in ("evento_id", "accion", "detalle",
                                    "actor", "timestamp", "version_motor"))
    meta = client.get("/api/v1/qualification/meta").json()
    assert meta["etapas"] == ["DQ", "IQ", "OQ", "PQ"]
    assert "condiciones_reales" in meta["entornos"]
