"""
Casos de uso del Telemetry Service.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Optional

from ..domain.entities import SeriesStats, TelemetryPoint
from ..domain.interfaces import TelemetryStore
from .deviations import (DEFAULT_PACK, DeviationEvent, DeviationRule, evaluate,
                         get_pack)
from .downsampling import downsample

_MAX_BATCH = 5000


class TelemetryService:
    def __init__(self, store: TelemetryStore) -> None:
        self._store = store

    async def ingest(self, points: list[TelemetryPoint]) -> int:
        if not points:
            raise ValueError("Lote de puntos vacío")
        if len(points) > _MAX_BATCH:
            raise ValueError(f"Máximo {_MAX_BATCH} puntos por ingesta")
        for p in points:
            if not p.series or len(p.series) > 120:
                raise ValueError(f"Nombre de serie inválido: {p.series!r}")
            if not math.isfinite(p.value):
                raise ValueError(f"Valor no finito en serie {p.series}")
            if p.ts.tzinfo is None:
                raise ValueError("El instante debe llevar zona horaria (UTC)")
        return await self._store.write(points)

    async def query(self, series: Optional[str], tags: Optional[dict],
                    start: Optional[datetime], end: Optional[datetime],
                    limit: int) -> list[TelemetryPoint]:
        return await self._store.query(series=series, tags=tags,
                                       start=start, end=end, limit=limit)

    async def list_series(self) -> list[str]:
        return await self._store.list_series()

    async def query_downsampled(self, series: Optional[str],
                                tags: Optional[dict],
                                start: Optional[datetime],
                                end: Optional[datetime], limit: int,
                                max_points: int, method: str) -> list[TelemetryPoint]:
        """Query con diezmado por serie (LTTB o bucket-mean) para gráficas."""
        points = await self._store.query(series=series, tags=tags,
                                         start=start, end=end, limit=limit)
        por_serie: dict[str, list[TelemetryPoint]] = {}
        for p in points:
            por_serie.setdefault(p.series, []).append(p)
        out: list[TelemetryPoint] = []
        for pts in por_serie.values():
            out.extend(downsample(pts, max_points, method))
        return sorted(out, key=lambda p: (p.series, p.ts))

    async def check_deviations(self, batch_id: str, pack: str = DEFAULT_PACK,
                               rules: Optional[list[DeviationRule]] = None,
                               grace_fraction: Optional[float] = None
                               ) -> tuple[list[DeviationEvent], int, str]:
        """Evalúa la telemetría del lote contra reglas de rango.

        Devuelve (eventos, puntos_evaluados, nombre_pack). Si se pasan
        `rules` propias, se ignoran las del pack y grace_fraction por
        defecto es 0 salvo indicación.
        """
        points = await self._store.query(tags={"batch_id": batch_id},
                                         limit=100000)
        if rules is not None:
            if not rules:
                raise ValueError("Lista de reglas vacía")
            reglas = rules
            grace = grace_fraction or 0.0
            pack_name = "custom"
        else:
            p = get_pack(pack)
            reglas = list(p.rules)
            grace = grace_fraction if grace_fraction is not None \
                else p.grace_fraction
            pack_name = p.name
        eventos = evaluate(points, reglas, grace)
        return eventos, len(points), pack_name

    async def stats_for_batch(self, batch_id: str,
                              start: Optional[datetime] = None,
                              end: Optional[datetime] = None) -> list[SeriesStats]:
        """Resumen por serie de toda la telemetría ligada a un lote."""
        points = await self._store.query(tags={"batch_id": batch_id},
                                         start=start, end=end, limit=100000)
        por_serie: dict[str, list[TelemetryPoint]] = {}
        for p in points:
            por_serie.setdefault(p.series, []).append(p)
        return [self._stats(s, pts) for s, pts in sorted(por_serie.items())]

    @staticmethod
    def _stats(series: str, pts: list[TelemetryPoint]) -> SeriesStats:
        vals = [p.value for p in pts]
        n = len(vals)
        mean = sum(vals) / n
        var = sum((v - mean) ** 2 for v in vals) / n
        ts = [p.ts for p in pts]
        return SeriesStats(series=series, count=n, mean=mean,
                           minimum=min(vals), maximum=max(vals),
                           stddev=math.sqrt(var),
                           first_ts=min(ts), last_ts=max(ts))
