"""Tests de modelado radioquímico (Informe 19.14 — Fase 15)."""
import math

import pytest
from fastapi.testclient import TestClient

from app.main import app

ETAPAS_FDG = [
    {"tipo": "sintesis", "nombre": "síntesis FDG en módulo",
     "eficiencia": 0.60, "duracion_min": 30.0,
     "fuente": "Yu 2006, Nucl Med Biol — rendimiento radioquímico"},
    {"tipo": "purificacion", "nombre": "purificación SPE",
     "eficiencia": 0.95, "duracion_min": 10.0,
     "fuente": "SOP validado del módulo (ficha del fabricante)"},
    {"tipo": "formulacion", "nombre": "formulación y filtrado estéril",
     "eficiencia": 0.98, "duracion_min": 10.0,
     "fuente": "SOP validado del módulo (ficha del fabricante)"},
]


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_registrar_proceso_ok(client):
    r = client.post("/api/v1/radiochemistry/processes", json={
        "producto": "FDG-test", "nucleido": "F-18", "etapas": ETAPAS_FDG,
        "registrado_por": "radioquímico"})
    assert r.status_code == 201
    p = r.json()
    assert p["proceso_id"].startswith("RQ-")
    assert p["version"] == 1
    assert len(p["etapas"]) == 3


def test_etapa_sin_fuente_rechazada(client):
    etapas = [dict(ETAPAS_FDG[0], fuente="")]
    r = client.post("/api/v1/radiochemistry/processes", json={
        "producto": "FDG-sin-fuente", "nucleido": "F-18", "etapas": etapas,
        "registrado_por": "op"})
    assert r.status_code == 422
    assert "49.11" in r.json()["detail"]


def test_eficiencia_fuera_de_rango(client):
    etapas = [dict(ETAPAS_FDG[0], eficiencia=1.2)]
    r = client.post("/api/v1/radiochemistry/processes", json={
        "producto": "FDG-mal", "nucleido": "F-18", "etapas": etapas,
        "registrado_por": "op"})
    assert r.status_code == 422


def test_tipo_etapa_invalido(client):
    etapas = [dict(ETAPAS_FDG[0], tipo="magia")]
    r = client.post("/api/v1/radiochemistry/processes", json={
        "producto": "FDG-magia", "nucleido": "F-18", "etapas": etapas,
        "registrado_por": "op"})
    assert r.status_code == 422


def test_eos_matematica_con_lambda_real(client):
    r = client.post("/api/v1/radiochemistry/processes", json={
        "producto": "FDG-eos", "nucleido": "F-18", "etapas": ETAPAS_FDG,
        "registrado_por": "radioquímico"})
    pid = r.json()["proceso_id"]
    res = client.post("/api/v1/radiochemistry/eos", json={
        "proceso_id": pid, "eob_gbq": 1000.0})
    assert res.status_code == 200
    d = res.json()
    # λ real del F-18: T½ ≈ 109.77 min → λ ≈ 1.052e-4 s⁻¹
    lam_f18 = math.log(2) / (109.77 * 60)
    assert abs(d["lambda_s"] - lam_f18) / lam_f18 < 0.02
    ef = 0.60 * 0.95 * 0.98
    t = (30 + 10 + 10) * 60
    esperado = 1000.0 * ef * math.exp(-lam_f18 * t)
    assert abs(d["eos_gbq"] - esperado) / esperado < 0.01
    assert d["eficiencia_total"] == round(ef, 5)
    assert "nunca un valor medido" in d["nota_honestidad"]
    assert "biblioteca nuclear" in d["fuente_lambda"]


def test_versionado_proceso_nunca_sobrescribe(client):
    r1 = client.post("/api/v1/radiochemistry/processes", json={
        "producto": "NaF-F18-test", "nucleido": "F-18",
        "etapas": ETAPAS_FDG[:1], "registrado_por": "op"})
    r2 = client.post("/api/v1/radiochemistry/processes", json={
        "producto": "NaF-F18-test", "nucleido": "F-18",
        "etapas": ETAPAS_FDG[:2], "registrado_por": "op",
        "motivo_version": "se añade purificación"})
    assert r2.json()["version"] == 2
    pid = r1.json()["proceso_id"]
    v1 = client.get(f"/api/v1/radiochemistry/processes/{pid}",
                    params={"version": 1})
    assert v1.json()["version"] == 1
    assert len(v1.json()["etapas"]) == 1   # la v1 sigue intacta
    vers = client.get(f"/api/v1/radiochemistry/processes/{pid}/versions")
    assert len(vers.json()["versiones"]) == 2


def test_eob_negativo_rechazado(client):
    r = client.post("/api/v1/radiochemistry/processes", json={
        "producto": "FDG-neg", "nucleido": "F-18", "etapas": ETAPAS_FDG[:1],
        "registrado_por": "op"})
    res = client.post("/api/v1/radiochemistry/eos", json={
        "proceso_id": r.json()["proceso_id"], "eob_gbq": -5.0})
    assert res.status_code == 422
