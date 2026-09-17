# -*- coding: utf-8 -*-
"""Tests del conector tally → φ → Bateman (Fase 33)."""
import numpy as np
import pytest

from app.domain.fluence_connector import (
    leer_tally_mhd, mapa_flujo, phi_medio_muros, tasa_neutrones_f18,
)


def _tally_sintetico(tmp_path, counts):
    counts = np.asarray(counts, dtype=np.float32)
    nz, ny, nx = counts.shape
    (tmp_path / "t.raw").write_bytes(counts.tobytes())
    (tmp_path / "t.mhd").write_text(
        "ObjectType = Image\nNDims = 3\nBinaryData = True\n"
        "DimSize = %d %d %d\nElementSpacing = 200 200 200\n"
        "ElementType = MET_FLOAT\nElementDataFile = t.raw\n" % (nx, ny, nz))
    return tmp_path / "t.mhd"


def test_tasa_neutrones_aritmetica_citada():
    q = tasa_neutrones_f18(60.0)
    assert q["q_n_s"] == pytest.approx(9.902e9 * 60.0)
    assert "cota_inferior" in q["naturaleza"]
    assert "IAEA-2021" in q["fuente"]


def test_tasa_rechaza_corriente_nula():
    with pytest.raises(ValueError):
        tasa_neutrones_f18(0.0)


def test_leer_tally(tmp_path):
    mhd = _tally_sintetico(tmp_path, np.ones((2, 3, 4)))
    t = leer_tally_mhd(mhd)
    assert t["counts"].shape == (2, 3, 4)
    assert t["spacing_mm"] == [200.0, 200.0, 200.0]


def test_mapa_flujo_formula_declarada(tmp_path):
    # un voxel con 100 counts, N=1000, Q=1e9: voxel 20 cm
    counts = np.zeros((1, 1, 1)); counts[0, 0, 0] = 100.0
    mhd = _tally_sintetico(tmp_path, counts)
    m = mapa_flujo(mhd, q_n_s=1e9, n_historias=1000)
    esperado = 100.0 * (2 * 20.0 / 3) / 1000 * 1e9 / 8000.0
    assert m["phi_n_cm2_s"][0, 0, 0] == pytest.approx(esperado)
    assert m["origen_flujo"].startswith("mesh_tally:")
    assert "declarado" in m["estimador"]


def test_phi_muros(tmp_path):
    counts = np.zeros((1, 2, 2)); counts[0, 0, 0] = 50; counts[0, 1, 1] = 150
    mhd = _tally_sintetico(tmp_path, counts)
    m = mapa_flujo(mhd, q_n_s=1e9, n_historias=1000)
    p = phi_medio_muros(m)
    assert p["voxels_activos"] == 2
    assert p["phi_max_n_cm2_s"] > p["phi_medio_n_cm2_s"]


def test_mapa_rechaza_entradas_nulas(tmp_path):
    mhd = _tally_sintetico(tmp_path, np.ones((1, 1, 1)))
    with pytest.raises(ValueError):
        mapa_flujo(mhd, q_n_s=0, n_historias=10)
    with pytest.raises(ValueError):
        mapa_flujo(mhd, q_n_s=1, n_historias=0)
