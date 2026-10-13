"""Tests F55 — deep dive de motores."""
from pipelines.motores_deepdive_f55 import construir_deepdive


def test_todos_los_motores_evaluados():
    d = construir_deepdive()
    for m in ["OpenMC", "DAGMC", "Geant4", "GAMOS", "GATE", "MATLAB",
              "CAD/CADQuery", "mesh/gmsh", "GitHub"]:
        assert m in d["motores"], m
        assert "estado" in d["motores"][m]


def test_veredictos_son_honestos():
    d = construir_deepdive()
    # DAGMC no instalable por pip (probado real en sandbox)
    assert d["motores"]["DAGMC"]["estado"] == "no_instalable_pip"
    # MATLAB propietario
    assert d["motores"]["MATLAB"]["estado"] == "no_aplica"
    # GitHub: solo bundle, sin credenciales
    assert d["motores"]["GitHub"]["estado"] == "entregado_bundle"


def test_decision_es_recomendacion_1810():
    d = construir_deepdive()
    assert "weight windows" in d["decision_1810"]
    assert d["estado"] == "deepdive_honesto_probado"
