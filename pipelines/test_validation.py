"""Pruebas del pipeline de validación consolidada (Fase 9, 18.13)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validation_report as vr  # noqa: E402


def test_validacion_cientifica_en_vivo():
    checks = vr.validacion_cientifica()
    nombres = {c["nombre"] for c in checks}
    assert "reproducibilidad_yield_engine" in nombres
    assert "decaimiento_exacto" in nombres
    assert "monte_carlo_vs_determinista" in nombres
    assert "puerta_8_11_elmer" in nombres
    for c in checks:
        assert c["ok"], f"{c['nombre']}: {c['detalle']}"
        assert c["detalle"] and c["referencia"]


def test_pre_despliegue():
    checks = vr.validacion_pre_despliegue()
    deps = next(c for c in checks if c["nombre"] == "dependencias")
    assert deps["ok"], deps["detalle"]
    solvers = next(c for c in checks if c["nombre"] == "disponibilidad_solvers")
    assert solvers["ok"]  # informativo, nunca bloquea
    assert "talys" in solvers["detalle"]


def test_reporte_estructura_y_honestidad():
    rep = vr.construir_reporte()
    niv = rep["niveles"]
    assert set(niv) == {"pruebas_unitarias_integracion", "validacion_cientifica",
                        "pruebas_rendimiento", "validacion_pre_despliegue",
                        "validacion_clinica", "validacion_regulatoria"}
    # 18.13: clínica y regulatoria nunca se declaran completas
    assert niv["validacion_clinica"]["estado"] == "no_iniciada"
    assert niv["validacion_regulatoria"]["estado"] == "no_iniciada"
    assert rep["veredicto_obligatorio"] in ("apto", "no_apto")
    assert niv["pruebas_unitarias_integracion"]["total_tests"] > 0


def test_main_escribe_json_y_exit_code(tmp_path):
    out = tmp_path / "rep.json"
    sys.argv = ["validation_report.py", "--out", str(out)]
    rc = vr.main()
    rep = json.loads(out.read_text())
    assert rep["reporte"].startswith("Validación Radiopharma OS")
    assert rc == (0 if rep["veredicto_obligatorio"] == "apto" else 1)


def test_run_py_propaga_error():
    with pytest.raises(RuntimeError):
        vr._run_py("yield_engine", "raise SystemExit(3)")
