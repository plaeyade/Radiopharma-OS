"""Tests F58-multi y F60: lotes teóricos 11C/68Ga/64Cu y eficiencias citadas."""
from __future__ import annotations

import json
import math

from pipelines.lotes_multi_f58 import correr_lotes, ESCENARIOS, _lambda
from pipelines.eficiencias_citadas_f60 import correr_f60, FUENTES


def test_lotes_multi_tres_isotopos(tmp_path):
    lotes = correr_lotes(tmp_path)
    assert set(lotes) == {"C11", "GA68", "CU64"}
    for l in lotes.values():
        assert l["irradiacion"]["eob_gbq"] > 0
        assert l["eos_gbq"] < l["irradiacion"]["eob_gbq"]
        assert l["liberacion"].startswith("no_liberada")
        assert "pendiente_entorno" in l["qc"]


def test_lotes_multi_cadena_monotona(tmp_path):
    for l in correr_lotes(tmp_path).values():
        acts = [l["irradiacion"]["eob_gbq"]] + [
            t["actividad_fin_gbq"] for t in l["traza_etapas"]]
        assert all(a2 <= a1 + 1e-9 for a1, a2 in zip(acts, acts[1:]))


def test_lambda_desde_biblioteca():
    lam = _lambda("c11.json")
    t12_min = math.log(2) / lam / 60.0
    assert abs(t12_min - 20.364) < 0.01


def test_lotes_multi_registro_append_only(tmp_path):
    correr_lotes(tmp_path)
    correr_lotes(tmp_path)
    lineas = (tmp_path / "fase58" / "registro_lotes.jsonl").read_text().strip().splitlines()
    assert len(lineas) == 6


def test_f60_escenarios_citados(tmp_path):
    s = correr_f60(tmp_path)
    assert set(s["escenarios_citados"]) == set(FUENTES)
    for e in s["escenarios_citados"].values():
        assert e["estado_eficiencia"].startswith("fuente_citada")
        assert e["fuente"] and e["url"].startswith("http")
        assert 0 < e["eos_gbq"] < s["irradiacion"]["eob_gbq"]
        assert "recomendacion" in e["despacho"]["estado"]
    assert s["liberacion"].startswith("no_liberada")


def test_f60_iaea_cota_inferior(tmp_path):
    s = correr_f60(tmp_path)
    iaea = s["escenarios_citados"]["iaea_pub1515"]["eos_gbq"]
    holler = s["escenarios_citados"]["holler_2022"]["eos_gbq"]
    assert iaea < holler  # 0.65 < 0.814


def test_f60_multi_citados(tmp_path):
    from pipelines.eficiencias_citadas_multi_f60 import correr_f60_multi, CASOS
    s = correr_f60_multi(tmp_path)
    assert set(s["isotopos"]) == {"C11", "GA68", "CU64"}
    for iso, d in s["isotopos"].items():
        assert d["eob_gbq"] > 0
        assert d["liberacion"].startswith("no_liberada")
        for e in d["escenarios_citados"].values():
            assert e["estado_eficiencia"].startswith("fuente_citada")
            assert e["url"].startswith("http")
            assert 0 < e["eos_gbq"] <= d["eob_gbq"] * 1.0


def test_f63_json_coherente(tmp_path):
    import json as j, math
    p = "/mnt/agents/work/evidencia_v072/fase63/comparacion_csg_dagmc_f63.json"
    r = j.loads(open(p).read())
    csg = r["csg"]["flujo_muro"]; dag = r["dagmc_f62"]["flujo_muro"]
    assert r["diferencia_relativa"] == abs(csg - dag) / dag
    assert r["diferencia_relativa"] < 0.01  # acuerdo sub-porcentual
    assert r["csg"]["particles"] == r["dagmc_f62"]["particles"]


def test_f64_simulacro_etiquetado(tmp_path):
    from pipelines.simulacro_jornada_f64 import correr_simulacro
    s = correr_simulacro(tmp_path)
    assert "NO_produccion_real" in s["estado"]
    assert len(s["lotes"]) == 4
    for l in s["lotes"]:
        assert l["liberacion"].startswith("no_liberada")
        assert "pendiente_entorno" in l["qc"]
        assert l["despacho_gbq"] > 0
    lineas = (tmp_path / "fase64" / "registro_simulacro.jsonl").read_text().strip().splitlines()
    assert len(lineas) == 1
