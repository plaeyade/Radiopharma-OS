"""Tests del Facility Twin (EDS cap. 33) y Asset Lifecycle (cap. 34).

Verifica: registry único 33.6, áreas/zonas 33.8/33.12, utilidades 33.10,
mediciones ambientales con fuente real obligatoria 33.11, ciclo de vida
34.7, planes versionados 34.9, historial de calibraciones nunca
eliminado 34.10, certificaciones 34.11, indicadores de confiabilidad
exactos 34.12, repuestos con stock mínimo 34.13 y auditoría.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.presentation.routers import facility_api


@pytest.fixture()
def client() -> TestClient:
    facility_api.init()
    c = TestClient(app)
    r = c.post("/api/v1/facility/areas", json={
        "area_id": "bunker-1", "funcion": "irradiacion",
        "clasificacion": "zona_caliente", "superficie_m2": 25.0,
        "nivel": "sotano-1", "procesos": ["irradiacion-f18"],
        "zona_restringida": True})
    assert r.status_code == 201
    r = c.post("/api/v1/facility/assets", json={
        "activo_id": "cyclo-1", "tipo": "equipo", "nombre": "Ciclotrón 18 MeV",
        "area_id": "bunker-1"})
    assert r.status_code == 201
    return c


def test_registry_nunca_sobrescribe(client: TestClient) -> None:
    r = client.post("/api/v1/facility/assets", json={
        "activo_id": "cyclo-1", "tipo": "equipo", "nombre": "otro"})
    assert r.status_code == 422
    r = client.post("/api/v1/facility/areas", json={
        "area_id": "bunker-1", "funcion": "x",
        "clasificacion": "zona_tecnica", "superficie_m2": 10.0})
    assert r.status_code == 422


def test_activo_exige_area_existente(client: TestClient) -> None:
    r = client.post("/api/v1/facility/assets", json={
        "activo_id": "hplc-1", "tipo": "equipo", "nombre": "HPLC",
        "area_id": "fantasma"})
    assert r.status_code == 422


def test_area_clasificacion_canonica(client: TestClient) -> None:
    r = client.post("/api/v1/facility/areas", json={
        "area_id": "lab-qc", "funcion": "control_calidad",
        "clasificacion": "clasificacion_inventada", "superficie_m2": 12.0})
    assert r.status_code == 422
    areas = client.get("/api/v1/facility/areas").json()
    assert areas[0]["clasificacion"] == "zona_caliente"
    assert areas[0]["procesos"] == ["irradiacion-f18"]


def test_utilidades_estado_propio(client: TestClient) -> None:
    r = client.post("/api/v1/facility/utilities", json={
        "utilidad_id": "ups-1", "tipo": "energia_electrica"})
    assert r.status_code == 201
    r = client.post("/api/v1/facility/utilities", json={
        "utilidad_id": "ut-x", "tipo": "gas_natural"})
    assert r.status_code == 422
    r = client.post("/api/v1/facility/utilities/ups-1/state",
                    json={"estado": "degradada", "usuario": "mant-1"})
    assert r.status_code == 200
    uts = client.get("/api/v1/facility/utilities").json()
    assert uts[0]["estado"] == "degradada"


def test_medicion_ambiental_exige_fuente_real(client: TestClient) -> None:
    r = client.post("/api/v1/facility/environment", json={
        "area_id": "bunker-1", "variable": "presion_diferencial",
        "valor": -15.0, "unidad": "Pa", "fuente": "tel:hvac.dP.bunker1"})
    assert r.status_code == 201
    r = client.post("/api/v1/facility/environment", json={
        "area_id": "bunker-1", "variable": "temperatura",
        "valor": 21.0, "unidad": "C", "fuente": ""})
    assert r.status_code == 422
    assert "nunca simula" in r.json()["detail"]
    meds = client.get("/api/v1/facility/environment",
                      params={"area_id": "bunker-1"}).json()
    assert len(meds) == 1 and meds[0]["fuente"] == "tel:hvac.dP.bunker1"


def test_ciclo_de_vida_registrado(client: TestClient) -> None:
    for estado in ("instalacion", "puesta_en_servicio", "operacion"):
        r = client.post("/api/v1/facility/assets/cyclo-1/lifecycle",
                        json={"estado": estado, "usuario": "ing-1"})
        assert r.status_code == 201
    r = client.post("/api/v1/facility/assets/cyclo-1/lifecycle",
                    json={"estado": "destruido"})
    assert r.status_code == 422
    h = client.get("/api/v1/facility/assets/cyclo-1/lifecycle").json()
    assert [t["a"] for t in h] == ["instalacion", "puesta_en_servicio",
                                   "operacion"]


def test_planes_versionados_nunca_sobrescriben(client: TestClient) -> None:
    plan = {"plan_id": "pm-cyclo-2026", "activo_id": "cyclo-1",
            "periodicidad": "trimestral", "responsable": "mantenimiento",
            "procedimiento": "PM-CYC-001", "criterios_aceptacion": "OEM",
            "version": "1.0.0"}
    assert client.post("/api/v1/facility/maintenance/plans",
                       json=plan).status_code == 201
    assert client.post("/api/v1/facility/maintenance/plans",
                       json=plan).status_code == 422
    sin_criterios = {k: v for k, v in plan.items()
                     if k != "criterios_aceptacion"}
    sin_criterios["plan_id"] = "pm-x"
    assert client.post("/api/v1/facility/maintenance/plans",
                       json=sin_criterios).status_code == 422


def _falla(client: TestClient, iid: str, ini: str, fin: str) -> None:
    assert client.post("/api/v1/facility/maintenance", json={
        "intervencion_id": iid, "activo_id": "cyclo-1", "tipo": "correctivo",
        "descripcion": "fallo fuente de iones", "inicio": ini,
        "es_falla": True}).status_code == 201
    assert client.post(f"/api/v1/facility/maintenance/{iid}/close",
                       json={"fin": fin}).status_code == 200


def test_confiabilidad_calculada_sobre_registros(client: TestClient) -> None:
    _falla(client, "corr-1", "2026-01-10T08:00:00+00:00",
           "2026-01-10T14:00:00+00:00")      # 6 h
    _falla(client, "corr-2", "2026-03-15T09:00:00+00:00",
           "2026-03-15T13:00:00+00:00")      # 4 h
    # intervención en curso: no computa
    client.post("/api/v1/facility/maintenance", json={
        "intervencion_id": "prev-1", "activo_id": "cyclo-1",
        "tipo": "preventivo", "descripcion": "PM Q2",
        "inicio": "2026-08-01T08:00:00+00:00"})
    r = client.get("/api/v1/facility/assets/cyclo-1/reliability",
                   params={"horas_periodo": 1000.0})
    assert r.status_code == 200
    c = r.json()
    assert c["tiempo_fuera_de_servicio_h"] == pytest.approx(10.0)
    assert c["disponibilidad"] == pytest.approx(0.99)
    assert c["n_fallas"] == 2
    assert c["mtbf_h"] == pytest.approx(495.0)


def test_historial_calibraciones_nunca_eliminado(client: TestClient) -> None:
    for cid, res in (("cal-1", "conforme"), ("cal-2", "no_conforme")):
        assert client.post("/api/v1/facility/calibrations", json={
            "calibracion_id": cid, "activo_id": "cyclo-1",
            "fecha": "2026-01-15", "laboratorio": "lab-metrologia",
            "procedimiento": "CAL-001", "resultado": res,
            "vigencia_hasta": "2026-12-31"}).status_code == 201
    cals = client.get("/api/v1/facility/assets/cyclo-1/calibrations").json()
    assert len(cals) == 2          # ambas permanecen, incluso no_conforme
    v = client.get("/api/v1/facility/assets/cyclo-1/calibration-current",
                   params={"fecha": "2026-08-10"}).json()
    assert v["vigente"] is True and v["calibracion_id"] == "cal-1"
    v2 = client.get("/api/v1/facility/assets/cyclo-1/calibration-current",
                    params={"fecha": "2027-01-15"}).json()
    assert v2["vigente"] is False


def test_certificaciones_asociadas(client: TestClient) -> None:
    assert client.post("/api/v1/facility/certifications", json={
        "documento_id": "cert-iq-1", "activo_id": "cyclo-1",
        "tipo": "calificacion", "referencia": "IQ-CYC-2026",
        "fecha": "2026-02-01"}).status_code == 201
    docs = client.get("/api/v1/facility/assets/cyclo-1/certifications").json()
    assert docs[0]["tipo"] == "calificacion"


def test_repuestos_stock_minimo(client: TestClient) -> None:
    assert client.post("/api/v1/facility/spares", json={
        "repuesto_id": "foil-havar", "descripcion": "Lámina Havar 25 µm",
        "stock": 3, "stock_minimo": 2,
        "compatibles": ["cyclo-1"]}).status_code == 201
    r = client.post("/api/v1/facility/spares/foil-havar/consume",
                    json={"cantidad": 2})
    assert r.json()["stock"] == 1 and r.json()["bajo_minimo"] is True
    assert client.post("/api/v1/facility/spares/foil-havar/consume",
                       json={"cantidad": 5}).status_code == 422


def test_auditoria_facility(client: TestClient) -> None:
    aud = client.get("/api/v1/facility/audit").json()
    acciones = {a["accion"] for a in aud}
    assert "registrar_area" in acciones and "registrar_activo" in acciones
    assert all(a["fecha"] for a in aud)
