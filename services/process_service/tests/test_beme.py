"""Tests del Building Environmental Management Engine (EDS cap. 35).

Verifica: sensores vinculados al Asset Registry 35.6, HVAC con fuente
SCADA obligatoria 35.7, gradiente y estabilidad de presión 35.8,
configuración de zonas versionada 35.11, alarmas de desviación 35.12,
gestión temporal 35.13 y validación 35.21 (rango, temporalidad, estado
del sensor, calidad) con eventos de validación — nunca corrección
silenciosa.
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.presentation.routers import beme_api


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture()
def client() -> TestClient:
    beme_api.init()
    c = TestClient(app)
    assert c.post("/api/v1/beme/sensors", json={
        "sensor_id": "s-temp-b1", "activo_id": "cyclo-1",
        "area_id": "bunker-1", "variable": "temperatura",
        "unidad": "C"}).status_code == 201
    assert c.post("/api/v1/beme/sensors", json={
        "sensor_id": "s-dp-b1", "activo_id": "hvac-1",
        "area_id": "bunker-1", "variable": "presion_diferencial",
        "unidad": "Pa"}).status_code == 201
    assert c.post("/api/v1/beme/sensors", json={
        "sensor_id": "s-dp-corr", "activo_id": "hvac-1",
        "area_id": "corredor-1", "variable": "presion_diferencial",
        "unidad": "Pa"}).status_code == 201
    assert c.post("/api/v1/beme/zones", json={
        "area_id": "bunker-1", "clasificacion": "zona_caliente",
        "objetivo": {"temp_min_c": 18.0, "temp_max_c": 25.0,
                     "presion_min_pa": -40.0, "presion_max_pa": -10.0},
        "version": "hvac-cfg-1.0.0"}).status_code == 201
    return c


def _medir(c: TestClient, sensor: str, valor: float, **kw) -> dict:
    cuerpo = {"sensor_id": sensor, "valor": valor, "calidad": "good",
              "origen": "opcua:plc1", "timestamp": _ahora()}
    cuerpo.update(kw)
    return c.post("/api/v1/beme/measurements", json=cuerpo)


def test_sensor_exige_vinculo_asset_registry(client: TestClient) -> None:
    r = client.post("/api/v1/beme/sensors", json={
        "sensor_id": "s-huerfano", "activo_id": "", "area_id": "bunker-1",
        "variable": "humedad", "unidad": "%HR"})
    assert r.status_code == 422
    assert "Asset Registry" in r.json()["detail"]


def test_hvac_parametros_exigen_fuente_scada(client: TestClient) -> None:
    r = client.post("/api/v1/beme/hvac", json={
        "hvac_id": "ahu-1", "area_id": "bunker-1",
        "parametros": {"renovaciones_h": 20}})
    assert r.status_code == 422
    assert "SCADA" in r.json()["detail"]
    r = client.post("/api/v1/beme/hvac", json={
        "hvac_id": "ahu-1", "area_id": "bunker-1",
        "parametros": {"renovaciones_h": 20, "caudal_m3_h": 3500},
        "fuente_scada": "modbus:ahu1"})
    assert r.status_code == 201
    # sin parámetros, el registro es válido (estado estructural)
    r = client.post("/api/v1/beme/hvac", json={
        "hvac_id": "ahu-2", "area_id": "corredor-1"})
    assert r.status_code == 201


def test_medicion_aceptada_dentro_de_objetivo(client: TestClient) -> None:
    r = _medir(client, "s-temp-b1", 21.0)
    assert r.status_code == 201
    assert r.json()["aceptada"] is True
    assert r.json()["desviacion"] is None


def test_desviacion_genera_alarma_area(client: TestClient) -> None:
    r = _medir(client, "s-dp-b1", -5.0)   # objetivo [-40,-10] Pa
    cuerpo = r.json()
    assert cuerpo["aceptada"] is True
    assert cuerpo["desviacion"]["tipo"] == "perdida_de_presion"
    assert "alarma:perdida_de_presion" in cuerpo["eventos"]
    evs = client.get("/api/v1/beme/events",
                     params={"area_id": "bunker-1"}).json()
    assert any(e["tipo"] == "alarma:perdida_de_presion" for e in evs)
    st = client.get("/api/v1/beme/zones/bunker-1/status").json()
    assert st["variables"]["presion_diferencial"]["valor"] == -5.0
    assert st["alarmas_activas"] >= 1


def test_validacion_rango_fisico(client: TestClient) -> None:
    r = _medir(client, "s-temp-b1", 500.0)   # físicamente imposible
    cuerpo = r.json()
    assert cuerpo["aceptada"] is False
    assert "validacion:fuera_de_rango" in cuerpo["eventos"]
    # la medición queda registrada como rechazada, nunca corregida
    meds = client.get("/api/v1/beme/measurements").json()
    assert meds[-1]["valor"] == 500.0 and meds[-1]["aceptada"] is False


def test_validacion_temporal_y_calidad(client: TestClient) -> None:
    futuro = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    r = _medir(client, "s-temp-b1", 21.0, timestamp=futuro)
    assert r.json()["aceptada"] is False
    assert "validacion:timestamp_futuro" in r.json()["eventos"]
    viejo = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    r = _medir(client, "s-temp-b1", 21.0, timestamp=viejo)
    assert "validacion:dato_obsoleto" in r.json()["eventos"]
    r = _medir(client, "s-temp-b1", 21.0, calidad="bad")
    assert r.json()["aceptada"] is False
    r = _medir(client, "s-temp-b1", 21.0, calidad="excelente")
    assert r.status_code == 422


def test_sensor_fuera_de_servicio_rechaza_mediciones(client: TestClient) -> None:
    client.post("/api/v1/beme/sensors/s-temp-b1/state",
                json={"estado": "fuera_de_servicio", "usuario": "mant-1"})
    r = _medir(client, "s-temp-b1", 21.0)
    assert r.json()["aceptada"] is False
    assert "validacion:sensor_fuera_de_servicio" in r.json()["eventos"]


def test_gradiente_presion_entre_zonas(client: TestClient) -> None:
    _medir(client, "s-dp-b1", -30.0)
    _medir(client, "s-dp-corr", 5.0)
    g = client.get("/api/v1/beme/pressure/gradient", params={
        "area_origen": "corredor-1", "area_destino": "bunker-1"}).json()
    assert g["gradiente_pa"] == pytest.approx(35.0)
    # honesto sin datos
    g2 = client.get("/api/v1/beme/pressure/gradient", params={
        "area_origen": "bunker-1", "area_destino": "sala-vacia"}).json()
    assert g2["gradiente_pa"] is None
    assert "sin mediciones" in g2["nota"]


def test_estabilidad_presion(client: TestClient) -> None:
    for v in (-30.0, -29.5, -30.5, -30.2):
        _medir(client, "s-dp-b1", v)
    e = client.get("/api/v1/beme/pressure/stability/bunker-1").json()
    assert e["dispersion_pa"] == pytest.approx(1.0)
    assert e["estable"] is True
    _medir(client, "s-dp-b1", -18.0)
    e2 = client.get("/api/v1/beme/pressure/stability/bunker-1").json()
    assert e2["estable"] is False


def test_configuracion_zona_versionada(client: TestClient) -> None:
    z = client.get("/api/v1/beme/zones/bunker-1").json()
    assert z["version"] == "hvac-cfg-1.0.0"
    r = client.post("/api/v1/beme/zones", json={
        "area_id": "bunker-1", "clasificacion": "zona_caliente",
        "objetivo": {"temp_min_c": 19.0, "temp_max_c": 24.0},
        "version": "hvac-cfg-1.1.0"})
    assert r.status_code == 201
    z2 = client.get("/api/v1/beme/zones/bunker-1").json()
    assert z2["versiones_disponibles"] == ["hvac-cfg-1.0.0",
                                           "hvac-cfg-1.1.0"]
    # misma versión: nunca sobrescribe
    r2 = client.post("/api/v1/beme/zones", json={
        "area_id": "bunker-1", "clasificacion": "zona_caliente",
        "objetivo": {}, "version": "hvac-cfg-1.1.0"})
    assert r2.status_code == 422


def test_auditoria_beme(client: TestClient) -> None:
    _medir(client, "s-temp-b1", 21.0)
    aud = client.get("/api/v1/beme/audit").json()
    acciones = {a["accion"] for a in aud}
    assert {"registrar_sensor", "configurar_zona", "medicion"} <= acciones
    assert all(a["fecha"] for a in aud)
