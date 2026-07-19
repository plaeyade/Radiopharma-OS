"""
Router de analítica GMP: trending del rendimiento de producción.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.application.analytics_service import AnalyticsService
from app.infrastructure.security.jwt_guard import Identity, current_identity

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

_service: AnalyticsService | None = None


def init(service: AnalyticsService) -> None:
    global _service
    _service = service


class TrendPointOut(BaseModel):
    batch_id: str
    created_at: datetime
    eob_activity_gbq: float
    eob_per_uah: float
    saturation_yield_mbq_ua: float
    status: str
    release_status: str
    warning: bool
    out_of_control: bool


class EobTrendOut(BaseModel):
    reaction_id: Optional[str]
    n_batches: int
    points: list[TrendPointOut]
    mean: Optional[float]
    std: Optional[float]
    ucl: Optional[float]
    lcl: Optional[float]
    uwl: Optional[float]
    lwl: Optional[float]
    slope_pct_per_day: Optional[float]
    r_squared: Optional[float]
    direction: str
    alerts: list[str]


@router.get("/eob-trend", response_model=EobTrendOut)
async def eob_trend(reaction_id: Optional[str] = None,
                    limit: int = Query(default=50, le=500),
                    include_voided: bool = False,
                    _: Identity = Depends(current_identity)) -> EobTrendOut:
    """Control chart de EOB normalizado (GBq/µA·h) con alertas de deriva.

    Gráfico de control de Shewhart (±2σ aviso, ±3σ control), run rule de
    6 puntos y regresión lineal temporal — el insumo del trending de la
    revisión periódica de producto (APR/PQR).
    """
    if _service is None:
        raise HTTPException(status_code=503,
                            detail="Servicio de analítica no configurado")
    t = await _service.eob_trend(reaction_id=reaction_id, limit=limit,
                                 include_voided=include_voided)
    return EobTrendOut(
        reaction_id=t.reaction_id, n_batches=t.n_batches,
        points=[TrendPointOut(**p.__dict__) for p in t.points],
        mean=t.mean, std=t.std, ucl=t.ucl, lcl=t.lcl, uwl=t.uwl, lwl=t.lwl,
        slope_pct_per_day=t.slope_pct_per_day, r_squared=t.r_squared,
        direction=t.direction, alerts=list(t.alerts))
