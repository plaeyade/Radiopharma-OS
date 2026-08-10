"""Tests del Regulatory Compliance & Audit Engine (EDS cap. 49).

Verifica: Requirement Registry versionado 49.6/49.12, evidencias
vinculadas a su origen 49.8/49.13, evaluación que exige evidencia
49.18 con marcador honesto no_demostrable, tablero sin inflar,
expedientes de auditoría 49.9 con hallazgos, CAPA vinculada al
hallazgo 49.10 (cierre bloqueado sin CAPA), expediente de inspección
honesto 49.11 y audit trail 49.20.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.presentation.routers import compliance_api


@pytest.fixture()
def client() -> TestClient:
    compliance_api.init()
    c = TestClient(app)
    # requisito con evidencia demostrable
    assert c.post("/api/v1/compliance/requirements", json={
        "requisito_id": "GMP-QC-001", "fuente": "EU GMP Part I",
        "version": "2022-rev1", "vigencia_desde": "2023-01-01",
        "alcance": "liberación de lotes",
        "descripcion": "La liberación exige especificaciones aprobadas"
        }).status_code == 201
    assert c.post("/api/v1/compliance/evidences", json={
        "evidencia_id": "ev-qc-rel-1", "tipo": "registro_electronico",
        "origen": "qc_engine:/api/v1/qc/release",
        "referencia": "release-batch-42"}).status_code == 201
    # requisito NO demostrable en sandbox (honesto)
    assert c.post("/api/v1/compliance/requirements", json={
        "requisito_id": "REG-PQ-001", "fuente": "IAEA GSR Part 3",
        "version": "2014", "vigencia_desde": "2014-07-01",
        "alcance": "calificación de desempeño (PQ)",
        "descripcion": "PQ en entorno real"}).status_code == 201
    return c


def test_requisitos_versionados_nunca_sobrescriben(client: TestClient) -> None:
    r = client.post("/api/v1/compliance/requirements", json={
        "requisito_id": "GMP-QC-001", "fuente": "EU GMP Part I",
        "version": "2022-rev1", "vigencia_desde": "2023-06-01",
        "alcance": "otro"})
    assert r.status_code == 422
    r = client.post("/api/v1/compliance/requirements", json={
        "requisito_id": "GMP-QC-001", "fuente": "EU GMP Part I",
        "version": "2025-rev2", "vigencia_desde": "2025-01-01",
        "alcance": "liberación de lotes (revisada)"})
    assert r.status_code == 201
    assert r.json()["n_revisiones"] == 2
    reqs = client.get("/api/v1/compliance/requirements").json()
    gmp = next(x for x in reqs if x["requisito_id"] == "GMP-QC-001")
    assert gmp["version_vigente"] == "2025-rev2"
    assert gmp["revisiones"] == ["2022-rev1", "2025-rev2"]


def test_evidencia_exige_origen(client: TestClient) -> None:
    r = client.post("/api/v1/compliance/evidences", json={
        "evidencia_id": "ev-huerfana", "tipo": "reporte",
        "origen": "", "referencia": "x"})
    assert r.status_code == 422
    assert "origen" in r.json()["detail"]


def test_evaluacion_exige_evidencia_vinculada(client: TestClient) -> None:
    # sin vínculo: no se puede declarar cumplimiento (49.18)
    r = client.post("/api/v1/compliance/requirements/GMP-QC-001/assess",
                    json={"estado": "cumple", "responsable": "rp-qc"})
    assert r.status_code == 422
    assert "49.18" in r.json()["detail"]
    # tras vincular: evaluación válida
    client.post("/api/v1/compliance/requirements/GMP-QC-001/link",
                json={"evidencia_id": "ev-qc-rel-1"})
    r = client.post("/api/v1/compliance/requirements/GMP-QC-001/assess",
                    json={"estado": "cumple", "responsable": "rp-qc",
                          "usuario": "jefe-calidad"})
    assert r.status_code == 200
    assert r.json()["estado"] == "cumple"


def test_marcador_honesto_no_demostrable(client: TestClient) -> None:
    r = client.post("/api/v1/compliance/requirements/REG-PQ-001/assess",
                    json={"estado": "no_demostrable", "responsable": "rp",
                          "nota": "exige entorno real"})
    assert r.status_code == 200
    # el otro requisito queda evaluado como cumple con su evidencia
    client.post("/api/v1/compliance/requirements/GMP-QC-001/link",
                json={"evidencia_id": "ev-qc-rel-1"})
    client.post("/api/v1/compliance/requirements/GMP-QC-001/assess",
                json={"estado": "cumple", "responsable": "rp-qc"})
    tablero = client.get("/api/v1/compliance/dashboard").json()
    assert tablero["por_estado"]["no_demostrable"] == 1
    # cobertura excluye los no demostrables: 1/1 = 100%
    assert tablero["cobertura_pct"] == 100.0
    assert "no_demostrable" in tablero["nota"]


def test_auditoria_expediente_con_hallazgos(client: TestClient) -> None:
    assert client.post("/api/v1/compliance/audits", json={
        "auditoria_id": "aud-int-2026-03", "tipo": "interna",
        "alcance": "liberación QC", "auditor": "aud-1"}).status_code == 201
    r = client.post("/api/v1/compliance/audits/aud-int-2026-03/findings",
                    json={"hallazgo_id": "hall-1", "severidad": "mayor",
                          "descripcion": "falta revisión periódica",
                          "requisito_id": "GMP-QC-001"})
    assert r.status_code == 201
    # cierre bloqueado: hallazgo mayor sin CAPA
    r = client.post("/api/v1/compliance/audits/aud-int-2026-03/close",
                    json={})
    assert r.status_code == 422
    assert "CAPA" in r.json()["detail"]


def test_capa_vinculada_al_hallazgo(client: TestClient) -> None:
    client.post("/api/v1/compliance/audits", json={
        "auditoria_id": "aud-2", "tipo": "interna", "alcance": "QC",
        "auditor": "aud-1"})
    client.post("/api/v1/compliance/audits/aud-2/findings", json={
        "hallazgo_id": "hall-2", "severidad": "mayor",
        "descripcion": "d", "requisito_id": "GMP-QC-001"})
    # CAPA contra hallazgo inexistente: rechazada (49.10)
    r = client.post("/api/v1/compliance/capas", json={
        "capa_id": "capa-x", "auditoria_id": "aud-2",
        "hallazgo_id": "hall-inexistente", "tipo": "correctiva",
        "descripcion": "d", "responsable": "rp",
        "fecha_objetivo": "2026-12-31"})
    assert r.status_code == 422
    r = client.post("/api/v1/compliance/capas", json={
        "capa_id": "capa-1", "auditoria_id": "aud-2",
        "hallazgo_id": "hall-2", "tipo": "correctiva",
        "descripcion": "implantar revisión anual",
        "responsable": "rp-qc", "fecha_objetivo": "2026-12-31"})
    assert r.status_code == 201
    client.post("/api/v1/compliance/capas/capa-1/follow", json={
        "nota": "procedimiento redactado", "usuario": "rp-qc",
        "nuevo_estado": "en_curso"})
    # con CAPA abierta el cierre ya es posible
    r = client.post("/api/v1/compliance/audits/aud-2/close", json={})
    assert r.status_code == 200
    exp = client.get("/api/v1/compliance/audits/aud-2").json()
    assert exp["estado"] == "cerrada"
    assert exp["hallazgos"][0]["capas"] == ["capa-1"]


def test_expediente_inspeccion_honesto(client: TestClient) -> None:
    exp = client.get("/api/v1/compliance/inspection").json()
    por_id = {r["requisito_id"]: r for r in exp["requisitos"]}
    # PQ sin evidencia: marcado explícitamente
    assert por_id["REG-PQ-001"]["evidencia_pendiente"] is True
    assert exp["n_sin_evidencia"] >= 1
    assert "organismo regulador" in exp["nota"]


def test_audit_trail(client: TestClient) -> None:
    trail = client.get("/api/v1/compliance/audit-trail").json()
    acciones = {a["accion"] for a in trail}
    assert {"registrar_requisito", "registrar_evidencia"} <= acciones
    assert all(a["usuario"] and a["fecha"] for a in trail)
