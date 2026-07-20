"""
Tests del Logistics Twin: geodesia, cadena aérea, decaimiento en
tránsito, proveedor local de routing, catálogos y API.
"""
from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.application.logistics_service import LogisticsService
from app.domain.logistics import (Facility, GeoPoint, build_air_route,
                                  decayed, flight_time_min, haversine_km,
                                  max_delivery_minutes, nearest_airport,
                                  summarize_route)
from app.infrastructure.routing import LocalRoutingProvider

client = TestClient(app)
service = LogisticsService()

HL_F18 = 109.77
MAD = GeoPoint(40.4168, -3.7038)
BCN = GeoPoint(41.3874, 2.1686)
VAL = GeoPoint(39.4699, -0.3763)


# ---------------- geodesia y modelos ----------------

def test_haversine_madrid_barcelona():
    """Distancia conocida Madrid-Barcelona ≈ 505 km (±2%)."""
    d = haversine_km(MAD, BCN)
    assert 495 < d < 515


def test_haversine_cero():
    assert haversine_km(MAD, MAD) == 0.0


def test_flight_time_modelo():
    """Vuelo MAD-BCN: ~505 km / 800 km/h + 30 min overhead."""
    t = flight_time_min(haversine_km(MAD, BCN))
    assert math.isclose(t, 505 / 800 * 60 + 30, rel_tol=0.03)


def test_flight_time_invalida():
    with pytest.raises(ValueError):
        flight_time_min(0.0)


def test_decayed_exacto():
    assert math.isclose(decayed(100.0, HL_F18, HL_F18), 50.0, rel_tol=1e-12)


def test_max_delivery_minutes():
    """Presupuesto: llegar con la mitad exige exactamente una vida media."""
    t = max_delivery_minutes(100.0, 50.0, HL_F18)
    assert math.isclose(t, HL_F18, rel_tol=1e-12)


def test_max_delivery_sin_presupuesto():
    assert max_delivery_minutes(100.0, 100.0, HL_F18) == 0.0
    with pytest.raises(ValueError):
        max_delivery_minutes(100.0, 0.0, HL_F18)


# ---------------- cadena aérea ----------------

def _fac(fid, name, kind, point, iata=""):
    return Facility(fid, name, kind, point, iata)


def test_air_route_piernas_y_tiempos():
    origen = _fac("cyc", "Ciclotrón", "cyclotron", MAD)
    destino = _fac("h", "Hospital Costa", "hospital", VAL)
    o_apt = _fac("mad", "Madrid-Barajas (MAD)", "airport", GeoPoint(40.4936, -3.5668), "MAD")
    d_apt = _fac("vlc", "Valencia (VLC)", "airport", GeoPoint(39.4893, -0.4816), "VLC")
    legs = build_air_route(origen, destino, o_apt, d_apt,
                           ground_to_airport_min=25.0, ground_to_airport_km=18.0,
                           courier_min=30.0, tdg_buffer_min=90.0)
    assert [l.kind for l in legs] == ["road", "tdg_buffer", "flight", "courier"]
    total = sum(l.duration_min for l in legs)
    vuelo = legs[2]
    esperado_vuelo = flight_time_min(haversine_km(o_apt.point, d_apt.point))
    assert math.isclose(vuelo.duration_min, esperado_vuelo, rel_tol=1e-12)
    # total coherente con la referencia operativa 5-6 h puerta a puerta
    # (aquí solo tramos post-EOS; aun así el orden de magnitud cuadra)
    assert total == 25.0 + 90.0 + esperado_vuelo + 30.0


def test_air_route_parametros_invalidos():
    with pytest.raises(ValueError):
        build_air_route(_fac("a", "A", "cyclotron", MAD),
                        _fac("b", "B", "hospital", VAL),
                        _fac("m", "M", "airport", MAD),
                        _fac("v", "V", "airport", VAL),
                        10.0, 8.0, courier_min=-1.0)


def test_summarize_route_decaimiento_y_dosis():
    legs = build_air_route(_fac("c", "C", "cyclotron", MAD),
                           _fac("h", "H", "hospital", VAL),
                           _fac("m", "M", "airport", MAD),
                           _fac("v", "V", "airport", VAL),
                           25.0, 18.0)
    r = summarize_route("air", _fac("c", "C", "cyclotron", MAD),
                        _fac("h", "H", "hospital", VAL),
                        legs, 66.7, HL_F18, 0.37, "test", False)
    esperado = decayed(66.7, r.total_minutes, HL_F18)
    assert math.isclose(r.arrival_activity_gbq, esperado, rel_tol=1e-12)
    assert r.patient_doses_on_arrival == math.floor(esperado / 0.37 + 1e-9)


def test_nearest_airport_madrid():
    apts = [_fac("mad", "MAD", "airport", GeoPoint(40.4936, -3.5668), "MAD"),
            _fac("bcn", "BCN", "airport", GeoPoint(41.2974, 2.0833), "BCN")]
    best, km = nearest_airport(MAD, apts)
    assert best.iata == "MAD"
    assert km < 25
    with pytest.raises(ValueError):
        nearest_airport(MAD, [])


# ---------------- proveedor local ----------------

def test_local_provider_determinista():
    p = LocalRoutingProvider()
    t1, k1 = p.road_time(MAD, VAL)
    t2, k2 = p.road_time(MAD, VAL)
    assert (t1, k1) == (t2, k2)
    # Madrid-Valencia: ~303 km ortodromia × 1.3 / 50 km/h ≈ 472 min
    assert 400 < t1 < 550


def test_local_provider_radio_monotono():
    p = LocalRoutingProvider()
    assert p.reachable_radius_km(MAD, 60) > p.reachable_radius_km(MAD, 30)


def test_local_provider_invalido():
    with pytest.raises(ValueError):
        LocalRoutingProvider(speed_kmh=0)


# ---------------- catálogos y servicio ----------------

def test_catalogo_aeropuertos_real():
    """El catálogo OpenFlights cargado tiene cobertura mundial y España."""
    assert len(service._airports) > 1000
    iatas = {a.iata for a in service._airports}
    assert {"MAD", "BCN", "VLC", "LHR", "JFK"} <= iatas


def test_facilities_demo_honestas():
    for f in service.list_facilities():
        assert f.validated is False  # coordenadas de demostración


def test_route_road_dosis_a_llegada():
    r = service.route("cyclotron_main", "hosp_norte", "fdg_18f", 66.7, "road")
    assert r.mode == "road"
    assert len(r.legs) == 1
    assert r.arrival_activity_gbq < r.eos_activity_gbq
    assert r.patient_doses_on_arrival >= 1
    assert r.routing_source == "local-haversine"


def test_route_air_mismo_aeropuerto_error():
    """Hospital cercano (mismo aeropuerto MAD): el modo aéreo no aplica."""
    with pytest.raises(ValueError, match="comparten aeropuerto"):
        service.route("cyclotron_main", "hosp_norte", "fdg_18f", 66.7, "air")


def test_route_air_vs_road_a_la_costa():
    """A la costa, el aéreo compite con ~8 h de carretera: llega con más."""
    road = service.route("cyclotron_main", "hosp_lejano", "fdg_18f", 66.7, "road")
    air = service.route("cyclotron_main", "hosp_lejano", "fdg_18f", 66.7, "air")
    assert len(air.legs) == 4
    assert air.total_minutes < road.total_minutes
    assert air.arrival_activity_gbq > road.arrival_activity_gbq


def test_route_errores():
    with pytest.raises(KeyError):
        service.route("cyclotron_main", "no_existe", "fdg_18f", 66.7, "road")
    with pytest.raises(ValueError):
        service.route("cyclotron_main", "hosp_norte", "fdg_18f", 0.0, "road")
    with pytest.raises(ValueError):
        service.route("cyclotron_main", "hosp_norte", "fdg_18f", 66.7, "submarino")


def test_reachability_bandas_y_presupuesto():
    r = service.reachability("cyclotron_main", "fdg_18f", 66.7)
    # bandas ordenadas y actividad decreciente
    assert [b.minutes for b in r.bands] == sorted(b.minutes for b in r.bands)
    acts = [b.arrival_activity_gbq for b in r.bands]
    assert acts == sorted(acts, reverse=True)
    # presupuesto para 1 dosis (0.37 GBq desde 66.7)
    esperado = HL_F18 * math.log2(66.7 / 0.37)
    assert math.isclose(r.max_delivery_minutes_one_dose, esperado, rel_tol=1e-9)
    # hospitales demo alcanzables con 66.7 GBq
    assert any(f.feasible_one_dose for f in r.facilities)


# ---------------- API ----------------

def test_api_facilities():
    r = client.get("/api/v1/logistics/facilities")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 4
    assert all(f["validated"] is False for f in data)


def test_api_route_road():
    r = client.post("/api/v1/logistics/route", json={
        "origin_id": "cyclotron_main", "dest_id": "hosp_sur",
        "protocol_id": "fdg_18f", "eos_activity_gbq": 66.7, "mode": "road"})
    assert r.status_code == 200
    d = r.json()
    assert d["legs"][0]["kind"] == "road"
    assert d["arrival_activity_gbq"] < d["eos_activity_gbq"]


def test_api_route_air_a_costa():
    r = client.post("/api/v1/logistics/route", json={
        "origin_id": "cyclotron_main", "dest_id": "hosp_lejano",
        "protocol_id": "fdg_18f", "eos_activity_gbq": 66.7, "mode": "air"})
    assert r.status_code == 200
    d = r.json()
    assert [l["kind"] for l in d["legs"]] == ["road", "tdg_buffer", "flight", "courier"]
    assert d["legs"][2]["destination"].endswith("(VLC)")


def test_api_route_no_encontrado():
    r = client.post("/api/v1/logistics/route", json={
        "origin_id": "cyclotron_main", "dest_id": "nope",
        "protocol_id": "fdg_18f", "eos_activity_gbq": 66.7})
    assert r.status_code == 404


def test_api_route_eob_invalida():
    r = client.post("/api/v1/logistics/route", json={
        "origin_id": "cyclotron_main", "dest_id": "hosp_sur",
        "protocol_id": "fdg_18f", "eos_activity_gbq": -1.0})
    assert r.status_code == 422


def test_api_reachability():
    r = client.post("/api/v1/logistics/reachability", json={
        "origin_id": "cyclotron_main", "protocol_id": "fdg_18f",
        "eos_activity_gbq": 66.7})
    assert r.status_code == 200
    d = r.json()
    assert len(d["bands"]) == 5
    assert d["max_delivery_minutes_one_dose"] > 400
    nombres = [f["name"] for f in d["facilities"]]
    assert any("Norte" in n for n in nombres)


def test_api_reachability_11c_presupuesto_menor():
    """11C (T½≈20 min): el presupuesto de reparto es ~5× menor que 18F."""
    d11 = client.post("/api/v1/logistics/reachability", json={
        "origin_id": "cyclotron_main", "protocol_id": "met_11c",
        "eos_activity_gbq": 66.7}).json()
    d18 = client.post("/api/v1/logistics/reachability", json={
        "origin_id": "cyclotron_main", "protocol_id": "fdg_18f",
        "eos_activity_gbq": 66.7}).json()
    assert d11["max_delivery_minutes_one_dose"] < d18["max_delivery_minutes_one_dose"] / 4
