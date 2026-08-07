"""
Calibration Layer F2 — indicadores de desempeño, drift y validación
(EDS v2.0, Vol. II cap. 17):

17.26 Indicadores de desempeño: error absoluto, error relativo,
      tendencia temporal y estabilidad del modelo, calculados sobre
      pares (fecha, EOB teórico, EOB medido). Su objetivo (17.27) es
      documentar continuamente la diferencia simulación ↔ producción.
17.10 Drift Analyzer: tendencia del rendimiento con significación
      estadística — avisa de degradación antes de que afecte a la
      producción. Criterio honesto: la deriva existe si el cambio
      acumulado por la pendiente sobre el intervalo observado supera
      2·σ de los residuos del ajuste lineal (no basta una pendiente
      positiva con ruido grande).
17.11 Gestión temporal: qué versión de calibración era válida en una
      fecha determinada (auditorías regulatorias).
17.23 Validación: una calibración nueva solo se acepta si no deteriora
      el desempeño global (RMS de los cocientes residuales sobre las
      mismas medidas) — si empeora, se rechaza de forma explícita.

Todo es determinista y sin IA: estadística clásica documentada.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from app.domain.calibration import Measurement


@dataclass(frozen=True)
class PerformanceIndicators:
    """17.26: desempeño del modelo sobre un histórico de pares."""
    n: int
    error_abs_mean_gbq: float        # media de |medido − teórico|
    error_rel_mean: float            # media de (medido−teórico)/teórico
    error_rel_max: float             # máximo |error relativo|
    error_rel_std: float             # estabilidad (dispersión del error)
    trend_slope_rel_per_day: float   # pendiente del error relativo por día
    trend_r2: float                  # calidad del ajuste lineal
    span_days: float


@dataclass(frozen=True)
class DriftVerdict:
    """17.10: veredicto de deriva con significación estadística."""
    drift_detected: bool
    accumulated_rel_change: float    # pendiente × intervalo observado
    residual_std: float              # σ de residuos del ajuste lineal
    threshold: float                 # 2·residual_std
    note: str


def _times_days(medidas: list[Measurement]) -> list[float]:
    fechas = [datetime.fromisoformat(m.fecha.replace("Z", "+00:00"))
              for m in medidas]
    t0 = min(fechas)
    return [(f - t0).total_seconds() / 86400.0 for f in fechas]


def performance_indicators(medidas: list[Measurement]) -> PerformanceIndicators:
    """17.26 sobre pares (teórico, medido) ordenados por fecha."""
    if len(medidas) < 2:
        raise ValueError("se requieren al menos 2 medidas")
    for m in medidas:
        if m.eob_predicho_gbq <= 0.0:
            raise ValueError("eob_predicho_gbq debe ser > 0")
    rel = [m.eob_medido_gbq / m.eob_predicho_gbq - 1.0 for m in medidas]
    abs_err = [abs(m.eob_medido_gbq - m.eob_predicho_gbq) for m in medidas]
    n = len(rel)
    mean_rel = sum(rel) / n
    std_rel = math.sqrt(sum((e - mean_rel) ** 2 for e in rel) / (n - 1))

    t = _times_days(medidas)
    span = max(t) - min(t)
    slope, r2 = 0.0, 0.0
    if span > 0.0:
        mt, mr = sum(t) / n, mean_rel
        sxx = sum((x - mt) ** 2 for x in t)
        if sxx > 0.0:
            slope = sum((x - mt) * (e - mr) for x, e in zip(t, rel)) / sxx
            ss_tot = sum((e - mr) ** 2 for e in rel)
            ss_res = sum((e - (mr + slope * (x - mt))) ** 2
                         for x, e in zip(t, rel))
            r2 = 1.0 - ss_res / ss_tot if ss_tot > 0.0 else 1.0
    return PerformanceIndicators(
        n=n, error_abs_mean_gbq=sum(abs_err) / n,
        error_rel_mean=mean_rel, error_rel_max=max(abs(e) for e in rel),
        error_rel_std=std_rel, trend_slope_rel_per_day=slope,
        trend_r2=r2, span_days=span)


def drift_analysis(medidas: list[Measurement]) -> DriftVerdict:
    """17.10: deriva significativa del rendimiento (2σ de residuos)."""
    ind = performance_indicators(medidas)
    accumulated = ind.trend_slope_rel_per_day * ind.span_days
    # σ de los residuos del ajuste lineal (no del error bruto)
    t = _times_days(medidas)
    rel = [m.eob_medido_gbq / m.eob_predicho_gbq - 1.0 for m in medidas]
    mt = sum(t) / len(t)
    resid = [e - (ind.error_rel_mean + ind.trend_slope_rel_per_day * (x - mt))
             for x, e in zip(t, rel)]
    n = len(rel)
    res_std = math.sqrt(sum(r ** 2 for r in resid) / (n - 1)) if n > 1 else 0.0
    threshold = 2.0 * res_std
    detected = abs(accumulated) > threshold and ind.span_days > 0.0
    direction = "degradación" if accumulated < 0 else "mejora"
    note = (f"cambio acumulado {accumulated:+.2%} en {ind.span_days:.1f} días "
            f"({'significativo' if detected else 'no significativo'}: "
            f"umbral 2σ = {threshold:.2%})")
    return DriftVerdict(drift_detected=detected,
                        accumulated_rel_change=accumulated,
                        residual_std=res_std, threshold=threshold,
                        note=f"{direction} {note}" if detected else note)


def active_at(models: list[dict], when: datetime) -> dict | None:
    """17.11: versión de calibración válida en una fecha dada.

    models: dicts con al menos 'fitted_at' y 'version' (como los guarda
    CalibrationService). Devuelve la de mayor fecha ≤ when, o None."""
    candidatos = []
    for m in models:
        fitted = datetime.fromisoformat(m["fitted_at"].replace("Z", "+00:00"))
        if fitted <= when:
            candidatos.append((fitted, m["version"], m))
    if not candidatos:
        return None
    return max(candidatos)[2]


def validate_new_factor(medidas: list[Measurement],
                        factor_new: float,
                        factor_old: float | None) -> dict:
    """17.23: acepta la calibración nueva solo si no deteriora el RMS.

    RMS de cocientes residuales r_i/factor sobre las mismas medidas.
    Sin calibración previa (factor_old=None → factor 1.0) se acepta
    siempre, pero se reporta el RMS de referencia del modelo físico."""
    def rms(factor: float) -> float:
        return math.sqrt(sum(
            (m.eob_medido_gbq / m.eob_predicho_gbq / factor - 1.0) ** 2
            for m in medidas) / len(medidas))

    r_new = rms(factor_new)
    r_old = rms(factor_old if factor_old is not None else 1.0)
    accepted = r_new <= r_old + 1e-12
    return {"accepted": accepted,
            "rms_new": r_new, "rms_reference": r_old,
            "factor_reference": factor_old if factor_old is not None else 1.0,
            "note": ("aceptada: RMS "
                     f"{r_new:.4f} ≤ {r_old:.4f} de referencia" if accepted
                     else f"rechazada: RMS {r_new:.4f} > {r_old:.4f} de la "
                          "versión vigente — deteriora el desempeño (17.23)")}
