"""
Reaction Engine (EDS Vol. II, cap. 22).

Núcleo científico del Process Twin: modela la evolución de la
reacción radioquímica desde la actividad EOB (condición inicial que
proporciona el Physics Twin, 22.14) hasta la transferencia al
Purification Engine (22.17).

Alcance estricto (22.3): NO modela irradiación, transporte del
blanco, purificación, formulación ni control de calidad.

Componentes implementados: Protocol Manager (22.6, vía catálogo
versionado), Reagent Manager (22.7), Reaction Sequence Manager
(22.8), Kinetic Solver (22.9), Thermal Profile Manager (22.10),
control temporal (22.11), Reaction Yield Calculator (22.12),
decaimiento durante la reacción (22.13), gestión de incertidumbre
(22.21) y Validation Engine previo a la ejecución (22.22).
"""
from __future__ import annotations

import math
from datetime import date, datetime, timezone

from app.domain.synthesis_entities import (ETAPAS_REACCION,
                                           KineticParams,
                                           ReactionProtocol,
                                           ReactionResult,
                                           ReactionStageResult,
                                           ThermalProfile)

R_J_MOLK = 8.314462618


class ProtocoloInvalido(ValueError):
    """Inconsistencias que detienen la ejecución (22.22)."""


def arrhenius_k(kinetic: KineticParams, t_c: float) -> float:
    """k(T) aparente (22.9, modelo fenomenológico)."""
    if kinetic.ea_j_mol <= 0:
        return kinetic.k_ref_min_inv
    t_k = t_c + 273.15
    t_ref = kinetic.t_ref_c + 273.15
    return kinetic.k_ref_min_inv * math.exp(
        -kinetic.ea_j_mol / R_J_MOLK * (1.0 / t_k - 1.0 / t_ref))


def conversion_primer_orden(kinetic: KineticParams, t_min: float,
                            t_c: float) -> float:
    """conversion(t) = cmax * (1 - exp(-k(T) t)) (22.9/22.12)."""
    return kinetic.conversion_max * (1.0 - math.exp(-arrhenius_k(kinetic, t_c) * t_min))


def validar_protocolo(p: ReactionProtocol, fecha_lote: date | None = None
                      ) -> list[str]:
    """Verificaciones previas a la ejecución (22.22).

    Las inconsistencias detienen la ejecución: el llamador debe
    rechazar si la lista no está vacía.
    """
    errores: list[str] = []
    if not p.steps:
        errores.append("integridad del protocolo: secuencia vacía (22.8)")
    for s in p.steps:
        if s.kind not in ETAPAS_REACCION:
            errores.append(f"etapa desconocida '{s.kind}' (22.8)")
        if s.duration_min <= 0:
            errores.append(f"coherencia temporal: duración <= 0 en '{s.kind}' (22.22)")
        if not (0 < s.efficiency <= 1.0):
            errores.append(f"eficiencia fuera de (0,1] en '{s.kind}'")
    if not any(s.kind == "reaccion" for s in p.steps):
        errores.append("integridad del protocolo: falta etapa 'reaccion' (22.8)")
    if any(s.kind == "reaccion" for s in p.steps) and p.kinetic is None:
        errores.append("la etapa 'reaccion' requiere parámetros cinéticos (22.9)")
    if p.kinetic is not None:
        if p.kinetic.modelo != "primer_orden":
            errores.append(f"modelo cinético no registrado: '{p.kinetic.modelo}' (22.9)")
        if not (0 < p.kinetic.conversion_max <= 1.0):
            errores.append("conversion_max fuera de (0,1] (22.9)")
        if p.kinetic.k_ref_min_inv <= 0:
            errores.append("k_ref debe ser positiva (22.9)")
    if p.half_life_min <= 0:
        errores.append("vida media debe ser positiva (22.13)")
    if not p.reagents:
        errores.append("sin reactivos registrados (22.7)")
    hoy = fecha_lote or datetime.now(timezone.utc).date()
    for r in p.reagents:
        try:
            cad = date.fromisoformat(r.caducidad)
        except ValueError:
            errores.append(f"caducidad inválida en reactivo '{r.nombre}' (22.7)")
            continue
        if cad < hoy:
            errores.append(
                f"reactivo '{r.nombre}' vencido el {r.caducidad} "
                "(disponibilidad de reactivos, 22.22)")
        if r.volumen_ml <= 0:
            errores.append(f"volumen <= 0 en reactivo '{r.nombre}' (22.7)")
    if p.thermal is not None:
        t = p.thermal
        if t.t_objetivo_c <= 0 or t.rampa_calentamiento_c_min <= 0 \
                or t.rampa_enfriamiento_c_min <= 0 or t.t_mantenimiento_min < 0:
            errores.append("perfil térmico incoherente (22.10)")
    return errores


def simular_reaccion(p: ReactionProtocol,
                     eob_activity_gbq: float,
                     incertidumbre_inicial_rel: float = 0.0,
                     operador: str = "sistema",
                     motivo: str = "",
                     lote: str = "",
                     fecha_lote: date | None = None) -> ReactionResult:
    """Ejecuta la secuencia de reacción con decaimiento por etapa.

    22.13: la actividad se recalcula en cada etapa (exp(-λ·Δt));
    22.21: la incertidumbre inicial se propaga a la actividad final
    (las eficiencias/conversión son nominales del protocolo);
    22.22: validación previa — inconsistencias detienen la ejecución.
    """
    errores = validar_protocolo(p, fecha_lote)
    if errores:
        raise ProtocoloInvalido("; ".join(errores))
    if eob_activity_gbq <= 0:
        raise ProtocoloInvalido("actividad EOB debe ser positiva (22.14)")
    if not (0.0 <= incertidumbre_inicial_rel < 1.0):
        raise ProtocoloInvalido("incertidumbre relativa fuera de [0,1) (22.21)")

    lam = math.log(2.0) / p.half_life_min
    t_c = p.thermal.t_objetivo_c if p.thermal else 25.0

    actividad = eob_activity_gbq
    reloj = 0.0
    conversion: float | None = None
    rendimiento_quimico = 1.0
    stages: list[ReactionStageResult] = []

    for s in p.steps:
        a_in = actividad
        a_decay = a_in * math.exp(-lam * s.duration_min)  # 22.13
        detalle: dict = {}
        eff = s.efficiency
        if s.kind == "reaccion" and p.kinetic is not None:
            conversion = conversion_primer_orden(p.kinetic, s.duration_min, t_c)
            detalle = {
                "modelo": p.kinetic.modelo,
                "temperatura_c": t_c,
                "k_aparente_min_inv": round(arrhenius_k(p.kinetic, t_c), 6),
                "conversion": round(conversion, 6),
            }
            eff = eff * conversion
        a_out = a_decay * eff
        stages.append(ReactionStageResult(
            kind=s.kind, inicio_min=round(reloj, 3),
            fin_min=round(reloj + s.duration_min, 3),
            duration_min=s.duration_min,
            activity_in_gbq=a_in, activity_after_decay_gbq=a_decay,
            activity_out_gbq=a_out, efficiency=eff,
            detalle=detalle or None))
        reloj += s.duration_min
        actividad = a_out

    # 22.12: conversión, rendimiento químico, pérdidas, eficiencia global
    factor_decay_total = math.exp(-lam * reloj)
    eficiencia_global = (actividad / eob_activity_gbq) if eob_activity_gbq else 0.0
    rend_quim = eficiencia_global / factor_decay_total if factor_decay_total > 0 else 0.0
    perdidas = (eob_activity_gbq * factor_decay_total) - actividad
    incert_final = actividad * incertidumbre_inicial_rel  # 22.21

    auditoria = {  # 22.24
        "fecha": datetime.now(timezone.utc).isoformat(),
        "operador": operador,
        "motivo": motivo,
        "lote": lote,
        "protocolo": p.protocol_id,
        "version": p.version,
        "n_etapas": len(stages),
        "fuente_parametros": p.source,
    }
    return ReactionResult(
        protocol_id=p.protocol_id, version=p.version,
        radiopharmaceutical=p.radiopharmaceutical, nuclide=p.nuclide,
        half_life_min=p.half_life_min,
        eob_activity_gbq=eob_activity_gbq,
        final_activity_gbq=actividad,
        conversion=conversion,
        rendimiento_quimico=rend_quim,
        perdidas_reaccion_gbq=max(perdidas, 0.0),
        eficiencia_global=eficiencia_global,
        total_time_min=reloj,
        incertidumbre_inicial_rel=incertidumbre_inicial_rel,
        incertidumbre_final_gbq=incert_final,
        validated=p.validated,
        stages=tuple(stages),
        auditoria=auditoria)
