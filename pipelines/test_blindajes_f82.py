"""Tests F82 - blindajes Zumaya (stdlib + pytest)."""
import json, os, subprocess, sys, hashlib

EV = "/mnt/agents/work/evidencia_v072/fase82"
EVJ = os.path.join(EV, "blindajes_zumaya_f82.json")
PIPE = "/mnt/agents/work/rpos25/pipelines/blindajes_zumaya_f82.py"


def setup_module(module):
    if not os.path.exists(EVJ):
        subprocess.run([sys.executable, PIPE], check=True)


def test_fuente_y_salas():
    ev = json.load(open(EVJ))
    assert ev["fase"] == "F82"
    assert len(ev["fuente"]["md5"]) == 32
    assert set(ev["salas"]) == {"acelerador_lineal", "braquiterapia_hdr", "gamma_knife",
                                "pet_ct", "spect_ct", "medicina_nuclear_I131"}


def test_criterios_y_cargas():
    ev = json.load(open(EVJ))
    s = ev["salas"]
    assert s["acelerador_lineal"]["criterio"] == "NCRP-151"
    assert s["acelerador_lineal"]["carga_trabajo"]["dosis_por_paciente_cGy"] == 300
    assert s["gamma_knife"]["carga_trabajo"]["actividad_max_Ci"] == 6600
    assert s["pet_ct"]["criterio"] == "AAPM Task Group 108 (restrictivo)"
    assert s["medicina_nuclear_I131"]["carga_trabajo"]["dosis_max_I131_mCi"] == 200
    assert s["braquiterapia_hdr"]["carga_trabajo"]["dosis_por_paciente_Gy"] == 7


def test_coherencia_interna():
    ev = json.load(open(EVJ))
    for c in ev["coherencia_interna"]:
        assert c["ok"], c["check"]


def test_registro_append_only():
    reg = os.path.join(EV, "registro_blindajes_f82.jsonl")
    lines = open(reg).read().strip().splitlines()
    e = json.loads(lines[-1])
    payload = {k: v for k, v in e.items() if k != "md5"}
    assert hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest() == e["md5"]
    assert len(e["md5_fuente"]) == 32
