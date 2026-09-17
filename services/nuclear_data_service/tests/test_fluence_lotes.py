# -*- coding: utf-8 -*-
"""Tests Fase 35 — estadística por lotes del conector tally→φ."""
import numpy as np
import pytest

from app.domain.fluence_connector import estadistica_lotes


def _mapa(valores, nombre):
    return {
        "phi_n_cm2_s": np.array(valores, dtype=float),
        "origen_flujo": f"mesh_tally:{nombre}:N=100:Q=1e11",
        "estimador": "declarado test",
    }


def test_media_y_sem_correctos():
    # 3 lotes, 2×2 voxels; valores conocidos
    m1 = _mapa([[1.0, 2.0], [0.0, 4.0]], "b1")
    m2 = _mapa([[3.0, 2.0], [0.0, 6.0]], "b2")
    m3 = _mapa([[2.0, 2.0], [0.0, 5.0]], "b3")
    r = estadistica_lotes([m1, m2, m3])
    # media voxel (0,0) = 2.0; s = 1.0 (ddof=1); SEM = 1/√3
    assert r["phi_media_n_cm2_s"][0, 0] == pytest.approx(2.0)
    assert r["phi_sem_n_cm2_s"][0, 0] == pytest.approx(1.0 / np.sqrt(3))
    assert r["k_lotes"] == 3
    assert "declarado" in r["estimador"]


def test_resumen_muros_excluye_voxels_cero():
    m1 = _mapa([[1.0, 0.0], [0.0, 3.0]], "b1")
    m2 = _mapa([[3.0, 0.0], [0.0, 5.0]], "b2")
    r = estadistica_lotes([m1, m2])
    assert r["muros"]["voxels_activos"] == 2
    assert r["muros"]["phi_medio_n_cm2_s"] == pytest.approx(3.0)
    assert r["muros"]["phi_max_n_cm2_s"] == pytest.approx(4.0)


def test_rechaza_un_solo_lote():
    with pytest.raises(ValueError, match=">= 2 lotes"):
        estadistica_lotes([_mapa([[1.0]], "b1")])


def test_rechaza_geometrias_distintas():
    with pytest.raises(ValueError, match="geometr"):
        estadistica_lotes([_mapa([[1.0]], "b1"),
                           _mapa([[1.0, 2.0]], "b2")])


def test_rechaza_tally_vacio():
    with pytest.raises(ValueError, match="vacío"):
        estadistica_lotes([_mapa([[0.0]], "b1"), _mapa([[0.0]], "b2")])


def test_sem_relativo_declarado():
    m1 = _mapa([[10.0]], "b1")
    m2 = _mapa([[12.0]], "b2")
    r = estadistica_lotes([m1, m2])
    # s = √2, SEM = 1 → rel = 1/11
    assert r["muros"]["sem_relativo_medio"] == pytest.approx(1.0 / 11.0)
    assert "indicativa" in r["estimador"]
