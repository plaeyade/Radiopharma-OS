"""Tests F58 — lote FDG extremo a extremo."""
import json
from pipelines.lote_fdg_f58 import correr_lote, ETAPAS


def test_eob_desde_dataset_iaea(tmp_path):
    l = correr_lote(tmp_path)
    ir = l["irradiacion"]
    assert ir["dataset"] == "o18_p_n_f18_iaea2021"
    assert ir["eob_gbq"] > 0
    assert 0 < ir["factor_saturacion"] < 1


def test_cadena_monotona_y_qc_nunca_liberado(tmp_path):
    l = correr_lote(tmp_path)
    acts = [l["irradiacion"]["eob_gbq"]] + \
           [e["actividad_fin_gbq"] for e in l["traza_etapas"]] + \
           [l["despacho"]["actividad_gbq"]]
    assert all(a > b for a, b in zip(acts, acts[1:]))  # solo pérdidas+decaimiento
    assert l["liberacion"].startswith("no_liberada")
    assert "pendiente_entorno" in l["qc"]


def test_flujo_canonico_eds_21_7(tmp_path):
    l = correr_lote(tmp_path)
    assert [e["etapa"] for e in l["traza_etapas"]] == \
           ["transfer", "reaction", "purification", "formulation",
            "sterile_filtration"]


def test_registro_append_only(tmp_path):
    correr_lote(tmp_path); correr_lote(tmp_path)
    lineas = (tmp_path / "fase58" / "registro_lotes.jsonl").read_text().strip().splitlines()
    assert len(lineas) == 2  # nunca se sobrescribe
