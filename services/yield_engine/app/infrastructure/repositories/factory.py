"""
Fábrica del proveedor de datos de reacción.

Conmutación por variable de entorno (EDS cap. 10, config por entorno):
- NUCLEAR_DATA_URL definida  -> cliente HTTP del Nuclear Data Service
- ausente                    -> datasets locales empaquetados (standalone)
"""
from __future__ import annotations

import os
from pathlib import Path

from app.domain.interfaces import ReactionDataProvider

ENV_NDS_URL = "NUCLEAR_DATA_URL"


def build_reaction_provider(data_dir: Path) -> ReactionDataProvider:
    base_url = os.environ.get(ENV_NDS_URL)
    if base_url:
        from app.infrastructure.repositories.nds_http_client import NdsHttpClient
        return NdsHttpClient(base_url)
    from app.infrastructure.repositories.local_reaction_data import LocalReactionDataProvider
    return LocalReactionDataProvider(data_dir)
