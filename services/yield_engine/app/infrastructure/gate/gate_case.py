"""
Constructor de casos Monte Carlo (componentes del cap. 19.5).

Genera el script OpenGATE autocontenido del caso: geometría del blanco
cilíndrico (Geometry Builder 19.6), material agua enriquecida H2-18O
consistente con la biblioteca del Physics Twin (Material Manager 19.7),
fuente primaria de protones desde los parámetros del ciclotrón (Source
Generator 19.8), lista de física registrada (Physics List Manager 19.9)
y scoring de energía depositada/dosis en el blanco (Scoring Manager
19.11).

Gestión de incertidumbre (19.20): las historias se ejecutan en K lotes
independientes con semillas distintas; la incertidumbre estadística se
estima como la desviación estándar entre lotes (√K), con lo que la
métrica no depende de detalles internos del actor. La convergencia se
declara cuando la incertidumbre relativa no supera el umbral configurado
(documentado en cada ejecución).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Listas de física admitidas y registradas para reproducibilidad (19.9).
# FTFP_BERT (referencia Geant4) corre con los datasets base instalados;
# las listas _HP requieren G4NDL adicional (ver /mc/status).
PHYSICS_LISTS_VALIDAS = ("FTFP_BERT", "QGSP_BIC_HP", "QGSP_BERT_HP")
PHYSICS_LIST_DEFAULT = "FTFP_BERT"

# Umbrales de dominio (19.20/19.21).
N_HIST_MIN = 100
N_HIST_MAX = 500_000
N_BATCHES_DEFAULT = 5
U_REL_CONVERGENCIA = 0.05

_SCRIPT = '''"""Caso Monte Carlo generado por Radiopharma OS (cap. 19).

No editar a mano: la configuración queda registrada en la auditoría
(19.24) y en el Data Lake; regenerar desde la API para reproducir.
"""
import json
import sys

import numpy as np
import opengate as gate
import opengate_core

MM = gate.g4_units.mm
CM = gate.g4_units.cm
MEV = gate.g4_units.MeV

CASE = __CASE_JSON__

results = {
    "case": CASE,
    "versions": {"opengate": gate.__version__},
    "batches_edep_mev": [],
    "batches_n": [],
}
try:
    results["versions"]["geant4"] = opengate_core.get_G4_version_string()
except Exception:
    results["versions"]["geant4"] = "unknown"

for ibatch in range(CASE["n_batches"]):
    sim = gate.Simulation()
    sim.output_dir = CASE["work_dir"]
    sim.random_seed = CASE["seed"] + 1000 * ibatch

    # --- Geometry Builder (19.6): mundo aire + blanco cilíndrico ---
    world = sim.world
    world.size = [20 * CM, 20 * CM, 20 * CM]
    world.material = "G4_AIR"

    # --- Material Manager (19.7): H2-18O enriquecida -----------------
    # Misma estequiometría H:O=2:1 (fracciones másicas de G4_WATER) con
    # la densidad del agua enriquecida al 97%% en 18O (1.11 g/cm3),
    # consistente con el catálogo de blancos del Physics Twin.
    sim.volume_manager.material_database.add_material_weights(
        "H2O18", ["H", "O"], [0.1119, 0.8881],
        CASE["target_density_g_cm3"] * gate.g4_units.g / gate.g4_units.cm3)
    target = sim.add_volume("Tubs", "target")
    target.rmin = 0
    target.rmax = CASE["target_radius_cm"] * CM
    target.dz = CASE["target_thickness_cm"] * CM
    target.mother = world.name
    target.material = "H2O18"

    # --- Source Generator (19.8): haz de protones del ciclotrón ------
    source = sim.add_source("GenericSource", "beam")
    source.particle = CASE["particle"]
    source.energy.mono = CASE["beam_energy_mev"] * MEV
    source.position.type = "disc"
    source.position.radius = CASE["beam_radius_cm"] * CM
    source.position.translation = [0, 0, -10 * CM]
    source.direction.type = "momentum"
    source.direction.momentum = [0, 0, 1]
    source.n = CASE["n_histories"] // CASE["n_batches"]

    # --- Physics List Manager (19.9) ---------------------------------
    sim.physics_manager.physics_list_name = CASE["physics_list"]

    # --- Scoring Manager (19.11): energía depositada en el blanco ----
    dose = sim.add_actor("DoseActor", "edep_target")
    dose.attached_to = target.name
    dose.output_filename = f"edep_batch{ibatch}.mhd"
    dose.size = [1, 1, 1]
    dose.spacing = [2 * CASE["target_radius_cm"] * CM,
                    2 * CASE["target_radius_cm"] * CM,
                    CASE["target_thickness_cm"] * CM]
    dose.edep.active = True
    dose.dose.active = True

    stats = sim.add_actor("SimulationStatisticsActor", "stats")
    stats.track_types_flag = True

    sim.run(start_new_process=True)
    edep_mev = float(np.asarray(dose.edep).sum())
    results["batches_edep_mev"].append(edep_mev)
    results["batches_n"].append(int(source.n))

edep = np.array(results["batches_edep_mev"], dtype=float)
n_tot = int(sum(results["batches_n"]))
mean = float(edep.mean()) if len(edep) else 0.0
std = float(edep.std(ddof=1)) if len(edep) > 1 else 0.0
k = len(edep)
rel_unc = float(std / np.sqrt(k) / mean) if mean > 0 and k > 1 else None
mass_g = (np.pi * CASE["target_radius_cm"] ** 2
          * CASE["target_thickness_cm"] * CASE["target_density_g_cm3"])
dose_gy_per_history = mean * 1.602176634e-13 / (mass_g / 1000.0) if mass_g > 0 else None

results.update({
    "n_histories_total": n_tot,
    "edep_mean_mev_per_batch": mean,
    "edep_std_mev": std,
    "n_batches": k,
    "edep_mev_per_history": mean / (n_tot / k) if n_tot else None,
    "statistical_uncertainty_rel": rel_unc,
    "target_mass_g": mass_g,
    "dose_gy_per_history": dose_gy_per_history,
})
with open(CASE["work_dir"] + "/mc_results.json", "w") as f:
    json.dump(results, f, indent=2)
print("MC_RESULTS_OK histories=%d edep_mean=%.6f MeV/batch" % (n_tot, mean))
'''


@dataclass(frozen=True)
class MonteCarloTargetCase:
    """Configuración completa y registrable del caso (19.24)."""

    particle: str = "proton"
    beam_energy_mev: float = 16.5
    beam_radius_cm: float = 0.5
    target_radius_cm: float = 1.0
    target_thickness_cm: float = 0.5
    target_density_g_cm3: float = 1.11  # H2-18O ~97 % enriquecida
    n_histories: int = 50_000
    n_batches: int = N_BATCHES_DEFAULT
    physics_list: str = PHYSICS_LIST_DEFAULT
    seed: int = 12345


def build_case(case_dir, case: MonteCarloTargetCase, work_dir: str | None = None) -> object:
    """Escribe `run_gate.py` y `case.json` (geometría/fuente/física versionadas)."""
    import json
    from pathlib import Path

    case_dir = Path(case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)
    payload = {**case.__dict__, "work_dir": str(work_dir or case_dir)}
    (case_dir / "case.json").write_text(json.dumps(payload, indent=2))
    script = _SCRIPT.replace("__CASE_JSON__", json.dumps(payload))
    (case_dir / "run_gate.py").write_text(script)
    return case_dir / "run_gate.py"
