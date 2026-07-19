"""
Tests del alertado activo: reglas validadas (código), persistencia,
registro en la pista de auditoría del eBR (ALCOA+), webhook best-effort
y endpoints de consulta/reconocimiento.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

from app.application.alert_service import RULES, AlertService
from app.application.ebr_service import EbrService
from tests.test_ebr import (FakeAuth, MemBatches, MemQc, MemSigs, _lote,
                            _record, client, run)  # noqa: F401 (fixture)
from tests.test_jwt_guard import auth_headers


class MemAlerts:
    def __init__(self):
        self._d = {}

    async def save(self, a):
        self._d[a.alert_id] = a
        return a

    async def get(self, alert_id):
        return self._d.get(alert_id)

    async def list(self, severity=None, only_unacked=False, limit=100):
        out = sorted(self._d.values(), key=lambda a: a.timestamp,
                     reverse=True)
        if severity is not None:
            out = [a for a in out if a.severity == severity]
        if only_unacked:
            out = [a for a in out if a.acked_by is None]
        return out[:limit]

    async def ack(self, alert_id, username):
        a = self._d.get(alert_id)
        if a is not None and a.acked_by is None:
            a = dataclasses.replace(
                a, acked_by=username, acked_at=datetime.now(timezone.utc))
            self._d[alert_id] = a
        return a


class MemEvents:
    def __init__(self):
        self._d = []

    async def save(self, e):
        self._d.append(e)
        return e

    async def list_for_batch(self, batch_id):
        return [e for e in self._d if e.batch_id == batch_id]


def _service(sender=None, webhook_url=None):
    repo = MemAlerts()
    svc = AlertService(repo, webhook_url=webhook_url, sender=sender)
    return svc, repo


# ---------------- reglas (unidad) ----------------

def test_regla_desviacion_critica():
    svc, repo = _service()
    a = run(svc.on_event("B-1", "process_deviation",
                         "cooling_flow_lpm por debajo de 10.0",
                         "operador.ciclotron"))
    assert a is not None
    assert a.rule == "desviacion_proceso" and a.severity == "critica"
    assert a.batch_id == "B-1" and a.acked_by is None
    assert run(repo.list()) == [a]


def test_regla_desviacion_palabra_espanol():
    svc, _ = _service()
    a = run(svc.on_event("B-1", "incidencia",
                         "Desviación de vacío en target", "op"))
    assert a is not None and a.rule == "desviacion_proceso"


def test_evento_normal_no_alerta():
    svc, repo = _service()
    a = run(svc.on_event("B-1", "observacion", "corrida nominal", "op"))
    assert a is None
    assert run(repo.list()) == []


def test_regla_qc_fail_critica():
    svc, _ = _service()
    a = run(svc.on_qc("B-1", "18F", "fail", "qc.analista"))
    assert a is not None
    assert a.rule == "qc_fail" and a.severity == "critica"


def test_regla_qc_warning_aviso():
    svc, _ = _service()
    a = run(svc.on_qc("B-1", "18F", "warning", "qc.analista"))
    assert a is not None
    assert a.rule == "qc_warning" and a.severity == "aviso"


def test_qc_pass_no_alerta():
    svc, _ = _service()
    assert run(svc.on_qc("B-1", "18F", "pass", "qc.analista")) is None


def test_regla_lote_anulado():
    svc, _ = _service()
    a = run(svc.on_void("B-1", "registro duplicado", "qa.jefe"))
    assert a.rule == "lote_anulado" and a.severity == "aviso"
    assert "registro duplicado" in a.message


def test_ack_idempotente_conserva_original():
    svc, _ = _service()
    a = run(svc.on_void("B-1", "motivo", "qa.jefe"))
    a1 = run(svc.ack(a.alert_id, "supervisor.turno"))
    assert a1.acked_by == "supervisor.turno" and a1.acked_at is not None
    a2 = run(svc.ack(a.alert_id, "otro.usuario"))
    assert a2.acked_by == "supervisor.turno"  # el original prevalece
    assert a2.acked_at == a1.acked_at
    assert run(svc.ack("AL-INEXISTENTE", "x")) is None


# ---------------- webhook (best-effort) ----------------

def test_webhook_despacha_payload():
    enviados = []
    svc, _ = _service(sender=lambda url, p: enviados.append((url, p)),
                      webhook_url="https://hooks.example/alertas")
    a = run(svc.on_qc("B-9", "18F", "fail", "qc.analista"))
    assert len(enviados) == 1
    url, p = enviados[0]
    assert url == "https://hooks.example/alertas"
    assert p["alert_id"] == a.alert_id and p["rule"] == "qc_fail"
    assert p["severity"] == "critica" and p["batch_id"] == "B-9"


def test_webhook_fallo_nunca_propaga():
    def malo(url, p):
        raise ConnectionError("sin red")

    svc, repo = _service(sender=malo, webhook_url="https://x")
    a = run(svc.on_void("B-1", "motivo", "qa.jefe"))  # no lanza
    assert run(repo.list()) == [a]  # la alerta quedó persistida


def test_sin_webhook_no_despacha():
    svc, _ = _service()
    # sin URL ni sender: no debe fallar
    run(svc.on_void("B-1", "motivo", "qa.jefe"))


# ---------------- integración eBR (ALCOA+) ----------------

def test_alerta_entra_en_pista_ebr():
    batches, qc, sigs, events = MemBatches(), MemQc(), MemSigs(), MemEvents()
    ebr = EbrService(batches, qc, sigs, FakeAuth(), audit_events=events)
    svc = AlertService(MemAlerts(), ebr=ebr)
    rec = _record()
    run(batches.save(rec))
    run(svc.on_event(rec.batch_id, "process_deviation",
                     "presión de target inestable", "operador.ciclotron"))
    doc = run(ebr.generate_ebr(rec.batch_id))
    acciones = [(e.actor, e.action) for e in doc.audit_trail]
    assert ("sistema", "alerta_disparada") in acciones


# ---------------- API ----------------

_OP = auth_headers("operador", "operador.ciclotron")
_QA = auth_headers("calidad", "qa.jefe")


def test_api_alerta_por_desviacion_ack_y_filtros(client):  # noqa: F811
    bid = _lote(client)
    r = client.post(f"/api/v1/batches/{bid}/events",
                    json={"action": "process_deviation",
                          "detail": "cooling_flow_lpm por debajo de 10.0"},
                    headers=_OP)
    assert r.status_code == 201

    r = client.get("/api/v1/alerts", headers=_OP)
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    a = items[0]
    assert a["rule"] == "desviacion_proceso" and a["severity"] == "critica"
    assert a["acked_by"] is None

    # la alerta quedó en la pista de auditoría del eBR
    r = client.get(f"/api/v1/batches/{bid}/ebr", headers=_OP)
    assert "alerta_disparada" in [e["action"]
                                  for e in r.json()["audit_trail"]]

    # reconocimiento atribuible e idempotente
    r = client.post(f"/api/v1/alerts/{a['alert_id']}/ack", headers=_OP)
    assert r.status_code == 200
    assert r.json()["acked_by"] == "operador.ciclotron"
    assert client.get("/api/v1/alerts?only_unacked=true",
                      headers=_OP).json() == []
    assert client.get("/api/v1/alerts?severity=critica",
                      headers=_OP).json()[0]["alert_id"] == a["alert_id"]


def test_api_alerta_qc_fail(client):  # noqa: F811
    bid = _lote(client)
    r = client.post(f"/api/v1/batches/{bid}/qc-reports",
                    json={"product": "fdg", "nuclide": "18F",
                          "overall_status": "fail",
                          "rules": [{"parameter": "ph", "status": "fail"}]},
                    headers=_OP)
    assert r.status_code == 201
    items = client.get("/api/v1/alerts", headers=_OP).json()
    assert [a["rule"] for a in items] == ["qc_fail"]
    assert items[0]["severity"] == "critica"


def test_api_alerta_qc_warning_y_pass_sin_alerta(client):  # noqa: F811
    bid = _lote(client)
    client.post(f"/api/v1/batches/{bid}/qc-reports",
                json={"product": "fdg", "nuclide": "18F",
                      "overall_status": "warning", "rules": []},
                headers=_OP)
    client.post(f"/api/v1/batches/{bid}/qc-reports",
                json={"product": "fdg", "nuclide": "18F",
                      "overall_status": "pass", "rules": []},
                headers=_OP)
    items = client.get("/api/v1/alerts", headers=_OP).json()
    assert [a["rule"] for a in items] == ["qc_warning"]


def test_api_alerta_lote_anulado(client):  # noqa: F811
    bid = _lote(client)
    r = client.post(f"/api/v1/batches/{bid}/void",
                    json={"reason": "registro duplicado"}, headers=_QA)
    assert r.status_code == 200
    items = client.get("/api/v1/alerts", headers=_OP).json()
    assert [a["rule"] for a in items] == ["lote_anulado"]
    assert "registro duplicado" in items[0]["message"]


def test_api_reglas_catalogo(client):  # noqa: F811
    r = client.get("/api/v1/alerts/rules", headers=_OP)
    assert r.status_code == 200
    reglas = {x["rule"] for x in r.json()}
    assert reglas == {x["rule"] for x in RULES}


def test_api_ack_404_y_sin_token(client):  # noqa: F811
    r = client.post("/api/v1/alerts/AL-INEXISTENTE/ack", headers=_OP)
    assert r.status_code == 404
    assert client.get("/api/v1/alerts").status_code == 401
    assert client.post("/api/v1/alerts/X/ack").status_code == 401
