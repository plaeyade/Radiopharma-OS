"""
Backend InfluxDB 2.x de telemetría (despliegue).

Sin dependencia del cliente oficial: escritura en protocolo de línea y
consultas Flux vía HTTP (POST /api/v2/write, /api/v2/query), con la misma
interfaz que el backend SQLite. La agregación se hace en aplicación para
mantener ambos backends equivalentes.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.domain.entities import TelemetryPoint

_FIELD = "value"


def _esc(texto: str) -> str:
    """Escapa claves/valores del protocolo de línea."""
    return (texto.replace(",", "\\,").replace(" ", "\\ ").replace("=", "\\="))


class InfluxTelemetryStore:
    def __init__(self, url: str, token: str, org: str, bucket: str,
                 transport: Optional[httpx.BaseTransport] = None) -> None:
        self._url = url.rstrip("/")
        self._org = org
        self._bucket = bucket
        self._headers = {"Authorization": f"Token {token}"}
        self._transport = transport

    async def create_schema(self) -> None:
        """El bucket se crea fuera (provisión); verifica salud del servidor."""
        async with httpx.AsyncClient(transport=self._transport,
                                     timeout=5.0) as http:
            r = await http.get(f"{self._url}/health", headers=self._headers)
            r.raise_for_status()

    async def dispose(self) -> None:
        return None

    # ---------------------------------------------------------------- write
    async def write(self, points: list[TelemetryPoint]) -> int:
        lines = []
        for p in points:
            tags = "".join(f",{_esc(k)}={_esc(v)}"
                           for k, v in sorted(p.tags_dict().items()))
            ts_ms = int(p.ts.timestamp() * 1000)
            lines.append(f"{_esc(p.series)}{tags} {_FIELD}={p.value} {ts_ms}")
        body = "\n".join(lines)
        async with httpx.AsyncClient(transport=self._transport,
                                     timeout=15.0) as http:
            r = await http.post(
                f"{self._url}/api/v2/write",
                params={"org": self._org, "bucket": self._bucket,
                        "precision": "ms"},
                content=body, headers=self._headers)
            r.raise_for_status()
        return len(points)

    # ---------------------------------------------------------------- query
    def _flux(self, series: Optional[str], tags: Optional[dict],
              start: Optional[datetime], end: Optional[datetime],
              limit: int) -> str:
        s = start.astimezone(timezone.utc).isoformat() if start else "1970-01-01T00:00:00Z"
        e = end.astimezone(timezone.utc).isoformat() if end else "now()"
        q = (f'from(bucket: "{self._bucket}") '
             f"|> range(start: {s}, stop: {e}) "
             f'|> filter(fn: (r) => r._field == "{_FIELD}") ')
        if series:
            q += f'|> filter(fn: (r) => r._measurement == "{series}") '
        for k, v in (tags or {}).items():
            q += f'|> filter(fn: (r) => r.{k} == "{v}") '
        q += f"|> limit(n: {limit})"
        return q

    async def query(self, series: Optional[str] = None,
                    tags: Optional[dict] = None,
                    start: Optional[datetime] = None,
                    end: Optional[datetime] = None,
                    limit: int = 10000) -> list[TelemetryPoint]:
        payload = {"query": self._flux(series, tags, start, end, limit),
                   "type": "flux"}
        async with httpx.AsyncClient(transport=self._transport,
                                     timeout=30.0) as http:
            r = await http.post(f"{self._url}/api/v2/query",
                                params={"org": self._org},
                                json=payload, headers=self._headers)
            r.raise_for_status()
        return _parse_csv(r.text)

    async def list_series(self) -> list[str]:
        q = ('import "influxdata/influxdb/schema" '
             f'schema.measurements(bucket: "{self._bucket}")')
        async with httpx.AsyncClient(transport=self._transport,
                                     timeout=15.0) as http:
            r = await http.post(f"{self._url}/api/v2/query",
                                params={"org": self._org},
                                json={"query": q, "type": "flux"},
                                headers=self._headers)
            r.raise_for_status()
        return sorted({row["_value"] for row in _raw_rows(r.text)
                       if row.get("_value")})

    async def count(self, series: Optional[str] = None,
                    tags: Optional[dict] = None) -> int:
        return len(await self.query(series=series, tags=tags))


# ------------------------------------------------------------------ CSV Flux
def _raw_rows(text: str) -> list[dict]:
    """Filas del CSV anotado de Flux (se ignoran bloques de anotaciones)."""
    lines = [ln for ln in text.splitlines()
             if ln and not ln.startswith("#")]
    if not lines:
        return []
    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    return [dict(r) for r in reader if r.get("_time") or r.get("_value")]


def _parse_csv(text: str) -> list[TelemetryPoint]:
    reservadas = {"result", "table", "_start", "_stop", "_time", "_value",
                  "_field", "_measurement", ""}
    points = []
    for row in _raw_rows(text):
        if not row.get("_time"):
            continue
        ts = datetime.fromisoformat(row["_time"].replace("Z", "+00:00"))
        tags = tuple(sorted((k, v) for k, v in row.items()
                            if k not in reservadas and v))
        points.append(TelemetryPoint(
            series=row.get("_measurement", ""), ts=ts,
            value=float(row["_value"]), tags=tags))
    points.sort(key=lambda p: p.ts)
    return points
