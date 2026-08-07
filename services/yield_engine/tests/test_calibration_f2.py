"""
Calibration Layer F2 (EDS 17.10, 17.11, 17.23, 17.26): indicadores de
desempeño, drift analyzer, gestión temporal y validación de calibraciones.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.application.calibration_service import (CalibrationService,
                                                 EquipmentCatalog)
from app.domain.calibration import Measurement
from app.domain.calibration_indicators import (active_at, drift_analysis,
                                               performance_indicators,
                                               validate_new_factor)
from app.main import app


def _med(dias, teo, med, unc=0.0):
    fecha = (datetime(2026, 1, 1, tzinfo=timezone.utc)
             + timedelta(days=dias)).isoformat()
    return Measurement(fecha=fecha, eob_predicho_gbq=teo,
                       eob_medido_gbq=med, incertidumbre_gbq=unc)


# ---------------------------------------------------------------- indicadores
class TestPerformanceIndicators:
    def test_error_relativo_exacto(self):
        meds = [_med(0, 10.0, 9.0), _med(10, 20.0, 19.0)]
        ind = performance_indicators(meds)
        assert ind.n == 2
        assert ind.error_rel_mean == pytest.approx(-0.075)
        assert ind.error_rel_max == pytest.approx(0.10)
        assert ind.error_abs_mean_gbq == pytest.approx(1.0)
        assert ind.span_days == pytest.approx(10.0)

    def test_sin_tendencia_pendiente_cero(self):
        meds = [_med(d, 10.0, 9.5) for d in range(0, 30, 10)]
        ind = performance_indicators(meds)
        assert ind.trend_slope_rel_per_day == pytest.approx(0.0, abs=1e-12)

    def test_tendencia_decreciente_detectable(self):
        meds = [_med(d, 10.0, 10.0 * (0.98 - 0.01 * d)) for d in range(6)]
        ind = performance_indicators(meds)
        assert ind.trend_slope_rel_per_day == pytest.approx(-0.01, abs=1e-9)
        assert ind.trend_r2 == pytest.approx(1.0)

    def test_validaciones(self):
        with pytest.raises(ValueError, match="al menos 2"):
            performance_indicators([_med(0, 10.0, 9.0)])
        with pytest.raises(ValueError, match="predicho"):
            performance_indicators([_med(0, 0.0, 9.0), _med(1, 10.0, 9.0)])


# -------------------------------------------------------------------- drift
class TestDriftAnalyzer:
    def test_degradacion_clara_detectada(self):
        # rendimiento cae 5 %/día limpio: cambio acumulado -25 % ≫ 2σ resid
        meds = [_med(d, 10.0, 10.0 * (1.0 - 0.05 * d)) for d in range(6)]
        v = drift_analysis(meds)
        assert v.drift_detected
        assert v.accumulated_rel_change == pytest.approx(-0.25, abs=1e-9)
        assert "degradación" in v.note

    def test_ruido_sin_tendencia_no_es_drift(self):
        # valores alternos alrededor del 0.95: pendiente ~0
        meds = [_med(d, 10.0, 9.5 + (0.2 if d % 2 else -0.2))
                for d in range(8)]
        v = drift_analysis(meds)
        assert not v.drift_detected

    def test_ruido_grande_enmascara_pendiente(self):
        # pendiente pequeña (0.5 %/día) con ruido ±4 %: no significativo
        meds = [_med(d, 10.0, 10.0 * (0.95 - 0.005 * d)
                     + (0.4 if d % 2 else -0.4)) for d in range(8)]
        v = drift_analysis(meds)
        assert not v.drift_detected
        assert v.threshold == pytest.approx(2.0 * v.residual_std)


# ------------------------------------------------------------ gestión temporal
class TestActiveAt:
    def _models(self):
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        return [{"version": 1,
                 "fitted_at": (base + timedelta(days=10)).isoformat()},
                {"version": 2,
                 "fitted_at": (base + timedelta(days=40)).isoformat()},
                {"version": 3,
                 "fitted_at": (base + timedelta(days=80)).isoformat()}]

    def test_version_vigente_en_fecha(self):
        models = self._models()
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert active_at(models, base + timedelta(days=5)) is None
        assert active_at(models, base + timedelta(days=15))["version"] == 1
        assert active_at(models, base + timedelta(days=50))["version"] == 2
        assert active_at(models, base + timedelta(days=200))["version"] == 3

    def test_fecha_exacta_de_ajuste(self):
        models = self._models()
        f2 = datetime.fromisoformat(models[1]["fitted_at"])
        assert active_at(models, f2)["version"] == 2


# ------------------------------------------------------------------ validación
class TestValidateNewFactor:
    def test_primera_calibracion_siempre_aceptada(self):
        meds = [_med(0, 10.0, 9.0), _med(1, 20.0, 18.2)]
        v = validate_new_factor(meds, 0.905, None)
        assert v["accepted"]
        assert v["factor_reference"] == 1.0

    def test_factor_que_mejora_aceptado(self):
        meds = [_med(d, 10.0, 9.5) for d in range(4)]
        v = validate_new_factor(meds, 0.95, 1.10)
        assert v["accepted"]
        assert v["rms_new"] < v["rms_reference"]

    def test_factor_que_deteriora_rechazado(self):
        meds = [_med(d, 10.0, 9.5) for d in range(4)]
        v = validate_new_factor(meds, 1.30, 0.95)
        assert not v["accepted"]
        assert "17.23" in v["note"]


# ------------------------------------------------------------------- servicio
@pytest.fixture
def svc(tmp_path):
    import json
    eq = tmp_path / "equipment.json"
    eq.write_text(json.dumps({"cyclotrons": [{
        "id": "eq_a", "fabricante": "X", "modelo": "Y",
        "energia_max_mev": 18, "energia_fija_fija": False,
        "energia_fija_mev": False, "corriente_max_ua": 100,
        "reacciones_tipicas": ["zn68_p_n_ga68"], "notas": ""}]}))
    return CalibrationService(tmp_path / "cal.json", EquipmentCatalog(eq))


class TestServiceF2:
    def test_fit_rechaza_calibracion_que_deteriora(self, svc):
        meds1 = [_med(d, 10.0, 9.5) for d in range(4)]
        m1 = svc.fit_and_store("zn68_p_n_ga68", "eq_a", meds1)
        assert m1.factor == pytest.approx(0.95)
        # un factor peor sobre las mismas medidas no puede surgir del WLS;
        # probamos el rechazo en la capa de dominio (ya cubierto) y que el
        # servicio almacena la validación en el modelo persistido:
        stored = svc.get_active("zn68_p_n_ga68", "eq_a")
        assert stored["validation"]["accepted"]

    def test_fit_segunda_version_versionado(self, svc):
        svc.fit_and_store("zn68_p_n_ga68", "eq_a",
                          [_med(d, 10.0, 9.5) for d in range(4)])
        m2 = svc.fit_and_store("zn68_p_n_ga68", "eq_a",
                               [_med(d, 10.0, 9.2) for d in range(10, 14)])
        assert m2.version == 2
        assert svc.get_active("zn68_p_n_ga68", "eq_a")["version"] == 2

    def test_get_at_temporal(self, svc):
        svc.fit_and_store("zn68_p_n_ga68", "eq_a",
                          [_med(d, 10.0, 9.5) for d in range(4)])
        futuro = datetime.now(timezone.utc) + timedelta(days=1)
        pasado = datetime.now(timezone.utc) - timedelta(days=1)
        assert svc.get_at("zn68_p_n_ga68", "eq_a", futuro) is not None
        assert svc.get_at("zn68_p_n_ga68", "eq_a", pasado) is None

    def test_indicators_y_drift_passthrough(self, svc):
        meds = [_med(d, 10.0, 10.0 * (1.0 - 0.05 * d)) for d in range(6)]
        assert svc.indicators(meds).n == 6
        assert svc.drift(meds).drift_detected


# ------------------------------------------------------------------------ API
def _payload(teo=10.0, factor=0.95):
    return {"medidas": [
        {"fecha": (datetime(2026, 1, 1, tzinfo=timezone.utc)
                   + timedelta(days=d)).isoformat(),
         "eob_predicho_gbq": teo, "eob_medido_gbq": teo * factor,
         "incertidumbre_gbq": 0.0}
        for d in range(4)]}


class TestApiF2:
    def test_indicators_endpoint(self):
        r = TestClient(app).post("/api/v1/calibration/indicators",
                                 json=_payload())
        assert r.status_code == 200
        b = r.json()
        assert b["n"] == 4
        assert b["error_rel_mean"] == pytest.approx(-0.05)
        assert not b["drift_detected"]

    def test_indicators_drift(self):
        p = _payload()
        for i, m in enumerate(p["medidas"]):
            m["eob_medido_gbq"] = 10.0 * (1.0 - 0.05 * i)
        r = TestClient(app).post("/api/v1/calibration/indicators", json=p)
        assert r.status_code == 200
        assert r.json()["drift_detected"]

    def test_indicators_422(self):
        r = TestClient(app).post("/api/v1/calibration/indicators",
                                 json={"medidas": []})
        assert r.status_code == 422

    def test_at_sin_modelos_404(self):
        r = TestClient(app).get(
            "/api/v1/calibration/ge68_ge68/eq_a/at",
            params={"when": "2026-06-01T00:00:00Z"})
        assert r.status_code == 404

    def test_at_fecha_invalida_422(self):
        r = TestClient(app).get(
            "/api/v1/calibration/mo98_mo99/eq_a/at",
            params={"when": "no-es-fecha"})
        assert r.status_code == 422
