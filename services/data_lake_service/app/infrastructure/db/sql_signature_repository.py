"""
Repositorio SQL de firmas electrónicas (append-only).
"""
from __future__ import annotations

from datetime import timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.entities import EbrSignature
from app.infrastructure.db.models import EbrSignatureRow


class SqlSignatureRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def save(self, sig: EbrSignature) -> EbrSignature:
        async with self._sf() as session:
            session.add(EbrSignatureRow(
                signature_id=sig.signature_id, batch_id=sig.batch_id,
                signed_by=sig.signed_by, signed_at=sig.signed_at,
                meaning=sig.meaning, record_hash_signed=sig.record_hash_signed,
                signature_hash=sig.signature_hash))
            await session.commit()
        return sig

    async def list_for_batch(self, batch_id: str) -> list[EbrSignature]:
        async with self._sf() as session:
            stmt = (select(EbrSignatureRow)
                    .where(EbrSignatureRow.batch_id == batch_id)
                    .order_by(EbrSignatureRow.signed_at.asc()))
            rows = (await session.execute(stmt)).scalars().all()
            return [self._to_entity(r) for r in rows]

    @staticmethod
    def _to_entity(row: EbrSignatureRow) -> EbrSignature:
        ts = row.signed_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return EbrSignature(
            signature_id=row.signature_id, batch_id=row.batch_id,
            signed_by=row.signed_by, signed_at=ts, meaning=row.meaning,
            record_hash_signed=row.record_hash_signed,
            signature_hash=row.signature_hash)
