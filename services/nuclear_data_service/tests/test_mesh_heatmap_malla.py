# -*- coding: utf-8 -*-
"""Tests Fase 32: render_heatmap con malla MC real."""
import numpy as np
import pytest

from app.domain.mesh_heatmap import render_heatmap


def test_malla_real_etiqueta_mc(tmp_path):
    malla = np.ones((20, 30)) * 10.0
    meta = render_heatmap(str(tmp_path / "h.png"),
                          origen="mesh_tally:corrida_x",
                          malla=malla)
    assert meta["etiqueta"] == "FLUENCIA MC — mesh tally real"
    assert meta["celdas"] == [20, 30]
    assert meta["flujo_max"] == pytest.approx(10.0)


def test_malla_real_png_generado(tmp_path):
    malla = np.random.default_rng(1).random((15, 15)) + 1.0
    meta = render_heatmap(str(tmp_path / "h.png"),
                          origen="mesh_tally:corrida_y",
                          malla=malla, backend="matplotlib")
    import os
    assert os.path.getsize(meta["png"]) > 10_000


def test_sin_malla_sigue_demo_marcada(tmp_path):
    meta = render_heatmap(str(tmp_path / "d.png"), origen="declarado_demo")
    assert "NO ES RESULTADO MC" in meta["etiqueta"]


def test_origen_sigue_obligatorio(tmp_path):
    with pytest.raises(ValueError):
        render_heatmap(str(tmp_path / "h.png"), origen="",
                       malla=np.ones((5, 5)))
