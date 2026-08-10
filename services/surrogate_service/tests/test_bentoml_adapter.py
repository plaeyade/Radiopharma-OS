"""Pruebas del adaptador BentoML (cap. 20.10): honestidad de runtime."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.infrastructure.bentoml_adapter import (BentoMLAdapter,  # noqa: E402
                                                BentoMLUnavailable)
from app.main import app  # noqa: E402
from app.presentation.routers import surrogate_api  # noqa: E402


@pytest.fixture()
def client():
    return TestClient(app)


def _train(client) -> None:
    r = client.post("/api/v1/surrogates/train",
                    json={"version": "bento-1", "responsable": "qa"})
    assert r.status_code == 200


def test_status_honesto(client):
    r = client.get("/api/v1/surrogates/bentoml/status")
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["bentoml_disponible"] == BentoMLAdapter.available()
    assert "20.10" in cuerpo["nota"]


def test_package_sin_runtime_es_503_honesto(client, tmp_path, monkeypatch):
    monkeypatch.setattr(BentoMLAdapter, "available", staticmethod(lambda: False))
    _train(client)
    models = client.get("/api/v1/surrogates/models").json()
    mid = models[-1]["model_id"]
    r = client.post(f"/api/v1/surrogates/bentoml/package/{mid}"
                    f"?dest_dir={tmp_path}")
    assert r.status_code == 503
    assert "20.10" in r.json()["detail"]


def test_package_modelo_inexistente_404(client, tmp_path, monkeypatch):
    monkeypatch.setattr(BentoMLAdapter, "available", staticmethod(lambda: True))
    r = client.post("/api/v1/surrogates/bentoml/package/no-existe"
                    f"?dest_dir={tmp_path}")
    assert r.status_code == 404


def test_package_con_runtime_no_sobrescribe(client, tmp_path, monkeypatch):
    """Con runtime (simulado disponible + stub), el paquete nunca se
    sobrescribe (20.9)."""
    monkeypatch.setattr(BentoMLAdapter, "available", staticmethod(lambda: True))
    import types
    stub = types.SimpleNamespace(__version__="stub-test")
    monkeypatch.setitem(sys.modules, "bentoml", stub)
    _train(client)
    models = client.get("/api/v1/surrogates/models").json()
    mid = models[-1]["model_id"]
    r1 = client.post(f"/api/v1/surrogates/bentoml/package/{mid}"
                     f"?dest_dir={tmp_path}")
    assert r1.status_code == 200
    assert (tmp_path / r1.json()["paquete"] / "model.json").is_file()
    assert (tmp_path / r1.json()["paquete"] / "service.py").is_file()
    r2 = client.post(f"/api/v1/surrogates/bentoml/package/{mid}"
                     f"?dest_dir={tmp_path}")
    assert r2.status_code == 409  # nunca reescribe (20.9)


def test_adapter_directo_sin_runtime():
    if BentoMLAdapter.available():
        pytest.skip("runtime BentoML presente en el entorno")
    with pytest.raises(BentoMLUnavailable):
        BentoMLAdapter().package(record=None, dest_dir="/tmp/x")
