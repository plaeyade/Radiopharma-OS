"""
Tests del Data Lake Service: dominio ALCOA+, repositorio SQL (SQLite) y API.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.domain.entities import (BatchRecord, BatchStatus, BeamParameters,
                                 DatasetLineage, ProductionResults)
from tests.test_jwt_guard import auth_headers


def _record(batch_id="B-20260718-TEST0001") -> BatchRecord:
    return BatchRecord(
        batch_id=batch_id,
        created_at=datetime(2026, 7, 18, 12, 0, 0, tzinfo=timezone.utc),
        created_by="operador.ciclotron",
        reaction_id="o18_p_n_f18", target_id="h2_18o", product_nuclide="18F",
        beam=BeamParameters(beam_energy_mev=16.5, current_ua=37.0,
                            irradiation_time_min=60.0),
        results=ProductionResults(
            saturation_yield_mbq_ua=9336.8, eob_activity_gbq=108.947,
            eob_activity_gbq_uncertainty=8.095, saturation_factor=0.31537,
            relative_uncertainty=0.0743),
        lineage=DatasetLineage(dataset_id="o18_p_n_f18_iaea2021",
                               dataset_sha256="abc123",
                               stopping_source="CATIMA/ATIMA (pycatima 1.981)"),
    ).with_integrity()


# ---------------- dominio ----------------

def test_hash_integridad_estable():
    r = _record()
    assert r.record_hash == r.compute_hash()
    assert len(r.record_hash) == 64


def test_hash_cambia_con_contenido():
    r1 = _record()
    r2 = BatchRecord(
        batch_id=r1.batch_id, created_at=r1.created_at, created_by="otro.operador",
        reaction_id=r1.reaction_id, target_id=r1.target_id,
        product_nuclide=r1.product_nuclide, beam=r1.beam, results=r1.results,
        lineage=r1.lineage).with_integrity()
    assert r1.record_hash != r2.record_hash


def test_estado_inicial_completed():
    assert _record().status == BatchStatus.COMPLETED


# ---------------- API + SQLite + local store ----------------

@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "objects"))
    # recargar settings y app con el entorno de test
    import importlib
    import app.config as config
    importlib.reload(config)
    import app.main as main
    importlib.reload(main)
    with TestClient(main.app) as c:
        yield c


def _payload():
    return {
        "created_by": "operador.ciclotron",
        "reaction_id": "o18_p_n_f18", "target_id": "h2_18o",
        "product_nuclide": "18F",
        "beam": {"beam_energy_mev": 16.5, "current_ua": 37.0,
                 "irradiation_time_min": 60.0},
        "results": {"saturation_yield_mbq_ua": 9336.8,
                    "eob_activity_gbq": 108.947,
                    "eob_activity_gbq_uncertainty": 8.095,
                    "saturation_factor": 0.31537,
                    "relative_uncertainty": 0.0743},
        "lineage": {"dataset_id": "o18_p_n_f18_iaea2021",
                    "dataset_sha256": "abc123",
                    "stopping_source": "CATIMA/ATIMA (pycatima 1.981)"},
    }


def test_health(client):
    assert client.get("/health").status_code == 200


def test_registrar_y_recuperar_lote(client):
    r = client.post("/api/v1/batches", json=_payload(),
                    headers=auth_headers("operador", "operador.ciclotron"))
    assert r.status_code == 201
    body = r.json()
    assert body["batch_id"].startswith("B-")
    assert body["integrity_ok"] is True
    assert body["status"] == "completed"
    assert len(body["record_hash"]) == 64

    # ALCOA+ atribuible: created_by viene del token, no del payload
    assert body["created_by"] == "operador.ciclotron"

    g = client.get(f"/api/v1/batches/{body['batch_id']}",
                   headers=auth_headers())
    assert g.status_code == 200
    assert g.json()["record_hash"] == body["record_hash"]


def test_listar_con_filtro(client):
    client.post("/api/v1/batches", json=_payload(), headers=auth_headers())
    r = client.get("/api/v1/batches?reaction_id=o18_p_n_f18",
                   headers=auth_headers())
    assert len(r.json()) == 1
    r = client.get("/api/v1/batches?reaction_id=n14_p_a_c11",
                   headers=auth_headers())
    assert len(r.json()) == 0


def test_void_sin_delete(client):
    r = client.post("/api/v1/batches", json=_payload(), headers=auth_headers())
    bid = r.json()["batch_id"]
    v = client.post(f"/api/v1/batches/{bid}/void",
                    json={"reason": "Captura duplicada por error"},
                    headers=auth_headers("calidad", "calidad.jefe"))
    assert v.status_code == 200
    assert v.json()["status"] == "voided"
    assert v.json()["void_reason"].startswith("Captura")
    # el registro sigue existiendo (ALCOA+: nada se borra)
    assert client.get(f"/api/v1/batches/{bid}",
                      headers=auth_headers()).status_code == 200


def test_void_requiere_motivo(client):
    r = client.post("/api/v1/batches", json=_payload(), headers=auth_headers())
    bid = r.json()["batch_id"]
    v = client.post(f"/api/v1/batches/{bid}/void", json={"reason": "x"},
                    headers=auth_headers("calidad"))
    assert v.status_code == 422


def test_artefacto_json_descargable(client):
    r = client.post("/api/v1/batches", json=_payload(), headers=auth_headers())
    bid = r.json()["batch_id"]
    a = client.get(f"/api/v1/batches/{bid}/artifact", headers=auth_headers())
    assert a.status_code == 200
    import json as _json
    artifact = a.json()
    assert artifact["reaction_id"] == "o18_p_n_f18"
    assert artifact["results"]["eob_activity_gbq"] == 108.947


# ---------------- autorización ----------------

def test_sin_token_401(client):
    assert client.post("/api/v1/batches", json=_payload()).status_code == 401
    assert client.get("/api/v1/batches").status_code == 401


def test_token_malo_401(client):
    r = client.get("/api/v1/batches",
                   headers={"Authorization": "Bearer token-falso"})
    assert r.status_code == 401


def test_void_prohibido_para_operador(client):
    r = client.post("/api/v1/batches", json=_payload(), headers=auth_headers())
    bid = r.json()["batch_id"]
    v = client.post(f"/api/v1/batches/{bid}/void",
                    json={"reason": "Intento con rol insuficiente"},
                    headers=auth_headers("operador"))
    assert v.status_code == 403


# ---------------- ciclo QC + liberación GMP ----------------

def _crear_lote(client):
    r = client.post("/api/v1/batches", json=_payload(), headers=auth_headers())
    return r.json()["batch_id"]


def _qc_payload(status="pass"):
    return {"product": "fdg", "nuclide": "18F", "overall_status": status,
            "rules": [{"parameter": "ph", "measured": 6.8, "status": "pass",
                       "detail": "dentro de límite", "limits": "[4.5, 8.5]",
                       "source": "test"}],
            "half_life_fit": {"half_life_min": 109.7, "within_tolerance": True}}


def test_registrar_y_listar_qc(client):
    bid = _crear_lote(client)
    r = client.post(f"/api/v1/batches/{bid}/qc-reports",
                    json=_qc_payload(), headers=auth_headers("operador", "qc.analista"))
    assert r.status_code == 201
    body = r.json()
    assert body["integrity_ok"] is True
    assert body["created_by"] == "qc.analista"
    lst = client.get(f"/api/v1/batches/{bid}/qc-reports", headers=auth_headers())
    assert len(lst.json()) == 1


def test_qc_sobre_lote_inexistente_404(client):
    r = client.post("/api/v1/batches/B-INEXISTENTE/qc-reports",
                    json=_qc_payload(), headers=auth_headers())
    assert r.status_code == 404


def test_liberacion_requiere_qc_pass(client):
    """GMP: sin informe QC 'pass' no se puede liberar."""
    bid = _crear_lote(client)
    r = client.post(f"/api/v1/batches/{bid}/release",
                    json={"decision": "released"},
                    headers=auth_headers("calidad", "qa.jefe"))
    assert r.status_code == 422
    # con QC fail tampoco
    client.post(f"/api/v1/batches/{bid}/qc-reports",
                json=_qc_payload("fail"), headers=auth_headers())
    r = client.post(f"/api/v1/batches/{bid}/release",
                    json={"decision": "released"},
                    headers=auth_headers("calidad"))
    assert r.status_code == 422


def test_ciclo_completo_liberacion(client):
    """lote -> QC pass -> liberado por calidad -> inmutable."""
    bid = _crear_lote(client)
    client.post(f"/api/v1/batches/{bid}/qc-reports",
                json=_qc_payload("pass"), headers=auth_headers())
    r = client.post(f"/api/v1/batches/{bid}/release",
                    json={"decision": "released", "reason": "Conforme a QC"},
                    headers=auth_headers("calidad", "qa.jefe"))
    assert r.status_code == 200
    body = r.json()
    assert body["release_status"] == "released"
    assert body["released_by"] == "qa.jefe"
    # doble liberación prohibida
    r2 = client.post(f"/api/v1/batches/{bid}/release",
                     json={"decision": "released"},
                     headers=auth_headers("calidad"))
    assert r2.status_code == 422
    # no se puede anular un lote liberado
    v = client.post(f"/api/v1/batches/{bid}/void",
                    json={"reason": "Intento de anulación tardía"},
                    headers=auth_headers("calidad"))
    assert v.status_code == 422


def test_rechazo_exige_motivo(client):
    bid = _crear_lote(client)
    r = client.post(f"/api/v1/batches/{bid}/release",
                    json={"decision": "rejected"},
                    headers=auth_headers("calidad"))
    assert r.status_code == 422
    r = client.post(f"/api/v1/batches/{bid}/release",
                    json={"decision": "rejected", "reason": "QC falló pureza"},
                    headers=auth_headers("calidad"))
    assert r.status_code == 200
    assert r.json()["release_status"] == "rejected"


def test_liberar_requiere_calidad(client):
    bid = _crear_lote(client)
    r = client.post(f"/api/v1/batches/{bid}/release",
                    json={"decision": "released"},
                    headers=auth_headers("operador"))
    assert r.status_code == 403
