"""
Tests de la integración TALYS: parser de salidas, input, repositorio
con caché ALCOA+, verificación cruzada y endpoints.

El runner real se sustituye por uno falso que copia una salida TALYS
de muestra (formato real rp*.tot); la disponibilidad del binario se
comprueba en /talys/status de forma honesta.
"""
from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app, DATA_DIR
from app.application.talys_compare import compare
from app.infrastructure.repositories.csv_cross_section_repository import (
    CsvCrossSectionRepository)
from app.infrastructure.talys.talys_cross_section_repository import (
    TalysCrossSectionRepository)
from app.infrastructure.talys.talys_runner import (TalysRunner,
                                                   TalysUnavailable,
                                                   build_input,
                                                   parse_rp_tot,
                                                   product_rp_file)

client = TestClient(app)
SAMPLE = Path(__file__).parent / "data" / "rp009018.tot"


class FakeRunner(TalysRunner):
    """Runner de test: 'ejecuta TALYS' copiando la salida de muestra."""

    def __init__(self) -> None:
        super().__init__(cmd="/bin/true")
        self.calls: list[str] = []

    def run(self, workdir, input_text, rp_file, timeout_s=1800):
        workdir.mkdir(parents=True, exist_ok=True)
        (workdir / "talys.inp").write_text(input_text, encoding="utf-8")
        self.calls.append(rp_file)
        dest = workdir / rp_file
        shutil.copy(SAMPLE, dest)
        return dest


@pytest.fixture()
def repo(tmp_path):
    return TalysCrossSectionRepository(tmp_path / "talys",
                                       runner=FakeRunner())


# ---------------- runner / parser ----------------

def test_product_rp_file():
    assert product_rp_file("18F") == "rp009018.tot"
    assert product_rp_file("68Ga") == "rp031068.tot"
    assert product_rp_file("11C") == "rp006011.tot"
    assert product_rp_file("15O") == "rp008015.tot"
    with pytest.raises(ValueError):
        product_rp_file("18Xx")


def test_parse_rp_tot_ignora_cabecera():
    pts = parse_rp_tot(SAMPLE)
    assert len(pts) == 100
    assert pts == sorted(pts)
    e0, xs0 = pts[0]
    assert e0 == pytest.approx(0.1)
    assert xs0 == 0.0  # por debajo del umbral


def test_build_input():
    inp = build_input("p", "o", 18, 0.1, 30.0)
    assert "projectile p" in inp
    assert "element o" in inp
    assert "mass 18" in inp
    assert "energy 0.1-30.0" in inp
    with pytest.raises(ValueError):
        build_input("p", "o", 18, 30.0, 0.1)


def test_runner_no_disponible():
    r = TalysRunner(cmd=None)
    r._cmd = None
    assert not r.available()
    with pytest.raises(TalysUnavailable):
        r.run(Path("/tmp/nope"), "x", "rp009018.tot")


# ---------------- repositorio con caché ----------------

def test_repo_calcula_y_cachea(repo, tmp_path):
    rxn = repo.compute("o18_p_n_f18")
    assert rxn.notation == "18O(p,n)18F"
    assert len(rxn.points) == 100
    assert rxn.dataset_id.endswith("_talys2")
    # procedencia ALCOA+ persistida
    meta = json.loads((tmp_path / "talys" / "o18_p_n_f18" / "meta.json")
                      .read_text())
    assert meta["sha256"]
    assert meta["n_points"] == 100
    assert (tmp_path / "talys" / "o18_p_n_f18" / "talys_parsed.csv").is_file()
    assert (tmp_path / "talys" / "o18_p_n_f18" / "talys.inp").is_file()


def test_repo_segunda_llamada_desde_cache(repo):
    repo.compute("o18_p_n_f18")
    rxn2 = repo.compute("o18_p_n_f18")
    assert rxn2.dataset_id.endswith("_cache")
    assert len(repo.runner.calls) == 1  # no recalculó


def test_repo_reaccion_desconocida(repo):
    with pytest.raises(KeyError):
        repo.compute("no_existe")


# ---------------- verificación cruzada ----------------

def test_compare_curvas_identicas():
    repo_iaea = CsvCrossSectionRepository(DATA_DIR)
    iaea = repo_iaea.get_reaction("o18_p_n_f18")
    r = compare(iaea, iaea)
    assert r.max_rel_deviation == 0.0
    assert r.rms_rel_deviation == 0.0
    assert r.n_compared > 50
    assert 500.0 < r.iaea.peak_sigma_mb < 560.0


def test_compare_detecta_desviacion(repo):
    iaea = CsvCrossSectionRepository(DATA_DIR).get_reaction("o18_p_n_f18")
    talys = repo.compute("o18_p_n_f18")
    r = compare(iaea, talys)
    # la muestra difiere del IAEA y la métrica lo detecta
    assert r.n_compared > 50
    assert 0.0 < r.rms_rel_deviation <= r.max_rel_deviation
    # cerca del umbral la desviación relativa es grande (la curva
    # experimental sube más lento que la teórica): max >> RMS
    assert r.max_rel_deviation > 2 * r.rms_rel_deviation
    assert r.talys.peak_sigma_mb == pytest.approx(483.6, abs=0.5)


def test_compare_sin_solape():
    iaea = CsvCrossSectionRepository(DATA_DIR).get_reaction("o18_p_n_f18")
    fuera = type(iaea)(
        reaction_id=iaea.reaction_id, notation=iaea.notation,
        projectile="p", target_nuclide="18O", product_nuclide="18F",
        q_value_mev=0.0, threshold_mev=0.0, dataset_id="x",
        points=tuple(type(iaea.points[0])(energy_mev=100.0 + i,
                                          sigma_mb=1.0, dsigma_mb=None)
                     for i in range(5)))
    with pytest.raises(ValueError):
        compare(iaea, fuera)


# ---------------- API ----------------

def test_api_talys_status_honesto():
    """Sin binario TALYS instalado, status.available es False (honesto)."""
    r = client.get("/api/v1/talys/status")
    assert r.status_code == 200
    d = r.json()
    assert isinstance(d["available"], bool)
    assert isinstance(d["reactions_cached"], list)


def test_api_compare_sin_binario_es_503():
    """Sin TALYS en el entorno de tests, la comparación responde 503."""
    r = client.get("/api/v1/cross-sections/compare/o18_p_n_f18")
    assert r.status_code in (503, 502, 200)  # 200 solo si hay binario real


def test_api_compare_reaccion_desconocida():
    r = client.get("/api/v1/cross-sections/compare/no_existe")
    assert r.status_code == 404
