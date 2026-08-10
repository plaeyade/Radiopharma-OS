"""Tests del Business Continuity, DR & Resilience Engine (EDS cap. 50).

Verifica: planes versionados 50.6 con aprobación validada 50.19,
respaldo REAL con verificación sha256 50.8 (nunca declarado sin
verificar), eventos DR documentados 50.7/50.12, estado honesto de
replicación 50.9, chequeo REAL de disponibilidad /health 50.10 e
indicadores de resiliencia sobre eventos reales 50.11 (null honesto
sin eventos).
"""
import os

import pytest
from fastapi.testclient import TestClient

from app.domain.bcdr import BcdrEngine
from app.main import app
from app.presentation.routers import bcdr_api


@pytest.fixture()
def client(tmp_path) -> TestClient:
    bcdr_api.init(BcdrEngine(backup_root=str(tmp_path / "backups")))
    c = TestClient(app)
    assert c.post("/api/v1/bcdr/backup-policies", json={
        "politica_id": "bk-db-diario", "dominio": "bases_de_datos",
        "frecuencia": "diario", "retencion_dias": 30,
        "destino": "backups/db"}).status_code == 201
    return c


def test_planes_versionados_y_aprobacion(client: TestClient) -> None:
    r = client.post("/api/v1/bcdr/plans", json={
        "plan_id": "bcp-planta", "alcance": "planta completa",
        "responsables": ["cio", "jefe-planta"],
        "procedimientos": ["activar sitio secundario"],
        "prioridades": ["qc", "produccion"], "rto_min": 240.0,
        "rpo_min": 60.0, "version": "1.0.0"})
    assert r.status_code == 201
    assert client.post("/api/v1/bcdr/plans/bcp-planta/approve",
                       json={"usuario": "comite"}).json()[
                           "estado"] == "aprobado"
    # misma versión: nunca sobrescribe
    assert client.post("/api/v1/bcdr/plans", json={
        "plan_id": "bcp-planta", "alcance": "x",
        "responsables": ["a"], "procedimientos": ["b"],
        "prioridades": ["c"], "version": "1.0.0"}).status_code == 422


def test_plan_incompleto_queda_en_revision(client: TestClient) -> None:
    client.post("/api/v1/bcdr/plans", json={
        "plan_id": "bcp-incompleto", "alcance": "ti",
        "responsables": ["cio"], "procedimientos": ["x"],
        "prioridades": ["y"], "version": "1.0.0"})   # sin RTO/RPO
    r = client.post("/api/v1/bcdr/plans/bcp-incompleto/approve", json={})
    assert r.status_code == 422
    assert "rto_min" in r.json()["detail"]
    planes = client.get("/api/v1/bcdr/plans").json()
    assert planes[0]["estado"] == "revision"


def test_backup_real_con_verificacion_sha256(client: TestClient,
                                             tmp_path) -> None:
    origen = tmp_path / "radiopharma.db"
    origen.write_bytes(os.urandom(4096))
    r = client.post("/api/v1/bcdr/backups", json={
        "politica_id": "bk-db-diario", "ruta_origen": str(origen),
        "usuario": "backup-job"})
    assert r.status_code == 201
    reg = r.json()
    assert reg["verificado"] is True
    assert os.path.isfile(reg["destino"])
    import hashlib
    assert hashlib.sha256(open(reg["destino"], "rb").read()
                          ).hexdigest() == reg["sha256"]
    # origen inexistente: error honesto, no respaldo ficticio
    r2 = client.post("/api/v1/bcdr/backups", json={
        "politica_id": "bk-db-diario", "ruta_origen": "/no/existe.db"})
    assert r2.status_code == 422


def test_eventos_dr_con_duracion(client: TestClient) -> None:
    assert client.post("/api/v1/bcdr/dr-events", json={
        "evento_id": "dr-2026-001", "tipo": "restauracion",
        "descripcion": "caída del volumen principal",
        "inicio": "2026-08-01T03:00:00+00:00"}).status_code == 201
    r = client.post("/api/v1/bcdr/dr-events/dr-2026-001/close",
                    json={"fin": "2026-08-01T05:30:00+00:00"})
    assert r.json()["duracion_min"] == pytest.approx(150.0)
    assert client.post("/api/v1/bcdr/dr-events", json={
        "evento_id": "dr-x", "tipo": "inventado", "descripcion": "d",
        "inicio": "2026-08-01T00:00:00+00:00"}).status_code == 422


def test_replicacion_estado_honesto(client: TestClient) -> None:
    est = client.get("/api/v1/bcdr/replication").json()
    assert est["estado"] == "no_configurada"
    assert "no declara" in est["nota"]
    client.post("/api/v1/bcdr/replication", json={
        "estrategia": "asíncrona", "destinos": ["sitio-secundario"]})
    est2 = client.get("/api/v1/bcdr/replication").json()
    assert est2["estado"] == "configurada"


def test_ha_check_real(client: TestClient) -> None:
    # servicio real: el propio /health del TestClient
    base = str(client.base_url).rstrip("/")
    assert client.post("/api/v1/bcdr/ha-services", json={
        "nombre": "data-lake", "health_url": f"{base}/health"}
        ).status_code == 201
    assert client.post("/api/v1/bcdr/ha-services", json={
        "nombre": "yield-engine",
        "health_url": "http://127.0.0.1:9/health"}).status_code == 201
    r = client.get("/api/v1/bcdr/ha-check").json()
    assert r["total"] == 2
    # el servicio caído se reporta como no disponible, nunca simulado
    assert r["servicios"]["yield-engine"]["disponible"] is False


def test_resiliencia_null_honesto_sin_eventos(client: TestClient) -> None:
    r = client.get("/api/v1/bcdr/resilience").json()
    assert r["mttr_min"] is None          # nunca estimado
    assert r["eventos_cerrados"] == 0
    client.post("/api/v1/bcdr/dr-events", json={
        "evento_id": "dr-1", "tipo": "recuperacion_servicio",
        "descripcion": "d", "inicio": "2026-08-01T00:00:00+00:00"})
    client.post("/api/v1/bcdr/dr-events/dr-1/close",
                json={"fin": "2026-08-01T01:00:00+00:00"})
    r2 = client.get("/api/v1/bcdr/resilience").json()
    assert r2["mttr_min"] == pytest.approx(60.0)
    assert r2["replicacion"] == "no_configurada"


def test_auditoria_bcdr(client: TestClient) -> None:
    aud = client.get("/api/v1/bcdr/audit").json()
    assert any(a["accion"] == "registrar_politica_backup" for a in aud)
    assert all(a["fecha"] for a in aud)
