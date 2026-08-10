"""Tests del Multi-Agent Decision Support Engine (EDS cap. 43).

Verifica: Agent Registry versionado 43.6, honestidad `sin_runtime`
(el motor nunca inventa contribuciones), Task Planner 43.12 con
secuencia, Orchestrator 43.8, Consensus Engine 43.9 con contribuciones
individuales registradas y procedencia, Conversation Manager 43.11,
recomendación marcada como soporte a la decisión (43.3/41.9) y
auditoría de inferencias.
"""
import pytest
from fastapi.testclient import TestClient

from app.domain.agents import Agente, MultiAgentEngine
from app.main import app
from app.presentation.routers import agents_api


def _agente_qc(contexto: dict) -> dict:
    """Contribución determinista de QC: regla sobre el contexto."""
    pureza = contexto.get("pureza_radioquimica_pct")
    out = {"hallazgos": [], "alertas": [], "sugerencias": []}
    if pureza is None:
        out["alertas"].append("sin dato de pureza en el contexto")
    elif pureza < 95.0:
        out["alertas"].append(f"pureza {pureza}% por debajo de 95%")
        out["sugerencias"].append("revisar módulo de purificación")
    else:
        out["hallazgos"].append(f"pureza conforme: {pureza}%")
    return out


def _agente_prod(contexto: dict) -> dict:
    actividad = contexto.get("actividad_eob_gbq", 0.0)
    return {"hallazgos": [f"EOB {actividad} GBq"],
            "sugerencias": ["mantener plan de irradiación"]
            if actividad >= 10.0 else ["aumentar corriente de haz"],
            "alertas": [] if actividad >= 10.0 else ["EOB bajo"]}


@pytest.fixture()
def client() -> TestClient:
    motor = MultiAgentEngine()
    motor.registrar_agente(
        Agente(agente_id="ag-qc-1", dominio="control_calidad",
               version="1.0.0", capacidades=["pureza", "especificaciones"]),
        _agente_qc, "test")
    motor.registrar_agente(
        Agente(agente_id="ag-prod-1", dominio="produccion",
               version="1.0.0", capacidades=["rendimiento"]),
        _agente_prod, "test")
    motor.registrar_agente(
        Agente(agente_id="ag-reg-1", dominio="regulacion",
               version="1.0.0", capacidades=["normativa"]),
        None, "test")          # honesto: sin runtime
    agents_api.init(motor)
    return TestClient(app)


def test_agente_sin_runtime_marcado_honestamente(client: TestClient) -> None:
    agentes = client.get("/api/v1/agents").json()
    reg = next(a for a in agentes if a["agente_id"] == "ag-reg-1")
    assert reg["estado"] == "sin_runtime"
    r = client.post("/api/v1/agents/register", json={
        "agente_id": "ag-qc-1", "dominio": "control_calidad",
        "version": "2.0.0", "capacidades": ["x"]})
    assert r.status_code == 422      # nunca sobrescribe


def test_consenso_con_procedencia_y_marcador(client: TestClient) -> None:
    r = client.post("/api/v1/agents/consult", json={
        "problema": "liberar lote FDG con pureza 92%",
        "dominios": ["control_calidad", "produccion"],
        "contexto": {"pureza_radioquimica_pct": 92.0,
                     "actividad_eob_gbq": 14.0},
        "usuario": "jefe-planta"})
    assert r.status_code == 201
    conv = r.json()
    rec = conv["recomendacion"]
    assert rec["n_contribuciones"] == 2
    # procedencia preservada
    alertas = rec["alertas"]
    assert any("pureza" in a["alerta"] for a in alertas)
    assert all("origen" in a for a in alertas)
    # marcador 43.3/41.9
    assert "RECOMENDACIÓN" in conv["naturaleza"]
    assert "nunca decide" in conv["naturaleza"]
    # contribuciones individuales registradas (43.9)
    assert len(conv["contribuciones"]) == 2
    assert conv["tareas"][0]["secuencia"] == 1


def test_dominio_sin_runtime_omitido_honestamente(client: TestClient) -> None:
    r = client.post("/api/v1/agents/consult", json={
        "problema": "¿cumplimos la normativa de liberación?",
        "dominios": ["regulacion", "control_calidad"],
        "contexto": {"pureza_radioquimica_pct": 97.0},
        "usuario": "rp"})
    conv = r.json()
    omitidos = conv["dominios_omitidos"]
    assert len(omitidos) == 1
    assert omitidos[0]["dominio"] == "regulacion"
    assert "nunca inventa" in omitidos[0]["motivo"]
    # la consulta sigue adelante con los dominios disponibles
    assert conv["recomendacion"]["n_contribuciones"] == 1


def test_consulta_sin_contribuciones_rechazada(client: TestClient) -> None:
    r = client.post("/api/v1/agents/consult", json={
        "problema": "solo regulación", "dominios": ["regulacion"],
        "contexto": {}, "usuario": "rp"})
    assert r.status_code == 422
    assert "honesto" in r.json()["detail"]


def test_dominio_desconocido_rechazado(client: TestClient) -> None:
    r = client.post("/api/v1/agents/consult", json={
        "problema": "x", "dominios": ["astrologia"], "contexto": {}})
    assert r.status_code == 422


def test_conversaciones_y_auditoria(client: TestClient) -> None:
    client.post("/api/v1/agents/consult", json={
        "problema": "p1", "dominios": ["produccion"],
        "contexto": {"actividad_eob_gbq": 12.0}, "usuario": "op-1"})
    convs = client.get("/api/v1/agents/conversations").json()
    assert len(convs) == 1
    assert convs[0]["usuario"] == "op-1"
    detalle = client.get(
        f"/api/v1/agents/conversations/{convs[0]['conversacion_id']}"
        ).json()
    assert detalle["contexto"]["actividad_eob_gbq"] == 12.0   # 43.10
    aud = client.get("/api/v1/agents/audit").json()
    assert any(a["accion"] == "consultar" for a in aud)
    r = client.get("/api/v1/agents/conversations/conv-9999")
    assert r.status_code == 404
