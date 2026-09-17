"""Tests e2e del router de componentes (Fase 27) — wiring real FastAPI."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.presentation.routers import component_api


def _client() -> TestClient:
    from app.domain.component_health import ComponentHealth
    from app.domain.facility_twin import Activo, FacilityTwin
    twin = FacilityTwin()
    twin.registrar_activo(Activo(activo_id="CYC-1", tipo="equipo",
                                 nombre="Ciclotrón"), "test")
    component_api.init(twin=twin, salud=ComponentHealth(twin))
    app = FastAPI()
    app.include_router(component_api.router)
    return TestClient(app)


def test_flujo_completo_api():
    c = _client()
    r = c.post("/api/v1/componentes", json={
        "componente_id": "FS-001", "tipo": "fuente_iones",
        "serie": "PIG-TA-114", "activo_id": "CYC-1",
        "umbral_vida": 60000.0,
        "fuente_umbral": "declaración interna — pendiente fabricante",
        "usuario": "qa"})
    assert r.status_code == 201
    assert r.json()["unidad_vida"] == "min_arco"
    r = c.post("/api/v1/componentes/FS-001/uso",
               json={"cantidad": 60.0, "origen": "corrida FDG evidencia_v072"})
    assert r.status_code == 201
    s = c.get("/api/v1/componentes/FS-001/salud").json()
    assert s["vida_consumida"] == 60.0
    assert s["estado_umbral"] == "declarado_interno_pendiente_fuente"
    assert len(c.get("/api/v1/componentes").json()) == 1
    assert len(c.get("/api/v1/componentes/audit").json()) == 2


def test_errores_honestos_422():
    c = _client()
    assert c.get("/api/v1/componentes/NADA/salud").status_code == 422
    c.post("/api/v1/componentes", json={
        "componente_id": "CB-1", "tipo": "cuerpo_blanco", "serie": "AG-01",
        "activo_id": "CYC-1", "umbral_vida": 500.0,
        "fuente_umbral": "declaración interna"})
    r = c.post("/api/v1/componentes/CB-1/uso",
               json={"cantidad": 1.0, "origen": ""})
    assert r.status_code == 422
    r = c.post("/api/v1/componentes/CB-1/reemplazo",
               json={"motivo": "desgaste", "responsable": "",
                     "nueva_serie": "AG-02"})
    assert r.status_code == 422
