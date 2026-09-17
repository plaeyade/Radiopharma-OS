# -*- coding: utf-8 -*-
"""Tests del generador PHITS (Fase 33)."""
import json

import pytest

from app.infrastructure.phits.phits_case import (
    ESTADO_PENDIENTE, PhitsBunkerCase, build_phits_case, phits_status,
)

SPEC = "/mnt/agents/work/evidencia_v072/fase32/nspec_o18.tot"


def test_estado_honesto_sin_binario(monkeypatch):
    monkeypatch.delenv("PHITS_CMD", raising=False)
    monkeypatch.setattr("shutil.which", lambda x: None)
    st = phits_status()
    assert st["estado"] == ESTADO_PENDIENTE
    assert "licencia" in st["que_falta"]
    assert st["ejecutable"] is None


def test_estado_con_binario(monkeypatch):
    monkeypatch.setenv("PHITS_CMD", "/opt/phits/bin/phits")
    assert phits_status()["estado"] == "disponible"


def test_deck_secciones_completas(tmp_path):
    p = build_phits_case(tmp_path, PhitsBunkerCase(spectrum_file=SPEC))
    deck = p.read_text()
    for sec in ("[ T i t l e ]", "[ P a r a m e t e r s ]", "[ S o u r c e ]",
                "[ M a t e r i a l ]", "[ S u r f a c e ]", "[ C e l l ]",
                "[ T - T r a c k ]", "[ E n d ]"):
        assert sec in deck
    assert "proj   = neutron" in deck
    assert "ttrack_bunker.out" in deck


def test_deck_espectro_real(tmp_path):
    p = build_phits_case(tmp_path, PhitsBunkerCase(spectrum_file=SPEC))
    deck = p.read_text()
    assert "ne = 190" in deck          # 190 bins del nspec real
    assert "e-type = 2" in deck
    case = json.loads((tmp_path / "case.json").read_text())
    assert case["spectrum_file"] == SPEC
    assert "pendiente" in case["geometria"]


def test_espectro_insuficiente_rechazado(tmp_path):
    f = tmp_path / "malo.tot"
    f.write_text("# header\n 1.0 5.0\n")
    with pytest.raises(ValueError):
        build_phits_case(tmp_path / "c", PhitsBunkerCase(spectrum_file=str(f)))
