"""Tests del Radiation Safety & Shielding Engine (EDS cap. 36).

Física verificable: atenuación exacta del modelo, tasa de dosis de
fuente puntual con Γ documentada, umbrales de zonificación y límites
dosimétricos ICRP/GSR Part 3.
"""
import math

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_dose_rate_exacta_fuente_puntual(client: TestClient) -> None:
    # Γ(¹⁸F) = 0.143 µSv·m²/(GBq·h): 37 GBq a 1 m → 5.291 µSv/h
    r = client.post("/api/v1/qc/radiation/dose-rate",
                    json={"actividad_gbq": 37.0, "distancia_m": 1.0})
    assert r.status_code == 200
    assert r.json()["tasa_usv_h"] == pytest.approx(0.143 * 37.0, rel=1e-9)
    # ley del cuadrado inverso: a 2 m, cuarto
    r2 = client.post("/api/v1/qc/radiation/dose-rate",
                     json={"actividad_gbq": 37.0, "distancia_m": 2.0})
    assert r2.json()["tasa_usv_h"] == pytest.approx(
        r.json()["tasa_usv_h"] / 4.0, rel=1e-9)


def test_dose_rate_rechaza_parametros_no_fisicos(client: TestClient) -> None:
    r = client.post("/api/v1/qc/radiation/dose-rate",
                    json={"actividad_gbq": 0.0, "distancia_m": 1.0})
    assert r.status_code == 422


def test_atenuacion_sin_blindaje_es_uno(client: TestClient) -> None:
    r = client.post("/api/v1/qc/radiation/attenuation",
                    json={"espesor_cm": 0.0, "material": "plomo"})
    assert r.status_code == 200
    assert r.json()["fraccion_transmitida"] == pytest.approx(1.0)


def test_plomo_blinda_mas_que_hormigon(client: TestClient) -> None:
    pb = client.post("/api/v1/qc/radiation/attenuation",
                     json={"espesor_cm": 5.0, "material": "plomo"}).json()
    co = client.post("/api/v1/qc/radiation/attenuation",
                     json={"espesor_cm": 5.0, "material": "hormigon"}).json()
    assert 0.0 < pb["fraccion_transmitida"] < co["fraccion_transmitida"] < 1.0


def test_atenuacion_material_desconocido(client: TestClient) -> None:
    r = client.post("/api/v1/qc/radiation/attenuation",
                    json={"espesor_cm": 1.0, "material": "unobtainium"})
    assert r.status_code == 422
    assert "version" in r.json()["detail"] or "xcom" in r.json()["detail"]


def test_shielding_cumple_objetivo_y_es_consistente(client: TestClient) -> None:
    r = client.post("/api/v1/qc/radiation/shielding",
                    json={"tasa_objetivo_usv_h": 0.5,
                          "tasa_inicial_usv_h": 50.0, "material": "plomo"})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["espesor_cm"] > 0
    assert cuerpo["version_constantes"]
    # coherencia: con ese espesor la tasa resultante ≤ objetivo
    att = client.post("/api/v1/qc/radiation/attenuation",
                      json={"espesor_cm": cuerpo["espesor_cm"],
                            "material": "plomo"}).json()
    assert att["fraccion_transmitida"] * 50.0 <= 0.5 * 1.001


def test_shielding_objetivo_ya_cumplido(client: TestClient) -> None:
    r = client.post("/api/v1/qc/radiation/shielding",
                    json={"tasa_objetivo_usv_h": 10.0,
                          "tasa_inicial_usv_h": 5.0, "material": "hierro"})
    assert r.status_code == 200
    assert r.json()["espesor_cm"] == 0.0


def test_clasificacion_areas_umbrales(client: TestClient) -> None:
    casos = [(0.3, "zona_publica"), (1.0, "zona_vigilada"),
             (10.0, "zona_controlada")]
    for tasa, zona in casos:
        r = client.post("/api/v1/qc/radiation/area-classification",
                        json={"tasa_usv_h": tasa})
        assert r.status_code == 200
        assert r.json()["zona"] == zona
        assert r.json()["umbrales_version"]
    r = client.post("/api/v1/qc/radiation/area-classification",
                    json={"tasa_usv_h": -1.0})
    assert r.status_code == 422


def test_contaminacion_evalua_contra_limite(client: TestClient) -> None:
    ok = client.post("/api/v1/qc/radiation/contamination",
                     json={"punto": "celda-1 superficie", "bq_cm2": 0.2,
                           "limite_bq_cm2": 0.4, "operador": "op-7"})
    assert ok.status_code == 201
    assert ok.json()["estado"] == "conforme"
    mal = client.post("/api/v1/qc/radiation/contamination",
                      json={"punto": "celda-1 superficie", "bq_cm2": 0.9,
                            "limite_bq_cm2": 0.4})
    assert mal.json()["estado"] == "supera_limite"


def test_dosimetria_acumula_y_controla_limite(client: TestClient) -> None:
    tid = "trab-3601"
    for dosis in (0.5, 0.5):
        r = client.post("/api/v1/qc/radiation/dosimetry/records",
                        json={"trabajador_id": tid, "dosis_msv": dosis,
                              "periodo": "2026-08"})
        assert r.status_code == 201
    acc = client.get(f"/api/v1/qc/radiation/dosimetry/{tid}/2026")
    assert acc.status_code == 200
    assert acc.json()["dosis_acumulada_msv"] == pytest.approx(1.0)
    assert acc.json()["estado"] == "conforme"
    # supera el límite ocupacional de 20 mSv/año
    client.post("/api/v1/qc/radiation/dosimetry/records",
                json={"trabajador_id": tid, "dosis_msv": 25.0,
                      "periodo": "2026-09"})
    acc2 = client.get(f"/api/v1/qc/radiation/dosimetry/{tid}/2026")
    assert acc2.json()["estado"] == "supera_limite"
    assert acc2.json()["limite_ano_msv"] == 20.0


def test_dosimetria_registro_auditado(client: TestClient) -> None:
    r = client.get("/api/v1/qc/radiation/dosimetry/records")
    assert r.status_code == 200
    assert all("fecha" in reg and reg["fecha"] for reg in r.json())


def test_constantes_versionadas_expuestas(client: TestClient) -> None:
    r = client.get("/api/v1/qc/radiation/constants")
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["gamma_f18_usv_m2_per_gbq_h"] == pytest.approx(0.143)
    assert "plomo" in cuerpo["materiales"]
    assert "no sustituyen" in cuerpo["nota"]
