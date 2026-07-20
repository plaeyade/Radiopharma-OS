"""
Tests del acoplamiento Elmer FEM: generación de malla nativa, SIF,
parser de SaveScalars, estado honesto del runner y comportamiento de la
API sin binario (503, nunca simulado).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.infrastructure.elmer.elmer_case import (BC_COOLED,
                                                 ElmerThermalCase,
                                                 build_case, write_mesh,
                                                 write_sif)
from app.infrastructure.elmer.elmer_runner import (ElmerRunner,
                                                   parse_save_scalars)
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

CASE = ElmerThermalCase(beam_power_w=720.0, spot_radius_cm=0.5642,
                        target_thickness_cm=0.5, conductivity_w_cm_k=0.006,
                        film_coeff_w_cm2_k=0.5, coolant_temp_k=293.15,
                        beam_sigma_cm=0.15)


# --- parser SaveScalars ------------------------------------------------------

SAMPLE_SCALARS = """! ElmerFEM SaveScalars output
! name: res: temperature max
! name: res: temperature mean
       1   3.42150000E+02   3.01870000E+02
       2   3.42160000E+02   3.01880000E+02
"""


def test_parser_ultima_fila_sin_columna_paso():
    vals = parse_save_scalars(SAMPLE_SCALARS)
    assert vals == pytest.approx([342.16, 301.88])


def test_parser_sin_datos():
    with pytest.raises(ValueError):
        parse_save_scalars("! solo cabecera\n! nada mas\n")


def test_parser_tolera_filas_no_numericas():
    vals = parse_save_scalars("cabecera libre\n1 10.0 20.0\nnotas finales\n")
    assert vals == pytest.approx([10.0, 20.0])


# --- generación de malla nativa ----------------------------------------------

def test_mesh_header_coherente(tmp_path: Path):
    mesh = write_mesh(tmp_path, CASE, n_r=10, n_z=5)
    header = (mesh / "mesh.header").read_text().split()
    n_nodes, n_elems, n_bdry = (int(header[0]), int(header[1]),
                                int(header[2]))
    assert n_nodes == 11 * 6
    assert n_elems == 10 * 5
    assert n_bdry == 10
    nodes = (mesh / "mesh.nodes").read_text().strip().splitlines()
    assert len(nodes) == n_nodes
    # primer nodo en el origen, último en (R, L)
    assert nodes[0].split()[2:] == ["0.0000000000e+00", "0.0000000000e+00", "0.0"]
    last = nodes[-1].split()
    assert float(last[2]) == pytest.approx(CASE.spot_radius_cm / 100.0)
    assert float(last[3]) == pytest.approx(CASE.target_thickness_cm / 100.0)
    # elementos: referencias de nodo válidas
    for line in (mesh / "mesh.elements").read_text().strip().splitlines():
        toks = line.split()
        assert toks[1] == "1" and toks[2] == "404"
        assert all(1 <= int(n) <= n_nodes for n in toks[3:7])
    # frontera: solo la cara refrigerada
    for line in (mesh / "mesh.boundary").read_text().strip().splitlines():
        toks = line.split()
        assert toks[1] == str(BC_COOLED) and toks[2] == "202"


def test_mesh_validacion(tmp_path: Path):
    with pytest.raises(ValueError):
        write_mesh(tmp_path, CASE, n_r=1, n_z=5)


# --- generación de SIF --------------------------------------------------------

def test_sif_contenido_gaussiano(tmp_path: Path):
    sif = write_sif(tmp_path, CASE).read_text()
    assert 'Equation = "Heat Equation"' in sif
    assert 'Coordinate System = "Axi Symmetric"' in sif
    assert "Real MATC" in sif and "exp(-(tx(0))^2" in sif
    # unidades SI: k = 0.006 W/cm·K → 0.6 W/m·K ; h = 0.5 → 5000 W/m²·K
    assert "Heat Conductivity = Real 6.0000000000e-01" in sif
    assert "Heat Transfer Coefficient = Real 5.0000000000e+03" in sif
    assert "External Temperature = Real 2.931500e+02" in sif
    assert 'Filename = "scalars.dat"' in sif


def test_sif_fuente_uniforme_sin_sigma(tmp_path: Path):
    case = ElmerThermalCase(**{**CASE.__dict__, "beam_sigma_cm": None})
    sif = write_sif(tmp_path, case).read_text()
    assert "Heat Source = Real" in sif and "Real MATC" not in sif
    # q''' = P/V = 720 / (π·0.5642²·0.5 cm³→m³)
    import math
    v = math.pi * (0.5642e-2) ** 2 * 0.5e-2
    assert f"{720.0 / v:.10e}" in sif


def test_build_case_completo(tmp_path: Path):
    sif = build_case(tmp_path, CASE, n_r=6, n_z=3)
    assert sif.exists()
    assert (tmp_path / "mesh" / "mesh.header").exists()


# --- runner honesto ------------------------------------------------------------

def test_runner_no_disponible_sin_binario():
    runner = ElmerRunner(cmd="elmersolver-inexistente-xyz")
    assert not runner.available()
    assert runner.version() is None
    from app.infrastructure.elmer.elmer_runner import ElmerUnavailable
    with pytest.raises(ElmerUnavailable):
        runner.run(Path("/tmp"))


def test_runner_detecta_binario(tmp_path: Path):
    # Fake ElmerSolver: escribe scalars.dat y sale con rc=0
    fake = tmp_path / "fake_elmer.sh"
    fake.write_text("#!/bin/sh\necho '1 350.0 310.0' > scalars.dat\nexit 0\n")
    fake.chmod(0o755)
    runner = ElmerRunner(cmd=str(fake))
    assert runner.available()
    vals = runner.run(tmp_path)
    assert vals == pytest.approx([350.0, 310.0])
    assert (tmp_path / "elmer.log").exists()


def test_runner_rc_no_cero(tmp_path: Path):
    fake = tmp_path / "fake_fail.sh"
    fake.write_text("#!/bin/sh\nexit 3\n")
    fake.chmod(0o755)
    from app.infrastructure.elmer.elmer_runner import ElmerError
    with pytest.raises(ElmerError):
        ElmerRunner(cmd=str(fake)).run(tmp_path)


# --- API honesta ---------------------------------------------------------------

def test_api_elmer_status():
    resp = client.get("/api/v1/elmer/status")
    assert resp.status_code == 200
    d = resp.json()
    assert set(d) >= {"available", "cmd", "version", "solver"}
    assert isinstance(d["available"], bool)
    if not d["available"]:
        assert d["version"] is None


def test_api_elmer_compare_503_sin_binario():
    if client.get("/api/v1/elmer/status").json()["available"]:
        pytest.skip("ElmerSolver instalado: el 503 no aplica")
    resp = client.post("/api/v1/elmer/thermal/compare", json={
        "beam_energy_mev": 18.0, "current_ua": 40.0, "beam_spot_cm2": 1.0,
        "target_thickness_cm": 0.5, "conductivity_w_cm_k": 0.006,
        "film_coeff_w_cm2_k": 0.5, "coolant_temp_k": 293.15,
        "beam_sigma_cm": 0.15})
    assert resp.status_code == 503
    assert "ElmerSolver" in resp.json()["detail"]


def test_api_elmer_compare_validacion():
    resp = client.post("/api/v1/elmer/thermal/compare", json={
        "beam_energy_mev": 18.0, "current_ua": 40.0, "beam_spot_cm2": -1.0,
        "target_thickness_cm": 0.5, "conductivity_w_cm_k": 0.006,
        "film_coeff_w_cm2_k": 0.5, "coolant_temp_k": 293.15})
    assert resp.status_code == 422
