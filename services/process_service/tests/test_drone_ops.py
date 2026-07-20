"""
Tests de la pierna con dron del Logistics Twin: catálogo, factibilidad
(alcance/payload), modelo de vuelo, notas regulatorias y API.
"""
from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.application.logistics_service import LogisticsService
from app.domain.drone_ops import (CONTAINER_KG, DroneModel,
                                  build_drone_route, check_drone_feasibility,
                                  drone_notes, package_mass_kg)
from app.domain.logistics import Facility, GeoPoint, haversine_km

client = TestClient(app)
service = LogisticsService()

MAD = GeoPoint(40.4168, -3.7038)
VAL = GeoPoint(39.4699, -0.3763)
BCN = GeoPoint(41.3874, 2.1686)


def _fac(fid, kind, point):
    return Facility(fid, fid, kind, point)


def _drone(cruise=120.0, rng=300.0, payload=60.0):
    return DroneModel("test_drone", "Dron test", "vtol_ala_fija",
                      cruise, rng, payload, False, "nota", "fuente")


# ---------------- modelo ----------------

def test_package_mass():
    assert package_mass_kg(20.0) == 20.0 + CONTAINER_KG
    with pytest.raises(ValueError):
        package_mass_kg(-1.0)


def test_factibilidad_ok():
    check_drone_feasibility(_drone(), 100.0, 22.0)


def test_factibilidad_alcance():
    with pytest.raises(ValueError, match="fuera de alcance"):
        check_drone_feasibility(_drone(rng=100.0), 150.0, 22.0)


def test_factibilidad_payload():
    with pytest.raises(ValueError, match="payload excedido"):
        check_drone_feasibility(_drone(payload=5.0), 50.0, 22.0)


def test_drone_route_piernas_y_tiempos():
    drone = _drone(cruise=120.0, rng=400.0)
    legs = build_drone_route(_fac("c", "cyclotron", MAD),
                             _fac("h", "hospital", VAL), drone, 20.0)
    assert [l.kind for l in legs] == ["preflight", "drone_flight"]
    dist = haversine_km(MAD, VAL)
    assert math.isclose(legs[1].duration_min, dist / 120.0 * 60.0, rel_tol=1e-12)
    assert math.isclose(legs[1].distance_km, dist, rel_tol=1e-12)
    assert legs[0].duration_min == 20.0


def test_notas_regulatorias():
    notas = drone_notes(_drone(), 20.0)
    assert any("EASA" in n for n in notas)
    assert any("Tipo A" in n for n in notas)
    assert any("22 kg" in n for n in notas)


# ---------------- catálogo y servicio ----------------

def test_catalogo_drones_honesto():
    drones = service.list_drones()
    assert len(drones) == 3
    for d in drones:
        assert d.validated is False  # parámetros de referencia, no medidos
        assert d.source
    clases = {d.drone_id for d in drones}
    assert clases == {"eiger_vtol", "vtol_ala_fija_pesado", "uvh_170_heli"}


def test_route_drone_pesado_cercano():
    """El VTOL pesado (300 km) sirve el área metropolitana con blindaje FDG."""
    r = service.route("cyclotron_main", "hosp_sur", "fdg_18f", 66.7,
                      mode="drone", drone_id="vtol_ala_fija_pesado",
                      shielding_kg=20.0)
    assert r.mode == "drone"
    assert len(r.legs) == 2
    assert r.notes  # notas regulatorias presentes
    assert r.arrival_activity_gbq < r.eos_activity_gbq
    assert r.routing_source.startswith("drone-haversine:")


def test_route_drone_pesado_no_llega_a_valencia():
    """302.6 km > 300 km de alcance del VTOL pesado: rechazo honesto."""
    with pytest.raises(ValueError, match="fuera de alcance"):
        service.route("cyclotron_main", "hosp_lejano", "fdg_18f", 66.7,
                      mode="drone", drone_id="vtol_ala_fija_pesado")


def test_route_drone_mas_rapido_que_carretera():
    """El helicóptero UAV (350 km, 15 kg) sí llega a Valencia y gana."""
    road = service.route("cyclotron_main", "hosp_lejano", "fdg_18f", 66.7, "road")
    drone = service.route("cyclotron_main", "hosp_lejano", "fdg_18f", 66.7,
                          mode="drone", drone_id="uvh_170_heli", shielding_kg=10.0)
    assert drone.total_minutes < road.total_minutes
    assert drone.arrival_activity_gbq > road.arrival_activity_gbq


def test_route_drone_ligero_rechaza_blindaje():
    """El VTOL ligero (3 kg) no puede con el blindaje FDG (20+2 kg)."""
    with pytest.raises(ValueError, match="payload excedido"):
        service.route("cyclotron_main", "hosp_norte", "fdg_18f", 66.7,
                      mode="drone", drone_id="eiger_vtol", shielding_kg=20.0)


def test_route_drone_fuera_de_alcance():
    """El ligero (100 km) no llega a Valencia (~303 km) ni vacío."""
    with pytest.raises(ValueError, match="fuera de alcance"):
        service.route("cyclotron_main", "hosp_lejano", "fdg_18f", 66.7,
                      mode="drone", drone_id="eiger_vtol", shielding_kg=0.5)


def test_route_drone_requiere_id():
    with pytest.raises(ValueError, match="drone_id"):
        service.route("cyclotron_main", "hosp_norte", "fdg_18f", 66.7,
                      mode="drone")


# ---------------- API ----------------

def test_api_drones():
    r = client.get("/api/v1/logistics/drones")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    assert all(d["validated"] is False for d in data)


def test_api_route_drone():
    r = client.post("/api/v1/logistics/route", json={
        "origin_id": "cyclotron_main", "dest_id": "hosp_lejano",
        "protocol_id": "fdg_18f", "eos_activity_gbq": 66.7,
        "mode": "drone", "drone_id": "uvh_170_heli", "shielding_kg": 10.0})
    assert r.status_code == 200
    d = r.json()
    assert [l["kind"] for l in d["legs"]] == ["preflight", "drone_flight"]
    assert len(d["notes"]) >= 3


def test_api_route_drone_payload_422():
    r = client.post("/api/v1/logistics/route", json={
        "origin_id": "cyclotron_main", "dest_id": "hosp_norte",
        "protocol_id": "fdg_18f", "eos_activity_gbq": 66.7,
        "mode": "drone", "drone_id": "eiger_vtol", "shielding_kg": 20.0})
    assert r.status_code == 422
    assert "payload" in r.json()["detail"]


def test_api_route_drone_desconocido_404():
    r = client.post("/api/v1/logistics/route", json={
        "origin_id": "cyclotron_main", "dest_id": "hosp_norte",
        "protocol_id": "fdg_18f", "eos_activity_gbq": 66.7,
        "mode": "drone", "drone_id": "no_existe"})
    assert r.status_code == 404
