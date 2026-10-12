# -*- coding: utf-8 -*-
"""Tests Fase 42 — caso búnker OpenMC (equivalencia geométrica analítica)."""
from __future__ import annotations

import json

from app.infrastructure.openmc.bunker_openmc import (
    BunkerOpenMCCase, GEOM_CM, vol_aire_cm3, vol_concreto_cm3, build_openmc_model,
)


def _v(b):
    return (b[1]-b[0]) * (b[3]-b[2]) * (b[5]-b[4])


def test_volumenes_analiticos_coherentes():
    # bloque 12x10x6 m = 7,2e8 cm³; bóveda 6x6x4 = 1,44e8; lab1 3x1,2x2,4 = 8,64e6
    assert vol_concreto_cm3() == _v(GEOM_CM["concreto"]) - _v(GEOM_CM["boveda"]) - _v(GEOM_CM["laberinto_1"])
    assert abs(vol_concreto_cm3() - (7.2e8 - 1.44e8 - 8.64e6)) < 1.0
    # aire = world - bloque + bóveda + lab1 + lab2 (1,2x4,0x2,4 = 1,152e7)
    esperado = _v(GEOM_CM["world"]) - _v(GEOM_CM["concreto"]) + _v(GEOM_CM["boveda"]) + _v(GEOM_CM["laberinto_1"]) + _v(GEOM_CM["laberinto_2"])
    assert abs(vol_aire_cm3() - esperado) < 1.0


def test_dimensiones_declaradas_oiea():
    # bóveda 6x6x4 m, muros 2,0 m (bloque - bóveda)/2 en cada eje
    bx, bx2 = GEOM_CM["concreto"][1] - GEOM_CM["concreto"][0], GEOM_CM["boveda"][1] - GEOM_CM["boveda"][0]
    # grosores REALES de la geometría F32: x (12-6)/2=3,0 m (lado laberinto),
    # y (10-6)/2=2,0 m (declarado "muros 2,0 m"), z (6-4)/2=1,0 m (losas)
    assert (bx - bx2) / 2 == 300.0
    by, by2 = GEOM_CM["concreto"][3] - GEOM_CM["concreto"][2], GEOM_CM["boveda"][3] - GEOM_CM["boveda"][2]
    assert (by - by2) / 2 == 200.0
    bz, bz2 = GEOM_CM["concreto"][5] - GEOM_CM["concreto"][4], GEOM_CM["boveda"][5] - GEOM_CM["boveda"][4]
    assert (bz - bz2) / 2 == 100.0
    # laberinto 1,2 m de ancho
    assert GEOM_CM["laberinto_1"][3] - GEOM_CM["laberinto_1"][2] == 120.0


def test_caso_serializable_alcoa(tmp_path):
    case = BunkerOpenMCCase(spectrum_file="nspec_o18.tot")
    d = json.loads(json.dumps({**case.__dict__, "mesh_bins": list(case.mesh_bins)}))
    assert d["n_histories"] == 40_000
    assert "sin S(α,β)" in d["nota_termico"]


def test_malla_identica_a_f32():
    assert BunkerOpenMCCase(spectrum_file="x.tot").mesh_bins == (110, 110, 60)


def test_modelo_construible_si_openmc_disponible():
    try:
        import openmc  # noqa: F401
    except ImportError:
        return  # entorno OpenMC no instalado en el runner — no bloqueante
    import numpy as np
    spec = "/mnt/agents/work/evidencia_v072/fase32/nspec_o18.tot"
    import os
    if not os.path.exists(spec):
        return
    model = build_openmc_model(BunkerOpenMCCase(spectrum_file=spec, n_histories=100, batches=2))
    mats = {m.name for m in model.materials}
    assert mats == {"G4_CONCRETE_NIST", "G4_AIR_NIST"}
    cells = {c.name for c in model.geometry.get_all_cells().values()}
    assert cells == {"concreto", "boveda", "laberinto_1", "laberinto_2", "aire_exterior"}
    t = model.tallies[0]
    assert t.scores == ["flux"]
    mesh = t.filters[0].mesh
    assert tuple(mesh.dimension) == (110, 110, 60)
    assert np.isclose(mesh.width[0], 20.0)  # 2200 cm / 110 = 20 cm = spacing F35
