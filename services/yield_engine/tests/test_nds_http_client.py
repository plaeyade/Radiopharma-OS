"""
Tests del cliente HTTP YE -> NDS con transporte simulado (sin red).
"""
from __future__ import annotations

import httpx

from app.infrastructure.repositories.nds_http_client import NdsHttpClient

_REACTION_PAYLOAD = {
    "reaction_id": "o18_p_n_f18", "notation": "18O(p,n)18F",
    "projectile": "p", "target_nuclide": "18O", "product_nuclide": "18F",
    "q_value_mev": -2.438, "threshold_mev": 2.574,
    "dataset_id": "o18_p_n_f18_iaea2021", "n_points": 2,
    "points": [
        {"energy_mev": 2.55, "sigma_mb": 0.1, "dsigma_mb": 0.01},
        {"energy_mev": 5.04, "sigma_mb": 533.4, "dsigma_mb": 29.6},
    ],
}

_DECAY_PAYLOAD = {
    "nuclide": "18F", "z": 9, "a": 18, "half_life_s": 6586.2,
    "decay_constant_s": 1.0524e-4, "decay_modes": [], "emissions": [],
    "dataset_id": "livechart-ddep-2021",
}


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/decay"):
        return httpx.Response(200, json=_DECAY_PAYLOAD)
    return httpx.Response(200, json=_REACTION_PAYLOAD)


def _client() -> NdsHttpClient:
    return NdsHttpClient("http://nds-test", transport=httpx.MockTransport(_handler))


def test_http_client_seccion_eficaz():
    e, s, ds = _client().get_excitation_function("o18_p_n_f18")
    assert e == [2.55, 5.04]
    assert s[1] == 533.4
    assert ds[1] == 29.6


def test_http_client_umbral_y_dataset():
    c = _client()
    assert c.get_threshold("o18_p_n_f18") == 2.574
    assert c.get_dataset_id("o18_p_n_f18") == "o18_p_n_f18_iaea2021"


def test_http_client_decaimiento():
    assert abs(_client().get_decay_constant("18F") - 1.0524e-4) < 1e-10


def test_factory_conmuta_a_http(monkeypatch, tmp_path):
    monkeypatch.setenv("NUCLEAR_DATA_URL", "http://nds:8001")
    from app.infrastructure.repositories.factory import build_reaction_provider
    from app.infrastructure.repositories.nds_http_client import NdsHttpClient
    assert isinstance(build_reaction_provider(tmp_path), NdsHttpClient)


def test_factory_local_sin_env(monkeypatch, tmp_path):
    monkeypatch.delenv("NUCLEAR_DATA_URL", raising=False)
    (tmp_path / "reactions.json").write_text("{}")
    (tmp_path / "decay").mkdir()
    from app.infrastructure.repositories.factory import build_reaction_provider
    from app.infrastructure.repositories.local_reaction_data import LocalReactionDataProvider
    assert isinstance(build_reaction_provider(tmp_path), LocalReactionDataProvider)
