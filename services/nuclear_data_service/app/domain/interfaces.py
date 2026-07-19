"""
Interfaces (puertos) del Nuclear Data Service.
La capa de aplicación solo conoce estas abstracciones.
"""
from __future__ import annotations

from typing import Protocol, Optional
from app.domain.entities import ReactionChannel, DecayScheme


class CrossSectionRepository(Protocol):
    """Puerto de acceso a funciones de excitación."""

    def list_reactions(self) -> list[ReactionChannel]: ...

    def get_reaction(self, reaction_id: str) -> Optional[ReactionChannel]: ...


class DecayDataRepository(Protocol):
    """Puerto de acceso a esquemas de decaimiento."""

    def get_decay(self, nuclide: str) -> Optional[DecayScheme]: ...
