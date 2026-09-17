# -*- coding: utf-8 -*-
"""Tests Fase 35 — estadística de lotes MC del búnker."""
import struct

import pytest

from app.domain.bunker_stats import (combinar_lotes, escribir_tally_combinado,
                                     estadistica)


def _escribir_tally(path, counts, dims=(2, 2, 1), spacing=(10, 10, 10)):
    raw = path.with_suffix(".raw")
    raw.write_bytes(struct.pack(f"<{len(counts)}f", *counts))
    path.write_text(
        "ObjectType = Image\nNDims = 3\nBinaryData = True\n"
        "BinaryDataByteOrderMSB = False\nCompressedData = False\n"
        "TransformMatrix = 1 0 0 0 1 0 0 0 1\nOffset = 0 0 0\n"
        "CenterOfRotation = 0 0 0\nAnatomicalOrientation = RAI\n"
        f"ElementSpacing = {spacing[0]} {spacing[1]} {spacing[2]}\n"
        f"DimSize = {dims[0]} {dims[1]} {dims[2]}\n"
        "ElementType = MET_FLOAT\n"
        f"ElementDataFile = {raw.name}\n")


def test_combinar_dos_lotes_media_y_sigma(tmp_path):
    # lote 1: [10, 20, 0, 0] con 100 historias; lote 2: [14, 16, 0, 0] con 100
    _escribir_tally(tmp_path / "l1.mhd", [10, 20, 0, 0])
    _escribir_tally(tmp_path / "l2.mhd", [14, 16, 0, 0])
    c = combinar_lotes([tmp_path / "l1.mhd", tmp_path / "l2.mhd"], [100, 100])
    assert c["estado"] == "estadistica_real_independiente"
    assert c["voxels_activos"] == 2
    # media por historia: voxel0 = 0.12, voxel1 = 0.18
    assert c["phi_media_muros"] == pytest.approx(0.15)
    assert c["phi_max_muros"] == pytest.approx(0.18)
    # sigma_rel voxel0: std muestral de {0.10, 0.14} = 0.028284;
    # sem = 0.028284/sqrt(2) = 0.02 → rel = 0.02/0.12 = 0.16667
    assert c["sigma_rel_media"] == pytest.approx((0.166667 + 0.111111) / 2,
                                                 rel=1e-3)


def test_un_lote_no_demostrable(tmp_path):
    _escribir_tally(tmp_path / "l1.mhd", [5, 5, 5, 5])
    e = estadistica([tmp_path / "l1.mhd"], [50])
    assert e.estado == "no_demostrable"
    assert e.sigma_rel_media is None


def test_lotes_geometria_distinta_rechazados(tmp_path):
    _escribir_tally(tmp_path / "l1.mhd", [1, 2, 3, 4])
    _escribir_tally(tmp_path / "l2.mhd", [1, 2], dims=(2, 1, 1))
    with pytest.raises(ValueError, match="geometr"):
        combinar_lotes([tmp_path / "l1.mhd", tmp_path / "l2.mhd"], [10, 10])


def test_historias_cero_rechazadas(tmp_path):
    _escribir_tally(tmp_path / "l1.mhd", [1, 2, 3, 4])
    with pytest.raises(ValueError):
        combinar_lotes([tmp_path / "l1.mhd"], [0])


def test_tally_combinado_relegible(tmp_path):
    from app.domain.fluence_connector import leer_tally_mhd
    _escribir_tally(tmp_path / "l1.mhd", [10, 20, 0, 0])
    _escribir_tally(tmp_path / "l2.mhd", [14, 16, 0, 0])
    salida = escribir_tally_combinado([tmp_path / "l1.mhd", tmp_path / "l2.mhd"],
                                      [100, 100], tmp_path / "comb.mhd")
    t = leer_tally_mhd(salida)
    # counts totales = media_por_historia × 200 = {24, 36, 0, 0}
    assert t["counts"].ravel()[0] == pytest.approx(24.0)
    assert t["counts"].ravel()[1] == pytest.approx(36.0)
    assert t["dims"] == [2, 2, 1]


def test_longitudes_distintas_rechazadas(tmp_path):
    _escribir_tally(tmp_path / "l1.mhd", [1, 2, 3, 4])
    with pytest.raises(ValueError):
        combinar_lotes([tmp_path / "l1.mhd"], [10, 20])
