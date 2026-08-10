"""Optimización física de parámetros de producción (cap. 41.13).

La optimización operacional (Informe 18.10) se resuelve siempre
sobre el **modelo físico determinista**: los surrogates pueden
acelerar la exploración (cap. 20), pero nunca reemplazan al modelo
de referencia (20.3). El resultado es una recomendación claramente
diferenciada de las decisiones operativas (41.9).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from app.domain.entities import TargetMaterial
from app.domain.yield_calculator import YieldCalculator


@dataclass
class OptimizationConstraint:
    """Restricciones operativas del espacio de búsqueda."""
    energy_min_mev: float = 8.0
    energy_max_mev: float = 18.0
    current_min_ua: float = 5.0
    current_max_ua: float = 80.0
    irradiation_min_min: float = 15.0
    irradiation_max_min: float = 240.0
    max_beam_power_w: float = 1500.0  # límite térmico del blanco


@dataclass
class OptimizationResult:
    """Recomendación de optimización (nunca decisión automática)."""
    objetivo: str
    mejor: dict
    evaluaciones: int
    grilla: dict
    restricciones: dict
    nota: str = ("recomendación del modelo físico determinista; la "
                 "decisión operativa permanece en manos del personal "
                 "habilitado (41.9)")


class ProductionOptimizer:
    """Búsqueda en grilla sobre el modelo físico (determinista)."""

    def __init__(self, calculator: YieldCalculator, n_grid: int = 9) -> None:
        self._yc = calculator
        self._n = n_grid

    def optimize_eob(self, reaction_id: str, target: TargetMaterial,
                     half_life_min: float,
                     constraints: OptimizationConstraint) -> OptimizationResult:
        """Maximiza la actividad EOB = A_sat·I·(1−e^(−λt)).

        La corriente y el tiempo entran de forma analítica (la
        actividad crece con ambos), por lo que la grilla explora la
        energía —que modifica σ(E) y el stopping— y se verifica la
        restricción de potencia del haz P = E·I.
        """
        lam = np.log(2.0) / half_life_min
        c = constraints
        energies = np.linspace(c.energy_min_mev, c.energy_max_mev, self._n)
        t_best = c.irradiation_max_min  # actividad monótona en t
        mejor: dict | None = None
        evaluaciones = 0
        for e in energies:
            y_sat, _, _ = self._yc.saturation_yield_mbq_ua(
                reaction_id, target, float(e))
            evaluaciones += 1
            i_max_termica = c.max_beam_power_w / e  # P = E·I ≤ límite
            i_best = min(c.current_max_ua, i_max_termica)
            if i_best < c.current_min_ua:
                continue  # restricciones incompatibles a esta energía
            eob = (y_sat * i_best
                   * (1.0 - float(np.exp(-lam * t_best))) / 1000.0)
            candidato = {"beam_energy_mev": round(float(e), 3),
                         "current_ua": round(i_best, 3),
                         "irradiation_min": t_best,
                         "beam_power_w": round(float(e) * i_best, 2),
                         "eob_gbq": round(eob, 4),
                         "y_sat_mbq_ua": round(y_sat, 2)}
            if mejor is None or candidato["eob_gbq"] > mejor["eob_gbq"]:
                mejor = candidato
        if mejor is None:
            raise ValueError("espacio de restricciones vacío: no hay "
                             "combinación factible (41.9)")
        return OptimizationResult(
            objetivo="maximizar actividad EOB (modelo físico determinista)",
            mejor=mejor, evaluaciones=evaluaciones,
            grilla={"energies_mev": [round(float(e), 2) for e in energies],
                    "n_por_dimension": self._n},
            restricciones=asdict(c))
