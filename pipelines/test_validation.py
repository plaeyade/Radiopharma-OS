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
                        "evidencia_runtimes_rcae",
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


def test_evidencia_runtimes_rcae_estado_honesto(tmp_path, monkeypatch):
    """Sin ficheros de evidencia: checks honestos, no bloqueantes, nunca
    inventados; con evidencia real fabricada: los checks la leen."""
    monkeypatch.setattr(vr, "ROOT", tmp_path)
    checks = vr.evidencia_runtimes_rcae()
    nombres = {c["nombre"] for c in checks}
    assert {"bateria_runtimes", "registro_rcae_fase8",
            "pq_periodico"} <= nombres
    assert all(c["ok"] for c in checks)  # honestos, no bloquean

    # evidencia real fabricada: la batería con MC desviado NO pasa
    out = tmp_path / "out"
    out.mkdir()
    (out / "prueba_teorica_fisica.json").write_text(json.dumps({
        "secciones": {"runtimes_cientificos": {
            "TALYS": {"ejecucion": "real",
                      "desviacion_media_abs_vs_iaea2021_pct": 23.6},
            "OpenGATE_Geant4": {"ejecucion": "real",
                                "edep_total_mev": 31980.9,
                                "desviacion_pct": -0.06},
            "ElmerFEM": {"ejecucion": "real", "t_max_k": 801785.5}}}}))
    checks2 = vr.evidencia_runtimes_rcae()
    por_nombre = {c["nombre"]: c for c in checks2}
    assert por_nombre["bateria_mc_real"]["ok"]
    # MC con desviación absurda → el check lo detecta (no se infla)
    (out / "prueba_teorica_fisica.json").write_text(json.dumps({
        "secciones": {"runtimes_cientificos": {
            "TALYS": {"ejecucion": "real",
                      "desviacion_media_abs_vs_iaea2021_pct": 23.6},
            "OpenGATE_Geant4": {"ejecucion": "real",
                                "edep_total_mev": 100.0,
                                "desviacion_pct": -68.0},
            "ElmerFEM": {"ejecucion": "real", "t_max_k": 801785.5}}}}))
    checks3 = vr.evidencia_runtimes_rcae()
    assert not {c["nombre"]: c for c in checks3}["bateria_mc_real"]["ok"]

    # registro RCAE con MC marcado cumple (deshonesto) → NO pasa
    (out / "registro_rcae_fase8.json").write_text(json.dumps({
        "simulaciones": [{"integridad_verificada": True}],
        "evaluaciones": [{"requisito_id": "REQ-PT-19.14-MC",
                          "estado": "cumple"}]}))
    checks4 = vr.evidencia_runtimes_rcae()
    assert not {c["nombre"]: c for c in checks4}["registro_rcae_fase8"]["ok"]
