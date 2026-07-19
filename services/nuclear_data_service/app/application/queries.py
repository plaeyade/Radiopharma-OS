"""
Casos de uso del Nuclear Data Service (capa de aplicación).
"""
from __future__ import annotations

from typing import Optional

from app.domain.entities import ReactionChannel, DecayScheme
from app.domain.interfaces import CrossSectionRepository, DecayDataRepository


class NuclearDataQueries:
    """Fachada de consultas nucleares para la capa de presentación."""

    def __init__(self, xs_repo: CrossSectionRepository, decay_repo: DecayDataRepository) -> None:
        self._xs = xs_repo
        self._decay = decay_repo

    def list_reactions(self) -> list[ReactionChannel]:
        return self._xs.list_reactions()

    def get_reaction(self, reaction_id: str) -> Optional[ReactionChannel]:
        return self._xs.get_reaction(reaction_id)

    def get_cross_section_window(
        self, reaction_id: str, e_min: float = 0.0, e_max: float = 1e3
    ) -> Optional[ReactionChannel]:
        """Devuelve la reacción con puntos filtrados a [e_min, e_max] MeV."""
        rxn = self._xs.get_reaction(reaction_id)
        if rxn is None:
            return None
        window = tuple(p for p in rxn.points if e_min <= p.energy_mev <= e_max)
        return ReactionChannel(
            reaction_id=rxn.reaction_id, notation=rxn.notation,
            projectile=rxn.projectile, target_nuclide=rxn.target_nuclide,
            product_nuclide=rxn.product_nuclide, q_value_mev=rxn.q_value_mev,
            threshold_mev=rxn.threshold_mev, dataset_id=rxn.dataset_id, points=window)

    def get_decay(self, nuclide: str) -> Optional[DecayScheme]:
        return self._decay.get_decay(nuclide)
