"""
Puertos del Telemetry Service.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol

from app.domain.entities import TelemetryPoint


class TelemetryStore(Protocol):
    """Almacén de series temporales (append-only)."""

    async def write(self, points: list[TelemetryPoint]) -> int: ...

    async def query(
        self,
        series: Optional[str] = None,
        tags: Optional[dict] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 10000,
    ) -> list[TelemetryPoint]: ...

    async def list_series(self) -> list[str]: ...

    async def count(self, series: Optional[str] = None,
                    tags: Optional[dict] = None) -> int: ...
