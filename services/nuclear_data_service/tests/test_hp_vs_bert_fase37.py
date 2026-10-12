# -*- coding: utf-8 -*-
"""Tests de hp_vs_bert — Fase 37. Sin MC: tallies sintéticos pequeños."""
import numpy as np
import pytest

import SimpleITK as sitk
from app.domain.hp_vs_bert import comparar_tallies


def _tally(tmp_path, nombre, datos):
    ruta = tmp_path / f"{nombre}.mhd"
    img = sitk.GetImageFromArray(np.array(datos, dtype=np.float32))
    sitk.WriteImage(img, str(ruta))
    return str(ruta)


def test_diferencia_media_detectada(tmp_path):
    # HP con capturas térmicas mayores → fluencia en muros mayor (caso
    # dirigido: HP = 1,2× BERT en todos los voxels).
    b = np.zeros((4, 4, 4)); b[1, 1, 1] = 100.0; b[2, 2, 2] = 200.0
    h = b * 1.2
    c = comparar_tallies(_tally(tmp_path, "b", b), _tally(tmp_path, "h", h))
    assert c.estado == "comparacion_real"
    assert c.delta_rel_media == pytest.approx(0.2, abs=1e-6)
    assert c.delta_rel_max == pytest.approx(0.2, abs=1e-6)
    assert c.voxels_comunes == 2
    assert c.dif_rel_mediana_voxel == pytest.approx(
        abs(1.2 - 1.0) / ((1.2 + 1.0) / 2), abs=1e-6)


def test_mapas_identicos_delta_cero(tmp_path):
    b = np.zeros((3, 3, 3)); b[0, 0, 0] = 50.0
    c = comparar_tallies(_tally(tmp_path, "b1", b), _tally(tmp_path, "b2", b))
    assert c.delta_rel_media == 0.0
    assert c.dif_rel_mediana_voxel == 0.0


def test_malla_distinta_no_demostrable(tmp_path):
    b = np.ones((2, 2, 2)); h = np.ones((3, 3, 3))
    c = comparar_tallies(_tally(tmp_path, "b", b), _tally(tmp_path, "h", h))
    assert c.estado == "no_demostrable"
    assert "mallas distintas" in c.nota


def test_mapa_vacio_no_demostrable(tmp_path):
    b = np.zeros((2, 2, 2)); h = np.ones((2, 2, 2))
    c = comparar_tallies(_tally(tmp_path, "b", b), _tally(tmp_path, "h", h))
    assert c.estado == "no_demostrable"


def test_voxels_no_comunes_no_entran_en_mediana(tmp_path):
    # voxel (0,0,0) activo solo en BERT, (1,1,1) solo en HP: la mediana
    # se calcula SOLO con el voxel común (2,2,2).
    b = np.zeros((3, 3, 3)); h = np.zeros((3, 3, 3))
    b[0, 0, 0] = 10.0; b[2, 2, 2] = 100.0
    h[1, 1, 1] = 10.0; h[2, 2, 2] = 130.0
    c = comparar_tallies(_tally(tmp_path, "b", b), _tally(tmp_path, "h", h))
    assert c.voxels_comunes == 1
    assert c.dif_rel_mediana_voxel == pytest.approx(30.0 / 115.0, abs=1e-6)


def test_escalado_global_vs_forma(tmp_path):
    # HP duplica BERT en un voxel y lo iguala en otro: la mediana voxel
    # a voxel distingue cambio de FORMA del simple escalado global.
    b = np.zeros((2, 2, 2)); b[0, 0, 0] = 100.0; b[1, 1, 1] = 100.0
    h = np.zeros((2, 2, 2)); h[0, 0, 0] = 200.0; h[1, 1, 1] = 100.0
    c = comparar_tallies(_tally(tmp_path, "b", b), _tally(tmp_path, "h", h))
    assert c.delta_rel_media == pytest.approx(0.5, abs=1e-6)
    esperada = float(np.median([100 / 150, 0.0]))
    assert c.dif_rel_mediana_voxel == pytest.approx(esperada, abs=1e-6)
