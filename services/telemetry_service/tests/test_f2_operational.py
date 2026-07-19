"""
Tests del Operational Twin F2: downsampling (LTTB/buckets) y detección
de desviaciones de proceso con packs de límites.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from app.application.deviations import (DeviationRule, evaluate, get_pack,
                                        PACKS)
from app.application.downsampling import downsample
from app.domain.entities import TelemetryPoint
from tests.test_jwt_guard import auth_headers
from tests.test_telemetry import client  # noqa: F401  (fixture importada)

T0 = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)


def _serie(vals, series="beam_current_ua", paso_s=10.0, batch="B-TEST"):
    return [TelemetryPoint(series=series, ts=T0 + timedelta(seconds=i * paso_s),
                           value=v, tags=(("batch_id", batch),))
            for i, v in enumerate(vals)]


# ---------------- downsampling ----------------

def test_lttb_no_diezma_si_cabe():
    pts = _serie([1.0] * 50)
    out = downsample(pts, 100)
    assert len(out) == 50
    assert out == sorted(pts, key=lambda p: p.ts)


def test_lttb_respeta_tamano_y_extremos():
    pts = _serie([math.sin(i / 20) * 10 + 40 for i in range(2000)])
    out = downsample(pts, 200)
    assert len(out) == 200
    assert out[0] == pts[0] and out[-1] == pts[-1]
    # todos son puntos reales de la serie (LTTB selecciona, no inventa)
    assert set(out).issubset(set(pts))


def test_lttb_preserva_picos():
    vals = [40.0] * 1000
    vals[500] = 60.0   # pico aislado
    vals[501] = 60.0
    pts = _serie(vals)
    out = downsample(pts, 50)
    assert max(p.value for p in out) == 60.0   # el pico sobrevive al diezmado


def test_bucket_mean_suaviza_y_centra():
    pts = _serie([10.0, 20.0, 30.0, 40.0], paso_s=10.0)
    out = downsample(pts, 2, method="bucket-mean")
    assert len(out) == 2
    assert out[0].value == pytest.approx(15.0)
    assert out[1].value == pytest.approx(35.0)
    assert out[0].ts == pts[0].ts + timedelta(seconds=7.5)  # centro de ventana


def test_downsample_errores():
    pts = _serie([1.0] * 10)
    with pytest.raises(ValueError):
        downsample(pts, 0)
    with pytest.raises(ValueError):
        downsample(pts, 5, method="fft")


# ---------------- desviaciones ----------------

def test_sin_desviacion_serie_limpia():
    pack = get_pack("cyclotron_generic")
    pts = _serie([40.0] * 100)  # dentro de [38, 42]
    assert evaluate(pts, pack.rules, pack.grace_fraction) == []


def test_detecta_racha_como_un_evento():
    regla = DeviationRule("cooling_flow_lpm", 10.0, 13.5, "lpm", "")
    vals = [12.0] * 50 + [8.5, 8.4, 8.6] + [12.0] * 50
    eventos = evaluate(_serie(vals, series="cooling_flow_lpm"), [regla])
    assert len(eventos) == 1
    e = eventos[0]
    assert e.side == "low" and e.limit == 10.0
    assert e.extreme_value == 8.4
    assert e.n_points == 3
    assert "cooling_flow_lpm" in e.describe()


def test_lados_y_limites_correctos():
    regla = DeviationRule("target_pressure_psi", 335.0, 355.0, "psi", "")
    vals = [345.0] * 30 + [360.0] * 4 + [345.0] * 30 + [330.0] * 2 + [345.0] * 10
    eventos = evaluate(_serie(vals, series="target_pressure_psi"), [regla])
    assert len(eventos) == 2
    alto, bajo = eventos
    assert alto.side == "high" and alto.limit == 355.0 and alto.extreme_value == 360.0
    assert bajo.side == "low" and bajo.limit == 335.0 and bajo.extreme_value == 330.0


def test_grace_fraction_excluye_rampa():
    regla = DeviationRule("beam_current_ua", 38.0, 42.0, "µA", "")
    vals = [i * 40 / 10 for i in range(11)] + [40.0] * 89   # rampa 0→40 en 10 %
    pts = _serie(vals)
    assert len(evaluate(pts, [regla], grace_fraction=0.0)) == 1   # sin gracia: rampa cuenta
    assert evaluate(pts, [regla], grace_fraction=0.15) == []      # con gracia: limpio


def test_grace_fraction_invalida():
    with pytest.raises(ValueError):
        evaluate(_serie([1.0, 2.0]), [], grace_fraction=0.9)


def test_pack_desconocido_error():
    with pytest.raises(ValueError):
        get_pack("nope")


def test_pack_contiene_tres_series_estandar():
    pack = PACKS["cyclotron_generic"]
    series = {r.series for r in pack.rules}
    assert series == {"beam_current_ua", "target_pressure_psi",
                      "cooling_flow_lpm"}
    for r in pack.rules:
        assert r.low < r.high


# ---------------- API ----------------

def test_api_query_con_diezmado(client):
    headers = auth_headers("operador", "operador.ciclotron")
    puntos = [{"series": "beam_current_ua",
               "ts": (T0 + timedelta(seconds=i * 5)).isoformat(),
               "value": 40.0 + math.sin(i / 10),
               "tags": {"batch_id": "B-DS"}} for i in range(500)]
    r = client.post("/api/v1/telemetry/points",
                    json={"points": puntos}, headers=headers)
    assert r.status_code == 201
    q = client.get("/api/v1/telemetry/query?batch_id=B-DS"
                   "&series=beam_current_ua&max_points=60",
                   headers=auth_headers())
    assert q.status_code == 200
    assert len(q.json()) == 60
    q2 = client.get("/api/v1/telemetry/query?batch_id=B-DS"
                    "&series=beam_current_ua&max_points=30&method=bucket-mean",
                    headers=auth_headers())
    assert len(q2.json()) == 30
    q3 = client.get("/api/v1/telemetry/query?batch_id=B-DS"
                    "&max_points=10&method=nope", headers=auth_headers())
    assert q3.status_code == 422


def test_api_deviation_check_detecta_excursion(client):
    headers = auth_headers("operador", "operador.ciclotron")
    puntos = []
    for i in range(200):
        frac = i / 199
        ts = (T0 + timedelta(minutes=60 * frac)).isoformat()
        caudal = 8.5 if 0.60 <= frac <= 0.66 else 12.0
        presion = 360.0 if 0.60 <= frac <= 0.66 else 345.0
        puntos += [
            {"series": "cooling_flow_lpm", "ts": ts, "value": caudal,
             "tags": {"batch_id": "B-DEV"}},
            {"series": "target_pressure_psi", "ts": ts, "value": presion,
             "tags": {"batch_id": "B-DEV"}},
            {"series": "beam_current_ua", "ts": ts,
             "value": 40.0 * min(1.0, frac / 0.05),
             "tags": {"batch_id": "B-DEV"}},
        ]
    assert client.post("/api/v1/telemetry/points", json={"points": puntos},
                       headers=headers).status_code == 201
    r = client.post("/api/v1/telemetry/batches/B-DEV/deviation-check",
                    json={"pack": "cyclotron_generic"}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["clean"] is False
    assert body["evaluated_points"] == 600
    assert body["pack"] == "cyclotron_generic"
    series_con_evento = {e["series"] for e in body["events"]}
    assert "cooling_flow_lpm" in series_con_evento
    assert "target_pressure_psi" in series_con_evento
    # la rampa del haz quedó excluida por grace_fraction del pack
    assert "beam_current_ua" not in series_con_evento


def test_api_deviation_check_limpio_y_packs(client):
    headers = auth_headers("operador", "operador.ciclotron")
    puntos = [{"series": s, "ts": (T0 + timedelta(seconds=i * 10)).isoformat(),
               "value": v, "tags": {"batch_id": "B-CLEAN"}}
              for i in range(100)
              for s, v in [("beam_current_ua", 40.0),
                           ("target_pressure_psi", 345.0),
                           ("cooling_flow_lpm", 12.0)]]
    client.post("/api/v1/telemetry/points", json={"points": puntos},
                headers=headers)
    r = client.post("/api/v1/telemetry/batches/B-CLEAN/deviation-check",
                    json={}, headers=headers)
    assert r.status_code == 200 and r.json()["clean"] is True
    p = client.get("/api/v1/telemetry/deviation-packs", headers=auth_headers())
    assert p.status_code == 200 and len(p.json()) >= 1
    assert p.json()[0]["rules"]
    bad = client.post("/api/v1/telemetry/batches/B-CLEAN/deviation-check",
                      json={"pack": "nope"}, headers=headers)
    assert bad.status_code == 422


def test_api_query_filtra_batch_antes_del_limit(client):
    """Regresión: el LIMIT no puede aplicarse antes del filtro por lote —
    con puntos de varios lotes, una query acotada debe seguir devolviendo
    los del lote pedido."""
    headers = auth_headers("operador", "operador.ciclotron")
    for lote, n in [("B-OTRO", 60), ("B-MIO", 10)]:
        puntos = [{"series": "beam_current_ua",
                   "ts": (T0 + timedelta(seconds=i * 5)).isoformat(),
                   "value": 40.0, "tags": {"batch_id": lote}}
                  for i in range(n)]
        assert client.post("/api/v1/telemetry/points", json={"points": puntos},
                           headers=headers).status_code == 201
    q = client.get("/api/v1/telemetry/query?batch_id=B-MIO&limit=5",
                   headers=auth_headers())
    assert q.status_code == 200
    assert len(q.json()) == 5
    assert all(p["tags"]["batch_id"] == "B-MIO" for p in q.json())


def test_api_deviation_check_reglas_custom(client):
    headers = auth_headers("operador", "operador.ciclotron")
    puntos = [{"series": "beam_current_ua",
               "ts": (T0 + timedelta(seconds=i * 10)).isoformat(),
               "value": 40.0 if i < 50 else 35.0,
               "tags": {"batch_id": "B-CUSTOM"}} for i in range(100)]
    client.post("/api/v1/telemetry/points", json={"points": puntos},
                headers=headers)
    r = client.post("/api/v1/telemetry/batches/B-CUSTOM/deviation-check",
                    json={"rules": [{"series": "beam_current_ua",
                                     "low": 39.0, "high": 41.0,
                                     "unit": "µA", "description": "estrecho"}]},
                    headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["pack"] == "custom"
    assert body["clean"] is False
    assert body["events"][0]["limit"] == 39.0
