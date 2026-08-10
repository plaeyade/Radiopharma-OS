"""Tests del Financial Forecasting & Scenario Analysis Engine (cap. 40).

Verifica: escenarios aislados versionados 40.6/40.3, proyección
mensual con aritmética exacta 40.7, sensibilidad 40.8, evaluación de
inversión con fórmulas explícitas 40.9 (propuesta, nunca decisión),
análisis de riesgo 40.10, KPIs 40.11, validación 40.20 y auditoría
40.22.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.presentation.routers import financial_api

BASE = {"escenario_id": "fin-base-2026", "hipotesis": "demanda FDG estable",
        "demanda_mensual_dosis": 1000.0, "precio_dosis": 250.0,
        "coste_por_dosis": 120.0, "coste_fijo_mensual": 50000.0,
        "crecimiento_mensual_pct": 0.0, "horizonte_meses": 12,
        "version": "esc-1.0.0"}


@pytest.fixture()
def client() -> TestClient:
    financial_api.init()
    c = TestClient(app)
    assert c.post("/api/v1/financial/scenarios", json=BASE).status_code == 201
    return c


def test_forecast_aritmetica_exacta(client: TestClient) -> None:
    r = client.post("/api/v1/financial/scenarios/fin-base-2026/forecast",
                    json={"usuario": "controller-1"})
    assert r.status_code == 201
    res = r.json()
    m1 = res["meses"][0]
    assert m1["ingresos"] == pytest.approx(250000.0)
    assert m1["costes"] == pytest.approx(170000.0)
    assert m1["margen"] == pytest.approx(80000.0)
    assert res["ingresos_totales"] == pytest.approx(12 * 250000.0)
    assert res["margen_total"] == pytest.approx(12 * 80000.0)
    assert res["mes_equilibrio"] == 1


def test_forecast_con_crecimiento_compuesto(client: TestClient) -> None:
    crec = {**BASE, "escenario_id": "fin-crece",
            "crecimiento_mensual_pct": 10.0}
    assert client.post("/api/v1/financial/scenarios",
                       json=crec).status_code == 201
    res = client.post("/api/v1/financial/scenarios/fin-crece/forecast",
                      json={}).json()
    # mes 3: demanda = 1000·1.1²
    assert res["meses"][2]["demanda_dosis"] == pytest.approx(1210.0)


def test_escenarios_nunca_alteran_historicos(client: TestClient) -> None:
    assert client.post("/api/v1/financial/scenarios",
                       json=BASE).status_code == 422
    r = client.post("/api/v1/financial/scenarios", json={
        **BASE, "escenario_id": "fin-malo", "coste_por_dosis": -1.0})
    assert r.status_code == 422
    r2 = client.post("/api/v1/financial/scenarios", json={
        **BASE, "escenario_id": "fin-malo2", "horizonte_meses": 0})
    assert r2.status_code == 422


def test_sensibilidad_precio(client: TestClient) -> None:
    r = client.post(
        "/api/v1/financial/scenarios/fin-base-2026/sensitivity",
        json={"parametro": "precio_dosis",
              "variaciones_pct": [-10.0, 0.0, 10.0]})
    assert r.status_code == 200
    puntos = {p["variacion_pct"]: p for p in r.json()["puntos"]}
    # +10 % precio: ingresos 275000/mes
    assert puntos[10.0]["ingresos_totales"] == pytest.approx(
        12 * 275000.0)
    assert puntos[-10.0]["margen_total"] < puntos[0.0]["margen_total"]
    # parámetro no sensible: rechazado
    r2 = client.post(
        "/api/v1/financial/scenarios/fin-base-2026/sensitivity",
        json={"parametro": "hipotesis", "variaciones_pct": [5.0]})
    assert r2.status_code == 422


def test_inversion_payback_van_roi(client: TestClient) -> None:
    r = client.post(
        "/api/v1/financial/scenarios/fin-base-2026/investment",
        json={"capex": 1200000.0, "delta_ingresos_mensual": 50000.0,
              "delta_coste_mensual": 10000.0,
              "tasa_descuento_anual_pct": 0.0, "horizonte_meses": 60})
    inv = r.json()
    # flujo 40000/mes: payback 30 meses; VAN (r=0) = −1.2M + 2.4M
    assert inv["payback_meses"] == pytest.approx(30.0)
    assert inv["van"] == pytest.approx(1200000.0)
    assert inv["roi_pct"] == pytest.approx(100.0)
    assert "PROPUESTA" in inv["naturaleza"]
    # flujo negativo: payback honestamente null
    r2 = client.post(
        "/api/v1/financial/scenarios/fin-base-2026/investment",
        json={"capex": 100000.0, "delta_ingresos_mensual": 1000.0,
              "delta_coste_mensual": 5000.0, "horizonte_meses": 12})
    assert r2.json()["payback_meses"] is None


def test_riesgo_caida_demanda(client: TestClient) -> None:
    r = client.post("/api/v1/financial/scenarios/fin-base-2026/risk",
                    json={"evento": {"nombre": "caída demanda 30 %",
                                     "demanda_pct": -30.0}})
    rk = r.json()
    assert rk["margen_base"] == pytest.approx(960000.0)
    # demanda 700: margen = 700·130 − 50000 = 41000/mes
    assert rk["margen_bajo_evento"] == pytest.approx(12 * 41000.0)
    assert rk["impacto"] < 0
    # el escenario base permanece intacto
    res = client.post("/api/v1/financial/scenarios/fin-base-2026/forecast",
                      json={}).json()
    assert res["meses"][0]["demanda_dosis"] == pytest.approx(1000.0)


def test_kpis(client: TestClient) -> None:
    k = client.get("/api/v1/financial/scenarios/fin-base-2026/kpis").json()
    # rentabilidad = 960000 / 3000000
    assert k["rentabilidad_pct"] == pytest.approx(32.0)
    assert k["crecimiento_ingresos_pct"] == pytest.approx(0.0)
    assert k["coste_medio_mensual"] == pytest.approx(170000.0)


def test_resultados_versionados_y_auditoria(client: TestClient) -> None:
    client.post("/api/v1/financial/scenarios/fin-base-2026/forecast",
                json={})
    client.post("/api/v1/financial/scenarios/fin-base-2026/forecast",
                json={})
    res = client.get(
        "/api/v1/financial/scenarios/fin-base-2026/results").json()
    assert len(res) == 2
    aud = client.get("/api/v1/financial/audit").json()
    assert any(a["accion"] == "registrar_escenario" for a in aud)
    assert sum(1 for a in aud if a["accion"] == "proyectar") >= 2
