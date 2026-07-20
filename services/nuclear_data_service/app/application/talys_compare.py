"""
Verificación cruzada de funciones de excitación: IAEA (experimental)
vs TALYS (teórico).

Interpolación lineal de la curva TALYS sobre las energías IAEA dentro
del rango solapado; métricas de desviación solo donde la referencia
IAEA supera el 5 % de su pico (evita ruido relativo junto al umbral).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.domain.entities import ReactionChannel

_REL_FLOOR = 0.05  # 5 % del pico IAEA


@dataclass(frozen=True)
class SourceSummary:
    dataset_id: str
    n_points: int
    e_min_mev: float
    e_max_mev: float
    peak_energy_mev: float
    peak_sigma_mb: float


@dataclass(frozen=True)
class CompareResult:
    reaction_id: str
    iaea: SourceSummary
    talys: SourceSummary
    n_compared: int
    max_rel_deviation: float
    rms_rel_deviation: float


def _summary(r: ReactionChannel) -> SourceSummary:
    peak = max(r.points, key=lambda p: p.sigma_mb)
    return SourceSummary(
        dataset_id=r.dataset_id, n_points=len(r.points),
        e_min_mev=r.points[0].energy_mev, e_max_mev=r.points[-1].energy_mev,
        peak_energy_mev=peak.energy_mev, peak_sigma_mb=peak.sigma_mb)


def _interp(points: tuple, e: float) -> float | None:
    """Interpolación lineal de sigma en e; None fuera de rango."""
    pts = sorted(points, key=lambda p: p.energy_mev)
    if e < pts[0].energy_mev or e > pts[-1].energy_mev:
        return None
    for a, b in zip(pts, pts[1:]):
        if a.energy_mev <= e <= b.energy_mev:
            if b.energy_mev == a.energy_mev:
                return a.sigma_mb
            f = (e - a.energy_mev) / (b.energy_mev - a.energy_mev)
            return a.sigma_mb + f * (b.sigma_mb - a.sigma_mb)
    return pts[-1].sigma_mb


def compare(iaea: ReactionChannel,
            talys: ReactionChannel) -> CompareResult:
    """Métricas de desviación relativa TALYS vs IAEA."""
    if not iaea.points or not talys.points:
        raise ValueError("ambas curvas deben tener puntos")
    peak_iaea = max(p.sigma_mb for p in iaea.points)
    floor = _REL_FLOOR * peak_iaea

    deviations: list[float] = []
    for p in iaea.points:
        if p.sigma_mb < floor:
            continue
        xs_t = _interp(talys.points, p.energy_mev)
        if xs_t is None:
            continue
        deviations.append((xs_t - p.sigma_mb) / p.sigma_mb)

    if not deviations:
        raise ValueError("sin solape útil entre curvas")

    max_dev = max(abs(d) for d in deviations)
    rms = math.sqrt(sum(d * d for d in deviations) / len(deviations))
    return CompareResult(
        reaction_id=iaea.reaction_id,
        iaea=_summary(iaea), talys=_summary(talys),
        n_compared=len(deviations),
        max_rel_deviation=max_dev, rms_rel_deviation=rms)
