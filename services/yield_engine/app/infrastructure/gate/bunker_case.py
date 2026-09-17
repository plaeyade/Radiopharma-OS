# -*- coding: utf-8 -*-
"""Caso Monte Carlo de fluencia neutrónica en búnker de ciclotrón — Fase 32.

Geometría declarada tipo OIEA para ciclotrón NO autoblindado (bóveda de
concreto con laberinto de acceso), fuente de neutrones con espectro REAL de
TALYS (archivo nspec*.tot, p.ej. 18O(p,xn) a 16,5 MeV) — nunca un espectro
fabricado. El mesh tally de fluencia alimenta después al motor Bateman
(hoja de ruta ②: retirar marcadores flujo_declarado_pendiente_mesh_tally).

Geometría declarada (simplificación documentada, pendiente de plano real):
  - bóveda interior 6 × 6 × 4 m (típica PET, IAEA SSG-46 orientativo)
  - muros de concreto 2,0 m
  - laberinto de acceso 1,2 m de ancho con un cambio de dirección
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_SCRIPT = '''"""Caso búnker generado por Radiopharma OS (Fase 32). No editar a mano."""
import json, os, sys
from pathlib import Path
import numpy as np
import opengate as gate

M = gate.g4_units.m
MEV = gate.g4_units.MeV
CASE = __CASE_JSON__

# Espectro TALYS real (E MeV, xs mb/MeV) → histograma de la fuente
e, xs = [], []
with open(CASE["spectrum_file"]) as f:
    for line in f:
        if line.startswith("#") or not line.strip():
            continue
        c = line.split()
        e.append(float(c[0])); xs.append(float(c[1]))

sim = gate.Simulation()
sim.output_dir = CASE["work_dir"]
sim.random_seed = CASE["seed"]
sim.visu = False

world = sim.world
world.size = [22 * M, 22 * M, 12 * M]
world.material = "G4_AIR"

# Bóveda de concreto (ciclotrón NO autoblindado): bloque exterior con
# cavidad interior; laberinto = corredor de aire que atraviesa el muro +X
# con un cambio de dirección (baffle de concreto).
concrete = sim.add_volume("Box", "concreto")
concrete.mother = world.name
concrete.size = [12 * M, 10 * M, 6 * M]
concrete.material = "G4_CONCRETE"
concrete.translation = [0, 0, 0]

room = sim.add_volume("Box", "boveda")
room.mother = concrete.name
room.size = [6 * M, 6 * M, 4 * M]
room.material = "G4_AIR"
room.translation = [0, 0, 0]

# Corredor del laberinto (aire) a lo largo de +X hasta el exterior, y
# segundo tramo en +Y (un cambio de dirección).
corr1 = sim.add_volume("Box", "laberinto_1")
corr1.mother = concrete.name
corr1.size = [3.0 * M, 1.2 * M, 2.4 * M]
corr1.material = "G4_AIR"
corr1.translation = [4.5 * M, -2.4 * M, -0.8 * M]

corr2 = sim.add_volume("Box", "laberinto_2")
corr2.mother = world.name
corr2.size = [1.2 * M, 4.0 * M, 2.4 * M]
corr2.material = "G4_AIR"
corr2.translation = [6.6 * M, 1.4 * M, -0.8 * M]

# Fuente: neutrones del blanco 18O con espectro TALYS real, isotrópica,
# en la posición del blanco del ciclotrón (declarada: centro de la bóveda).
src = sim.add_source("GenericSource", "target_n")
src.particle = "neutron"
src.position.type = "point"
src.position.translation = [0, 0, 0]
src.direction.type = "iso"
src.energy.type = "histogram"
src.energy.histogram_energy = np.array(e) * MEV
src.energy.histogram_weight = np.array(xs)
src.n = CASE["n_histories"]

sim.physics_manager.physics_list_name = CASE["physics_list"]

# Mesh tally: fluencia (track-length) en todo el conjunto bóveda+muros.
act = sim.add_actor(CASE["actor_type"], "mesh_tally")
act.attached_to = world.name
act.output_filename = "tally.mhd"
nx, ny, nz = CASE["mesh_bins"]
act.size = [nx, ny, nz]
act.spacing = [22 * M / nx, 22 * M / ny, 12 * M / nz]
try:
    act.fluence.active = True
except Exception:
    pass
try:
    act.edep.active = True
    act.dose.active = True
except Exception:
    pass

stats = sim.add_actor("SimulationStatisticsActor", "stats")
stats.track_types_flag = True

sim.run(start_new_process=True)
print("BUNKER_TALLY_OK")
'''


@dataclass(frozen=True)
class BunkerCase:
    """Configuración registrable del caso de búnker (19.24)."""
    spectrum_file: str            # nspec*.tot REAL de TALYS
    n_histories: int = 100_000
    physics_list: str = "FTFP_BERT"   # HP para térmicos: pendiente G4NDL completo
    actor_type: str = "FluenceActor"  # respaldo: "DoseActor" (edep, declarado)
    mesh_bins: tuple = (110, 110, 60)
    seed: int = 20260917
    geometria: str = ("declarada tipo OIEA (bóveda 6x6x4 m, muros concreto "
                      "2,0 m, laberinto con un cambio de dirección), pendiente "
                      "de plano real de la instalación")


def build_bunker_case(case_dir: str | Path, case: BunkerCase) -> Path:
    """Escribe run_bunker.py + case.json versionados."""
    case_dir = Path(case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)
    payload = {**case.__dict__, "mesh_bins": list(case.mesh_bins),
               "work_dir": str(case_dir)}
    (case_dir / "case.json").write_text(json.dumps(payload, indent=2))
    (case_dir / "run_bunker.py").write_text(
        _SCRIPT.replace("__CASE_JSON__", json.dumps(payload)))
    return case_dir / "run_bunker.py"
