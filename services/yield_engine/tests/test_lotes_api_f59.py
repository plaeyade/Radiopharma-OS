"""Tests F59 — Batch Manager API (EDS 21.6)."""
from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import DATA_DIR
from app.application.production_service import ProductionService
from app.infrastructure.repositories.local_reaction_data import (
    LocalReactionDataProvider)
from app.infrastructure.stopping.factory import build_stopping_provider
from app.presentation.routers import lotes_api


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("REGISTRO_LOTES", str(tmp_path / "reg.jsonl"))
    service = ProductionService(
        stopping=build_stopping_provider(DATA_DIR / "stopping"),
        rxn=LocalReactionDataProvider(DATA_DIR))
    app = FastAPI()
    app.include_router(lotes_api.build_router(service))
    return TestClient(app)


def test_crear_y_listar_lote(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/lotes/teorico", json={"isotopo": "F18", "operador": "op1",
                                       "blanco": "B1", "modulo_sintesis": "M1"})
    assert r.status_code == 201
    lote = r.json()
    assert lote["irradiacion"]["eob_gbq"] > 0
    assert lote["eos_gbq"] < lote["irradiacion"]["eob_gbq"]
    assert lote["trazabilidad"]["operador"] == "op1"
    assert lote["liberacion"].startswith("no_liberada")
    assert "pendiente_entorno" in lote["qc"]
    r2 = c.get("/lotes")
    assert r2.status_code == 200 and r2.json()["n"] == 1


def test_append_only_dos_lotes_ids_unicos(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    a = c.post("/lotes/teorico", json={"isotopo": "C11"}).json()
    b = c.post("/lotes/teorico", json={"isotopo": "C11"}).json()
    assert a["lote_id"] != b["lote_id"]
    assert c.get("/lotes").json()["n"] == 2


def test_isotopo_no_soportado_400(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.post("/lotes/teorico", json={"isotopo": "TC99M"}).status_code == 400


def test_escenarios_declarados(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    j = c.get("/lotes/escenarios").json()
    assert set(j["isotopos"]) == {"F18", "C11", "GA68", "CU64"}
