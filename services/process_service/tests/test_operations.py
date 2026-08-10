"""Pruebas del Operational Twin Fase 5: inventarios, economía ABC, KPIs."""
from __future__ import annotations

import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import app  # noqa: E402

client = TestClient(app)

LOTE = {"lote_id": "FDG-OPS-001", "radiopharmaceutical": "FDG",
        "nuclide": "F-18", "half_life_min": 109.77,
        "actividad_gbq": 37.0,
        "referencia_temporal": datetime.now(timezone.utc).isoformat(),
        "volumen_ml": 10.0, "operador": "qa", "motivo": "test"}


def test_registrar_lote_y_stock_con_decaimiento():
    r = client.post("/api/v1/inventory/lotes", json=LOTE)
    assert r.status_code == 201
    futuro = (datetime.fromisoformat(LOTE["referencia_temporal"])
              + timedelta(minutes=109.77)).isoformat()
    s = client.get(f"/api/v1/inventory/lotes/{LOTE['lote_id']}/stock",
                   params={"instante": futuro})
    assert s.status_code == 200
    assert s.json()["actividad_gbq"] == pytest.approx(18.5, rel=1e-6)
    assert "decaimiento" in s.json()["nota"]


def test_lote_duplicado_nunca_sobrescribe():
    client.post("/api/v1/inventory/lotes",
                json={**LOTE, "lote_id": "FDG-OPS-DUP"})
    r = client.post("/api/v1/inventory/lotes",
                    json={**LOTE, "lote_id": "FDG-OPS-DUP"})
    assert r.status_code == 422


def test_cambio_estado_auditado():
    client.post("/api/v1/inventory/lotes",
                json={**LOTE, "lote_id": "FDG-OPS-EST"})
    r = client.post("/api/v1/inventory/lotes/FDG-OPS-EST/estado",
                    json={"estado": "consumido", "operador": "qa",
                          "motivo": "despacho"})
    assert r.status_code == 200
    movs = client.get("/api/v1/inventory/movimientos").json()
    assert any(m["tipo"] == "salida" and m["item_id"] == "FDG-OPS-EST"
               for m in movs)


def test_consumible_consumo_y_caducidad_22_7():
    r = client.post("/api/v1/inventory/consumibles", json={
        "item_id": "K222-01", "nombre": "Kryptofix 222", "cantidad": 100.0,
        "unidad": "mg", "lote": "L1", "caducidad": "2020-01-01",
        "operador": "qa", "motivo": "test"})
    assert r.status_code == 201
    r2 = client.post("/api/v1/inventory/consumir", json={
        "item_id": "K222-01", "cantidad": 10.0, "operador": "qa",
        "motivo": "test", "fecha_lote": "2026-08-10"})
    assert r2.status_code == 422
    assert "caducado" in r2.json()["detail"]
    r3 = client.post("/api/v1/inventory/consumir", json={
        "item_id": "K222-01", "cantidad": 10.0, "operador": "qa",
        "motivo": "test", "fecha_lote": "2019-06-01"})
    assert r3.status_code == 200
    assert r3.json()["cantidad"] == 90.0


def _costeo(lote: str) -> dict:
    return client.post("/api/v1/economics/costeo", json={
        "lote_id": lote, "radiopharmaceutical": "FDG",
        "consumos": [
            {"actividad": "irradiacion", "unidades_driver": 2.0},
            {"actividad": "sintesis", "unidades_driver": 45.0},
            {"actividad": "purificacion", "unidades_driver": 20.0},
            {"actividad": "formulacion", "unidades_driver": 15.0},
            {"actividad": "qc", "unidades_driver": 8.0},
            {"actividad": "logistica", "unidades_driver": 1.0}],
        "dosis": 10, "actividad_eob_gbq": 37.0, "operador": "qa",
        "motivo": "test"})


def test_costeo_abc_desglose_y_dosis():
    r = _costeo("FDG-COST-1")
    assert r.status_code == 201
    c = r.json()
    # 2*350 + 45*2.5 + 20*1.8 + 15*1.5 + 8*45 + 120 = 1351.0
    assert c["coste_total"] == pytest.approx(1351.0, abs=0.01)
    assert c["coste_por_dosis"] == pytest.approx(135.10, abs=0.01)
    assert c["coste_por_gbq"] == pytest.approx(1351.0 / 37.0, abs=0.05)
    assert c["desglose"]["irradiacion"] == 700.0
    assert "39.9" in c["auditoria"]["nota"]


def test_costeo_actividad_desconocida_rechazada():
    r = client.post("/api/v1/economics/costeo", json={
        "lote_id": "X", "radiopharmaceutical": "FDG",
        "consumos": [{"actividad": "magia", "unidades_driver": 1.0}],
        "dosis": 1, "actividad_eob_gbq": 1.0, "operador": "qa",
        "motivo": "test"})
    assert r.status_code == 422


def test_agregacion_radiofarmaco_y_kpis():
    _costeo("FDG-COST-AGG")
    agg = client.get("/api/v1/economics/radiofarmaco/FDG")
    assert agg.status_code == 200
    assert agg.json()["lotes"] >= 2
    k = client.get("/api/v1/economics/kpis?precio_dosis=300.0").json()
    assert k["margen"] > 0
    assert 0 < k["margen_pct"] < 100


def test_kpis_operativos_con_qc():
    client.post("/api/v1/operations/qc-result",
                json={"lote_id": "FDG-OPS-001", "recomendacion": "liberacion"})
    client.post("/api/v1/operations/qc-result",
                json={"lote_id": "FDG-OPS-EST", "recomendacion": "rechazo"})
    k = client.get("/api/v1/operations/kpis").json()
    assert k["tasa_liberacion_qc"] == pytest.approx(0.5, abs=0.01)
    assert k["lotes_registrados"] >= 3
    assert "38.12" in k["nota"]


def test_catalogo_versionado_y_honesto():
    c = client.get("/api/v1/economics/catalogo").json()
    assert c["version"] == "1.0.0"
    assert c["validado"] is False  # honestidad: tarifas de referencia
