#!/usr/bin/env python3
"""Tests F80 — matriz de trazabilidad canónica (stdlib only)."""
import json, pathlib

EV = pathlib.Path("/mnt/agents/work/evidencia_v072/fase80")
E = json.load(open(EV / "matriz_trazabilidad_f80.json"))


def test_campos_canonicos():
    assert E["fase"] == 80 and E["pq"] == "no_declarada_nunca"
    assert "MVP INDUSTRIAL" in E["documento_canonico"]
    assert len(E["md5_fuentes"]["mvp"]) == 32


def test_matriz_completa_60_capitulos():
    assert len(E["matriz"]) == 60
    assert {f"cap{c}" for c in range(1, 61)} == set(E["matriz"])
    for v in E["matriz"].values():
        assert v["estado"] in ("cubierto", "parcial", "sin_fase")
    r = E["resumen"]
    assert r["cubiertos"] + r["parciales"] + r["sin_fase"] == 60


def test_gaps_honestos():
    gaps = E["gaps_explicitos"]["sin_fase"]
    # los gaps duros deben estar declarados
    for cap in ["cap16", "cap26", "cap27", "cap32", "cap35", "cap40", "cap42", "cap43", "cap44", "cap45"]:
        assert cap in gaps
    assert len(gaps) == E["resumen"]["sin_fase"] >= 10
    # núcleo científico debe estar cubierto
    for cap in ["cap15", "cap19", "cap36", "cap49"]:
        assert E["matriz"][cap]["estado"] == "cubierto"


def test_pendientes_y_registro():
    p = E["pendientes_estructurales"]
    assert any("memoria permanente 3" in x for x in p)
    assert any("no_declarada_nunca" in x for x in p)
    assert any("mapeo curado" in a for a in E["advertencias"])
    reg = EV / "registro_trazabilidad.jsonl"
    assert reg.exists() and len(reg.read_text().strip().splitlines()) >= 1
