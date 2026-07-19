"""
Servicio de alertado activo (EDS v2.0: alarmas y desviaciones).

Las reglas son CÓDIGO VALIDADO, no configuración opaca: cada disparo es una
función con criterio explícito y revisable en la validación del sistema (CSV).
Toda alerta queda:
  1. Persistida (reconocimiento atribuible: quién y cuándo).
  2. Registrada en la pista de auditoría del lote (evento ``alerta_disparada``,
     ALCOA+: entra en el eBR).
  3. Despachada al webhook configurado (best-effort: 2 intentos; NUNCA bloquea
     ni tira el flujo del lote — la persistencia ya garantiza el registro).
"""
from __future__ import annotations

import logging
import unicodedata
from datetime import datetime, timezone
from uuid import uuid4

from app.domain.entities import Alert

logger = logging.getLogger("radiopharma.alerts")


def _norm(texto: str) -> str:
    """Minúsculas sin acentos: «Desviación» y «desviacion» equivalen."""
    return (unicodedata.normalize("NFD", texto)
            .encode("ascii", "ignore").decode().lower())

# Reglas validadas del sistema (criterio -> severidad)
RULES: tuple[dict, ...] = (
    {"rule": "desviacion_proceso", "severity": "critica",
     "description": "Evento de proceso declarado como desviación"},
    {"rule": "qc_fail", "severity": "critica",
     "description": "Informe QC con veredicto global FAIL"},
    {"rule": "qc_warning", "severity": "aviso",
     "description": "Informe QC con veredicto global WARNING"},
    {"rule": "lote_anulado", "severity": "aviso",
     "description": "Lote anulado (void) con motivo registrado"},
)

SEVERITIES = ("critica", "aviso")


def _send_httpx(url: str, payload: dict) -> None:
    """Emisor por defecto: POST JSON síncrono con timeout corto."""
    import httpx

    with httpx.Client(timeout=5.0) as client:
        client.post(url, json=payload)


class AlertService:
    """Evalúa reglas sobre sucesos del Data Lake y levanta alertas."""

    def __init__(self, repo, ebr=None, webhook_url: str | None = None,
                 sender=None) -> None:
        self._repo = repo
        self._ebr = ebr
        self._webhook_url = webhook_url
        self._sender = sender or _send_httpx

    # ── disparadores (llamados desde los routers del dominio) ────────────
    async def on_event(self, batch_id: str, action: str, detail: str,
                       actor: str) -> Alert | None:
        texto = _norm(f"{action} {detail}")
        if "desviacion" in texto or "deviation" in texto:
            return await self._raise(
                "desviacion_proceso", "critica", batch_id,
                f"Desviación de proceso declarada por {actor}: "
                f"{action} — {detail}")
        return None

    async def on_qc(self, batch_id: str, nuclide: str, overall_status: str,
                    actor: str) -> Alert | None:
        st = overall_status.lower()
        if st == "fail":
            return await self._raise(
                "qc_fail", "critica", batch_id,
                f"QC {nuclide} con veredicto FAIL (registrado por {actor})")
        if st == "warning":
            return await self._raise(
                "qc_warning", "aviso", batch_id,
                f"QC {nuclide} con veredicto WARNING (registrado por {actor})")
        return None

    async def on_void(self, batch_id: str, reason: str,
                      actor: str) -> Alert:
        return await self._raise(
            "lote_anulado", "aviso", batch_id,
            f"Lote anulado por {actor}. Motivo: {reason}")

    # ── núcleo ────────────────────────────────────────────────────────────
    async def _raise(self, rule: str, severity: str, batch_id: str,
                     message: str) -> Alert:
        alert = Alert(alert_id=str(uuid4()),
                      timestamp=datetime.now(timezone.utc),
                      severity=severity, rule=rule, batch_id=batch_id,
                      message=message)
        await self._repo.save(alert)
        logger.warning("ALERTA [%s] %s — lote %s: %s",
                       severity, rule, batch_id, message)
        if self._ebr is not None:
            try:
                await self._ebr.add_event(batch_id, "sistema",
                                          "alerta_disparada",
                                          f"[{severity}] {rule}: {message}")
            except Exception:
                # La alerta ya está persistida; un fallo del eBR no debe
                # tumbar el flujo del lote.
                logger.exception(
                    "No se pudo registrar la alerta en el eBR del lote %s",
                    batch_id)
        self._dispatch(alert)
        return alert

    def _dispatch(self, alert: Alert) -> None:
        """Webhook best-effort: 2 intentos, nunca propaga excepciones."""
        if not self._webhook_url:
            return
        payload = {
            "alert_id": alert.alert_id,
            "timestamp": alert.timestamp.isoformat(),
            "severity": alert.severity,
            "rule": alert.rule,
            "batch_id": alert.batch_id,
            "message": alert.message,
            "source": "radiopharma-os/data-lake",
        }
        for intento in (1, 2):
            try:
                self._sender(self._webhook_url, payload)
                return
            except Exception:
                logger.exception(
                    "Fallo enviando webhook de alerta %s (intento %d/2)",
                    alert.alert_id, intento)

    # ── consulta y reconocimiento ────────────────────────────────────────
    async def list(self, severity: str | None = None,
                   only_unacked: bool = False,
                   limit: int = 100) -> list[Alert]:
        return await self._repo.list(severity=severity,
                                     only_unacked=only_unacked, limit=limit)

    async def ack(self, alert_id: str, username: str) -> Alert | None:
        """Reconocimiento idempotente (ALCOA+: atribuible y fechado)."""
        return await self._repo.ack(alert_id, username)
