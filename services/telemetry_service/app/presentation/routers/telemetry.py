"""
Router REST del Telemetry Service.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.application.deviations import PACKS, DeviationEvent, DeviationRule
from app.application.downsampling import METODOS
from app.application.telemetry_service import TelemetryService
from app.domain.entities import TelemetryPoint
from app.infrastructure.security.jwt_guard import (Identity, current_identity,
                                                   require_operator)
from app.presentation.schemas import (AnomalyDetectIn, BatchSummaryOut,
                                      DeviationCheckIn,
                                      DeviationCheckOut, DeviationEventOut,
                                      DeviationPackOut, DeviationRuleOut,
                                      IngestIn, IngestOut, PointOut,
                                      SeriesStatsOut)

router = APIRouter(prefix="/api/v1/telemetry", tags=["telemetry"])

_service: TelemetryService | None = None


def init(service: TelemetryService) -> None:
    global _service
    _service = service


def _out(p: TelemetryPoint) -> PointOut:
    return PointOut(series=p.series, ts=p.ts, value=p.value,
                    tags=p.tags_dict())


@router.post("/points", response_model=IngestOut, status_code=201)
async def ingest(payload: IngestIn,
                 _: Identity = Depends(require_operator)) -> IngestOut:
    points = [TelemetryPoint(series=p.series, ts=p.ts, value=p.value,
                             tags=tuple(sorted(p.tags.items())))
              for p in payload.points]
    try:
        written = await _service.ingest(points)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return IngestOut(written=written)


@router.get("/series", response_model=list[str])
async def list_series(_: Identity = Depends(current_identity)) -> list[str]:
    return await _service.list_series()


@router.get("/query", response_model=list[PointOut])
async def query(series: Optional[str] = None,
                batch_id: Optional[str] = None,
                start: Optional[datetime] = None,
                end: Optional[datetime] = None,
                limit: int = Query(default=1000, le=100000),
                max_points: Optional[int] = Query(default=None, le=100000),
                method: str = Query(default="lttb"),
                _: Identity = Depends(current_identity)) -> list[PointOut]:
    tags = {"batch_id": batch_id} if batch_id else None
    if max_points is None:
        points = await _service.query(series=series, tags=tags,
                                      start=start, end=end, limit=limit)
    else:
        if method not in METODOS:
            raise HTTPException(
                status_code=422,
                detail=f"Método de diezmado inválido: {method!r} "
                       f"(válidos: {', '.join(METODOS)})")
        points = await _service.query_downsampled(
            series=series, tags=tags, start=start, end=end, limit=limit,
            max_points=max_points, method=method)
    return [_out(p) for p in points]


@router.get("/batches/{batch_id}/summary", response_model=BatchSummaryOut)
async def batch_summary(batch_id: str,
                        start: Optional[datetime] = None,
                        end: Optional[datetime] = None,
                        _: Identity = Depends(current_identity)
                        ) -> BatchSummaryOut:
    stats = await _service.stats_for_batch(batch_id, start=start, end=end)
    return BatchSummaryOut(
        batch_id=batch_id, total_points=sum(s.count for s in stats),
        series=[SeriesStatsOut(**s.__dict__) for s in stats])


# ---------------- desviaciones de proceso (F2) ----------------

def _evento_out(e: DeviationEvent) -> DeviationEventOut:
    return DeviationEventOut(
        series=e.series, started_at=e.started_at, ended_at=e.ended_at,
        n_points=e.n_points, extreme_value=e.extreme_value, limit=e.limit,
        side=e.side, unit=e.unit, description=e.describe())


@router.get("/deviation-packs", response_model=list[DeviationPackOut])
async def deviation_packs(_: Identity = Depends(current_identity)
                          ) -> list[DeviationPackOut]:
    return [DeviationPackOut(
        name=p.name, description=p.description,
        grace_fraction=p.grace_fraction,
        rules=[DeviationRuleOut(**r.__dict__) for r in p.rules])
        for p in PACKS.values()]


@router.post("/batches/{batch_id}/deviation-check",
             response_model=DeviationCheckOut)
async def deviation_check(batch_id: str, payload: DeviationCheckIn,
                          _: Identity = Depends(require_operator)
                          ) -> DeviationCheckOut:
    """Evalúa la corrida del lote contra las reglas de rango del pack.

    Los eventos detectados deben registrarse en el Data Lake
    (POST /api/v1/batches/{id}/events) para quedar en el eBR.
    """
    reglas = ([DeviationRule(**r.__dict__) for r in payload.rules]
              if payload.rules is not None else None)
    try:
        eventos, n, pack_name = await _service.check_deviations(
            batch_id, pack=payload.pack, rules=reglas,
            grace_fraction=payload.grace_fraction)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return DeviationCheckOut(
        batch_id=batch_id, pack=pack_name, evaluated_points=n,
        clean=not eventos, events=[_evento_out(e) for e in eventos])


# ---------------- detección de anomalías (6.22/6.23) ----------------

@router.post("/anomalies/detect")
async def anomaly_detect(payload: AnomalyDetectIn,
                         _: Identity = Depends(require_operator)) -> dict:
    """Detección robusta (MAD) con política externa versionada.

    Las anomalías y los datos inválidos generan eventos de auditoría
    (6.23). El detector reporta; nunca actúa sobre el proceso."""
    from app.application.anomalies import (DeteccionInvalida,
                                           PoliticaAnomalias, detectar_anomalias,
                                           resultado_a_dict)
    pol = PoliticaAnomalias(
        version=payload.politica or PoliticaAnomalias().version,
        umbral_mad=(payload.umbral_mad
                    if payload.umbral_mad is not None
                    else PoliticaAnomalias().umbral_mad))
    try:
        res = detectar_anomalias(payload.values, payload.timestamps,
                                 series=payload.series, politica=pol,
                                 batch_id=payload.batch_id)
    except DeteccionInvalida as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return resultado_a_dict(res)


@router.get("/anomalies/detect/{batch_id}/{series}")
async def anomaly_detect_batch(batch_id: str, series: str,
                               umbral_mad: float = Query(default=5.0),
                               _: Identity = Depends(current_identity)) -> dict:
    """Detección sobre una serie almacenada de un lote (6.22)."""
    from app.application.anomalies import (DeteccionInvalida,
                                           PoliticaAnomalias, detectar_anomalias,
                                           resultado_a_dict)
    pts = await _service.query(series=series, tags={"batch_id": batch_id},
                               limit=100000)
    if not pts:
        raise HTTPException(status_code=404,
                            detail=f"sin puntos para {series}/{batch_id}")
    try:
        res = detectar_anomalias(
            [p.value for p in pts], [p.ts.isoformat() for p in pts],
            series=series,
            politica=PoliticaAnomalias(umbral_mad=umbral_mad),
            batch_id=batch_id)
    except DeteccionInvalida as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return resultado_a_dict(res)
