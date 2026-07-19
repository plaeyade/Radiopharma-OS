"""
Modelo relacional del registro de lote (SQLAlchemy 2.0).

Tabla append-only: sin UPDATE de contenido; solo el campo de estado
cambia a "voided" mediante la operación de anulación controlada.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Float, DateTime, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class BatchRow(Base):
    __tablename__ = "batch_records"

    batch_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    reaction_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    product_nuclide: Mapped[str] = mapped_column(String(16), nullable=False)
    beam_energy_mev: Mapped[float] = mapped_column(Float, nullable=False)
    current_ua: Mapped[float] = mapped_column(Float, nullable=False)
    irradiation_time_min: Mapped[float] = mapped_column(Float, nullable=False)
    enrichment: Mapped[float | None] = mapped_column(Float, nullable=True)
    saturation_yield_mbq_ua: Mapped[float] = mapped_column(Float, nullable=False)
    eob_activity_gbq: Mapped[float] = mapped_column(Float, nullable=False)
    eob_activity_gbq_uncertainty: Mapped[float] = mapped_column(Float, nullable=False)
    saturation_factor: Mapped[float] = mapped_column(Float, nullable=False)
    relative_uncertainty: Mapped[float] = mapped_column(Float, nullable=False)
    dataset_id: Mapped[str] = mapped_column(String(120), nullable=False)
    dataset_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stopping_source: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="completed")
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    release_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    released_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    release_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EbrSignatureRow(Base):
    __tablename__ = "ebr_signatures"

    signature_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    signed_by: Mapped[str] = mapped_column(String(120), nullable=False)
    signed_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    meaning: Mapped[str] = mapped_column(String(32), nullable=False)
    record_hash_signed: Mapped[str] = mapped_column(String(64), nullable=False)
    signature_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class QcReportRow(Base):
    __tablename__ = "qc_reports"

    qc_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    product: Mapped[str] = mapped_column(String(64), nullable=False)
    nuclide: Mapped[str] = mapped_column(String(16), nullable=False)
    overall_status: Mapped[str] = mapped_column(String(16), nullable=False)
    rules_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    half_life_fit_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class AuditEventRow(Base):
    """Eventos de proceso declarados (desviaciones, incidencias)."""
    __tablename__ = "audit_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    timestamp: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
