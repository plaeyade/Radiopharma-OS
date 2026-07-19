"""
Tests del trending EOB (gráfico de control de Shewhart + deriva).
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.application.analytics_service import AnalyticsService
from app.domain.entities import BatchRecord, BatchStatus
from tests.test_ebr import MemBatches, _record, client, run   # noqa: F401
from tests.test_jwt_guard import auth_headers

T0 = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)


def _lote(i: int, eob: float, dias: int = 1, status=BatchStatus.COMPLETED):
    """Lote i con EOB dado, separado `dias` días del anterior."""
    r = _record(batch_id=f"B-20260701-{i:08X}")
    beam = replace(r.beam)  # mismos parámetros de haz
    return BatchRecord(
        batch_id=r.batch_id,
        created_at=T0 + timedelta(days=i * dias), created_by=r.created_by,
        reaction_id=r.reaction_id, target_id=r.target_id,
        product_nuclide=r.product_nuclide, beam=beam,
        results=replace(r.results, eob_activity_gbq=eob),
        lineage=r.lineage, status=status).with_integrity()


def _svc_con(eobs, **kw) -> AnalyticsService:
    batches = MemBatches()
    for i, eob in enumerate(eobs):
        run(batches.save(_lote(i, eob, **kw)))
    return AnalyticsService(batches)


# ---------------- servicio ----------------

def test_proceso_estable_sin_alertas():
    # EOB ~108.9 ± ruido pequeño (37 µA, 1 h → eob_per_uah ≈ 2.94)
    svc = _svc_con([108.9, 109.5, 108.3, 109.1, 108.7, 109.3, 108.5])
    t = run(svc.eob_trend())
    assert t.n_batches == 7
    assert t.direction == "stable"
    assert t.mean and t.std is not None and t.std < 0.05
    assert t.ucl > t.uwl > t.mean > t.lwl > t.lcl
    assert t.alerts == ()
    assert not any(p.warning or p.out_of_control for p in t.points)


def test_punto_fuera_de_control_3sigma():
    # 9 lotes estables + 1 desplome: el desplome excede 3σ
    svc = _svc_con([109.0, 108.8, 109.2, 108.9, 109.1, 108.85, 109.05,
                    108.95, 109.1, 60.0])
    t = run(svc.eob_trend())
    fuera = [p for p in t.points if p.out_of_control]
    assert len(fuera) == 1 and fuera[0].eob_activity_gbq == 60.0
    assert any("fuera del límite de control" in a for a in t.alerts)


def test_tendencia_decreciente_detectada():
    # deriva clara: -1 GBq por lote diario (~ -0.9 %/día)
    svc = _svc_con([112.0, 111.0, 110.0, 109.0, 108.0, 107.0, 106.0, 105.0])
    t = run(svc.eob_trend())
    assert t.direction == "declining"
    assert t.slope_pct_per_day < -0.5
    assert t.r_squared > 0.95
    assert any("decreciente" in a for a in t.alerts)


def test_racha_monotona_detecta_deriva_sin_linealidad():
    # deriva real al final aunque el inicio irregular rompa el R² global
    svc = _svc_con([109.3, 108.7, 109.4, 108.8, 109.2,
                    112.0, 111.0, 110.0, 109.0, 108.0, 107.0])
    t = run(svc.eob_trend())
    assert t.direction == "declining"
    assert any("racha monótona" in a for a in t.alerts)


def test_run_rule_seis_mismo_lado():
    # 8 lotes todos por debajo de la media conjunta (sin deriva temporal:
    # mezcla alta al principio para que la media quede alta y el final bajo)
    svc = _svc_con([111.5, 111.5, 111.5, 108.5, 108.4, 108.6,
                    108.5, 108.45, 108.55, 108.5])
    t = run(svc.eob_trend())
    assert any("racha" in a for a in t.alerts)


def test_voided_excluido_por_defecto():
    batches = MemBatches()
    run(batches.save(_lote(0, 109.0)))
    run(batches.save(_lote(1, 30.0, status=BatchStatus.VOIDED)))
    run(batches.save(_lote(2, 109.2)))
    svc = AnalyticsService(batches)
    t = run(svc.eob_trend())
    assert t.n_batches == 2            # el voided no distorsiona
    assert all(p.eob_activity_gbq > 100 for p in t.points)
    t2 = run(svc.eob_trend(include_voided=True))
    assert t2.n_batches == 3


def test_pocos_lotes_sin_estadisticos():
    svc = _svc_con([109.0])
    t = run(svc.eob_trend())
    assert t.n_batches == 1 and t.mean is None and t.direction == "stable"


def test_normalizacion_por_corriente_y_tiempo():
    # mismo rendimiento específico pero corriente distinta → sin falsos avisos
    batches = MemBatches()
    for i, (eob, ua) in enumerate([(108.9, 37.0), (147.2, 50.0), (88.3, 30.0)]):
        base = _lote(i, eob)
        run(batches.save(BatchRecord(
            batch_id=base.batch_id, created_at=base.created_at,
            created_by=base.created_by, reaction_id=base.reaction_id,
            target_id=base.target_id, product_nuclide=base.product_nuclide,
            beam=replace(base.beam, current_ua=ua), results=base.results,
            lineage=base.lineage).with_integrity()))
    t = run(AnalyticsService(batches).eob_trend())
    per = [p.eob_per_uah for p in t.points]
    assert max(per) - min(per) < 0.01    # todos ≈ 2.94 GBq/µA·h


# ---------------- API ----------------

def test_api_eob_trend(client):   # noqa: F811
    headers = auth_headers("operador", "operador.ciclotron")
    for i, eob in enumerate([109.0, 108.8, 109.2, 108.9, 109.1, 60.0]):
        payload = {
            "reaction_id": "o18_p_n_f18", "target_id": "h2_18o",
            "product_nuclide": "18F",
            "beam": {"beam_energy_mev": 16.5, "current_ua": 37.0,
                     "irradiation_time_min": 60.0},
            "results": {"saturation_yield_mbq_ua": 9336.8,
                        "eob_activity_gbq": eob,
                        "eob_activity_gbq_uncertainty": 8.1,
                        "saturation_factor": 0.315,
                        "relative_uncertainty": 0.074},
            "lineage": {"dataset_id": "ds", "dataset_sha256": "abc",
                        "stopping_source": "CATIMA"},
        }
        assert client.post("/api/v1/batches", json=payload,
                           headers=headers).status_code == 201
    r = client.get("/api/v1/analytics/eob-trend?reaction_id=o18_p_n_f18",
                   headers=auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["n_batches"] == 6
    assert body["reaction_id"] == "o18_p_n_f18"
    assert body["mean"] and body["ucl"] > body["mean"]
    fuera = [p for p in body["points"] if p["out_of_control"]]
    assert len(fuera) == 1
    assert any("fuera del límite de control" in a for a in body["alerts"])
    assert body["direction"] in ("stable", "declining")


def test_api_eob_trend_sin_token_401(client):   # noqa: F811
    assert client.get("/api/v1/analytics/eob-trend").status_code in (401, 403)
