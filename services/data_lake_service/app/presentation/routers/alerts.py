"""
Router REST de alertas activas del Data Lake Service.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.application.alert_service import RULES, AlertService
from app.infrastructure.security.jwt_guard import (Identity, current_identity,
                                                   require_operator)
from app.presentation.schemas import AlertOut

router = APIRouter(prefix="/api/v1/alerts", tags=["alertas"])

_service: AlertService | None = None


def init(service: AlertService) -> None:
    global _service
    _service = service


def _out(a) -> AlertOut:
    return AlertOut(alert_id=a.alert_id, timestamp=a.timestamp,
                    severity=a.severity, rule=a.rule, batch_id=a.batch_id,
                    message=a.message, acked_by=a.acked_by,
                    acked_at=a.acked_at)


@router.get("", response_model=list[AlertOut])
async def list_alerts(severity: str | None = None,
                      only_unacked: bool = False, limit: int = 100,
                      _: Identity = Depends(current_identity)) -> list[AlertOut]:
    alerts = await _service.list(severity=severity,
                                 only_unacked=only_unacked, limit=limit)
    return [_out(a) for a in alerts]


@router.get("/rules")
async def list_rules(_: Identity = Depends(current_identity)) -> list[dict]:
    """Catálogo de reglas validadas del sistema (código, no config opaca)."""
    return [dict(r) for r in RULES]


@router.post("/{alert_id}/ack", response_model=AlertOut)
async def ack_alert(alert_id: str,
                    identity: Identity = Depends(require_operator)) -> AlertOut:
    alert = await _service.ack(alert_id, identity.username)
    if alert is None:
        raise HTTPException(status_code=404,
                            detail=f"Alerta no encontrada: {alert_id}")
    return _out(alert)
