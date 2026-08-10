"""Clinical Delivery & Dose Management Engine (EDS cap. 32).

Coordina la transición producción → clínica tras la liberación del lote:

- **Dose Manager (32.6)**: asignación trazable de actividad a dosis.
- **Patient Schedule Manager (32.7)**: programación de pacientes.
- **Decay Calculator (32.8)**: el cálculo de actividad usa
  EXCLUSIVAMENTE el NNDC Service (constante de decaimiento remota);
  si el servicio no está disponible, el motor devuelve 503 honesto —
  nunca sustituye la constante por un valor local.
- **Delivery Coordinator (32.9)** y **Administration Manager (32.10)**:
  secuencia temporal completa 32.19 (preparación → despacho → recepción
  → confirmación → administración).
- **Reprogramación por decaimiento (32.11)**: el motor PROPONE; la
  reprogramación exige confirmación de un usuario autorizado — nunca
  es automática.
- **Validación (32.21)** y **Auditoría (32.23)**.

Límites canónicos (32.3): el motor NO produce, NO hace QC, NO
interpreta clínicamente y NO prescribe. Las recomendaciones quedan
identificadas como soporte a la decisión (32.18/41.9).
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

VERSION_MOTOR = "cddme-1.0.0"

SECUENCIA_ENTREGA = ("preparacion", "despacho", "recepcion",
                     "confirmacion_entrega")  # 32.9


class ClinicoInvalido(ValueError):
    """Inconsistencia que impide la asignación o la transición (32.21)."""


class NndsUnavailable(RuntimeError):
    """NNDC Service no disponible: 503 honesto, nunca se simula (32.8)."""


class NndsDecayClient:
    """Cliente HTTP del Decay Calculator hacia el NNDC Service (32.8)."""

    def __init__(self, base_url: str | None = None,
                 timeout_s: float = 5.0) -> None:
        self.base_url = (base_url
                         or os.environ.get("NUCLEAR_DATA_URL", "")).rstrip("/")
        self.timeout_s = timeout_s

    def constante_decaimiento_s(self, nuclide: str) -> float:
        """λ (s⁻¹) del nuclido según el NNDC Service; 503 si no hay."""
        if not self.base_url:
            raise NndsUnavailable(
                "NUCLEAR_DATA_URL no configurado: Decay Calculator 32.8 "
                "exige el NNDC Service")
        import httpx
        try:
            r = httpx.get(f"{self.base_url}/api/v1/nuclides/{nuclide}/decay",
                          timeout=self.timeout_s)
        except Exception as exc:
            raise NndsUnavailable(f"NNDC Service inalcanzable: {exc}")
        if r.status_code == 404:
            raise ClinicoInvalido(f"nuclido no registrado en NNDC: {nuclide}")
        if r.status_code != 200:
            raise NndsUnavailable(f"NNDC Service respondió {r.status_code}")
        return float(r.json()["decay_constant_s"])


@dataclass
class CitaPaciente:
    """Patient Schedule Manager (32.7)."""
    cita_id: str
    procedimiento: str
    horario: str                    # ISO 8601
    prioridad: int = 3              # política parametrizable 32.12
    estado: str = "programado"      # programado/reprogramado/cancelado/
                                    # completado


@dataclass
class Dosis:
    """Dose Manager (32.6): cada dosis permanece asociada a su lote."""
    dosis_id: str
    lote_id: str
    cita_id: str
    actividad_asignada_gbq: float   # en el instante de referencia del lote
    volumen_ml: float
    destino: str
    estado: str = "asignada"
    tiempos: dict = field(default_factory=dict)   # 32.19


class ClinicalDeliveryEngine:
    """Motor CDDME: coordinación, validación y auditoría (32.4)."""

    def __init__(self, decay_client: NndsDecayClient) -> None:
        self._decay = decay_client
        self._citas: dict[str, CitaPaciente] = {}
        self._dosis: dict[str, Dosis] = {}
        self._propuestas: dict[str, dict] = {}
        self._auditoria: list[dict] = []

    # ---------------------------------------------------------- auditoría
    def _auditar(self, usuario: str, accion: str, resultado: str,
                 dosis_id: str = "", cita_id: str = "",
                 lote_id: str = "") -> None:
        self._auditoria.append({                       # 32.23
            "usuario": usuario, "accion": accion, "resultado": resultado,
            "dosis_id": dosis_id, "paciente_id": cita_id,
            "lote_id": lote_id,
            "fecha": datetime.now(timezone.utc).isoformat()})

    def auditoria(self) -> list[dict]:
        return list(self._auditoria)

    # ------------------------------------------------- programación 32.7
    def programar_paciente(self, cita: CitaPaciente, usuario: str) -> dict:
        if cita.cita_id in self._citas:
            raise ClinicoInvalido(                     # nunca sobrescribe
                f"cita ya registrada: {cita.cita_id}")
        if not cita.procedimiento or not cita.horario:
            raise ClinicoInvalido("procedimiento y horario obligatorios")
        self._citas[cita.cita_id] = cita
        self._auditar(usuario, "programar_paciente", "ok",
                      cita_id=cita.cita_id)
        return {"cita_id": cita.cita_id, "estado": cita.estado,
                "version_motor": VERSION_MOTOR}

    def programacion(self) -> list[dict]:
        return [{"cita_id": c.cita_id, "procedimiento": c.procedimiento,
                 "horario": c.horario, "prioridad": c.prioridad,
                 "estado": c.estado} for c in self._citas.values()]

    # ------------------------------------------------- asignación 32.6
    def actividad_en_instante(self, nuclide: str, actividad_ref_gbq: float,
                              referencia_iso: str, instante_iso: str
                              ) -> float:
        """A(t) = A_ref · e^(−λΔt) con λ EXCLUSIVAMENTE del NNDC (32.8)."""
        lam = self._decay.constante_decaimiento_s(nuclide)
        t0 = datetime.fromisoformat(referencia_iso)
        t1 = datetime.fromisoformat(instante_iso)
        dt = (t1 - t0).total_seconds()
        return actividad_ref_gbq * math.exp(-lam * dt)

    def asignar_dosis(self, dosis: Dosis, lote: dict,
                      instante_administracion: str, usuario: str) -> dict:
        """Asignación con validación previa 32.21.

        `lote` debe incluir: lote_id, nuclide, actividad_gbq,
        referencia_temporal (ISO) y liberado_qc (bool) — sólo lotes
        liberados por el QC Twin pueden asignarse (32.15).
        """
        if dosis.dosis_id in self._dosis:
            raise ClinicoInvalido(f"dosis ya registrada: {dosis.dosis_id}")
        if dosis.cita_id not in self._citas:
            raise ClinicoInvalido(f"cita inexistente: {dosis.cita_id}")
        cita = self._citas[dosis.cita_id]
        if cita.estado == "cancelado":
            raise ClinicoInvalido("la cita está cancelada")
        if not lote.get("liberado_qc"):
            self._auditar(usuario, "asignar_dosis", "rechazada: lote no "
                          "liberado por QC (32.15)", dosis_id=dosis.dosis_id,
                          cita_id=dosis.cita_id, lote_id=dosis.lote_id)
            raise ClinicoInvalido(
                "sólo lotes liberados por el QC Twin pueden asignarse "
                "a pacientes (32.15)")
        if lote.get("lote_id") != dosis.lote_id:
            raise ClinicoInvalido("el lote declarado no coincide con la dosis")
        # actividad disponible del lote en el instante de administración
        disponible = self.actividad_en_instante(
            lote["nuclide"], float(lote["actividad_gbq"]),
            lote["referencia_temporal"], instante_administracion)
        asignada_previas = sum(
            d.actividad_asignada_gbq for d in self._dosis.values()
            if d.lote_id == dosis.lote_id)
        requerida_ref = dosis.actividad_asignada_gbq
        # la actividad asignada se expresa en el instante de referencia
        if asignada_previas + requerida_ref > float(lote["actividad_gbq"]):
            raise ClinicoInvalido(
                "actividad asignada supera la actividad del lote (32.21)")
        if dosis.actividad_asignada_gbq <= 0 or dosis.volumen_ml <= 0:
            raise ClinicoInvalido("actividad y volumen deben ser > 0")
        lam = self._decay.constante_decaimiento_s(lote["nuclide"])
        t0 = datetime.fromisoformat(lote["referencia_temporal"])
        t1 = datetime.fromisoformat(instante_administracion)
        actividad_admin = requerida_ref * math.exp(
            -lam * (t1 - t0).total_seconds())
        dosis.tiempos["asignacion"] = datetime.now(timezone.utc).isoformat()
        self._dosis[dosis.dosis_id] = dosis
        self._auditar(usuario, "asignar_dosis", "ok", dosis_id=dosis.dosis_id,
                      cita_id=dosis.cita_id, lote_id=dosis.lote_id)
        return {"dosis_id": dosis.dosis_id, "lote_id": dosis.lote_id,
                "cita_id": dosis.cita_id,
                "actividad_asignada_gbq": requerida_ref,
                "actividad_estimada_administracion_gbq":
                    round(actividad_admin, 6),
                "actividad_lote_disponible_en_administracion_gbq":
                    round(disponible - asignada_previas * math.exp(
                        -lam * (t1 - t0).total_seconds()), 6),
                "fuente_decaimiento": "NNDC Service (32.8)",
                "version_motor": VERSION_MOTOR}

    # ------------------------------------------------- entrega 32.9/32.19
    def registrar_transicion(self, dosis_id: str, evento: str,
                             usuario: str) -> dict:
        if dosis_id not in self._dosis:
            raise ClinicoInvalido(f"dosis inexistente: {dosis_id}")
        d = self._dosis[dosis_id]
        if evento not in SECUENCIA_ENTREGA and evento != "administracion":
            raise ClinicoInvalido(f"evento desconocido: {evento}")
        if evento in SECUENCIA_ENTREGA:
            idx = SECUENCIA_ENTREGA.index(evento)
            if idx > 0 and SECUENCIA_ENTREGA[idx - 1] not in d.tiempos:
                raise ClinicoInvalido(
                    f"falta la transición previa "
                    f"'{SECUENCIA_ENTREGA[idx - 1]}' (32.9)")
        elif "confirmacion_entrega" not in d.tiempos:
            raise ClinicoInvalido(
                "la administración exige entrega confirmada (32.10)")
        ahora = datetime.now(timezone.utc).isoformat()
        d.tiempos[evento] = ahora
        if evento == "administracion":
            d.estado = "administrada"
            self._citas[d.cita_id].estado = "completado"
        self._auditar(usuario, f"transicion:{evento}", "ok",
                      dosis_id=dosis_id, cita_id=d.cita_id,
                      lote_id=d.lote_id)
        return {"dosis_id": dosis_id, "evento": evento, "fecha": ahora,
                "estado": d.estado}

    def trazabilidad_dosis(self, dosis_id: str) -> dict:
        if dosis_id not in self._dosis:
            raise ClinicoInvalido(f"dosis inexistente: {dosis_id}")
        d = self._dosis[dosis_id]
        return {"dosis_id": d.dosis_id, "lote_id": d.lote_id,
                "cita_id": d.cita_id, "destino": d.destino,
                "actividad_asignada_gbq": d.actividad_asignada_gbq,
                "volumen_ml": d.volumen_ml, "estado": d.estado,
                "tiempos": dict(d.tiempos)}          # 32.19/32.20

    # ------------------------------------------- reprogramación 32.11
    def proponer_reprogramacion(self, cita_id: str, retraso_min: float,
                                nuevo_horario: str, usuario: str) -> dict:
        """El sistema PROPONE; nunca reprograma automáticamente (32.11)."""
        if cita_id not in self._citas:
            raise ClinicoInvalido(f"cita inexistente: {cita_id}")
        if retraso_min <= 0:
            raise ClinicoInvalido("retraso debe ser > 0")
        pid = f"prop-{len(self._propuestas) + 1:04d}"
        self._propuestas[pid] = {
            "propuesta_id": pid, "cita_id": cita_id,
            "retraso_min": retraso_min, "nuevo_horario": nuevo_horario,
            "estado": "pendiente_confirmacion",
            "nota": "propuesta del motor (32.11): requiere confirmación "
                    "de usuario autorizado; nunca es automática",
            "fecha": datetime.now(timezone.utc).isoformat()}
        self._auditar(usuario, "proponer_reprogramacion", "propuesta",
                      cita_id=cita_id)
        return self._propuestas[pid]

    def confirmar_reprogramacion(self, propuesta_id: str,
                                 usuario_autorizado: str) -> dict:
        if propuesta_id not in self._propuestas:
            raise ClinicoInvalido(f"propuesta inexistente: {propuesta_id}")
        p = self._propuestas[propuesta_id]
        if p["estado"] != "pendiente_confirmacion":
            raise ClinicoInvalido(f"propuesta ya resuelta: {p['estado']}")
        cita = self._citas[p["cita_id"]]
        cita.horario = p["nuevo_horario"]
        cita.estado = "reprogramado"
        p["estado"] = "confirmada"
        p["confirmado_por"] = usuario_autorizado
        self._auditar(usuario_autorizado, "confirmar_reprogramacion", "ok",
                      cita_id=cita.cita_id)
        return p
