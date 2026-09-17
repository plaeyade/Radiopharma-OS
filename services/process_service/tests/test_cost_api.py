"""Pruebas API del Motor de Costos (Fase 29)."""
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from app.main import app


def test_api_costos_flujo_completo():
    c = TestClient(app)
    assert c.get("/api/v1/costos/ciclotrones").status_code == 200
    assert c.get("/api/v1/costos/tarifas").status_code == 200
    assert c.get("/api/v1/costos/proveedores-agua").status_code == 200

    import uuid
    rid = "API-RUN-" + uuid.uuid4().hex[:8]
    body = {
        "corrida_id": rid, "isotopo": "F-18",
        "ciclotron_id": "iba_cyclone_kiube", "tarifa_id": "GDMTO",
        "t_irradiacion_min": 60.0, "t_standby_min": 10.0, "potencia_haz_kw": 50.0,
        "proveedor_agua_id": "chempep_98", "agua_cargada_g": 1.5,
        "fraccion_recuperada": 0.8, "fuente_reciclaje": "Protocolo rev. A",
        "actividad_producida_gb": 50.0, "n_dosis": 10,
        "costo_desgaste_mxn": 250.0, "fuente_desgaste": "Costeo rev. A",
        "costo_consumibles_mxn": 200.0, "fuente_consumibles": "Cotización rev. A",
        "motivo": "Prueba API", "responsable": "RSO",
    }
    r = c.post("/api/v1/costos/corridas", json=body)
    assert r.status_code == 201, r.text
    assert r.json()["kwh_haz"] == pytest.approx(50.0, rel=1e-9)

    # duplicado → 422
    assert c.post("/api/v1/costos/corridas", json=body).status_code == 422

    e = c.post("/api/v1/costos/corridas/" + rid + "/escenarios",
               json={"modo": "unidosis_mxn_dosis", "margen_pct": 30.0,
                     "motivo": "Escenario comercial"})
    assert e.status_code == 201
    assert "RECOMENDACIÓN" in e.json()["naturaleza"]

    assert c.get("/api/v1/costos/corridas/" + rid).status_code == 200
    assert c.get("/api/v1/costos/corridas/NOPE").status_code == 404
