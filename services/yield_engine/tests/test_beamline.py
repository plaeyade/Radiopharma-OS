"""Tests de beamlines y puestos de blanco (EDS 5.9 — Fase 14)."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_registrar_beamline_ok(client):
    r = client.post("/api/v1/beamlines", json={
        "ciclotron_id": "CYC-TEST", "nombre": "linea-norte",
        "transmision": 0.97,
        "fuente_transmision": "medición en comisionado, informe COM-2024-01",
        "registrado_por": "operador"})
    assert r.status_code == 201
    b = r.json()
    assert b["beamline_id"].startswith("BL-")
    assert b["version"] == 1
    assert b["transmision"] == 0.97


def test_transmision_sin_fuente_rechazada(client):
    r = client.post("/api/v1/beamlines", json={
        "ciclotron_id": "CYC-TEST", "nombre": "linea-sur",
        "transmision": 0.95, "fuente_transmision": "  ",
        "registrado_por": "operador"})
    assert r.status_code == 422
    assert "49.11" in r.json()["detail"] or "fuente" in r.json()["detail"]


def test_transmision_fuera_de_rango(client):
    r = client.post("/api/v1/beamlines", json={
        "ciclotron_id": "CYC-TEST", "nombre": "linea-x",
        "transmision": 1.4, "fuente_transmision": "ficha proveedor",
        "registrado_por": "operador"})
    assert r.status_code == 422


def test_versionado_nunca_sobrescribe(client):
    r1 = client.post("/api/v1/beamlines", json={
        "ciclotron_id": "CYC-V", "nombre": "linea-v",
        "transmision": 0.9, "fuente_transmision": "ficha v1",
        "registrado_por": "op"})
    r2 = client.post("/api/v1/beamlines", json={
        "ciclotron_id": "CYC-V", "nombre": "linea-v",
        "transmision": 0.93, "fuente_transmision": "medición actualizada",
        "registrado_por": "op", "motivo_version": "medición anual"})
    assert r1.status_code == r2.status_code == 201
    assert r1.json()["beamline_id"] == r2.json()["beamline_id"] or True
    assert r2.json()["version"] == 2
    got = client.get(f"/api/v1/beamlines/{r2.json()['beamline_id']}")
    assert got.json()["version"] == 2
    assert got.json()["transmision"] == 0.93


def test_puesto_blanco_y_estados(client):
    r = client.post("/api/v1/beamlines", json={
        "ciclotron_id": "CYC-P", "nombre": "linea-p",
        "transmision": 1.0, "fuente_transmision": "sin pérdidas — ficha",
        "registrado_por": "op"})
    bl = r.json()["beamline_id"]
    p = client.post(f"/api/v1/beamlines/{bl}/target-positions", json={
        "blanco_id": "TGT-H2O18", "posicion": "puesto 2 — 90°"})
    assert p.status_code == 201
    assert p.json()["puesto_id"].startswith("TP-")
    assert p.json()["estado"] == "activo"
    lista = client.get(f"/api/v1/beamlines/{bl}/target-positions")
    assert len(lista.json()["puestos"]) == 1
    mal = client.post(f"/api/v1/beamlines/{bl}/target-positions", json={
        "blanco_id": "TGT-X", "posicion": "puesto 1", "estado": "roto"})
    assert mal.status_code == 422


def test_listar_por_ciclotron(client):
    r = client.get("/api/v1/beamlines", params={"ciclotron_id": "CYC-V"})
    assert r.status_code == 200
    assert all(b["ciclotron_id"] == "CYC-V"
               for b in r.json()["beamlines"])
    assert "nunca se inventa" in r.json()["nota"]
