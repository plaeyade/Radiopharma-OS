"""
Puertos del Data Lake Service.
"""
from __future__ import annotations

from typing import Optional, Protocol

from app.domain.entities import (AuditEventRecord, BatchRecord, EbrSignature,
                                 QcRecord)


class BatchRepository(Protocol):
    """Persistencia de registros de lote (append-only, sin delete)."""

    async def save(self, record: BatchRecord) -> BatchRecord: ...

    async def get(self, batch_id: str) -> Optional[BatchRecord]: ...

    async def list(self, reaction_id: Optional[str] = None,
                   limit: int = 100) -> list[BatchRecord]: ...

    async def void(self, batch_id: str, reason: str) -> Optional[BatchRecord]: ...

    async def release(self, batch_id: str, decision: str, released_by: str,
                      reason: Optional[str]) -> Optional[BatchRecord]: ...


class SignatureRepository(Protocol):
    """Persistencia de firmas electrónicas (append-only)."""

    async def save(self, signature: EbrSignature) -> EbrSignature: ...

    async def list_for_batch(self, batch_id: str) -> list[EbrSignature]: ...


class QcRepository(Protocol):
    """Persistencia de informes QC (append-only)."""

    async def save(self, record: QcRecord) -> QcRecord: ...

    async def list_for_batch(self, batch_id: str) -> list[QcRecord]: ...

    async def get(self, qc_id: str) -> Optional[QcRecord]: ...


class AuditEventRepository(Protocol):
    """Persistencia de eventos de proceso declarados (append-only)."""

    async def save(self, event: AuditEventRecord) -> AuditEventRecord: ...

    async def list_for_batch(self, batch_id: str) -> list[AuditEventRecord]: ...


class ObjectStore(Protocol):
    """Almacenamiento de objetos (artefactos de lote: JSON, reportes)."""

    def put(self, key: str, data: bytes, content_type: str = "application/json") -> str: ...

    def get(self, key: str) -> bytes: ...


class AuthVerifier(Protocol):
    """Re-autenticación de credenciales para firmas electrónicas (21 CFR Part 11)."""

    def authenticate(self, username: str, password: str) -> Optional[dict]:
        """Devuelve {'username': ..., 'role': ...} si las credenciales son válidas; None si no."""
        ...
