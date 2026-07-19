"""
Modelo relacional del backend SQLite de telemetría (dev/test).
"""
from __future__ import annotations

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TelemetryRow(Base):
    __tablename__ = "telemetry_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    ts_epoch: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
