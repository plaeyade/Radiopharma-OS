"""Tests F42b — caso OpenMC con geometría real del plano BIND (F38)."""
import json

import pytest

from app.infrastructure.openmc.bunker_openmc import (
    GEOM_CM,
    GEOM_REAL_BIND_CM,
    BunkerOpenMCCase,
    vol_concreto_cm3,
)


def test_caso_oiea_intacto():
    # ALCOA+: la geometría OIEA de F42 no se toca
    assert GEOM_CM["concreto"] == (-600.0, 600.0, -500.0, 500.0, -300.0, 300.0)
    c = BunkerOpenMCCase(spectrum_file="x.tot")
    assert c.geometria == "oiea"
    assert c.geom() is GEOM_CM


def test_bind_real_envolvente_medida():
    g = GEOM_REAL_BIND_CM
    ancho = g["concreto"][1] - g["concreto"][0]
    largo = g["concreto"][3] - g["concreto"][2]
    assert ancho == pytest.approx(971.0)   # 9,71 m medidos
    assert largo == pytest.approx(1549.0)  # 15,49 m = cota 15,499 del plano
    assert g["muro_oeste_medido_m"] == pytest.approx(2.11)


def test_bind_real_estado_honesto():
    assert "pendiente_verificacion" in GEOM_REAL_BIND_CM["estado"]


def test_bind_real_muro_oeste_coherente():
    g = BunkerOpenMCCase(spectrum_file="x.tot", geometria="bind_real").geom()
    # cara exterior oeste −479 → la sala interior no puede empezar antes
    # de −479 + 211 (muro medido) = −268
    assert g["boveda"][0] >= g["concreto"][0] + 211.0 - 1e-9


def test_volumenes_bind_real_positivos():
    c = BunkerOpenMCCase(spectrum_file="x.tot", geometria="bind_real")
    vc = vol_concreto_cm3(c)
    assert vc > 0
    # envolvente 9,71×15,49×4,0 ≈ 6,0e8 cm³ menos sala y laberinto
    assert vc == pytest.approx(
        971.0 * 1549.0 * 400.0 - 590.0 * 470.0 * 370.0 - 200.0 * 232.0 * 240.0,
        rel=1e-9)


def test_serializable_alcoa():
    c = BunkerOpenMCCase(spectrum_file="x.tot", geometria="bind_real")
    s = json.dumps({**c.__dict__, "mesh_bins": list(c.mesh_bins)},
                   ensure_ascii=False)
    assert "bind_real" in s
