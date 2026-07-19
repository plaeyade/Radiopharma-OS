"""
Tests del Telemetry Service: dominio, aplicación, backend SQLite y API.
"""
from __future__ import annotations

import asyncio
import math
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.application.telemetry_service import TelemetryService
from app.domain.entities import TelemetryPoint
from app.infrastructure.db.sqlite_telemetry_store import SqliteTelemetryStore
from tests.test_jwt_guard import auth_headers

T0 = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)


def run(coro):
    return asyncio.run(coro)


def _pt(series="beam_current_ua", value=40.0, minutes=0, batch="B-1"):
    return TelemetryPoint(series=series, ts=T0 + timedelta(minutes=minutes),
                          value=value, tags=(("batch_id", batch),))


# ---------------- dominio / aplicación ----------------

def test_tags_dict():
    p = TelemetryPoint(series="s", ts=T0, value=1.0,
                       tags=(("b", "2"), ("a", "1")))
    assert p.tags_dict() == {"a": "1", "b": "2"}


@pytest.fixture()
def svc(tmp_path):
    store = SqliteTelemetryStore(f"sqlite+aiosqlite:///{tmp_path}/tel.db")
    run(store.create_schema())
    return TelemetryService(store), store


def test_ingesta_valida(svc):
    service, store = svc
    n = run(service.ingest([_pt(minutes=0), _pt(minutes=1, value=41.0)]))
    assert n == 2
    assert run(store.count()) == 2


def test_ingesta_rechaza_lote_vacio(svc):
    service, _ = svc
    with pytest.raises(ValueError):
        run(service.ingest([]))


def test_ingesta_rechaza_valor_no_finito(svc):
    service, _ = svc
    with pytest.raises(ValueError):
        run(service.ingest([_pt(value=float("nan"))]))
    with pytest.raises(ValueError):
        run(service.ingest([_pt(value=float("inf"))]))


def test_ingesta_rechaza_ts_sin_zona(svc):
    service, _ = svc
    p = TelemetryPoint(series="s", ts=datetime(2026, 7, 1, 12, 0, 0), value=1.0)
    with pytest.raises(ValueError):
        run(service.ingest([p]))


def test_stats_por_lote(svc):
    service, _ = svc
    pts = [_pt(value=v, minutes=i, batch="B-77") for i, v in
           enumerate([40.0, 41.0, 39.0, 40.5])]
    pts += [_pt(series="target_pressure_psi", value=330.0, minutes=0,
                batch="B-77")]
    pts += [_pt(value=99.0, minutes=0, batch="B-OTRO")]
    run(service.ingest(pts))
    stats = run(service.stats_for_batch("B-77"))
    assert {s.series for s in stats} == {"beam_current_ua",
                                         "target_pressure_psi"}
    corriente = next(s for s in stats if s.series == "beam_current_ua")
    assert corriente.count == 4
    assert abs(corriente.mean - 40.125) < 1e-9
    assert corriente.minimum == 39.0 and corriente.maximum == 41.0
    assert corriente.stddev > 0
    # el punto de otro lote no contamina
    assert all(s.series != "beam_current_ua" or s.count == 4 for s in stats)


# ---------------- backend SQLite ----------------

def test_sqlite_query_rango_y_etiquetas(svc):
    service, store = svc
    pts = [_pt(minutes=m, batch="B-9") for m in range(10)]
    pts += [_pt(series="target_pressure_psi", minutes=m, batch="B-9")
            for m in range(3)]
    run(store.write(pts))
    rango = run(store.query(start=T0 + timedelta(minutes=3),
                            end=T0 + timedelta(minutes=5)))
    assert all(T0 + timedelta(minutes=3) <= p.ts <= T0 + timedelta(minutes=5)
               for p in rango)
    solo = run(store.query(series="beam_current_ua", tags={"batch_id": "B-9"}))
    assert len(solo) == 10
    assert {s for s in run(store.list_series())} == {
        "beam_current_ua", "target_pressure_psi"}


# ---------------- API ----------------

@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEMETRY_BACKEND", "sqlite")
    monkeypatch.setenv("TELEMETRY_DATABASE_URL",
                       f"sqlite+aiosqlite:///{tmp_path}/tel.db")
    import importlib
    import app.config as config
    importlib.reload(config)
    import app.main as main
    importlib.reload(main)
    with TestClient(main.app) as c:
        yield c


def _punto(serie="beam_current_ua", valor=40.0, batch="B-1", minutos=0):
    return {"series": serie, "value": valor,
            "ts": (T0 + timedelta(minutes=minutos)).isoformat(),
            "tags": {"batch_id": batch}}


def test_api_ingesta_y_consulta(client):
    r = client.post("/api/v1/telemetry/points",
                    json={"points": [_punto(valor=40.1), _punto(valor=40.3, minutos=1)]},
                    headers=auth_headers())
    assert r.status_code == 201
    assert r.json()["written"] == 2

    q = client.get("/api/v1/telemetry/query",
                   params={"series": "beam_current_ua", "batch_id": "B-1"},
                   headers=auth_headers())
    assert q.status_code == 200
    assert len(q.json()) == 2
    assert q.json()[0]["tags"]["batch_id"] == "B-1"

    s = client.get("/api/v1/telemetry/series", headers=auth_headers())
    assert "beam_current_ua" in s.json()


def test_api_resumen_por_lote(client):
    puntos = [_punto(valor=40.0 + i * 0.1, minutos=i) for i in range(5)]
    puntos.append(_punto(serie="target_pressure_psi", valor=331.0))
    client.post("/api/v1/telemetry/points", json={"points": puntos},
                headers=auth_headers())
    r = client.get("/api/v1/telemetry/batches/B-1/summary",
                   headers=auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["total_points"] == 6
    corriente = next(x for x in body["series"]
                     if x["series"] == "beam_current_ua")
    assert corriente["count"] == 5
    assert abs(corriente["mean"] - 40.2) < 1e-9


def test_api_validacion_422(client):
    # valor no finito (NaN crudo: el JSON estándar lo admite en lectura)
    cuerpo = ('{"points": [{"series": "s", "value": NaN, '
              f'"ts": "{T0.isoformat()}", "tags": {{}}' + "]}")
    r = client.post("/api/v1/telemetry/points", content=cuerpo,
                    headers={**auth_headers(),
                             "Content-Type": "application/json"})
    assert r.status_code == 422
    # instante sin zona horaria
    naive = {"series": "s", "value": 1.0,
             "ts": "2026-07-01T12:00:00", "tags": {}}
    r = client.post("/api/v1/telemetry/points", json={"points": [naive]},
                    headers=auth_headers())
    assert r.status_code == 422


def test_api_requiere_token(client):
    assert client.post("/api/v1/telemetry/points",
                       json={"points": [_punto()]}).status_code == 401
    assert client.get("/api/v1/telemetry/series").status_code == 401
