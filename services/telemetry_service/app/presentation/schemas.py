"""
Esquemas Pydantic del Telemetry Service.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PointIn(BaseModel):
    series: str = Field(..., min_length=1, max_length=120,
                        examples=["beam_current_ua"])
    ts: datetime = Field(..., description="Instante con zona horaria (UTC)")
    value: float
    tags: dict[str, str] = Field(default_factory=dict,
                                 examples=[{"batch_id": "B-20260718-XXXX"}])


class IngestIn(BaseModel):
    points: list[PointIn] = Field(..., min_length=1)


class IngestOut(BaseModel):
    written: int


class PointOut(BaseModel):
    series: str
    ts: datetime
    value: float
    tags: dict[str, str]


class SeriesStatsOut(BaseModel):
    series: str
    count: int
    mean: float
    minimum: float
    maximum: float
    stddev: float
    first_ts: Optional[datetime]
    last_ts: Optional[datetime]


class BatchSummaryOut(BaseModel):
    batch_id: str
    total_points: int
    series: list[SeriesStatsOut]


# ---------------- desviaciones de proceso (F2) ----------------

class DeviationRuleIn(BaseModel):
    series: str = Field(..., min_length=1, max_length=120)
    low: float
    high: float
    unit: str = ""
    description: str = ""


class DeviationRuleOut(BaseModel):
    series: str
    low: float
    high: float
    unit: str
    description: str


class DeviationPackOut(BaseModel):
    name: str
    description: str
    grace_fraction: float
    rules: list[DeviationRuleOut]


class DeviationCheckIn(BaseModel):
    pack: str = "cyclotron_generic"
    rules: Optional[list[DeviationRuleIn]] = None
    grace_fraction: Optional[float] = Field(default=None, ge=0.0, lt=0.5)


class DeviationEventOut(BaseModel):
    series: str
    started_at: datetime
    ended_at: datetime
    n_points: int
    extreme_value: float
    limit: float
    side: str
    unit: str
    description: str


class DeviationCheckOut(BaseModel):
    batch_id: str
    pack: str
    evaluated_points: int
    clean: bool
    events: list[DeviationEventOut]
