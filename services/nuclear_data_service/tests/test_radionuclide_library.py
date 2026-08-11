"""Tests de la Biblioteca Universal de Radionúclidos (Informe cap. 19)."""

import math

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.presentation.routers import library_api

LN2 = math.log(2)


@pytest.fixture()
def client():
    library_api.init()
    return TestClient(app)


def test_catalogo_canonico_completo(client):
    c = client
    pet = c.get("/api/v1/library/catalog?categoria=PET").json()
    assert len(pet) == 11  # 19.6
    assert {e["nuclide"] for e in pet} >= {"f18", "c11", "n13", "o15", "ga68",
                                           "zr89", "cu64", "cu61", "sc44",
                                           "mn52", "i124"}
    spect = c.get("/api/v1/library/catalog?categoria=SPECT").json()
    assert len(spect) == 5  # 19.7
    tera = c.get("/api/v1/library/catalog?categoria=terapeutico").json()
    assert len(tera) == 8  # 19.8
    total = c.get("/api/v1/library/catalog").json()
    assert len(total) == 24


def test_estructura_completa_19_5(client):
    c = client
    r = c.get("/api/v1/library/nuclides/f18").json()
    assert r["categoria"] == "PET" and r["version"] == 1
    for seccion in ("nuclear", "fisica", "quimica", "clinica", "economica"):
        assert seccion in r
    assert r["nuclear"]["reaccion"] == "18O(p,n)18F"
    assert r["nuclear"]["vida_media_s"] == pytest.approx(109.77 * 60, rel=1e-3)
    assert r["fisica"]["tipo_blanco"] == "liquido"
    assert r["clinica"]["ventana_horas"] == 10.0
    assert r["bibliografia"] and r["autor"]  # 19.17


def test_incorporacion_sin_modificar_software(client):
    c = client
    entrada = c.get("/api/v1/library/nuclides/f18").json()
    r = c.post("/api/v1/library/nuclides", json={
        "nuclide": "lu177", "categoria": "terapeutico",
        "nuclear": {**entrada["nuclear"], "reaccion": "176Yb(n,γ)177Yb→177Lu",
                    "energia_umbral_mev": 0.0, "vida_media_s": 6.65 * 86400,
                    "modos_decaimiento": ["β−"], "emisiones": ["γ 113/208 keV"]},
        "fisica": {**entrada["fisica"], "material_blanco": "Yb-176",
                   "tipo_blanco": "solido"},
        "quimica": {**entrada["quimica"], "precursor": "177LuCl3",
                    "sintesis": "marcaje DOTA/PSMA", "eficiencia": 0.95},
        "clinica": {**entrada["clinica"], "indicaciones": ["PRRT NET", "PSMA"],
                    "dosis_habitual_mbq": 7400.0, "ventana_horas": 168.0},
        "economica": entrada["economica"],
        "bibliografia": ["IAEA TECDOC Lu-177"],
        "autor": "radiofarmacia"})
    assert r.status_code == 200 and r.json()["version"] == 1  # 19.16
    total = c.get("/api/v1/library/catalog").json()
    assert len(total) == 25
    # bibliografía obligatoria
    r = c.post("/api/v1/library/nuclides", json={
        "nuclide": "x1", "categoria": "PET", "nuclear": entrada["nuclear"],
        "fisica": entrada["fisica"], "quimica": entrada["quimica"],
        "clinica": entrada["clinica"], "economica": entrada["economica"],
        "bibliografia": [], "autor": "x"})
    assert r.status_code == 422


def test_versionado_nunca_sobrescribe(client):
    c = client
    entrada = c.get("/api/v1/library/nuclides/ga68").json()
    r = c.post("/api/v1/library/nuclides", json={
        "nuclide": "ga68", "categoria": "PET",
        "nuclear": entrada["nuclear"], "fisica": entrada["fisica"],
        "quimica": {**entrada["quimica"], "eficiencia": 0.90},
        "clinica": entrada["clinica"], "economica": entrada["economica"],
        "bibliografia": entrada["bibliografia"] + ["validación interna 2026"],
        "autor": "radiofarmacia", "historial": "mejora de eficiencia validada"})
    assert r.status_code == 200 and r.json()["version"] == 2  # 19.17
    v2 = c.get("/api/v1/library/nuclides/ga68").json()
    assert v2["quimica"]["eficiencia"] == 0.90 and v2["revisiones"] == 2
    assert v2["historial"] == "mejora de eficiencia validada"
    v1 = c.get("/api/v1/library/nuclides/ga68?version=1").json()
    assert v1["quimica"]["eficiencia"] == 0.85  # la anterior permanece


def test_eos_formula_documentada(client):
    c = client
    r = c.post("/api/v1/library/nuclides/f18/eos", json={
        "actividad_eob_gbqe": 10.0, "horas_sintesis": 1.0})
    assert r.status_code == 200
    eos = r.json()
    vida = 109.77 * 60
    esperado = 10.0 * math.exp(-LN2 / vida * 3600) * 0.72 * (1 - 0.05) * 0.95 * 0.98
    assert eos["actividad_eos_gbqe"] == pytest.approx(esperado, rel=1e-4)
    assert "A_EOS" in eos["formula"]  # 19.14 documentada


def test_ventana_clinica(client):
    c = client
    v = c.get("/api/v1/library/nuclides/f18/clinical-window").json()
    vida = 109.77 * 60
    assert v["fraccion_restante_en_ventana"] == pytest.approx(
        math.exp(-LN2 / vida * 10 * 3600), rel=1e-4)
    assert v["dosis_habitual_mbq"] == 370.0  # 19.15


def test_exfor_prioridad_experimental(client):
    c = client
    r = c.post("/api/v1/library/nuclides/f18/experimental", json={
        "tipo": "seccion_eficaz", "datos": [{"e_mev": 8.6, "sigma_mb": 331.0}],
        "referencia": "EXFOR O1803", "version_datos": "2024-01",
        "fecha": "2024-01-15", "fuente": "IAEA-EXFOR", "autor": "fisico1"})
    assert r.status_code == 200
    assert "prevalece" in r.json()["prioridad"]  # 19.12
    r = c.post("/api/v1/library/nuclides/f18/experimental", json={
        "tipo": "seccion_eficaz", "datos": [{"e_mev": 8.6}],
        "referencia": "", "version_datos": "x", "fecha": "x", "fuente": "x",
        "autor": "x"})
    assert r.status_code == 422  # referencia obligatoria
    regs = c.get("/api/v1/library/nuclides/f18/experimental").json()
    assert len(regs) == 1 and regs[0]["fuente"] == "IAEA-EXFOR"


def test_integraciones_estado_honesto_y_auditoria(client):
    c = client
    integ = c.get("/api/v1/library/integrations").json()
    assert integ["exfor"] == "no_configurado"  # honesto
    assert integ["nndc"].startswith("integrado")
    audit = c.get("/api/v1/library/audit").json()
    assert any(a["accion"] == "radionuclido_incorporado" for a in audit)
    assert all("timestamp" in a and "version_motor" in a for a in audit)
