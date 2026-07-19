"""
Radiopharma OS - Telemetry Service (Operational Twin, Fase 1)
Capa de dominio: series de telemetría de la corrida de irradiación.

La telemetría (corriente de haz, presión de blanco, temperatura, caudal de
agua de enfriamiento...) se almacena como series temporales append-only,
etiquetadas por batch_id/run_id para vincular la evidencia operacional
al expediente del lote (EDS v2.0, gemelo operacional).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class TelemetryPoint:
    """Un punto de una serie temporal."""
    series: str                 # p.ej. beam_current_ua, target_pressure_psi
    ts: datetime                # instante (UTC)
    value: float
    tags: tuple[tuple[str, str], ...] = ()   # etiquetas ordenadas (batch_id, run_id, target...)

    def tags_dict(self) -> dict:
        return dict(self.tags)


@dataclass(frozen=True)
class SeriesStats:
    """Resumen estadístico de una serie en un intervalo."""
    series: str
    count: int
    mean: float
    minimum: float
    maximum: float
    stddev: float
    first_ts: Optional[datetime]
    last_ts: Optional[datetime]
