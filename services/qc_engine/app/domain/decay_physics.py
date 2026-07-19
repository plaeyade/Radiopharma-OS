"""
Física del QC Engine: decaimiento y ajuste de vida media.

Ajuste por mínimos cuadrados ponderados sobre ln(A):
    ln A_i = ln A0 - λ t_i   (lineal)
Incertidumbres propagadas analíticamente; chi² reducido como indicador
de pureza radionuclídica (un monoexponencial debe describir la serie).
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np

from app.domain.entities import ActivityMeasurement, HalfLifeFitResult


def decay_correction(
    activity: float,
    half_life_min: float,
    delta_time_min: float,
    to_future: bool = True,
) -> float:
    """Actividad corregida por decaimiento.

    to_future=True:  A(t+Δt) = A0 * e^{-λ Δt}   (hacia adelante)
    to_future=False: A(t-Δt) = A0 * e^{+λ Δt}   (retro-corrección, p. ej. a EOB)
    """
    lam = math.log(2.0) / half_life_min
    factor = math.exp(-lam * delta_time_min) if to_future else math.exp(lam * delta_time_min)
    return activity * factor


def decay_correction_uncertainty(
    relative_activity_unc: float,
    half_life_min: float,
    delta_time_min: float,
    time_unc_min: float = 0.5,
    half_life_unc_min: float = 0.05,
) -> float:
    """Incertidumbre relativa combinada de la corrección (cuadratura).

    Componentes:
    - actividad de partida: relative_activity_unc
    - tiempo: λ * σ_t                (constante en Δt)
    - vida media: Δt * σ_λ           (crece con Δt; σ_λ = ln2 * σ_T / T²)
    """
    lam = math.log(2.0) / half_life_min
    sigma_lam = math.log(2.0) * half_life_unc_min / half_life_min ** 2
    return math.sqrt(relative_activity_unc ** 2
                     + (lam * time_unc_min) ** 2
                     + (delta_time_min * sigma_lam) ** 2)


def fit_half_life(
    measurements: list[ActivityMeasurement],
    reference_half_life_min: float,
    tolerance_percent: float = 5.0,
    chi2_threshold: float = 3.0,
) -> HalfLifeFitResult:
    """Ajusta la vida media de una serie de mediciones (WLS sobre ln A).

    impurity_suspected=True si el chi² reducido supera el umbral: la serie
    no es monoexponencial (posible impureza radionuclídica o deriva del
    calibrador de dosis).
    """
    if len(measurements) < 3:
        raise ValueError("Se requieren al menos 3 mediciones para el ajuste")

    t = np.array([m.time_min for m in measurements], dtype=float)
    a = np.array([m.activity for m in measurements], dtype=float)
    if np.any(a <= 0):
        raise ValueError("Las actividades deben ser positivas")

    y = np.log(a)
    if any(m.uncertainty for m in measurements):
        sig = np.array([m.uncertainty if m.uncertainty else a_i * 0.01
                        for m, a_i in zip(measurements, a)])
        w = 1.0 / (sig / a) ** 2            # peso en escala log: (a/σ_a)²
    else:
        w = np.ones_like(t)

    # WLS: y = b - λ t
    sw = w.sum()
    t_bar = (w * t).sum() / sw
    y_bar = (w * y).sum() / sw
    s_tt = (w * (t - t_bar) ** 2).sum()
    s_ty = (w * (t - t_bar) * (y - y_bar)).sum()
    lam = -s_ty / s_tt
    b = y_bar + lam * t_bar
    sigma_lam = math.sqrt(1.0 / s_tt)

    y_fit = b - lam * t
    chi2 = float((w * (y - y_fit) ** 2).sum())
    dof = max(len(t) - 2, 1)
    chi2_red = chi2 / dof

    hl = math.log(2.0) / lam
    hl_unc = math.log(2.0) * sigma_lam / lam ** 2
    a0 = math.exp(b)

    residuals = tuple((a - np.exp(y_fit)).tolist())
    deviation = abs(hl - reference_half_life_min) / reference_half_life_min * 100.0

    return HalfLifeFitResult(
        half_life_min=hl,
        half_life_uncertainty_min=hl_unc,
        activity_at_t0=a0,
        chi_squared_reduced=chi2_red,
        n_points=len(t),
        residuals=residuals,
        reference_half_life_min=reference_half_life_min,
        deviation_percent=deviation,
        within_tolerance=deviation <= tolerance_percent,
        tolerance_percent=tolerance_percent,
        impurity_suspected=chi2_red > chi2_threshold,
    )
