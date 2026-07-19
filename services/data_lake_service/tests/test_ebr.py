"""
Tests del eBR: documento consolidado, firmas electrónicas (21 CFR Part 11)
y verificación de integridad.
"""
from __future__ import annotations

import asyncio
import dataclasses
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.application.ebr_service import EbrService
from app.domain.entities import (BatchRecord, BatchStatus, BeamParameters,
                                 DatasetLineage, ProductionResults, QcRecord,
                                 ReleaseStatus, SignatureMeaning)
from tests.test_jwt_guard import auth_headers


def run(coro):
    """Ejecuta una corrutina en tests síncronos (sin pytest-asyncio)."""
    return asyncio.run(coro)


# ------------------------------------------------------------------ fakes
class MemBatches:
    def __init__(self):
        self._d = {}

    async def save(self, r):
        self._d[r.batch_id] = r
        return r

    async def get(self, batch_id):
        return self._d.get(batch_id)

    async def list(self, reaction_id=None, limit=100):
        return list(self._d.values())

    async def void(self, batch_id, reason):
        r = self._d.get(batch_id)
        if r:
            self._d[batch_id] = dataclasses.replace(
                r, status=BatchStatus.VOIDED, void_reason=reason)
        return self._d.get(batch_id)

    async def release(self, batch_id, decision, released_by, reason):
        r = self._d.get(batch_id)
        if r:
            self._d[batch_id] = dataclasses.replace(
                r, release_status=ReleaseStatus(decision),
                released_by=released_by, release_reason=reason,
                released_at=datetime.now(timezone.utc))
        return self._d.get(batch_id)


class MemQc:
    def __init__(self):
        self._d = {}

    async def save(self, r):
        self._d[r.qc_id] = r
        return r

    async def list_for_batch(self, batch_id):
        return [r for r in self._d.values() if r.batch_id == batch_id]

    async def get(self, qc_id):
        return self._d.get(qc_id)


class MemSigs:
    def __init__(self):
        self._d = {}

    async def save(self, s):
        self._d[s.signature_id] = s
        return s

    async def list_for_batch(self, batch_id):
        return sorted((s for s in self._d.values() if s.batch_id == batch_id),
                      key=lambda s: s.signed_at)


class FakeAuth:
    """AuthVerifier de prueba: usuarios -> (contraseña, rol)."""
    USERS = {
        "operador.ciclotron": ("op-secret", "operador"),
        "supervisor.turno": ("sup-secret", "supervisor"),
        "qa.jefe": ("qa-secret", "calidad"),
    }

    def __init__(self, *args, **kwargs):
        pass

    def authenticate(self, username, password):
        rec = self.USERS.get(username)
        if rec and rec[0] == password:
            return {"username": username, "role": rec[1]}
        return None


def _record(batch_id="B-20260701-EBR00001") -> BatchRecord:
    return BatchRecord(
        batch_id=batch_id,
        created_at=datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc),
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


def _qc(batch_id, status="pass") -> QcRecord:
    return QcRecord(
        qc_id=f"QC-{batch_id}", batch_id=batch_id,
        created_at=datetime(2026, 7, 2, 13, 0, 0, tzinfo=timezone.utc),
        created_by="qc.analista", product="fdg", nuclide="18F",
        overall_status=status,
        rules=({"parameter": "ph", "status": "pass"},),
    ).with_integrity()


@pytest.fixture()
def svc():
    batches, qc, sigs = MemBatches(), MemQc(), MemSigs()
    service = EbrService(batches, qc, sigs, FakeAuth())
    return service, batches, qc, sigs


# ---------------- generación del documento ----------------

def test_ebr_no_encontrado(svc):
    service, *_ = svc
    with pytest.raises(KeyError):
        run(service.generate_ebr("B-INEXISTENTE"))


def test_ebr_consolida_lote_qc_firmas(svc):
    service, batches, qc, _ = svc
    rec = _record()
    run(batches.save(rec))
    run(qc.save(_qc(rec.batch_id)))
    sig = run(service.sign_batch(rec.batch_id, "operador.ciclotron",
                                 "op-secret", "performed_by"))

    doc = run(service.generate_ebr(rec.batch_id))
    assert doc.batch["batch_id"] == rec.batch_id
    assert doc.batch["record_hash"] == rec.record_hash
    assert len(doc.qc_reports) == 1
    assert len(doc.signatures) == 1
    assert doc.signatures[0]["signature_hash"] == sig.signature_hash
    assert len(doc.integrity["document_hash"]) == 64


def test_ebr_pista_auditoria_cronologica(svc):
    service, batches, qc, _ = svc
    rec = _record()
    run(batches.save(rec))
    run(qc.save(_qc(rec.batch_id)))
    run(service.sign_batch(rec.batch_id, "operador.ciclotron",
                           "op-secret", "performed_by"))
    doc = run(service.generate_ebr(rec.batch_id))
    acciones = [e.action for e in doc.audit_trail]
    assert acciones[0] == "batch_registered"
    assert "qc_report_registered" in acciones
    assert "signature_performed_by" in acciones
    tiempos = [e.timestamp for e in doc.audit_trail]
    assert tiempos == sorted(tiempos)


# ---------------- firma electrónica ----------------

def test_firma_vinculada_al_hash_del_registro(svc):
    service, batches, *_ = svc
    rec = _record()
    run(batches.save(rec))
    sig = run(service.sign_batch(rec.batch_id, "operador.ciclotron",
                                 "op-secret", "performed_by"))
    assert sig.record_hash_signed == rec.record_hash
    assert sig.signature_hash == sig.compute_hash()
    assert sig.meaning == SignatureMeaning.PERFORMED_BY.value


def test_firma_requiere_reautenticacion(svc):
    service, batches, *_ = svc
    rec = _record()
    run(batches.save(rec))
    with pytest.raises(PermissionError):
        run(service.sign_batch(rec.batch_id, "operador.ciclotron",
                               "password-incorrecto", "performed_by"))


def test_firma_significado_invalido(svc):
    service, batches, *_ = svc
    rec = _record()
    run(batches.save(rec))
    with pytest.raises(ValueError):
        run(service.sign_batch(rec.batch_id, "operador.ciclotron",
                               "op-secret", "firmado_como_sea"))


def test_aprobacion_requiere_rol_calidad(svc):
    service, batches, *_ = svc
    rec = _record()
    run(batches.save(rec))
    run(batches.release(rec.batch_id, "rejected", "qa.jefe", "QC falló"))
    # supervisor no basta para approved_by
    with pytest.raises(PermissionError):
        run(service.sign_batch(rec.batch_id, "supervisor.turno",
                               "sup-secret", "approved_by"))
    # calidad sí
    sig = run(service.sign_batch(rec.batch_id, "qa.jefe",
                                 "qa-secret", "approved_by"))
    assert sig.meaning == "approved_by"


def test_aprobacion_requiere_decision_previa(svc):
    service, batches, *_ = svc
    rec = _record()
    run(batches.save(rec))
    with pytest.raises(ValueError):
        run(service.sign_batch(rec.batch_id, "qa.jefe",
                               "qa-secret", "approved_by"))


def test_no_se_firma_lote_anulado(svc):
    service, batches, *_ = svc
    rec = _record()
    run(batches.save(rec))
    run(batches.void(rec.batch_id, "Captura duplicada"))
    with pytest.raises(ValueError):
        run(service.sign_batch(rec.batch_id, "operador.ciclotron",
                               "op-secret", "performed_by"))


# ---------------- verificación ----------------

def test_verificacion_todo_ok(svc):
    service, batches, qc, _ = svc
    rec = _record()
    run(batches.save(rec))
    run(qc.save(_qc(rec.batch_id)))
    run(service.sign_batch(rec.batch_id, "operador.ciclotron",
                            "op-secret", "performed_by"))
    result = run(service.verify_ebr(rec.batch_id))
    assert result["all_ok"] is True
    assert all(c["ok"] for c in result["checks"])
    sig_checks = [c for c in result["checks"] if c["item"].startswith("signature:")]
    assert sig_checks[0]["bound_record_current"] is True


def test_verificacion_detecta_firma_manipulada(svc):
    service, batches, _, sigs = svc
    rec = _record()
    run(batches.save(rec))
    sig = run(service.sign_batch(rec.batch_id, "operador.ciclotron",
                                 "op-secret", "performed_by"))
    # manipulación del hash almacenado (simula alteración en BD)
    sigs._d[sig.signature_id] = dataclasses.replace(sig, signature_hash="0" * 64)
    result = run(service.verify_ebr(rec.batch_id))
    assert result["all_ok"] is False


def test_verificacion_detecta_firma_obsoleta(svc):
    """Si el registro cambia tras la firma, la firma queda obsoleta."""
    service, batches, _, _sigs = svc
    rec = _record()
    run(batches.save(rec))
    run(service.sign_batch(rec.batch_id, "operador.ciclotron",
                           "op-secret", "performed_by"))
    # el registro cambia (nuevo hash) después de firmar
    batches._d[rec.batch_id] = dataclasses.replace(rec, record_hash="f" * 64)
    result = run(service.verify_ebr(rec.batch_id))
    sig_checks = [c for c in result["checks"] if c["item"].startswith("signature:")]
    assert sig_checks[0]["bound_record_current"] is False


# ---------------- API ----------------

@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "objects"))
    # Auth real no está disponible en tests: se inyecta el verificador falso
    monkeypatch.setattr(
        "app.infrastructure.security.auth_client.AuthServiceClient", FakeAuth)
    import importlib
    import app.config as config
    importlib.reload(config)
    import app.main as main
    importlib.reload(main)
    with TestClient(main.app) as c:
        yield c


def _payload():
    return {
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


def _lote(client):
    r = client.post("/api/v1/batches", json=_payload(),
                    headers=auth_headers("operador", "operador.ciclotron"))
    assert r.status_code == 201
    return r.json()["batch_id"]


def test_api_firmar_y_emitir_ebr(client):
    bid = _lote(client)
    r = client.post(f"/api/v1/batches/{bid}/signatures",
                    json={"username": "operador.ciclotron",
                          "password": "op-secret", "meaning": "performed_by"},
                    headers=auth_headers("operador", "operador.ciclotron"))
    assert r.status_code == 201
    body = r.json()
    assert body["signed_by"] == "operador.ciclotron"
    assert len(body["signature_hash"]) == 64

    e = client.get(f"/api/v1/batches/{bid}/ebr", headers=auth_headers())
    assert e.status_code == 200
    doc = e.json()
    assert doc["batch"]["batch_id"] == bid
    assert len(doc["signatures"]) == 1
    assert doc["audit_trail"][0]["action"] == "batch_registered"


def test_api_firmar_requiere_misma_identidad(client):
    bid = _lote(client)
    r = client.post(f"/api/v1/batches/{bid}/signatures",
                    json={"username": "qa.jefe", "password": "qa-secret",
                          "meaning": "approved_by"},
                    headers=auth_headers("operador", "operador.ciclotron"))
    assert r.status_code == 422


def test_api_firmar_password_incorrecto_403(client):
    bid = _lote(client)
    r = client.post(f"/api/v1/batches/{bid}/signatures",
                    json={"username": "operador.ciclotron",
                          "password": "malo", "meaning": "performed_by"},
                    headers=auth_headers("operador", "operador.ciclotron"))
    assert r.status_code == 403


def test_api_verificar_ebr(client):
    bid = _lote(client)
    client.post(f"/api/v1/batches/{bid}/signatures",
                json={"username": "operador.ciclotron",
                      "password": "op-secret", "meaning": "performed_by"},
                headers=auth_headers("operador", "operador.ciclotron"))
    v = client.get(f"/api/v1/batches/{bid}/ebr/verify", headers=auth_headers())
    assert v.status_code == 200
    assert v.json()["all_ok"] is True


def test_api_ebr_lote_inexistente_404(client):
    assert client.get("/api/v1/batches/B-INEXISTENTE/ebr",
                      headers=auth_headers()).status_code == 404
    assert client.get("/api/v1/batches/B-INEXISTENTE/ebr/verify",
                      headers=auth_headers()).status_code == 404
    r = client.post("/api/v1/batches/B-INEXISTENTE/signatures",
                    json={"username": "operador.ciclotron",
                          "password": "op-secret", "meaning": "performed_by"},
                    headers=auth_headers("operador", "operador.ciclotron"))
    assert r.status_code == 404


def test_api_ebr_requiere_token(client):
    assert client.get("/api/v1/batches/B-X/ebr").status_code == 401
