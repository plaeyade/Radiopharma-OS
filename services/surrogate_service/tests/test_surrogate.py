"""
Tests del Surrogate Modeling Server (EDS Vol. II, cap. 20).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.application.surrogate_service import (SurrogateNoEncontrado,
                                               SurrogateService)
from app.main import app


@pytest.fixture()
def svc() -> SurrogateService:
    return SurrogateService()


@pytest.fixture()
def svc_entrenado(svc) -> SurrogateService:
    svc.train_yield_surrogate("1.0.0", "tester")
    return svc


class TestDataset:
    def test_dataset_real_versionado(self, svc):
        ds = svc.load_dataset()
        assert ds.n_points == 41
        assert "Yield Engine" in ds.source  # datos modelados de alta fidelidad
        assert ds.content_hash == svc.load_dataset().content_hash  # 20.23

    def test_listado(self, svc):
        svc.load_dataset()
        d = svc.list_datasets()[0]
        assert d["n_points"] == 41 and "log10" in d["transform"]  # 20.7


class TestEntrenamiento:
    def test_aprobacion_y_registro(self, svc):
        r = svc.train_yield_surrogate("1.0.0", "fisico-1")
        assert r["validation"]["approved"] is True
        assert r["validation"]["rel_rmse"] < 0.05  # puerta 20.21
        assert r["registrado"] is True
        assert r["algorithm"] == "ridge-polinomico-loglog"

    def test_ningun_modelo_se_sobrescribe(self, svc_entrenado):
        with pytest.raises(ValueError):
            svc_entrenado.train_yield_surrogate("1.0.0", "otro")  # 20.9

    def test_puerta_bloquea_umbral_imposible(self, svc):
        r = svc.train_yield_surrogate("9.9.9", "t", umbral_rel_rmse=1e-9,
                                      umbral_max_rel_err=1e-9)
        assert r["registrado"] is False  # 20.21: no se publica
        assert r["validation"]["approved"] is False


class TestInferencia:
    def test_precision_vs_modelo_fisico(self, svc_entrenado):
        # el surrogate reproduce el modelo determinista con error <5%
        import json
        from pathlib import Path
        raw = json.loads((Path(__file__).parents[1] / "app" / "data" /
                          "yield_saturation_dataset.json").read_text())
        for e, y in zip(raw["energies_mev"][::7], raw["yield_sat_mbq_ua"][::7]):
            r = svc_entrenado.infer("yield_sat_f18", None, e, "tester")
            assert r["prediccion_yield_sat_mbq_ua"] == pytest.approx(y, rel=0.05)

    def test_respuesta_identificada_como_ia(self, svc_entrenado):
        r = svc_entrenado.infer("yield_sat_f18", None, 12.0, "tester")  # 20.15
        assert "modelo IA" in r["tipo"]
        assert r["confianza_rel_holdout"] > 0  # 20.22
        assert r["metadatos"]["dataset_id"] == "yield_sat_f18_h2o18"

    def test_auditoria_por_inferencia(self, svc_entrenado):
        r = svc_entrenado.infer("yield_sat_f18", None, 12.0, "op-7")  # 20.24
        a = r["auditoria"]
        assert a["usuario"] == "op-7" and a["version"] == "1.0.0"
        assert len(svc_entrenado.audit_log()) == 1

    def test_no_extrapola(self, svc_entrenado):
        with pytest.raises(ValueError):
            svc_entrenado.infer("yield_sat_f18", None, 25.0, "t")

    def test_modelo_inexistente(self, svc_entrenado):
        with pytest.raises(SurrogateNoEncontrado):
            svc_entrenado.infer("no_existe", None, 12.0, "t")


class TestDrift:
    def test_observacion_y_estado_estable(self, svc_entrenado):
        svc_entrenado.drift_observe("yield_sat_f18", None, 8900.0, 8800.0,
                                    "medición activímetro validada L-1")
        st = svc_entrenado.drift_status("yield_sat_f18")
        assert st["n"] == 1
        assert st["reentrenamiento_recomendado"] is False  # 20.20

    def test_deriva_detecta_reentrenamiento(self, svc_entrenado):
        for i in range(4):
            svc_entrenado.drift_observe("yield_sat_f18", None, 9000.0,
                                        7000.0 + i, f"fuente-{i}")
        st = svc_entrenado.drift_status("yield_sat_f18")
        assert st["estabilidad_temporal"] == "deriva"
        assert st["reentrenamiento_recomendado"] is True  # 20.20

    def test_medicion_invalida(self, svc_entrenado):
        with pytest.raises(ValueError):
            svc_entrenado.drift_observe("yield_sat_f18", None, 1.0, 0.0, "x")


class TestApi:
    def test_train_infer_flow(self):
        c = TestClient(app)
        r = c.post("/api/v1/surrogates/train",
                   json={"version": "api-1", "responsable": "tester"})
        assert r.status_code == 200
        assert r.json()["registrado"] is True
        r = c.post("/api/v1/surrogates/infer",
                   json={"beam_energy_mev": 16.5, "usuario": "tester"})
        assert r.status_code == 200
        body = r.json()
        assert body["prediccion_yield_sat_mbq_ua"] > 8000
        assert body["auditoria"]["usuario"] == "tester"

    def test_drift_flow_api(self):
        c = TestClient(app)
        c.post("/api/v1/surrogates/train",
               json={"version": "api-drift", "responsable": "tester"})
        r = c.post("/api/v1/surrogates/drift/observe",
                   json={"prediccion": 8900, "medicion": 8800,
                         "fuente": "activímetro L-2"})
        assert r.status_code == 200
        r = c.get("/api/v1/surrogates/drift/status")
        assert r.status_code == 200
        assert r.json()["n"] >= 1

    def test_infer_sin_modelo_404(self):
        c = TestClient(app)
        r = c.post("/api/v1/surrogates/infer",
                   json={"model_id": "no_existe", "beam_energy_mev": 10.0,
                         "usuario": "t"})
        assert r.status_code == 404

    def test_health_reporta_bentoml_honesto(self):
        c = TestClient(app)
        body = c.get("/health").json()
        assert "bentoml_disponible" in body  # 20.10 honesto
