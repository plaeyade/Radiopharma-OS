"""
Purification Engine (EDS Vol. II, cap. 23).

Recibe del Reaction Engine (23.14): actividad, composición,
rendimiento y productos secundarios; transfiere al Formulation
Engine (23.17): actividad, composición, volumen, rendimiento e
impurezas remanentes.

Componentes implementados: Purification Protocol Manager (23.6,
protocolos versionados), Separation Manager (23.7, operaciones
retención/lavado/elución/intercambio/recuperación desacopladas del
equipo físico), Cartridge Manager (23.8), Impurity Manager (23.10)
y Recovery Calculator (23.11).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone


ETAPAS_PURIFICACION = ("retencion", "lavado", "elucion",
                       "intercambio", "recuperacion")  # 23.7


@dataclass(frozen=True)
class Cartridge:
    """Cartucho de purificación registrado (23.8)."""
    identificacion: str
    tipo: str
    fabricante: str
    lote: str
    estado: str  # 'nuevo' | 'en_uso' | 'agotado'


@dataclass(frozen=True)
class PurificationStep:
    """Operación de separación (23.7).

    recovery: fracción de actividad de producto que continúa;
    impurity_removal: fracción eliminada por tipo de impureza
    (0-1] por clave; 23.10).
    """
    kind: str
    duration_min: float
    recovery: float
    impurity_removal: dict | None = None


@dataclass(frozen=True)
class PurificationProtocol:
    """Protocolo de purificación versionado (23.6)."""
    protocol_id: str
    version: str
    radiopharmaceutical: str
    half_life_min: float
    steps: tuple[PurificationStep, ...]
    cartridges: tuple[Cartridge, ...]
    validated: bool
    source: str


@dataclass(frozen=True)
class PurificationStageResult:
    kind: str
    duration_min: float
    activity_in_gbq: float
    activity_after_decay_gbq: float
    activity_out_gbq: float
    recovery: float


@dataclass(frozen=True)
class PurificationResult:
    """Salida del Purification Engine (23.11/23.17)."""
    protocol_id: str
    version: str
    radiopharmaceutical: str
    input_activity_gbq: float
    final_activity_gbq: float
    producto_recuperado_gbq: float
    perdidas_acumuladas_gbq: float
    eficiencia_recuperacion: float
    total_time_min: float
    impurezas_iniciales: dict
    impurezas_remanentes: dict
    validated: bool
    stages: tuple[PurificationStageResult, ...]
    auditoria: dict


class PurificacionInvalida(ValueError):
    """Inconsistencias del protocolo de purificación."""


def validar_protocolo(p: PurificationProtocol) -> list[str]:
    errores: list[str] = []
    if not p.steps:
        errores.append("secuencia de purificación vacía (23.7)")
    for s in p.steps:
        if s.kind not in ETAPAS_PURIFICACION:
            errores.append(f"operación desconocida '{s.kind}' (23.7)")
        if s.duration_min <= 0:
            errores.append(f"duración <= 0 en '{s.kind}'")
        if not (0 < s.recovery <= 1.0):
            errores.append(f"recovery fuera de (0,1] en '{s.kind}' (23.11)")
        for imp, frac in (s.impurity_removal or {}).items():
            if not (0.0 <= frac <= 1.0):
                errores.append(f"remoción de '{imp}' fuera de [0,1] en '{s.kind}' (23.10)")
    if p.half_life_min <= 0:
        errores.append("vida media debe ser positiva")
    for c in p.cartridges:
        if c.estado == "agotado":
            errores.append(f"cartucho '{c.identificacion}' agotado (23.8)")
    return errores


def simular_purificacion(p: PurificationProtocol,
                         input_activity_gbq: float,
                         impurezas_iniciales: dict | None = None,
                         operador: str = "sistema",
                         motivo: str = "",
                         lote: str = "") -> PurificationResult:
    """Ejecuta la secuencia de purificación.

    Cada etapa aplica decaimiento físico durante su duración y su
    recuperación nominal; el Impurity Manager descuenta las
    impurezas según la remoción declarada por etapa (23.10).
    """
    errores = validar_protocolo(p)
    if errores:
        raise PurificacionInvalida("; ".join(errores))
    if input_activity_gbq <= 0:
        raise PurificacionInvalida("actividad de entrada debe ser positiva (23.14)")
    imp_in = dict(impurezas_iniciales or {})
    for k, v in imp_in.items():
        if v < 0:
            raise PurificacionInvalida(f"impureza '{k}' negativa (23.10)")

    lam = math.log(2.0) / p.half_life_min
    actividad = input_activity_gbq
    impurezas = dict(imp_in)
    reloj = 0.0
    stages: list[PurificationStageResult] = []

    for s in p.steps:
        a_in = actividad
        a_decay = a_in * math.exp(-lam * s.duration_min)
        a_out = a_decay * s.recovery
        stages.append(PurificationStageResult(
            kind=s.kind, duration_min=s.duration_min,
            activity_in_gbq=a_in, activity_after_decay_gbq=a_decay,
            activity_out_gbq=a_out, recovery=s.recovery))
        for imp, frac in (s.impurity_removal or {}).items():
            if imp in impurezas:
                impurezas[imp] = impurezas[imp] * (1.0 - frac)
        reloj += s.duration_min
        actividad = a_out

    factor_decay = math.exp(-lam * reloj)
    perdidas = (input_activity_gbq * factor_decay) - actividad
    eficiencia = actividad / input_activity_gbq if input_activity_gbq else 0.0

    auditoria = {
        "fecha": datetime.now(timezone.utc).isoformat(),
        "operador": operador,
        "motivo": motivo,
        "lote": lote,
        "protocolo": p.protocol_id,
        "version": p.version,
        "cartuchos": [c.identificacion for c in p.cartridges],
        "fuente_parametros": p.source,
    }
    return PurificationResult(
        protocol_id=p.protocol_id, version=p.version,
        radiopharmaceutical=p.radiopharmaceutical,
        input_activity_gbq=input_activity_gbq,
        final_activity_gbq=actividad,
        producto_recuperado_gbq=actividad,
        perdidas_acumuladas_gbq=max(perdidas, 0.0),
        eficiencia_recuperacion=eficiencia,
        total_time_min=reloj,
        impurezas_iniciales=imp_in,
        impurezas_remanentes=impurezas,
        validated=p.validated,
        stages=tuple(stages),
        auditoria=auditoria)
