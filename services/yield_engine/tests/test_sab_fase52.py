"""Pruebas F52: soporte S(α,β) en el caso búnker OpenMC."""
from __future__ import annotations

from app.infrastructure.openmc.bunker_openmc import BunkerOpenMCCase


def test_caso_sin_sab_por_defecto():
    c = BunkerOpenMCCase(spectrum_file="x.tot")
    assert c.sab == ""
    assert "JEFF 3.2" in c.sab_fuente  # mezcla declarada


def test_caso_con_sab_declara_fuente():
    c = BunkerOpenMCCase(spectrum_file="x.tot", sab="c_H_in_H2O")
    assert c.sab == "c_H_in_H2O"
    assert "pendiente_entorno" in c.sab_fuente or "JEFF" in c.sab_fuente


def test_geometrias_intactas():
    for g in ("oiea", "bind_real"):
        c = BunkerOpenMCCase(spectrum_file="x.tot", geometria=g,
                             sab="c_H_in_H2O")
        assert c.geom()["concreto"]
