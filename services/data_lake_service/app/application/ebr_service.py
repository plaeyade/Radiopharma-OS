"""Servicio eBR: generación del Electronic Batch Record y firmas electrónicas.

Cumplimiento 21 CFR Part 11 (EDS v2.0, cap. 58):
- §11.50/11.70: la firma liga registro (hash) + firmante + significado + instante.
- §11.200(a): la firma exige re-autenticación con ambos componentes (usuario+contraseña).
- Pista de auditoría: reconstruida de eventos con sello de tiempo, ordenada.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from ..domain.entities import (
    AuditEvent, AuditEventRecord, BatchRecord, BatchStatus, EbrDocument,
    EbrSignature, QcRecord, ReleaseStatus, SignatureMeaning,
)
from ..domain.interfaces import (
    AuditEventRepository, AuthVerifier, BatchRepository, QcRepository,
    SignatureRepository,
)

# Rol mínimo requerido por significado de firma (segregación de funciones)
_ROLE_FOR_MEANING = {
    SignatureMeaning.PERFORMED_BY: "operador",
    SignatureMeaning.REVIEWED_BY: "supervisor",
    SignatureMeaning.APPROVED_BY: "calidad",
}
_ROLE_RANK = {"operador": 1, "supervisor": 2, "calidad": 3, "admin": 4}


# ---------------------------------------------------------------- serialización
def _batch_dict(b: BatchRecord) -> dict:
    d = b.canonical_payload()
    d.update({
        "status": b.status.value,
        "void_reason": b.void_reason,
        "artifact_key": b.artifact_key,
        "record_hash": b.record_hash,
        "release_status": b.release_status.value,
        "released_by": b.released_by,
        "release_reason": b.release_reason,
        "released_at": b.released_at.isoformat() if b.released_at else None,
    })
    return d


def _qc_dict(r: QcRecord) -> dict:
    d = r.canonical_payload()
    d["record_hash"] = r.record_hash
    return d


def _sig_dict(s: EbrSignature) -> dict:
    return {
        "signature_id": s.signature_id,
        "batch_id": s.batch_id,
        "signed_by": s.signed_by,
        "signed_at": s.signed_at.isoformat(),
        "meaning": s.meaning,
        "record_hash_signed": s.record_hash_signed,
        "signature_hash": s.signature_hash,
    }


def _audit_dict(e: AuditEvent) -> dict:
    return {"timestamp": e.timestamp.isoformat(), "actor": e.actor,
            "action": e.action, "detail": e.detail}


def _integrity(payload: dict) -> dict:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)
    return {"algorithm": "sha256",
            "document_hash": hashlib.sha256(blob.encode("utf-8")).hexdigest()}


# ---------------------------------------------------------------- servicio
class EbrService:
    def __init__(
        self,
        batches: BatchRepository,
        qc: QcRepository,
        signatures: SignatureRepository,
        auth: AuthVerifier,
        audit_events: Optional[AuditEventRepository] = None,
    ) -> None:
        self._batches = batches
        self._qc = qc
        self._sigs = signatures
        self._auth = auth
        self._events = audit_events

    # ── generación del documento consolidado ─────────────────────────────
    async def generate_ebr(self, batch_id: str) -> EbrDocument:
        batch = await self._batches.get(batch_id)
        if batch is None:
            raise KeyError(f"Lote no encontrado: {batch_id}")
        reports = await self._qc.list_for_batch(batch_id)
        signatures = await self._sigs.list_for_batch(batch_id)

        # Pista de auditoría reconstruida (orden cronológico)
        trail: List[AuditEvent] = [
            AuditEvent(timestamp=batch.created_at, actor=batch.created_by,
                       action="batch_registered",
                       detail=f"reacción {batch.reaction_id} · blanco {batch.target_id} · "
                              f"hash {batch.record_hash[:12]}…"),
        ]
        for r in reports:
            trail.append(AuditEvent(
                timestamp=r.created_at, actor=r.created_by,
                action="qc_report_registered",
                detail=f"{r.qc_id} · resultado global: {r.overall_status}"))
        if batch.release_status is not ReleaseStatus.PENDING:
            trail.append(AuditEvent(
                timestamp=batch.released_at or batch.created_at,
                actor=batch.released_by or "system",
                action=f"batch_{batch.release_status.value}",
                detail=batch.release_reason or ""))
        for s in signatures:
            trail.append(AuditEvent(
                timestamp=s.signed_at, actor=s.signed_by,
                action=f"signature_{s.meaning}",
                detail=f"firma {s.signature_hash[:12]}… sobre registro "
                       f"{s.record_hash_signed[:12]}…"))
        # Eventos de proceso declarados (desviaciones, incidencias)
        if self._events is not None:
            for e in await self._events.list_for_batch(batch_id):
                trail.append(AuditEvent(timestamp=e.timestamp, actor=e.actor,
                                        action=e.action, detail=e.detail))
        trail.sort(key=lambda e: e.timestamp)

        doc_payload = {
            "batch": _batch_dict(batch),
            "qc_reports": [_qc_dict(r) for r in reports],
            "signatures": [_sig_dict(s) for s in signatures],
            "audit_trail": [_audit_dict(e) for e in trail],
        }
        return EbrDocument(
            ebr_id=str(uuid4()),
            generated_at=datetime.now(timezone.utc),
            batch=doc_payload["batch"],
            qc_reports=tuple(doc_payload["qc_reports"]),
            signatures=tuple(doc_payload["signatures"]),
            audit_trail=tuple(trail),
            integrity=_integrity(doc_payload),
        )

    # ── firma electrónica ────────────────────────────────────────────────
    async def sign_batch(
        self,
        batch_id: str,
        username: str,
        password: str,
        meaning: str,
    ) -> EbrSignature:
        batch = await self._batches.get(batch_id)
        if batch is None:
            raise KeyError(f"Lote no encontrado: {batch_id}")

        try:
            sig_meaning = SignatureMeaning(meaning)
        except ValueError:
            valid = [m.value for m in SignatureMeaning]
            raise ValueError(
                f"Significado de firma inválido: {meaning}. Válidos: {valid}") from None

        # §11.200(a): re-autenticación con credenciales en el momento de firmar
        user = self._auth.authenticate(username, password)
        if user is None:
            raise PermissionError(
                "Credenciales inválidas: la firma requiere re-autenticación")

        # Autorización por rol según significado (segregación de funciones)
        required_role = _ROLE_FOR_MEANING[sig_meaning]
        if _ROLE_RANK.get(user["role"], 0) < _ROLE_RANK[required_role]:
            raise PermissionError(
                f"Rol insuficiente: '{user['role']}' no puede firmar como "
                f"'{sig_meaning.value}' (requiere '{required_role}')")

        # Reglas de estado del lote
        if batch.status is BatchStatus.VOIDED:
            raise ValueError("No se puede firmar un lote anulado (voided)")
        if (sig_meaning is SignatureMeaning.APPROVED_BY
                and batch.release_status is ReleaseStatus.PENDING):
            raise ValueError(
                "APPROVED_BY requiere decisión de liberación previa "
                "(released o rejected)")

        # La firma se vincula al hash del registro vigente: si el registro
        # cambiara después, la firma quedaría inválida (verificable).
        sig = EbrSignature(
            signature_id=str(uuid4()),
            batch_id=batch_id,
            signed_by=username,
            signed_at=datetime.now(timezone.utc),
            meaning=sig_meaning.value,
            record_hash_signed=batch.record_hash,
        ).with_integrity()
        return await self._sigs.save(sig)

    # ── eventos de proceso declarados ────────────────────────────────────
    async def add_event(self, batch_id: str, actor: str, action: str,
                        detail: str) -> AuditEventRecord:
        """Registra un evento de proceso en la pista de auditoría del lote.

        Append-only (ALCOA+): sello de tiempo de servidor y actor derivado
        del token — nunca del cuerpo de la petición.
        """
        if self._events is None:
            raise RuntimeError("Repositorio de eventos no configurado")
        if await self._batches.get(batch_id) is None:
            raise KeyError(f"Lote no encontrado: {batch_id}")
        event = AuditEventRecord(
            event_id=str(uuid4()), batch_id=batch_id,
            timestamp=datetime.now(timezone.utc), actor=actor,
            action=action, detail=detail)
        return await self._events.save(event)

    # ── verificación de integridad ───────────────────────────────────────
    async def verify_ebr(self, batch_id: str) -> dict:
        """Verifica el hash del lote y la vigencia de cada firma."""
        batch = await self._batches.get(batch_id)
        if batch is None:
            raise KeyError(f"Lote no encontrado: {batch_id}")
        checks = [{
            "item": "batch_record_hash",
            "ok": batch.compute_hash() == batch.record_hash,
        }]
        for r in await self._qc.list_for_batch(batch_id):
            checks.append({
                "item": f"qc_report:{r.qc_id}",
                "ok": r.compute_hash() == r.record_hash,
            })
        for s in await self._sigs.list_for_batch(batch_id):
            checks.append({
                "item": f"signature:{s.meaning}:{s.signed_by}",
                "ok": s.signature_hash == s.compute_hash(),
                "bound_record_current": s.record_hash_signed == batch.record_hash,
            })
        return {"batch_id": batch_id,
                "all_ok": all(c["ok"] for c in checks),
                "checks": checks}
