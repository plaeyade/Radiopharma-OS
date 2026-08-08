"""
Radiopharma OS - Data Lake Service (Fase 1)
Capa de dominio: registro de lote de irradiación (ALCOA+).

Principios regulatorios (EDS v2.0, cap. 49 y 58):
- Los registros son INMUTABLES: no existen operaciones de borrado ni edición.
- Las correcciones se hacen anulando (void) con motivo y creando un registro nuevo.
- Cada registro lleva un hash SHA-256 de su contenido canónico (integridad)
  y la linaje completa de datasets usados en el cálculo (trazabilidad).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class BatchStatus(str, Enum):
    COMPLETED = "completed"
    VOIDED = "voided"


class ReleaseStatus(str, Enum):
    """Estado de liberación GMP del lote."""
    PENDING = "pending"
    RELEASED = "released"
    REJECTED = "rejected"


@dataclass(frozen=True)
class DatasetLineage:
    """Linaje de los datos nucleares usados en el cálculo del lote."""
    dataset_id: str
    dataset_sha256: Optional[str]
    stopping_source: str


@dataclass(frozen=True)
class BeamParameters:
    beam_energy_mev: float
    current_ua: float
    irradiation_time_min: float
    enrichment: Optional[float] = None


@dataclass(frozen=True)
class ProductionResults:
    saturation_yield_mbq_ua: float
    eob_activity_gbq: float
    eob_activity_gbq_uncertainty: float
    saturation_factor: float
    relative_uncertainty: float


@dataclass(frozen=True)
class BatchRecord:
    """Registro inmutable de un lote de producción."""
    batch_id: str
    created_at: datetime
    created_by: str
    reaction_id: str
    target_id: str
    product_nuclide: str
    beam: BeamParameters
    results: ProductionResults
    lineage: DatasetLineage
    status: BatchStatus = BatchStatus.COMPLETED
    void_reason: Optional[str] = None
    artifact_key: Optional[str] = None
    record_hash: str = ""
    release_status: ReleaseStatus = ReleaseStatus.PENDING
    released_by: Optional[str] = None
    release_reason: Optional[str] = None
    released_at: Optional[datetime] = None

    def canonical_payload(self) -> dict:
        """Contenido canónico para el hash de integridad (sin metacampos)."""
        return {
            "batch_id": self.batch_id,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "reaction_id": self.reaction_id,
            "target_id": self.target_id,
            "product_nuclide": self.product_nuclide,
            "beam": {
                "beam_energy_mev": self.beam.beam_energy_mev,
                "current_ua": self.beam.current_ua,
                "irradiation_time_min": self.beam.irradiation_time_min,
                "enrichment": self.beam.enrichment,
            },
            "results": {
                "saturation_yield_mbq_ua": self.results.saturation_yield_mbq_ua,
                "eob_activity_gbq": self.results.eob_activity_gbq,
                "eob_activity_gbq_uncertainty": self.results.eob_activity_gbq_uncertainty,
                "saturation_factor": self.results.saturation_factor,
                "relative_uncertainty": self.results.relative_uncertainty,
            },
            "lineage": {
                "dataset_id": self.lineage.dataset_id,
                "dataset_sha256": self.lineage.dataset_sha256,
                "stopping_source": self.lineage.stopping_source,
            },
        }

    def compute_hash(self) -> str:
        """SHA-256 del payload canónico (orden de claves fijo)."""
        blob = json.dumps(self.canonical_payload(), sort_keys=True,
                          separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def with_integrity(self) -> "BatchRecord":
        """Devuelve una copia con el hash de integridad calculado."""
        return BatchRecord(
            batch_id=self.batch_id, created_at=self.created_at,
            created_by=self.created_by, reaction_id=self.reaction_id,
            target_id=self.target_id, product_nuclide=self.product_nuclide,
            beam=self.beam, results=self.results, lineage=self.lineage,
            status=self.status, void_reason=self.void_reason,
            artifact_key=self.artifact_key, record_hash=self.compute_hash(),
            release_status=self.release_status, released_by=self.released_by,
            release_reason=self.release_reason, released_at=self.released_at)


@dataclass(frozen=True)
class QcRecord:
    """Informe QC inmutable ligado a un lote (ALCOA+)."""
    qc_id: str
    batch_id: str
    created_at: datetime
    created_by: str
    product: str
    nuclide: str
    overall_status: str                    # pass | fail | warning
    rules: tuple[dict, ...] = ()           # evaluaciones de reglas
    half_life_fit: Optional[dict] = None   # ajuste de vida media
    record_hash: str = ""

    def canonical_payload(self) -> dict:
        return {
            "qc_id": self.qc_id, "batch_id": self.batch_id,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by, "product": self.product,
            "nuclide": self.nuclide, "overall_status": self.overall_status,
            "rules": list(self.rules), "half_life_fit": self.half_life_fit,
        }

    def compute_hash(self) -> str:
        blob = json.dumps(self.canonical_payload(), sort_keys=True,
                          separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def with_integrity(self) -> "QcRecord":
        return QcRecord(
            qc_id=self.qc_id, batch_id=self.batch_id,
            created_at=self.created_at, created_by=self.created_by,
            product=self.product, nuclide=self.nuclide,
            overall_status=self.overall_status, rules=self.rules,
            half_life_fit=self.half_life_fit,
            record_hash=self.compute_hash())


class SignatureMeaning(str, Enum):
    """Significado de la firma electrónica (21 CFR Part 11)."""
    PERFORMED_BY = "performed_by"
    REVIEWED_BY = "reviewed_by"
    APPROVED_BY = "approved_by"


@dataclass(frozen=True)
class EbrSignature:
    """Firma electrónica vinculada al hash del registro firmado.

    El signature_hash liga: registro + firmante + significado + instante;
    cualquier cambio en el registro invalida la firma (verificable).
    """
    signature_id: str
    batch_id: str
    signed_by: str
    signed_at: datetime
    meaning: str
    record_hash_signed: str           # hash del lote en el momento de firmar
    signature_hash: str = ""

    def compute_hash(self) -> str:
        blob = "|".join([
            self.record_hash_signed, self.signed_by, self.meaning,
            self.signed_at.isoformat(), self.batch_id])
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def with_integrity(self) -> "EbrSignature":
        return EbrSignature(
            signature_id=self.signature_id, batch_id=self.batch_id,
            signed_by=self.signed_by, signed_at=self.signed_at,
            meaning=self.meaning, record_hash_signed=self.record_hash_signed,
            signature_hash=self.compute_hash())


@dataclass(frozen=True)
class AuditEvent:
    """Evento de la pista de auditoría del eBR."""
    timestamp: datetime
    actor: str
    action: str
    detail: str


@dataclass(frozen=True)
class AuditEventRecord:
    """Evento de proceso persistido (append-only, ALCOA+).

    A diferencia de la pista reconstruida (registro/QC/liberación/firmas),
    estos eventos se declaran explícitamente: desviaciones de proceso,
    incidencias de la corrida, observaciones del operador. Quedan ligados
    al lote y entran en el eBR con sello de tiempo y actor atribuible.
    """
    event_id: str
    batch_id: str
    timestamp: datetime
    actor: str
    action: str
    detail: str


@dataclass(frozen=True)
class EbrDocument:
    """Electronic Batch Record: consolidado firmable del lote."""
    ebr_id: str
    generated_at: datetime
    batch: dict
    qc_reports: tuple[dict, ...]
    signatures: tuple[dict, ...]
    audit_trail: tuple[AuditEvent, ...]
    integrity: dict


@dataclass(frozen=True)
class Alert:
    """Alerta activa disparada por una regla validada del sistema.

    ALCOA+: persistida con sello de tiempo, reconocimiento atribuible
    (``acked_by``/``acked_at``) y registrada además en la pista de
    auditoría del lote (evento ``alerta_disparada`` del eBR).
    """
    alert_id: str
    timestamp: datetime
    severity: str            # "critica" | "aviso"
    rule: str                # id de la regla (código validado)
    batch_id: str
    message: str
    acked_by: str | None = None
    acked_at: datetime | None = None


@dataclass
class SimulationRecord:
    """Resultado de una simulación científica persistido (EDS 4.9, 7.11):
    p. ej. FEM térmico Elmer (temperature, stresses, deformations, heat
    flux). Append-only como todo el Data Lake (ALCOA+)."""
    simulation_id: str
    created_at: datetime
    created_by: str
    kind: str                      # "elmer_thermal", "burnup_radial", ...
    solver: str                    # binario y versión usados
    reaction_id: Optional[str]     # linaje yield→burnup→elmer (cap. 8.11)
    target_id: Optional[str]
    inputs: dict                   # parámetros físicos del caso
    results: dict                  # temperature/stresses/deformations/heat flux
    artifact_key: Optional[str] = None   # simulation/<kind>/<id>/...
    record_hash: str = ""

    def canonical_payload(self) -> dict:
        return {
            "simulation_id": self.simulation_id,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "kind": self.kind,
            "solver": self.solver,
            "reaction_id": self.reaction_id,
            "target_id": self.target_id,
            "inputs": self.inputs,
            "results": self.results,
        }

    def compute_hash(self) -> str:
        blob = json.dumps(self.canonical_payload(), sort_keys=True,
                          separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()
