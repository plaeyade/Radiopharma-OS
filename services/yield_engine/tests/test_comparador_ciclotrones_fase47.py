"""Tests F47 — comparador KIUBE vs PETtrace (regla 49.11: fuentes citadas)."""
import json

import pytest

from app.domain.comparador_ciclotrones import (
    FUENTES,
    SPECS,
    comparar,
    gbq_por_uA,
)


def test_toda_spec_tiene_fuente_o_pendiente():
    for equipo, specs in SPECS.items():
        for campo, s in specs.items():
            if not isinstance(s, dict) or "valor" not in s:
                continue
            if s["valor"] is None:
                assert s.get("estado") == "pendiente_fuente"
            else:
                assert s.get("fuente") in FUENTES, (equipo, campo)


def test_metrica_derivada_declarada():
    k = gbq_por_uA("IBA_Cyclone_KIUBE")
    p = gbq_por_uA("GE_PETtrace_800")
    assert k["estado"] == "derivado_declarado"
    assert k["valor"] == pytest.approx(1110.0 / 300, rel=1e-9)
    assert p["valor"] == pytest.approx(648.0 / 160, rel=1e-9)
    assert len(k["fuentes"]) == 2


def test_comparar_diferencias_correctas():
    r = comparar()
    assert r["diferencias"]["energia_protones_MeV"] == pytest.approx(1.5)
    assert r["diferencias"]["corriente_max_uA"] == 140
    assert r["diferencias"]["f18_max_GBq_2h"] == pytest.approx(462.0)
    assert "18.10" in r["nota_honesta"]


def test_comparar_serializable_alcoa():
    s = json.dumps(comparar(), ensure_ascii=False)
    assert "KIUBE" in s and "pendiente_fuente" in s
