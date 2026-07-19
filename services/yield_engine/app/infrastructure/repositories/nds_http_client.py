"""
Cliente HTTP del Nuclear Data Service (modo despliegue completo).

Implementa ReactionDataProvider consumiendo la API REST del NDS,
sustituyendo al proveedor local cuando la plataforma corre en
docker-compose o Kubernetes (patrón Anti-Corruption Layer, EDS cap. 8).
"""
from __future__ import annotations

from typing import Optional

import httpx

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class NdsHttpClient:
    """ReactionDataProvider remoto vía Nuclear Data Service."""

    def __init__(self, base_url: str, transport: Optional[httpx.BaseTransport] = None) -> None:
        self._base = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self._base, timeout=_TIMEOUT,
                                    transport=transport)

    # ------------------------------------------------------------------
    def get_excitation_function(self, reaction_id: str):
        r = self._client.get(f"/api/v1/reactions/{reaction_id}")
        r.raise_for_status()
        payload = r.json()
        e = [pt["energy_mev"] for pt in payload["points"]]
        s = [pt["sigma_mb"] for pt in payload["points"]]
        ds = [pt["dsigma_mb"] for pt in payload["points"]]
        return e, s, ds

    def get_decay_constant(self, nuclide: str) -> float:
        r = self._client.get(f"/api/v1/nuclides/{nuclide}/decay")
        r.raise_for_status()
        return float(r.json()["decay_constant_s"])

    def get_threshold(self, reaction_id: str) -> float:
        r = self._client.get(f"/api/v1/reactions/{reaction_id}")
        r.raise_for_status()
        return float(r.json()["threshold_mev"])

    def get_dataset_id(self, reaction_id: str) -> str:
        r = self._client.get(f"/api/v1/reactions/{reaction_id}")
        r.raise_for_status()
        return str(r.json()["dataset_id"])
