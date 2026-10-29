"""Tests F86 - utilidades completas 5.12 (stdlib + pytest)."""
import json, os, subprocess, sys, hashlib

EV = "/mnt/agents/work/evidencia_v072/fase86"
EVJ = os.path.join(EV, "utilidades_completas_f86.json")
PIPE = "/mnt/agents/work/rpos25/pipelines/utilidades_completas_f86.py"


def setup_module(module):
    if not os.path.exists(EVJ):
        subprocess.run([sys.executable, PIPE], check=True)


def test_estructura_y_fuentes():
    ev = json.load(open(EVJ))
    assert ev["fase"] == "F86" and ev["estado"] == "completada"
    assert "F85" in ev["fuentes"] and "F84" in ev["fuentes"]
    assert len(ev["items"]) == 8


def test_hvac_analitico():
    ev = json.load(open(EVJ))
    # Q = 1.2*1.005*(25*20/3600)*8 = 1.34 kW
    assert 1.2 < ev["hvac_cuarto_caliente_kW"] < 1.5


def test_totales_coherentes():
    ev = json.load(open(EVJ))
    t = ev["totales"]
    assert t["costo_utilidades_mxn_lote"] == round(sum(i["costo_mxn_lote"] for i in ev["items"]), 2)
    assert 300 < t["costo_utilidades_mxn_lote"] < 800
    assert 18 < t["electricidad_kWh_lote"] < 28
    for i in ev["items"]:
        assert i["costo_mxn_lote"] >= 0 and i["fuente"]


def test_registro_append_only():
    lines = open(os.path.join(EV, "registro_f86.jsonl")).read().strip().splitlines()
    e = json.loads(lines[-1])
    payload = {k: v for k, v in e.items() if k != "md5"}
    assert hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest() == e["md5"]
