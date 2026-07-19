"""
Puertos del Yield Engine.
"""
from __future__ import annotations

from typing import Protocol, Optional


class StoppingPowerProvider(Protocol):
    """Poder de frenado másico S(E) [MeV·cm²/g] para protones."""

    def stopping_power(self, material_key: str, energy_mev: float) -> float: ...

    def source_label(self) -> str: ...

    def range_g_cm2(self, material_key: str, energy_mev: float) -> float: ...


class ReactionDataProvider(Protocol):
    """Acceso a sigma(E) y datos de decaimiento (normalmente vía Nuclear Data Service)."""

    def get_excitation_function(self, reaction_id: str) -> tuple[list[float], list[float], list[Optional[float]]]: ...

    def get_decay_constant(self, nuclide: str) -> float: ...

    def get_threshold(self, reaction_id: str) -> float: ...

    def get_dataset_id(self, reaction_id: str) -> str: ...
