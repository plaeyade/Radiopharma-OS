"""
Radiopharma OS - QC Engine (EDS v2.0, Vol. IV Quality Control Twin)
Capa de dominio: entidades de control de calidad del radiofármaco.

Alcance v0.1.0 (física nuclear del QC):
- corrección por decaimiento a tiempo de referencia,
- verificación de vida media (identidad radionuclídica),
- detección de impurezas radionuclídicas por desviación del monoexponencial,
- evaluación contra criterios de aceptación configurables (farmacopea).

NOTA REGULATORIA: los límites precargados son valores por defecto de
referencia general (USP <823>, Ph. Eur. fludeoxyglucosa). Cada instalación
debe verificarlos contra la monografía vigente antes de uso GMP.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class QcStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"


@dataclass(frozen=True)
class ActivityMeasurement:
    """Medición de actividad en un instante relativo (t=0 arbitrario)."""
    time_min: float
    activity: float                    # misma unidad para toda la serie
    uncertainty: Optional[float] = None  # 1 sigma; si falta, se pondera uniforme


@dataclass(frozen=True)
class HalfLifeFitResult:
    """Resultado del ajuste A(t) = A0 * exp(-lambda * t)."""
    half_life_min: float
    half_life_uncertainty_min: float
    activity_at_t0: float
    chi_squared_reduced: float
    n_points: int
    residuals: tuple[float, ...]
    reference_half_life_min: float
    deviation_percent: float
    within_tolerance: bool
    tolerance_percent: float
    impurity_suspected: bool


@dataclass(frozen=True)
class AcceptanceRule:
    """Regla de aceptación: parámetro dentro de [min, max]."""
    parameter: str
    min_value: Optional[float]
    max_value: Optional[float]
    unit: str
    source: str                        # p. ej. "Ph. Eur. fludeoxyglucose (verificar)"


@dataclass(frozen=True)
class RuleEvaluation:
    rule: AcceptanceRule
    measured: Optional[float]
    status: QcStatus
    detail: str


@dataclass(frozen=True)
class QcReport:
    """Informe consolidado de control de calidad."""
    product: str
    nuclide: str
    overall_status: QcStatus
    rule_evaluations: tuple[RuleEvaluation, ...] = ()
    half_life_fit: Optional[HalfLifeFitResult] = None
