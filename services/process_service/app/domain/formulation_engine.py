"""
Formulation Engine (EDS Vol. II, caps. 21.13 y 24).

Recibe del Purification Engine (23.17): actividad, composición,
volumen, rendimiento e impurezas remanentes; produce la forma
final lista para filtración estéril: dilución, ajuste de volumen,
incorporación de excipientes (21.13).

Componentes implementados: Formulation Protocol Manager (24.6,
protocolos versionados con límites operativos) y Excipient Manager
(24.7, excipientes con trazabilidad y fecha de vencimiento).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timezone


@dataclass(frozen=True)
class Excipient:
    """Excipiente registrado (24.7)."""
    identificacion: str
    concentracion: str
    volumen_ml: float
    lote: str
    proveedor: str
    caducidad: str  # ISO date


@dataclass(frozen=True)
class FormulationProtocol:
    """Protocolo de formulación versionado (24.6)."""
    protocol_id: str
    version: str
    radiopharmaceutical: str
    half_life_min: float
    duration_min: float
    volumen_final_ml: float
    concentracion_max_gbq_ml: float | None  # límite operativo (24.6)
    excipients: tuple[Excipient, ...]
    validated: bool
    source: str


@dataclass(frozen=True)
class FormulationResult:
    """Producto formulado (entrada del EOS/filtración estéril)."""
    protocol_id: str
    version: str
    radiopharmaceutical: str
    input_activity_gbq: float
    input_volumen_ml: float
    final_activity_gbq: float
    volumen_final_ml: float
    concentracion_final_gbq_ml: float
    factor_dilucion: float
    duration_min: float
    validated: bool
    excipientes_aplicados: tuple[str, ...]
    auditoria: dict


class FormulacionInvalida(ValueError):
    """Inconsistencias del protocolo de formulación."""


def validar_protocolo(p: FormulationProtocol,
                      fecha_lote: date | None = None) -> list[str]:
    errores: list[str] = []
    if p.duration_min <= 0:
        errores.append("duración de formulación debe ser positiva")
    if p.volumen_final_ml <= 0:
        errores.append("volumen final debe ser positivo (21.13)")
    if p.half_life_min <= 0:
        errores.append("vida media debe ser positiva")
    hoy = fecha_lote or datetime.now(timezone.utc).date()
    for e in p.excipients:
        try:
            cad = date.fromisoformat(e.caducidad)
        except ValueError:
            errores.append(f"caducidad inválida en excipiente '{e.identificacion}' (24.7)")
            continue
        if cad < hoy:
            errores.append(
                f"excipiente '{e.identificacion}' vencido el {e.caducidad} (24.7)")
        if e.volumen_ml <= 0:
            errores.append(f"volumen <= 0 en excipiente '{e.identificacion}' (24.7)")
    return errores


def simular_formulacion(p: FormulationProtocol,
                        input_activity_gbq: float,
                        input_volumen_ml: float,
                        operador: str = "sistema",
                        motivo: str = "",
                        lote: str = "",
                        fecha_lote: date | None = None) -> FormulationResult:
    """Diluye y ajusta el volumen final con decaimiento físico.

    El volumen de excipientes forma parte del volumen final
    declarado por el protocolo; la actividad decae durante la
    duración de la formulación (mismo criterio que 22.13).
    """
    errores = validar_protocolo(p, fecha_lote)
    if errores:
        raise FormulacionInvalida("; ".join(errores))
    if input_activity_gbq <= 0:
        raise FormulacionInvalida("actividad de entrada debe ser positiva (23.17)")
    if input_volumen_ml <= 0:
        raise FormulacionInvalida("volumen de entrada debe ser positivo (23.17)")
    vol_exc = sum(e.volumen_ml for e in p.excipients)
    if input_volumen_ml + vol_exc > p.volumen_final_ml + 1e-9:
        raise FormulacionInvalida(
            f"volumen de entrada + excipientes ({input_volumen_ml + vol_exc:.2f} ml) "
            f"supera el volumen final del protocolo ({p.volumen_final_ml} ml) (21.13)")

    lam = math.log(2.0) / p.half_life_min
    actividad = input_activity_gbq * math.exp(-lam * p.duration_min)
    concentracion = actividad / p.volumen_final_ml
    if p.concentracion_max_gbq_ml is not None and \
            concentracion > p.concentracion_max_gbq_ml:
        raise FormulacionInvalida(
            f"concentración final {concentracion:.4f} GBq/ml supera el límite "
            f"operativo {p.concentracion_max_gbq_ml} GBq/ml (24.6)")

    auditoria = {
        "fecha": datetime.now(timezone.utc).isoformat(),
        "operador": operador,
        "motivo": motivo,
        "lote": lote,
        "protocolo": p.protocol_id,
        "version": p.version,
        "fuente_parametros": p.source,
    }
    return FormulationResult(
        protocol_id=p.protocol_id, version=p.version,
        radiopharmaceutical=p.radiopharmaceutical,
        input_activity_gbq=input_activity_gbq,
        input_volumen_ml=input_volumen_ml,
        final_activity_gbq=actividad,
        volumen_final_ml=p.volumen_final_ml,
        concentracion_final_gbq_ml=concentracion,
        factor_dilucion=p.volumen_final_ml / input_volumen_ml,
        duration_min=p.duration_min,
        validated=p.validated,
        excipientes_aplicados=tuple(e.identificacion for e in p.excipients),
        auditoria=auditoria)
