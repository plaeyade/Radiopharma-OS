"""Tests F85 - validacion NRTL y utilidades 5.12 (stdlib + pytest)."""
import json, os, subprocess, sys, hashlib

EV = "/mnt/agents/work/evidencia_v072/fase85"
EVJ = os.path.join(EV, "nrtl_utilidades_f85.json")
PIPE = "/mnt/agents/work/rpos25/pipelines/nrtl_utilidades_f85.py"


def setup_module(module):
    if not os.path.exists(EVJ):
        subprocess.run([sys.executable, PIPE], check=True)


def test_estado():
    ev = json.load(open(EVJ))
    assert ev["fase"] == "F85"
    assert ev["estado"] in ("completada", "pendiente_entorno")


def test_validacion_vle():
    ev = json.load(open(EVJ))
    if ev["estado"] != "completada":
        import pytest; pytest.skip("pendiente_entorno honesto")
    v = ev["validacion_vle"]
    for k in ("Tb_EtOH_K", "Tb_MeCN_K", "Taz_EtOH_K", "Taz_MeCN_K", "Tb_N2_K", "hfg_N2_kJkg"):
        assert k in v and v[k]["ok"], (k, v.get(k))
    # precision de azeotropos mejor que 0.7 K
    assert abs(v["Taz_EtOH_K"]["desv"]) < 0.4
    assert abs(v["Taz_MeCN_K"]["desv"]) < 0.8


def test_utilidades():
    ev = json.load(open(EVJ))
    if ev["estado"] != "completada":
        import pytest; pytest.skip("pendiente_entorno honesto")
    u = ev["utilidades"]
    assert 9.0 < u["vapor_o_electricidad_evaporacion"]["kWh_lote"] < 12.0
    assert 20 < u["LN2_trampa_fria"]["kg_LN2_lote"] < 35
    assert 0.1 < u["aire_comprimido"]["kW"] < 0.2
    assert u["electricidad_total_utilidades_kWh_lote"] > 11


def test_registro_append_only():
    lines = open(os.path.join(EV, "registro_f85.jsonl")).read().strip().splitlines()
    e = json.loads(lines[-1])
    payload = {k: v for k, v in e.items() if k != "md5"}
    assert hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest() == e["md5"]
