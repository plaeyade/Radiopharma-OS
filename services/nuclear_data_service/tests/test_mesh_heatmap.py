"""Pruebas del módulo de mapas de calor mesh tally (Fase 30)."""
import pytest

from app.domain import mesh_heatmap as mh


def test_origen_obligatorio():
    with pytest.raises(ValueError, match="origen"):
        mh.render_heatmap("/tmp/x.png", origen="")


def test_etiqueta_demo_vs_mc():
    assert "NO ES RESULTADO MC" in mh._etiqueta("declarado_demo")
    assert "MC" in mh._etiqueta("mesh_tally:corrida_001.vtu")
    assert "NO ES RESULTADO" not in mh._etiqueta("mesh_tally:corrida_001.vtu")


def test_malla_demo_dimensiones_y_positividad():
    xx, yy, fl = mh.construir_malla_demo(nx=20, ny=10)
    assert xx.shape == (20, 10)
    assert fl.shape == (20, 10)
    assert (fl > 0).all()


def test_render_matplotlib_genera_png(tmp_path):
    pytest.importorskip("matplotlib")
    out = mh.render_heatmap(str(tmp_path / "h.png"), origen="declarado_demo",
                            backend="matplotlib")
    assert out["backend_usado"] == "matplotlib"
    assert "NO ES RESULTADO MC" in out["etiqueta"]
    import os
    assert os.path.getsize(out["png"]) > 10000


def test_backend_invalido():
    with pytest.raises(ValueError, match="backend"):
        mh.render_heatmap("/tmp/x.png", origen="declarado_demo",
                          backend="unreal_engine")
