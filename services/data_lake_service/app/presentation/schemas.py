"""
Esquemas Pydantic de la API del Data Lake Service.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class BeamIn(BaseModel):
    beam_energy_mev: float = Field(..., gt=0, le=40)
    current_ua: float = Field(..., gt=0, le=500)
    irradiation_time_min: float = Field(..., gt=0, le=1000)
    enrichment: Optional[float] = Field(None, gt=0, le=1.0)


class ResultsIn(BaseModel):
    saturation_yield_mbq_ua: float
    eob_activity_gbq: float
    eob_activity_gbq_uncertainty: float
    saturation_factor: float
    relative_uncertainty: float


class LineageIn(BaseModel):
    dataset_id: str
    dataset_sha256: Optional[str] = None
    stopping_source: str


class BatchCreateIn(BaseModel):
    # created_by es opcional e informativo: el valor real lo fija el token JWT
    created_by: str | None = Field(None, examples=["operador.ciclotron"])
    reaction_id: str
    target_id: str
    product_nuclide: str
    beam: BeamIn
    results: ResultsIn
    lineage: LineageIn


class VoidIn(BaseModel):
    reason: str = Field(..., min_length=5, examples=["Lote repetido por error de captura"])


class QcReportCreateIn(BaseModel):
    product: str = Field(..., examples=["fdg"])
    nuclide: str = Field(..., examples=["18F"])
    overall_status: str = Field(..., examples=["pass"])
    rules: list[dict] = Field(default_factory=list)
    half_life_fit: Optional[dict] = None


class QcReportOut(BaseModel):
    qc_id: str
    batch_id: str
    created_at: datetime
    created_by: str
    product: str
    nuclide: str
    overall_status: str
    rules: list[dict]
    half_life_fit: Optional[dict]
    record_hash: str
    integrity_ok: bool


class ReleaseIn(BaseModel):
    decision: str = Field(..., examples=["released"])
    reason: Optional[str] = Field(None, examples=["Liberado conforme a QC"])


class BatchOut(BaseModel):
    batch_id: str
    created_at: datetime
    created_by: str
    reaction_id: str
    target_id: str
    product_nuclide: str
    beam: BeamIn
    results: ResultsIn
    lineage: LineageIn
    status: str
    void_reason: Optional[str] = None
    artifact_key: Optional[str] = None
    record_hash: str
    integrity_ok: bool
    release_status: str = "pending"
    released_by: Optional[str] = None
    release_reason: Optional[str] = None
    released_at: Optional[datetime] = None


# ---------------- eBR y firmas electrónicas ----------------

class SignatureIn(BaseModel):
    """Petición de firma electrónica (21 CFR Part 11: re-autenticación)."""
    username: str = Field(..., examples=["operador.ciclotron"])
    password: str = Field(..., min_length=1)
    meaning: str = Field(..., examples=["performed_by"])


class SignatureOut(BaseModel):
    signature_id: str
    batch_id: str
    signed_by: str
    signed_at: datetime
    meaning: str
    record_hash_signed: str
    signature_hash: str


class AuditEventOut(BaseModel):
    timestamp: datetime
    actor: str
    action: str
    detail: str


class EventIn(BaseModel):
    """Declaración de un evento de proceso (desviación, incidencia)."""
    action: str = Field(..., min_length=1, max_length=64,
                        pattern=r"^[a-z][a-z0-9_]*$",
                        examples=["process_deviation"])
    detail: str = Field(..., min_length=1, max_length=2000)


class EventOut(BaseModel):
    event_id: str
    batch_id: str
    timestamp: datetime
    actor: str
    action: str
    detail: str


class EbrOut(BaseModel):
    """Electronic Batch Record consolidado."""
    ebr_id: str
    generated_at: datetime
    batch: dict
    qc_reports: list[dict]
    signatures: list[dict]
    audit_trail: list[AuditEventOut]
    integrity: dict


class EbrVerifyOut(BaseModel):
    batch_id: str
    all_ok: bool
    checks: list[dict]


class VeraPdfOut(BaseModel):
    batch_id: str
    available: bool
    compliant: bool | None = None
    profile: str = ""
    failed_rules: list[str] = []
    summary: str = ""
    error: str = ""
    internal_findings: list[str] = []
    registered_in_ebr: bool = False


class AlertOut(BaseModel):
    """Alerta activa (persistida y reconocible)."""
    alert_id: str
    timestamp: datetime
    severity: str
    rule: str
    batch_id: str
    message: str
    acked_by: str | None = None
    acked_at: datetime | None = None
