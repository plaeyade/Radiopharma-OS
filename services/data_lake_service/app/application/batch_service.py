"""
Casos de uso del Data Lake: registrar, consultar y anular lotes.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.domain.entities import (BatchRecord, BatchStatus, BeamParameters,
                                 DatasetLineage, ProductionResults, QcRecord,
                                 ReleaseStatus)
from app.domain.interfaces import BatchRepository, ObjectStore, QcRepository


class BatchService:
    def __init__(self, repo: BatchRepository, store: ObjectStore,
                 qc_repo: QcRepository | None = None) -> None:
        self._repo = repo
        self._store = store
        self._qc = qc_repo

    async def register_batch(
        self,
        created_by: str,
        reaction_id: str,
        target_id: str,
        product_nuclide: str,
        beam: BeamParameters,
        results: ProductionResults,
        lineage: DatasetLineage,
    ) -> BatchRecord:
        batch_id = f"B-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"
        record = BatchRecord(
            batch_id=batch_id,
            created_at=datetime.now(timezone.utc),
            created_by=created_by,
            reaction_id=reaction_id, target_id=target_id,
            product_nuclide=product_nuclide,
            beam=beam, results=results, lineage=lineage,
            status=BatchStatus.COMPLETED,
        ).with_integrity()

        # artefacto: payload canónico completo en el object store
        key = f"batches/{record.created_at:%Y/%m}/{batch_id}.json"
        artifact = json.dumps(record.canonical_payload(), indent=2,
                              ensure_ascii=False).encode("utf-8")
        uri = self._store.put(key, artifact)
        record = BatchRecord(
            batch_id=record.batch_id, created_at=record.created_at,
            created_by=record.created_by, reaction_id=record.reaction_id,
            target_id=record.target_id, product_nuclide=record.product_nuclide,
            beam=record.beam, results=record.results, lineage=record.lineage,
            status=record.status, artifact_key=key,
            record_hash=record.record_hash)
        return await self._repo.save(record)

    async def get_batch(self, batch_id: str) -> Optional[BatchRecord]:
        return await self._repo.get(batch_id)

    async def list_batches(self, reaction_id: Optional[str] = None,
                           limit: int = 100) -> list[BatchRecord]:
        return await self._repo.list(reaction_id=reaction_id, limit=limit)

    async def void_batch(self, batch_id: str, reason: str) -> Optional[BatchRecord]:
        if not reason.strip():
            raise ValueError("El motivo de anulación es obligatorio (ALCOA+)")
        batch = await self._repo.get(batch_id)
        if batch is not None and batch.release_status == ReleaseStatus.RELEASED:
            raise ValueError("No se puede anular un lote ya liberado")
        return await self._repo.void(batch_id, reason)

    def get_artifact(self, record: BatchRecord) -> bytes:
        if not record.artifact_key:
            raise ValueError("El lote no tiene artefacto asociado")
        return self._store.get(record.artifact_key)

    @staticmethod
    def verify_integrity(record: BatchRecord) -> bool:
        """Re-calcula el hash y lo compara con el almacenado."""
        return record.compute_hash() == record.record_hash

    # ---------------- informes QC ----------------

    async def register_qc_report(
        self,
        batch_id: str,
        created_by: str,
        product: str,
        nuclide: str,
        overall_status: str,
        rules: tuple[dict, ...],
        half_life_fit: dict | None,
    ) -> QcRecord:
        batch = await self._repo.get(batch_id)
        if batch is None:
            raise LookupError(f"Lote no encontrado: {batch_id}")
        if batch.status == BatchStatus.VOIDED:
            raise ValueError("No se puede registrar QC sobre un lote anulado")
        if overall_status not in ("pass", "fail", "warning"):
            raise ValueError("overall_status debe ser pass | fail | warning")
        qc_id = f"QC-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"
        record = QcRecord(
            qc_id=qc_id, batch_id=batch_id,
            created_at=datetime.now(timezone.utc), created_by=created_by,
            product=product, nuclide=nuclide, overall_status=overall_status,
            rules=rules, half_life_fit=half_life_fit).with_integrity()
        return await self._qc.save(record)

    async def list_qc_reports(self, batch_id: str) -> list[QcRecord]:
        return await self._qc.list_for_batch(batch_id)

    # ---------------- liberación GMP ----------------

    async def release_batch(self, batch_id: str, decision: str,
                            released_by: str,
                            reason: str | None = None) -> BatchRecord:
        """
        Decisión de liberación con reglas GMP:
        - released: exige al menos un informe QC con overall_status=pass.
        - rejected: exige motivo.
        - lote anulado o ya liberado/rechazado: inmutable.
        """
        batch = await self._repo.get(batch_id)
        if batch is None:
            raise LookupError(f"Lote no encontrado: {batch_id}")
        if batch.status == BatchStatus.VOIDED:
            raise ValueError("Lote anulado: no admite liberación")
        if batch.release_status != ReleaseStatus.PENDING:
            raise ValueError(f"El lote ya tiene decisión: {batch.release_status.value}")
        if decision == "released":
            reports = await self._qc.list_for_batch(batch_id)
            if not any(r.overall_status == "pass" for r in reports):
                raise ValueError(
                    "GMP: no se puede liberar sin al menos un informe QC 'pass'")
        elif decision == "rejected":
            if not reason or not reason.strip():
                raise ValueError("El rechazo exige motivo (ALCOA+)")
        else:
            raise ValueError("decision debe ser released | rejected")
        return await self._repo.release(batch_id, decision, released_by, reason)
