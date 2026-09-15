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
cm, mm, MeV = g4_units.cm, g4_units.mm, g4_units.MeV

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

# Capas de blindaje concéntricas (materiales NIST reales, nunca
# efectivos inventados): cada capa es una esfera hueca real, con un
# micro-gap de 0.001 cm entre superficies (las superficies coincidentes
# hacen que Geant4 no marque el cruce de frontera y el tally quedaría
# ciego — la separación es físicamente despreciable y se declara).
GAP_CM = 0.001
radio = case["radio_cm"]
capas = []
for i, capa in enumerate(case.get("blindajes", [])):
    radio = radio + GAP_CM
    sh = sim.add_volume("Sphere", f"blindaje_{i}")
    sh.rmin = radio * cm
    radio = radio + capa["espesor_cm"]
    sh.rmax = radio * cm
    sh.material = capa["material_g4"]
    sh.mother = "world"
    capas.append(sh)

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
phsp.attributes = ["KineticEnergy", "PrePosition"]
phsp.output_filename = "fuga.root"

# Fuga tras la última capa de blindaje (impacto residual real)
if capas:
    phsp2 = sim.add_actor("PhaseSpaceActor", "fuga_blindaje")
    phsp2.attached_to = capas[-1].name
    phsp2.steps_to_store = "exiting"
    phsp2.attributes = ["KineticEnergy"]
    phsp2.output_filename = "fuga_blindaje.root"

# Energía depositada por capa (impacto en paredes — edep real).
# El DoseActor usa por defecto vóxeles de 1 mm: hay que darle un
# `spacing` que cubra la caja envolvente de la capa (1 solo vóxel).
radio_int = case["radio_cm"]
for i, sh in enumerate(capas):
    radio_ext = radio_int + GAP_CM + case["blindajes"][i]["espesor_cm"]
    d = sim.add_actor("DoseActor", f"dose_blindaje_{i}")
    d.attached_to = sh.name
    d.output_filename = f"dose_blindaje_{i}.mhd"
    d.size = [1, 1, 1]
    d.spacing = [2.0 * radio_ext * 10.0] * 3  # mm — caja envolvente
    radio_int = radio_ext

# estadística global para conteo real de historias
stats = sim.add_actor("SimulationStatisticsActor", "stats")
stats.track_types_flag = True

sim.physics_manager.physics_list_name = case.get("physics_list",
                                                 "FTFP_BERT_HP")
sim.run(start_new_process=True)

import uproot

def bandas_de(e_mev):
    e_ev = np.asarray(e_mev, dtype=float) * 1e6
    return {
        "termicos_lt_0.4eV": int((e_ev < 0.4).sum()),
        "epitermicos": int(((e_ev >= 0.4) & (e_ev < 1e5)).sum()),
        "rapidos_ge_100keV": int((e_ev >= 1e5).sum()),
        "total_registrados": int(e_ev.size),
    }

salida = {}
with uproot.open("fuga.root") as f:
    tree = f[f.keys()[0]]
    e = tree["KineticEnergy"].array(library="np")  # MeV
    pos_y = tree["PrePosition_Y"].array(library="np")  # mm
    pos_z = tree["PrePosition_Z"].array(library="np")
salida.update(bandas_de(e))
# Dispersión real: posición y energía de CADA neutrón que sale
salida["dispersion"] = {
    "y_mm": [round(float(p), 2) for p in pos_y],
    "z_mm": [round(float(p), 2) for p in pos_z],
    "e_mev": [round(float(x), 6) for x in e],
    "radio_moderador_mm": round(case["radio_cm"] * 10.0, 2),
}

if capas:
    with uproot.open("fuga_blindaje.root") as f:
        tree = f[f.keys()[0]]
        eb = tree["KineticEnergy"].array(library="np")
    salida["fuga_tras_blindaje"] = bandas_de(eb)
    # Geometría real de las capas (radios del case.json + micro-gap
    # declarado) para el renderizador fotorrealista (scripts/
    # render_blender.py) — comunicación visual, nunca física.
    salida["blindajes_geometria"] = [
        {
            "material": sh.material,
            "rmin_mm": round(sh.rmin / mm, 3),
            "rmax_mm": round(sh.rmax / mm, 3),
        }
        for sh in capas
    ]
    import SimpleITK as sitk
    import glob
    edeps = []
    for i in range(len(capas)):
        cand = sorted(glob.glob(f"dose_blindaje_{i}*edep*.mhd"))
        if not cand:
            raise RuntimeError(
                f"DoseActor blindaje_{i} no produjo imagen edep — "
                "impacto no_demostrable")
        img = sitk.ReadImage(cand[0])
        edeps.append(float(sitk.GetArrayFromImage(img).sum()))
    salida["edep_por_capa_mev"] = edeps

json.dump(salida, open("tally.json", "w"), indent=2)
print(json.dumps({k: v for k, v in salida.items() if k != "dispersion"}))
"""


def build_case(case_dir: Path, espectro: list[list[float]],
               radio_cm: float, n_histories: int, material_g4: str,
               seed: int, physics_list: str = "FTFP_BERT_HP",
               blindajes: list[dict] | None = None) -> Path:
    """Escribe case.json + run_tally.py (entrada real del MC)."""
    case_dir = Path(case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "case.json").write_text(json.dumps({
        "espectro": espectro, "radio_cm": radio_cm,
        "n_histories": n_histories, "material_g4": material_g4,
        "seed": seed, "physics_list": physics_list,
        "blindajes": list(blindajes or [])}))
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
