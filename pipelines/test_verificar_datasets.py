"""Pruebas del pipeline de verificación de datasets (ALCOA+ — Fase 18)."""
from __future__ import annotations

import csv
import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verificar_datasets as vd  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "znp68ga4.html"
DATA = (Path(__file__).resolve().parents[1]
        / "services" / "yield_engine" / "data")


def test_dataset_zn68_verificado_contra_fuente_oficial():
    """El CSV versionado coincide punto a punto con la tabla IAEA."""
    r = vd.verificar_dataset(DATA, "zn68_p_n_ga68", fuente_local=FIXTURE)
    assert r["estado"] == "verificado"
    assert r["n_puntos_versionados"] == r["n_puntos_fuente"] == 60
    assert r["discrepancias"] == []


def test_discrepancia_detectada():
    """Un dato alterado produce veredicto `discrepancia`, nunca verificado."""
    with tempfile.TemporaryDirectory() as td:
        data = Path(td)
        (data / "cross_sections" / "fake").mkdir(parents=True)
        (data / "reactions.json").write_text(json.dumps({
            "zn68_p_n_ga68": {"notation": "68Zn(p,n)68Ga",
                              "threshold_mev": 3.76, "q_value_mev": -3.7,
                              "dataset_id": "fake",
                              "file": "cross_sections/fake/fake.csv"}}))
        with open(data / "cross_sections" / "fake" / "fake.csv", "w",
                  newline="") as fh:
            fh.write('# url: https://www-nds.iaea.org/medical/znp68ga4.html\n')
            w = csv.writer(fh)
            w.writerow(["energy_MeV", "sigma_mb", "dsigma_mb"])
            w.writerow([12.0, 999.0, 51.4])   # oficial: 868.9 → alterado
        r = vd.verificar_dataset(data, "zn68_p_n_ga68",
                                 fuente_local=FIXTURE)
        assert r["estado"] == "discrepancia"
        assert r["discrepancias"][0]["energia_mev"] == 12.0


def test_fuente_inaccesible_honesto():
    """Fuente inaccesible → `no_verificable`, nunca se asume."""
    with tempfile.TemporaryDirectory() as td:
        data = Path(td)
        (data / "cross_sections" / "fake").mkdir(parents=True)
        (data / "reactions.json").write_text(json.dumps({
            "zn68_p_n_ga68": {"notation": "x", "threshold_mev": 0,
                              "q_value_mev": 0, "dataset_id": "fake",
                              "file": "cross_sections/fake/fake.csv"}}))
        (data / "cross_sections" / "fake" / "fake.csv").write_text(
            "# url: http://127.0.0.1:9/inexistente\n"
            "energy_MeV,sigma_mb,dsigma_mb\n12.0,868.9,51.3\n")
        r = vd.verificar_dataset(data, "zn68_p_n_ga68")
        assert r["estado"] == "no_verificable"
        assert "inaccesible" in r["motivo"]


FIXTURE_GA67 = Path(__file__).parent / "fixtures" / "zn8p7ga4.html"


def test_dataset_ga67_layout_sin_incertidumbre():
    """68Zn(p,2n)67Ga: layout de 8 columnas sin dσ — verificado igual."""
    r = vd.verificar_dataset(DATA, "zn68_p_2n_ga67",
                             fuente_local=FIXTURE_GA67)
    assert r["estado"] == "verificado"
    assert r["n_puntos_versionados"] == r["n_puntos_fuente"] == 68
    assert r["discrepancias"] == []


FIXTURE_CU64 = Path(__file__).parent / "fixtures" / "nip64cu4.html"


def test_dataset_cu64_verificado_contra_fuente_oficial():
    """64Ni(p,n)64Cu: el CSV versionado coincide punto a punto con IAEA."""
    r = vd.verificar_dataset(DATA, "ni64_p_n_cu64",
                             fuente_local=FIXTURE_CU64)
    assert r["estado"] == "verificado"
    assert r["n_puntos_versionados"] == r["n_puntos_fuente"] == 46
    assert r["discrepancias"] == []
