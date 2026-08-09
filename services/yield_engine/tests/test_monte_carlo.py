"""
Monte Carlo Interface — cap. 19: validación previa (19.21), gestión de
incertidumbre estadística por lotes (19.20), comparación con el modelo
determinista (19.14) y auditoría completa (19.24). Tests con runner
sustituido (sin motor real) + generación del caso OpenGATE.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.application.production_service import ProductionService
from app.domain import monte_carlo as mc
from app.infrastructure.gate.gate_case import (PHYSICS_LISTS_VALIDAS,
                                               MonteCarloTargetCase,
                                               build_case)
from app.infrastructure.gate.gate_runner import (GateUnavailable,
                                                 build_gate_env,
                                                 datasets_instalados)
from app.main import app
from app.presentation.routers import yield_api


def _case(**kw) -> MonteCarloTargetCase:
    base = dict(beam_energy_mev=16.5, n_histories=10_000, n_batches=5)
    base.update(kw)
    return MonteCarloTargetCase(**base)


# ------------------------------------------------- validación previa (19.21)
class TestValidacionCaso:
    def test_caso_canonico_ok(self):
        assert mc.validar_caso(_case()) == []

    def test_particula_no_admitida(self):
        assert any("19.10" in r for r in mc.validar_caso(_case(particle="alpha")))

    def test_energia_fuera_de_rango(self):
        assert mc.validar_caso(_case(beam_energy_mev=0.5))

    def test_haz_mayor_que_blanco_rechazado(self):
        r = mc.validar_caso(_case(beam_radius_cm=2.0, target_radius_cm=1.0))
        assert any("19.8" in x for x in r)

    def test_geometria_invalida(self):
        assert mc.validar_caso(_case(target_thickness_cm=0.0))

    def test_physics_list_no_registrada(self):
        r = mc.validar_caso(_case(physics_list="INVENTED_PL"))
        assert any("19.9" in x for x in r)

    def test_physics_lists_registradas(self):
        assert "FTFP_BERT" in PHYSICS_LISTS_VALIDAS
        assert "QGSP_BIC_HP" in PHYSICS_LISTS_VALIDAS

    def test_historias_acotadas_19_25(self):
        assert mc.validar_caso(_case(n_histories=50))
        assert mc.validar_caso(_case(n_histories=10_000_000))

    def test_un_lote_insuficiente_19_20(self):
        assert any("19.20" in r for r in mc.validar_caso(_case(n_batches=1)))


# -------------------------------------------- métricas y comparación (19.20/19.14)
def _results(edep_hist=16.5, u_rel=0.02, n=10_000):
    return {"case": {"n_histories": n}, "n_histories_total": n,
            "edep_mev_per_history": edep_hist,
            "statistical_uncertainty_rel": u_rel}


class TestMetricas:
    def test_convergencia_ok(self):
        m = mc.evaluar_resultados(_results())
        assert m["validation_ok"] and m["convergence_ok"]
        assert not m["review_required"]

    def test_incertidumbre_alta_marca_revision(self):
        m = mc.evaluar_resultados(_results(u_rel=0.30))
        assert m["validation_ok"] and not m["convergence_ok"]
        assert m["review_required"]

    def test_simulacion_incompleta_no_valida_19_21(self):
        r = _results(n=10_000)
        r["n_histories_total"] = 6_666  # no completó las historias
        m = mc.evaluar_resultados(r)
        assert not m["checks"]["histories_complete"]
        assert not m["validation_ok"]

    def test_edep_nula_no_valida(self):
        m = mc.evaluar_resultados(_results(edep_hist=0.0))
        assert not m["validation_ok"]

    def test_comparacion_potencia_determinista(self):
        # 16.5 MeV/historia × 37 µA = 610.5 W exactos (modelo determinista)
        c = mc.comparar_con_determinista(16.5, 37.0, 610.5)
        assert c["power_mc_w"] == pytest.approx(610.5, rel=1e-6)
        assert abs(c["desviacion_pct"]) < 1e-4
        assert "19.14" in c["nota"]


# ------------------------------------------------------ generación del caso
class TestBuildCase:
    def test_script_componentes_cap19(self, tmp_path):
        script = build_case(tmp_path, _case())
        txt = script.read_text()
        assert 'sim.add_volume("Tubs", "target")' in txt          # 19.6
        assert "add_material_weights" in txt                       # 19.7
        assert 'sim.add_source("GenericSource", "beam")' in txt    # 19.8
        assert 'source.particle = CASE["particle"]' in txt
        assert "physics_list_name = CASE[\"physics_list\"]" in txt  # 19.9
        assert 'sim.add_actor("DoseActor", "edep_target")' in txt   # 19.11
        assert "SimulationStatisticsActor" in txt
        assert "mc_results.json" in txt

    def test_case_json_versionado(self, tmp_path):
        build_case(tmp_path, _case(seed=777))
        cfg = json.loads((tmp_path / "case.json").read_text())
        assert cfg["seed"] == 777
        assert cfg["physics_list"] == "FTFP_BERT"

    def test_lotes_con_semillas_independientes(self, tmp_path):
        txt = build_case(tmp_path, _case()).read_text()
        assert 'CASE["seed"] + 1000 * ibatch' in txt               # 19.20


# ------------------------------------------------------------------ servicio
class _RunnerFalso:
    """Runner sustituido: deposición total realista (16.5 MeV/historia)."""

    cmd_label = "python3-falso (+opengate)"

    def check(self, force=False):
        return True

    def versions(self):
        return {"opengate": "10.1.1", "geant4": "11.4.0"}

    def run(self, script_path, work_dir):
        from pathlib import Path
        cfg = json.loads((Path(work_dir) / "case.json").read_text())
        n = cfg["n_histories"] // cfg["n_batches"]
        e = cfg["beam_energy_mev"]
        batches = [n * e * f for f in (0.999, 1.001, 1.000, 0.998, 1.002)]
        mass = 3.14159265 * cfg["target_radius_cm"] ** 2 * \
            cfg["target_thickness_cm"] * cfg["target_density_g_cm3"]
        results = {
            "case": cfg, "versions": self.versions(),
            "batches_edep_mev": batches, "batches_n": [n] * 5,
            "n_histories_total": cfg["n_histories"],
            "edep_mev_per_history": sum(batches) / 5 / n,
            "statistical_uncertainty_rel": 0.0007,
            "target_mass_g": mass,
            "dose_gy_per_history": e * 1.602e-13 / (mass / 1000.0),
        }
        (Path(work_dir) / "mc_results.json").write_text(json.dumps(results))
        return "MC_RESULTS_OK"


class _RunnerNoDisponible(_RunnerFalso):
    def check(self, force=False):
        return False


def _svc(gate) -> ProductionService:
    from app.infrastructure.repositories.local_reaction_data import \
        LocalReactionDataProvider
    from app.infrastructure.stopping.factory import build_stopping_provider
    from app.main import DATA_DIR
    return ProductionService(
        stopping=build_stopping_provider(DATA_DIR / "stopping"),
        rxn=LocalReactionDataProvider(DATA_DIR), gate=gate)


class TestMonteCarloService:
    def test_resultado_completo_cap19(self):
        r = _svc(_RunnerFalso()).monte_carlo_target(
            reaction_id="o18_p_n_f18", target_id="h2_18o",
            beam_energy_mev=16.5, current_ua=37.0, n_histories=10_000,
            operador="mlopez", motivo="validación yield")
        assert r["pipeline"].startswith("monte-carlo")
        assert r["edep_mev_per_history"] == pytest.approx(16.5, rel=1e-3)
        # 19.14: la potencia MC coincide con la determinista (<1 %)
        assert abs(r["comparacion_determinista"]["desviacion_pct"]) < 1.0
        assert r["metricas_mc"]["validation_ok"]
        assert r["metricas_mc"]["n_histories"] == 10_000
        # 19.24: auditoría completa
        a = r["auditoria"]
        assert a["usuario"] == "mlopez" and a["motivo"] == "validación yield"
        assert a["opengate_version"] == "10.1.1"
        assert a["geant4_version"] == "11.4.0"
        assert a["physics_list"] == "FTFP_BERT"
        assert a["geometria"]["material"].startswith("H2O18")

    def test_sin_motor_503_honesto(self):
        with pytest.raises(GateUnavailable):
            _svc(_RunnerNoDisponible()).monte_carlo_target(
                reaction_id="o18_p_n_f18", target_id="h2_18o",
                beam_energy_mev=16.5, current_ua=37.0, operador="mlopez")

    def test_caso_invalido_422_dominio(self):
        with pytest.raises(ValueError, match="19.9"):
            _svc(_RunnerFalso()).monte_carlo_target(
                reaction_id="o18_p_n_f18", target_id="h2_18o",
                beam_energy_mev=16.5, current_ua=37.0,
                physics_list="INVENTED", operador="mlopez")


# ---------------------------------------------------------------------- API
@pytest.fixture()
def api_client():
    yield_api.init(_svc(_RunnerFalso()))
    return TestClient(app)


class TestMonteCarloApi:
    def test_mc_status_honesto(self, api_client):
        r = api_client.get("/api/v1/mc/status")
        assert r.status_code == 200
        body = r.json()
        assert body["available"] is True
        assert "datasets" in body and "solver" in body

    def test_mc_target_ok(self, api_client):
        r = api_client.post("/api/v1/mc/target", json={
            "reaction_id": "o18_p_n_f18", "target_id": "h2_18o",
            "beam_energy_mev": 16.5, "current_ua": 37.0,
            "n_histories": 10_000, "operador": "mlopez",
            "motivo": "estudio de validación"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["model"] == "OpenGATE/Geant4 FTFP_BERT (cap. 19)"
        assert body["validation_ok"] is True

    def test_mc_target_422_validacion(self, api_client):
        r = api_client.post("/api/v1/mc/target", json={
            "reaction_id": "o18_p_n_f18", "target_id": "h2_18o",
            "beam_energy_mev": 16.5, "current_ua": 37.0,
            "physics_list": "INVENTED", "operador": "mlopez"})
        assert r.status_code == 422


# ------------------------------------------------------- entorno de ejecución
class TestGateEnv:
    def test_env_omite_autodescarga_y_tls(self, tmp_path):
        env = build_gate_env(gatepy_dir=str(tmp_path))
        assert env["GATEONRTD"] == "1"
        assert "optional_static_tls" in env["GLIBC_TUNABLES"]
        assert str(tmp_path) in env["PYTHONPATH"]

    def test_inventario_datasets_honesto(self, tmp_path):
        g4 = tmp_path / "g4data"
        g4.mkdir()
        st = datasets_instalados(g4data_dir=str(g4))
        assert st["ftfp_bert_ok"] is False
        assert st["hp_lists_ok"] is False
        # instalando los datasets base, FTFP_BERT pasa a ejecutable
        for folder in ("G4EMLOW8.8", "PhotonEvaporation6.1.2",
                       "RadioactiveDecay6.1.2", "G4PARTICLEXS4.2", "G4PII1.3",
                       "G4SAIDDATA2.0", "G4ABLA3.3", "G4INCL1.3",
                       "G4ENSDFSTATE3.0"):
            (g4 / folder).mkdir()
        st = datasets_instalados(g4data_dir=str(g4))
        assert st["ftfp_bert_ok"] is True
        assert st["hp_lists_ok"] is False  # G4NDL sigue ausente
        (g4 / "G4NDL4.7.1").mkdir()
        assert datasets_instalados(g4data_dir=str(g4))["hp_lists_ok"] is True
