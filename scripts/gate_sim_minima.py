#!/usr/bin/env python3
"""Simulación Monte Carlo REAL mínima (OpenGATE/Geant4): haz de protones
de 16 MeV sobre un blanco de agua de 10 cm. Mide la energía depositada
total con un DoseActor y la compara con la energía cinética inyectada
(esperado ≈ frenado total: N × 16 MeV).

La ejecuta scripts/prueba_teorica_fisica.py en un subproceso; escribe
resultado_mc.json en el directorio indicado. Nunca simula: los números
salen del transporte Geant4.

Uso:  python3 scripts/gate_sim_minima.py <dir_salida>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)

    import opengate as og
    from opengate.utility import g4_units as u

    n_protones = 2000
    energia_mev = 16.0

    sim = og.Simulation()
    sim.g4_verbose = False
    sim.visu = False
    sim.random_seed = 12345
    sim.output_dir = str(out_dir)

    world = sim.world
    world.size = [1 * u.m, 1 * u.m, 1 * u.m]
    world.material = "G4_AIR"

    blanco = sim.add_volume("Box", "blanco")
    blanco.size = [10 * u.cm, 10 * u.cm, 10 * u.cm]
    blanco.material = "G4_WATER"

    fuente = sim.add_source("GenericSource", "protones")
    fuente.particle = "proton"
    fuente.energy.type = "mono"
    fuente.energy.mono = energia_mev * u.MeV
    fuente.position.type = "point"
    fuente.direction.type = "momentum"
    fuente.direction.momentum = [0, 0, 1]
    fuente.n = n_protones

    dosis = sim.add_actor("DoseActor", "dosis")
    dosis.attached_to = blanco.name
    dosis.size = [1, 1, 100]
    dosis.spacing = [10 * u.cm, 10 * u.cm, 1 * u.mm]

    sim.run(start_new_process=True)

    import numpy as np
    import SimpleITK as sitk
    raw = next(out_dir.glob("*edep.mhd"))
    arr = sitk.GetArrayFromImage(sitk.ReadImage(str(raw)))
    edep = float(np.nansum(arr))
    esperada = n_protones * energia_mev

    import importlib.metadata
    try:
        ver = importlib.metadata.version("opengate")
    except importlib.metadata.PackageNotFoundError:
        ver = "10.1.1"
    resultado = {
        "motor": f"OpenGATE {ver} / Geant4",
        "historias": n_protones,
        "particula": "proton",
        "energia_mev": energia_mev,
        "blanco": "agua 10x10x10 cm",
        "semilla": 12345,
        "edep_total_mev": round(edep, 1),
        "edep_esperada_mev": round(esperada, 1),
        "desviacion_pct": round((edep - esperada) / esperada * 100, 3),
    }
    (out_dir / "resultado_mc.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2))
    print(json.dumps(resultado, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
