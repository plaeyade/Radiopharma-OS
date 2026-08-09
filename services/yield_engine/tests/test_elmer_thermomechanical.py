"""
Elmer FEM Interface — cap. 18: análisis termo-mecánico acoplado (18.13),
Material Library (18.8/18.14), solver mecánico (18.12) y validación
numérica (18.22). Tests con runner sustituido (sin binario) + SIF.
"""
from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from app.application.production_service import ProductionService
from app.domain.elmer_materials import (get_material, list_materials)
from app.infrastructure.elmer.elmer_case import (
    ElmerThermalCase, build_case_thermomechanical)
from app.infrastructure.elmer.elmer_runner import ElmerUnavailable
from app.main import app
from app.presentation.routers import yield_api


def _case() -> ElmerThermalCase:
    return ElmerThermalCase(beam_power_w=610.5,
                            spot_radius_cm=math.sqrt(1.0 / math.pi),
                            target_thickness_cm=0.5,
                            conductivity_w_cm_k=0.006,
                            film_coeff_w_cm2_k=0.5,
                            coolant_temp_k=293.15)


# ------------------------------------------------------- Material Library 18.8
class TestMaterialLibrary:
    def test_materiales_disponibles_completos(self):
        mats = list_materials()
        assert len(mats) >= 2
        assert all(m.completo_termomecanico() for m in mats)

    def test_material_desconocido_rechazado_18_14(self):
        with pytest.raises(ValueError, match="18.8"):
            get_material("unobtanium")

    def test_trazabilidad_version_y_referencia(self):
        m = get_material("havar_foil")
        assert m.version and m.referencia
        assert m.young_pa == pytest.approx(2.0e11)


# ------------------------------------------------------------- generador SIF
class TestSifThermomechanical:
    def test_sif_tiene_solver_stress_y_scalars(self, tmp_path):
        sif = build_case_thermomechanical(
            tmp_path, _case(), get_material("havar_foil"))
        txt = sif.read_text()
        assert 'Procedure = "StressSolve" "StressSolver"' in txt
        assert 'Procedure = "HeatSolve" "HeatSolver"' in txt
        assert "Calculate Stresses = True" in txt
        assert 'Variable = -dofs 2 "Displacement"' in txt
        assert 'Variable 3 = "vonMises"' in txt
        assert 'Variable 4 = "Displacement"' in txt
        assert "Active Solvers(3) = 1 2 3" in txt

    def test_sif_propiedades_mecanicas_material(self, tmp_path):
        m = get_material("acero_316l")
        sif = build_case_thermomechanical(tmp_path, _case(), m)
        txt = sif.read_text()
        assert f"Youngs Modulus = Real {m.young_pa:.10e}" in txt
        assert f"Poisson Ratio = Real {m.poisson:.6f}" in txt
        assert "Heat Expansion Coefficient" in txt
        assert "Reference Temperature = Real 2.931500e+02" in txt

    def test_sif_empotramiento_cara_refrigerada(self, tmp_path):
        sif = build_case_thermomechanical(
            tmp_path, _case(), get_material("havar_foil"))
        txt = sif.read_text()
        assert "Displacement 1 = Real 0.0" in txt
        assert "Displacement 2 = Real 0.0" in txt

    def test_fuente_volumetrica_presente(self, tmp_path):
        sif = build_case_thermomechanical(
            tmp_path, _case(), get_material("havar_foil"))
        assert "Volumetric Heat Source = Real" in sif.read_text()


# ---------------------------------------------------------------- servicio
class _RunnerFalso:
    """Runner sustituido: 4 escalares plausibles (T_max, T_mean, vM, disp)."""

    cmd_label = "ElmerSolver-falso"

    def available(self):
        return True

    def run(self, case_dir):
        return [962.7, 850.1, 4.2e8, 3.1e-5]


class _RunnerNoDisponible(_RunnerFalso):
    def available(self):
        return False


def _svc(runner) -> ProductionService:
    from app.infrastructure.repositories.local_reaction_data import \
        LocalReactionDataProvider
    from app.infrastructure.stopping.factory import build_stopping_provider
    from app.main import DATA_DIR
    return ProductionService(
        stopping=build_stopping_provider(DATA_DIR / "stopping"),
        rxn=LocalReactionDataProvider(DATA_DIR), elmer=runner)


class TestThermomechanicalService:
    def test_resultado_completo_cap18(self):
        r = _svc(_RunnerFalso()).elmer_thermomechanical(
            reaction_id="o18_p_n_f18", target_id="h2_18o",
            irradiation_time_min=60.0, beam_energy_mev=16.5,
            current_ua=37.0, material_id="havar_foil")
        # linaje 8.11
        assert r["pipeline"] == "yield→burnup→elmer(thermomechanical)"
        assert r["yield_eob_gbq"] > 0 and r["burnup_eob_gbq"] > 0
        # 18.12: temperatura, esfuerzo, desplazamiento
        assert r["t_peak_fem_k"] == pytest.approx(962.7)
        assert r["von_mises_max_mpa"] == pytest.approx(420.0)
        assert r["displacement_max_mm"] == pytest.approx(0.031)
        assert r["material"]["material_id"] == "havar_foil"

    def test_sin_binario_503_honesto(self):
        with pytest.raises(ElmerUnavailable):
            _svc(_RunnerNoDisponible()).elmer_thermomechanical(
                reaction_id="o18_p_n_f18", target_id="h2_18o",
                irradiation_time_min=60.0, beam_energy_mev=16.5,
                current_ua=37.0, material_id="havar_foil")

    def test_material_desconocido_rechazado(self):
        with pytest.raises(ValueError, match="18.8"):
            _svc(_RunnerFalso()).elmer_thermomechanical(
                reaction_id="o18_p_n_f18", target_id="h2_18o",
                irradiation_time_min=60.0, beam_energy_mev=16.5,
                current_ua=37.0, material_id="unobtanium")


# -------------------------------------------------------------------- API
class TestApiThermomechanical:
    def _payload(self, material="havar_foil"):
        return {"reaction_id": "o18_p_n_f18", "target_id": "h2_18o",
                "beam_energy_mev": 16.5, "current_ua": 37.0,
                "irradiation_time_min": 60.0, "material_id": material}

    def test_503_sin_binario(self, monkeypatch):
        monkeypatch.setattr(yield_api, "_service",
                            _svc(_RunnerNoDisponible()))
        r = TestClient(app).post("/api/v1/elmer/thermomechanical",
                                 json=self._payload())
        assert r.status_code == 503

    def test_422_material_desconocido(self, monkeypatch):
        monkeypatch.setattr(yield_api, "_service", _svc(_RunnerFalso()))
        r = TestClient(app).post("/api/v1/elmer/thermomechanical",
                                 json=self._payload(material="unobtanium"))
        assert r.status_code == 422
        assert "18.8" in r.json()["detail"]

    def test_200_con_runner_sustituido(self, monkeypatch):
        monkeypatch.setattr(yield_api, "_service", _svc(_RunnerFalso()))
        r = TestClient(app).post("/api/v1/elmer/thermomechanical",
                                 json=self._payload())
        assert r.status_code == 200
        b = r.json()
        assert b["von_mises_max_mpa"] == pytest.approx(420.0)
        assert b["pipeline"] == "yield→burnup→elmer(thermomechanical)"
        assert b["review_required"] is False or isinstance(
            b["review_required"], bool)
