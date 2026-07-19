"""
Radiopharma OS - Nuclear Data Service
Capa de dominio: entidades nucleares inmutables.

Convenciones del proyecto (EDS v2.0, Vol. I):
- snake_case, type hints obligatorios, docstrings en español.
- El dominio no depende de infraestructura (Clean Architecture).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class CrossSectionPoint:
    """Un punto de la función de excitación sigma(E)."""
    energy_mev: float
    sigma_mb: float
    dsigma_mb: Optional[float] = None


@dataclass(frozen=True)
class ReactionChannel:
    """Canal de reacción nuclear con su función de excitación y procedencia."""
    reaction_id: str               # p. ej. "o18_p_n_f18"
    notation: str                  # p. ej. "18O(p,n)18F"
    projectile: str                # "p"
    target_nuclide: str            # "18O"
    product_nuclide: str           # "18F"
    q_value_mev: float
    threshold_mev: float
    dataset_id: str                # referencia al registry de procedencia
    points: tuple[CrossSectionPoint, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DecayMode:
    mode: str                      # "beta+", "electron_capture", ...
    branching_ratio: float
    endpoint_energy_kev: Optional[float] = None


@dataclass(frozen=True)
class Emission:
    type: str
    energy_kev: float
    intensity_percent: float


@dataclass(frozen=True)
class DecayScheme:
    """Esquema de decaimiento de un radionúclido."""
    nuclide: str
    z: int
    a: int
    half_life_s: float
    decay_constant_s: float        # lambda [s^-1]
    decay_modes: tuple[DecayMode, ...]
    emissions: tuple[Emission, ...]
    dataset_id: str
