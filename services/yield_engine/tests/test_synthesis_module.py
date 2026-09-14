"""Tests de módulos de síntesis por proveedor + EOS multiisótopo +
tablas externas de frenado (Fase 16)."""
import math

import pytest
from fastapi.testclient import TestClient

from app.main import app

MOD_SYNTHERA = {
    "fabricante": "IBA", "modelo": "Synthera",
    "nucleidos_soportados": ["F-18"],
    "fuente": "J Nucl Med 2022;63(suppl 2):4123 — comparativa de "
              "módulos (Synthera/All-in-One/Neptis): rendimiento FDG "
              "60-66 %, tiempo 21-24 min",
    "registrado_por": "radioquímico",
}

ETAPA_FDG = [{"tipo": "sintesis", "nombre": "síntesis FDG",
              "eficiencia": 0.63, "duracion_min": 22.0,
              "fuente": "J Nucl Med 2022;63(suppl 2):4123 (60-66 %)"}]


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_registrar_modulo_ok(client):
    r = client.post("/api/v1/radiochemistry/modules", json=MOD_SYNTHERA)
    assert r.status_code == 201
    m = r.json()
    assert m["modulo_id"].startswith("MOD-")
    assert m["version"] == 1


def test_modulo_sin_fuente_rechazado(client):
    r = client.post("/api/v1/radiochemistry/modules", json={
        **MOD_SYNTHERA, "modelo": "X", "fuente": " "})
    assert r.status_code == 422
    assert "49.11" in r.json()["detail"]


def test_modulo_versionado_nunca_sobrescribe(client):
    r1 = client.post("/api/v1/radiochemistry/modules", json={
        **MOD_SYNTHERA, "modelo": "AllinOne", "fabricante": "Trasis"})
    r2 = client.post("/api/v1/radiochemistry/modules", json={
        **MOD_SYNTHERA, "modelo": "AllinOne", "fabricante": "Trasis",
        "nucleidos_soportados": ["F-18", "Ga-68"],
        "motivo_version": "ficha actualizada: soporte Ga-68"})
    assert r2.json()["version"] == 2
    assert r1.json()["modulo_id"] == r2.json()["modulo_id"]
    got = client.get(f"/api/v1/radiochemistry/modules/{r2.json()['modulo_id']}")
    assert "Ga-68" in got.json()["nucleidos_soportados"]


def test_proceso_vinculado_a_modulo_valida_nucleido(client):
    mod = client.post("/api/v1/radiochemistry/modules", json={
        **MOD_SYNTHERA, "modelo": "Synthera-Val"}).json()
    mal = client.post("/api/v1/radiochemistry/processes", json={
        "producto": "PSMA11-test", "nucleido": "Ga-68",
        "etapas": ETAPA_FDG, "registrado_por": "op",
        "modulo_id": mod["modulo_id"]})
    assert mal.status_code == 422
    assert "no declara soporte" in mal.json()["detail"]
    bien = client.post("/api/v1/radiochemistry/processes", json={
        "producto": "FDG-synthera-test", "nucleido": "F-18",
        "etapas": ETAPA_FDG, "registrado_por": "op",
        "modulo_id": mod["modulo_id"]})
    assert bien.status_code == 201
    assert bien.json()["modulo_id"] == mod["modulo_id"]


def test_eos_batch_multiisotopo(client):
    fdg = client.post("/api/v1/radiochemistry/processes", json={
        "producto": "FDG-batch", "nucleido": "F-18", "etapas": ETAPA_FDG,
        "registrado_por": "op"}).json()
    psma = client.post("/api/v1/radiochemistry/processes", json={
        "producto": "PSMA11-batch", "nucleido": "Ga-68",
        "etapas": [{"tipo": "sintesis", "nombre": "marcaje Ga-68",
                    "eficiencia": 0.76, "duracion_min": 20.0,
                    "fuente": "Wichmann 2021, J Label Compd Radiopharm "
                              "(76 % d.c. automatizado)"}],
        "registrado_por": "op"}).json()
    r = client.post("/api/v1/radiochemistry/eos/batch", json={"items": [
        {"proceso_id": fdg["proceso_id"], "eob_gbq": 1000.0},
        {"proceso_id": psma["proceso_id"], "eob_gbq": 3.7},
        {"proceso_id": "RQ-9999", "eob_gbq": 1.0}]})
    assert r.status_code == 200
    d = r.json()
    assert len(d["resultados"]) == 2
    assert len(d["errores"]) == 1           # error aislado por ítem
    f18, ga68 = d["resultados"]
    lam_f18 = math.log(2) / (109.77 * 60)
    lam_ga68 = math.log(2) / (67.71 * 60)
    assert abs(f18["lambda_s"] - lam_f18) / lam_f18 < 0.02
    assert abs(ga68["lambda_s"] - lam_ga68) / lam_ga68 < 0.02
    esp = 3.7 * 0.76 * math.exp(-lam_ga68 * 20 * 60)
    assert abs(ga68["eos_gbq"] - esp) / esp < 0.01
    assert "nunca valores medidos" in d["nota_honestidad"]


def test_tabla_externa_registro_y_honestidad(client):
    r = client.post("/api/v1/stopping-power/external-tables", json={
        "material": "agua_test", "ejecutado_en": "2026-09-14, SRIM-2013 en PC del laboratorio",
        "fuente": "SRIM-2013 ejecutado por el usuario, export PROTONS in water",
        "descripcion": "tabla de prueba",
        "filas": [[1.0, 260.0], [10.0, 45.0], [18.0, 27.0]],
        "registrado_por": "físico"})
    assert r.status_code == 201
    t = r.json()
    assert t["estado"] == "registrada_no_calibrada"
    assert len(t["sha256"]) == 64
    assert "nunca ejecuta ni simula SRIM" in t["nota_honestidad"]
    lista = client.get("/api/v1/stopping-power/external-tables")
    assert any(x["material"] == "agua_test" for x in lista.json()["tablas"])


def test_tabla_externa_sin_fuente_rechazada(client):
    r = client.post("/api/v1/stopping-power/external-tables", json={
        "material": "agua_x", "fuente": "", "ejecutado_en": "hoy",
        "filas": [[1.0, 2.0], [2.0, 1.0]], "registrado_por": "op"})
    assert r.status_code == 422
    assert "49.11" in r.json()["detail"]


def test_tabla_externa_energias_no_crecientes(client):
    r = client.post("/api/v1/stopping-power/external-tables", json={
        "material": "agua_y", "ejecutado_en": "hoy",
        "fuente": "SRIM-2013 ejecutado por el usuario",
        "filas": [[10.0, 45.0], [1.0, 260.0]], "registrado_por": "op"})
    assert r.status_code == 422
