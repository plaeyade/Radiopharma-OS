"""
Tests de eventos de proceso declarados (desviaciones de la corrida) en el
Data Lake: endpoint append-only y su integración en la pista de auditoría
del eBR (ALCOA+: actor del token, sello de tiempo de servidor).
"""
from __future__ import annotations

from app.application.ebr_service import EbrService
from tests.test_ebr import (FakeAuth, MemBatches, MemQc, MemSigs, _qc, _record,
                            client, run)   # noqa: F401  (fixture importada)
from tests.test_jwt_guard import auth_headers


class MemEvents:
    def __init__(self):
        self._d = []

    async def save(self, e):
        self._d.append(e)
        return e

    async def list_for_batch(self, batch_id):
        return [e for e in self._d if e.batch_id == batch_id]


_PAYLOAD = {
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


def _crear_lote(client) -> str:   # noqa: F811
    r = client.post("/api/v1/batches", json=_PAYLOAD,
                    headers=auth_headers("operador", "operador.ciclotron"))
    assert r.status_code == 201
    return r.json()["batch_id"]


# ---------------- servicio (integración en eBR) ----------------

def test_evento_entra_en_pista_cronologica():
    batches, qc, sigs, events = MemBatches(), MemQc(), MemSigs(), MemEvents()
    svc = EbrService(batches, qc, sigs, FakeAuth(), audit_events=events)
    rec = _record()
    run(batches.save(rec))
    e = run(svc.add_event(rec.batch_id, "operador.ciclotron",
                          "process_deviation",
                          "cooling_flow_lpm por debajo de 10.0 lpm"))
    assert e.actor == "operador.ciclotron"
    doc = run(svc.generate_ebr(rec.batch_id))
    acciones = [a.action for a in doc.audit_trail]
    assert acciones[0] == "batch_registered"
    assert "process_deviation" in acciones
    # orden cronológico: el evento va después del registro
    assert acciones.index("process_deviation") > acciones.index("batch_registered")


def test_evento_lote_inexistente_servicio():
    svc = EbrService(MemBatches(), MemQc(), MemSigs(), FakeAuth(),
                     audit_events=MemEvents())
    try:
        run(svc.add_event("B-NOPE", "x", "process_deviation", "detalle"))
        assert False, "debió lanzar KeyError"
    except KeyError:
        pass


def test_sin_repo_eventos_ebr_sigue_funcionando():
    batches, qc, sigs = MemBatches(), MemQc(), MemSigs()
    svc = EbrService(batches, qc, sigs, FakeAuth())   # sin repo de eventos
    rec = _record()
    run(batches.save(rec))
    run(qc.save(_qc(rec.batch_id)))
    doc = run(svc.generate_ebr(rec.batch_id))
    assert len(doc.audit_trail) == 2  # registro + informe QC


# ---------------- API ----------------

def test_api_declarar_evento(client):   # noqa: F811
    bid = _crear_lote(client)
    r = client.post(f"/api/v1/batches/{bid}/events",
                    json={"action": "process_deviation",
                          "detail": "cooling_flow_lpm por debajo de 10.0 lpm "
                                    "(extremo 8.4, 3 puntos)"},
                    headers=auth_headers("operador", "operador.ciclotron"))
    assert r.status_code == 201
    body = r.json()
    assert body["actor"] == "operador.ciclotron"      # actor del token
    assert body["action"] == "process_deviation"
    assert body["timestamp"]                          # sello de servidor
    # el evento aparece en la pista del eBR
    e = client.get(f"/api/v1/batches/{bid}/ebr", headers=auth_headers())
    assert e.status_code == 200
    trail = e.json()["audit_trail"]
    assert any(ev["action"] == "process_deviation"
               and "cooling_flow_lpm" in ev["detail"] for ev in trail)


def test_api_evento_lote_inexistente_404(client):   # noqa: F811
    r = client.post("/api/v1/batches/B-NOPE/events",
                    json={"action": "process_deviation", "detail": "x"},
                    headers=auth_headers("operador", "operador.ciclotron"))
    assert r.status_code == 404


def test_api_evento_action_invalida_422(client):   # noqa: F811
    bid = _crear_lote(client)
    r = client.post(f"/api/v1/batches/{bid}/events",
                    json={"action": "Process Deviation!", "detail": "x"},
                    headers=auth_headers("operador", "operador.ciclotron"))
    assert r.status_code == 422


def test_api_evento_sin_token_401(client):   # noqa: F811
    bid = _crear_lote(client)
    r = client.post(f"/api/v1/batches/{bid}/events",
                    json={"action": "process_deviation", "detail": "x"})
    assert r.status_code in (401, 403)
