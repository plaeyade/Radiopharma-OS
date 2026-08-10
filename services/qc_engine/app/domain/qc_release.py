"""
QC Engine — especificaciones, validación y liberación
(EDS Vol. II, cap. 25).

Componentes implementados: QC Protocol Manager (25.6, protocolos
versionados), Analytical Result Manager (25.8, resultados con
trazabilidad), Specification Manager (25.10, especificaciones
oficiales versionadas con vigencia), Validation Engine (25.11,
comparación automática resultado vs especificación) y Release
Engine (25.12, recomendación técnica liberación/rechazo/revisión).

La decisión definitiva de liberación sigue el flujo de aprobación
de la organización (25.12): este motor emite una RECOMENDACIÓN
técnica documentada, nunca la liberación final.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone


ESTADOS_QC = ("conforme", "fuera_de_especificacion",
              "pendiente", "no_aplicable")  # 25.11
RECOMENDACIONES = ("liberacion", "rechazo", "revision")  # 25.12


@dataclass(frozen=True)
class Specification:
    """Especificación oficial versionada (25.10)."""
    parametro: str
    limite_inferior: float | None
    limite_superior: float | None
    unidades: str
    version: str
    vigencia_desde: str  # ISO date


@dataclass(frozen=True)
class QcProtocol:
    """Protocolo QC versionado (25.6)."""
    protocol_id: str
    radiopharmaceutical: str
    version: str
    ensayos_requeridos: tuple[str, ...]  # 25.9
    criterios_aceptacion: str
    documentacion: str
    validated: bool
    source: str


@dataclass(frozen=True)
class EvaluacionParametro:
    """Estado asignado por el Validation Engine (25.11)."""
    parametro: str
    valor: float | None
    unidades: str
    estado: str  # ESTADOS_QC
    spec_version: str | None
    detalle: str


@dataclass(frozen=True)
class ReleaseResult:
    """Recomendación técnica del Release Engine (25.12)."""
    protocol_id: str
    radiopharmaceutical: str
    recomendacion: str  # RECOMENDACIONES
    motivos: tuple[str, ...]
    evaluaciones: tuple[EvaluacionParametro, ...]
    n_conformes: int
    n_oos: int
    n_pendientes: int
    validated: bool
    auditoria: dict


class QcInvalido(ValueError):
    """Inconsistencias de protocolo, especificaciones o resultados."""


def evaluar_resultados(protocol: QcProtocol,
                       specs: dict[str, Specification],
                       resultados: dict[str, float | None],
                       fecha: date | None = None
                       ) -> tuple[EvaluacionParametro, ...]:
    """Validation Engine (25.11).

    Para cada ensayo requerido por el protocolo:
      - sin resultado registrado → 'pendiente';
      - sin especificación vigente → 'no_aplicable' solo si el
        protocolo lo permite (el parámetro no está en specs);
      - con resultado y especificación → conforme / OOS.
    """
    hoy = fecha or datetime.now(timezone.utc).date()
    evaluaciones: list[EvaluacionParametro] = []
    for ensayo in protocol.ensayos_requeridos:
        spec = specs.get(ensayo)
        valor = resultados.get(ensayo)
        if spec is None:
            evaluaciones.append(EvaluacionParametro(
                parametro=ensayo, valor=valor, unidades="",
                estado="no_aplicable", spec_version=None,
                detalle="sin especificación registrada (25.10)"))
            continue
        try:
            vigente = date.fromisoformat(spec.vigencia_desde) <= hoy
        except ValueError:
            raise QcInvalido(
                f"vigencia inválida en especificación '{ensayo}' (25.10)")
        if not vigente:
            evaluaciones.append(EvaluacionParametro(
                parametro=ensayo, valor=valor, unidades=spec.unidades,
                estado="pendiente", spec_version=spec.version,
                detalle=f"especificación vigente desde {spec.vigencia_desde} (25.10)"))
            continue
        if valor is None:
            evaluaciones.append(EvaluacionParametro(
                parametro=ensayo, valor=None, unidades=spec.unidades,
                estado="pendiente", spec_version=spec.version,
                detalle="resultado no registrado (25.8)"))
            continue
        bajo = spec.limite_inferior is not None and valor < spec.limite_inferior
        alto = spec.limite_superior is not None and valor > spec.limite_superior
        if bajo or alto:
            evaluaciones.append(EvaluacionParametro(
                parametro=ensayo, valor=valor, unidades=spec.unidades,
                estado="fuera_de_especificacion", spec_version=spec.version,
                detalle=f"valor {valor} fuera de "
                        f"[{spec.limite_inferior}, {spec.limite_superior}]"))
        else:
            evaluaciones.append(EvaluacionParametro(
                parametro=ensayo, valor=valor, unidades=spec.unidades,
                estado="conforme", spec_version=spec.version,
                detalle="dentro de especificación"))
    return tuple(evaluaciones)


def recomendar_liberacion(protocol: QcProtocol,
                          evaluaciones: tuple[EvaluacionParametro, ...],
                          operador: str = "sistema",
                          motivo: str = "",
                          lote: str = "") -> ReleaseResult:
    """Release Engine (25.12): recomendación técnica documentada.

    - cualquier OOS → 'rechazo';
    - sin OOS pero con pendientes → 'revision';
    - todo conforme (o no_aplicable) → 'liberacion'.
    La decisión definitiva permanece en el flujo de aprobación
    organizativo (25.12).
    """
    oos = [e for e in evaluaciones if e.estado == "fuera_de_especificacion"]
    pend = [e for e in evaluaciones if e.estado == "pendiente"]
    conf = [e for e in evaluaciones if e.estado == "conforme"]
    motivos: list[str] = []
    if oos:
        recomendacion = "rechazo"
        motivos = [f"{e.parametro}: {e.detalle}" for e in oos]
    elif pend:
        recomendacion = "revision"
        motivos = [f"{e.parametro}: {e.detalle}" for e in pend]
    else:
        recomendacion = "liberacion"
        motivos = ["todos los ensayos requeridos conformes (25.11)"]
    auditoria = {
        "fecha": datetime.now(timezone.utc).isoformat(),
        "operador": operador,
        "motivo": motivo,
        "lote": lote,
        "protocolo": protocol.protocol_id,
        "version": protocol.version,
        "nota": "recomendación técnica; la liberación final sigue el "
                "flujo de aprobación organizativo (25.12)",
    }
    return ReleaseResult(
        protocol_id=protocol.protocol_id,
        radiopharmaceutical=protocol.radiopharmaceutical,
        recomendacion=recomendacion,
        motivos=tuple(motivos),
        evaluaciones=evaluaciones,
        n_conformes=len(conf), n_oos=len(oos), n_pendientes=len(pend),
        validated=protocol.validated,
        auditoria=auditoria)
