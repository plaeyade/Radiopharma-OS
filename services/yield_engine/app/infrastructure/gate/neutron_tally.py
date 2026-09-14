"""Tally de neutrones por bandas de energía con OpenGATE/Geant4 real.

El espectro fuente sale de TALYS (ejecución real, ver
``talys_spectra.py``); la termalización se calcula transportando ese
espectro en un moderador esférico con OpenGATE (Geant4 FTFP_BERT_HP +
G4NDL real): un PhaseSpaceActor registra la energía de cada neutrón que
SALE del moderador y el histograma por bandas se computa del ROOT real.

Sin runtime OpenGATE → 503 `sin_runtime` honesto (nunca se estima el
tally). Sin G4NDL (datos HP) → error honesto: la termalización sin
datos de scattering térmico no es demostrable y no se declara.

Bandas (convención declarada):
- térmicos:      E < 0.4 eV
- epitérmicos:   0.4 eV ≤ E < 100 keV
- rápidos:       E ≥ 100 keV
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

E_TERMICO_MAX_EV = 0.4
E_EPITERMICO_MAX_KEV = 100.0  # keV


class TallyGateUnavailable(RuntimeError):
    """OpenGATE/Geant4 no disponible (sin_runtime)."""


class TallyGateError(RuntimeError):
    """El tally MC se ejecutó pero no produjo datos válidos."""


_SCRIPT = r"""
import json, sys
import numpy as np

case = json.load(open("case.json"))
import opengate as gate
from opengate import g4_units
cm, MeV = g4_units.cm, g4_units.MeV

sim = gate.Simulation()
sim.verbose_level = gate.logger.NONE
sim.visu = False
sim.random_seed = case["seed"]
sim.number_of_threads = 1
sim.output_dir = "."

sim.world.size = [10 * 100 * cm] * 3
sim.world.material = "G4_Galactic"

mod = sim.add_volume("Sphere", "moderador")
mod.rmax = case["radio_cm"] * cm
mod.material = case["material_g4"]
mod.mother = "world"

src = sim.add_source("GenericSource", "fuente_talys")
src.particle = "neutron"
src.position.type = "point"
src.position.translation = [0, 0, 0]
src.direction.type = "iso"
src.n = case["n_histories"]
esp = np.array(case["espectro"], dtype=float)
src.energy.type = "histogram"
src.energy.histogram_energy = list(esp[:, 0] * MeV / MeV)  # MeV
src.energy.histogram_weight = list(esp[:, 1])

phsp = sim.add_actor("PhaseSpaceActor", "fuga")
phsp.attached_to = "moderador"
phsp.steps_to_store = "exiting"
phsp.attributes = ["KineticEnergy"]
phsp.output_filename = "fuga.root"

# estadística global para conteo real de historias
stats = sim.add_actor("SimulationStatisticsActor", "stats")
stats.track_types_flag = True

sim.physics_manager.physics_list_name = case.get("physics_list",
                                                 "FTFP_BERT_HP")
sim.run(start_new_process=True)

import uproot
with uproot.open("fuga.root") as f:
    tree = f[f.keys()[0]]
    e = tree["KineticEnergy"].array(library="np")  # MeV
e_ev = np.asarray(e, dtype=float) * 1e6
bandas = {
    "termicos_lt_0.4eV": int((e_ev < 0.4).sum()),
    "epitermicos": int(((e_ev >= 0.4) & (e_ev < 1e5)).sum()),
    "rapidos_ge_100keV": int((e_ev >= 1e5).sum()),
    "total_registrados": int(e_ev.size),
}
json.dump(bandas, open("tally.json", "w"), indent=2)
print(json.dumps(bandas))
"""


def build_case(case_dir: Path, espectro: list[list[float]],
               radio_cm: float, n_histories: int, material_g4: str,
               seed: int, physics_list: str = "FTFP_BERT_HP") -> Path:
    """Escribe case.json + run_tally.py (entrada real del MC)."""
    case_dir = Path(case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "case.json").write_text(json.dumps({
        "espectro": espectro, "radio_cm": radio_cm,
        "n_histories": n_histories, "material_g4": material_g4,
        "seed": seed, "physics_list": physics_list}))
    script = case_dir / "run_tally.py"
    script.write_text(_SCRIPT)
    return script


class NeutronTallyRunner:
    """Ejecuta el tally con el intérprete OpenGATE (patrón GateRunner)."""

    def __init__(self, python_cmd: str | None = None,
                 env_extra: dict | None = None, timeout_s: int = 3600) -> None:
        self.python_cmd = python_cmd or os.environ.get(
            "OPENGATE_PYTHON", "python3")
        self.env_extra = dict(env_extra or {})
        self.timeout_s = timeout_s

    def _env(self) -> dict:
        env = dict(os.environ)
        env.update(self.env_extra)
        # G4NDL (scattering térmico HP) — sin él FTFP_BERT_HP no es
        # demostrable y el tally se declara no_demostrable.
        g4ndl = os.environ.get("G4NEUTRONHPDATA")
        if g4ndl:
            env["G4NEUTRONHPDATA"] = g4ndl
        return env

    def check(self) -> bool:
        try:
            proc = subprocess.run(
                [self.python_cmd, "-c", "import opengate, uproot"],
                capture_output=True, timeout=180, env=self._env())
            return proc.returncode == 0
        except Exception:
            return False

    def run(self, case_dir: Path) -> dict:
        if not self.check():
            raise TallyGateUnavailable(
                "OpenGATE/Geant4 no disponible (sin_runtime): configurar "
                "OPENGATE_PYTHON/GATEPY_DIR — la plataforma nunca estima "
                "un tally de neutrones")
        if "G4NEUTRONHPDATA" not in self._env():
            raise TallyGateUnavailable(
                "sin G4NDL (G4NEUTRONHPDATA no definido): la "
                "termalización requiere datos HP reales de scattering "
                "térmico — tally térmico no_demostrable, nunca estimado")
        case_dir = Path(case_dir)
        log = case_dir / "gate_tally.log"
        with open(log, "w", encoding="utf-8") as fh:
            proc = subprocess.run([self.python_cmd, "run_tally.py"],
                                  cwd=case_dir, stdout=fh,
                                  stderr=subprocess.STDOUT, text=True,
                                  timeout=self.timeout_s, env=self._env())
        tally = case_dir / "tally.json"
        if proc.returncode != 0 or not tally.exists():
            raise TallyGateError(
                f"tally MC rc={proc.returncode}; ver {log}")
        return json.loads(tally.read_text())


def bandas_desde_espectro_fuente(espectro: list[list[float]]) -> dict:
    """Bandas del espectro FUENTE (TALYS), antes de moderar.

    TALYS (p,xn) arranca en 1 keV: los térmicos de la fuente son 0 de
    forma declarada — los térmicos reales solo salen del transporte MC.
    """
    rap = epi = ter = 0.0
    for (e0, s0), (e1, s1) in zip(espectro, espectro[1:]):
        area = 0.5 * (s0 + s1) * (e1 - e0)   # mb
        e_mid_ev = 0.5 * (e0 + e1) * 1e6
        if e_mid_ev < 0.4:
            ter += area
        elif e_mid_ev < 1e5:
            epi += area
        else:
            rap += area
    total = ter + epi + rap
    return {"termicos_mb": round(ter, 4), "epitermicos_mb": round(epi, 4),
            "rapidos_mb": round(rap, 4), "total_mb": round(total, 4),
            "nota": ("espectro fuente TALYS (p,xn): termalización solo "
                     "demostrable por transporte MC (OpenGATE) — nunca "
                     "estimada")}
