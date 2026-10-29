"""Tests F84 - DWSIM/COCO sustituto Aspen (stdlib + pytest)."""
import json, os, subprocess, sys, hashlib

EV = "/mnt/agents/work/evidencia_v072/fase84"
EVJ = os.path.join(EV, "dwsim_service_f84.json")
PIPE = "/mnt/agents/work/rpos25/pipelines/dwsim_service_f84.py"


def setup_module(module):
    if not os.path.exists(EVJ):
        subprocess.run([sys.executable, PIPE], check=True)


def test_estado_y_runtime():
    ev = json.load(open(EVJ))
    assert ev["fase"] == "F84"
    assert ev["estado"] in ("completada", "pendiente_entorno")
    assert "DWSIM 9.0.5" in ev["runtime"]["software"]


def test_termodinamica_verificada():
    ev = json.load(open(EVJ))
    if ev["estado"] != "completada":
        import pytest; pytest.skip("runtime no disponible: pendiente_entorno honesto")
    v = ev["verificacion"]
    assert v["h_vapor_100C_vs_IAPWS"]["ok"]
    assert abs(v["h_vapor_100C_vs_IAPWS"]["dwsim"] - 2675.6) < 2.0
    assert 1.2 < v["Q_evap_kW"] < 1.4          # 2 kg/h * (2675.6-335) kJ/kg
    assert 9.0 < v["kWh_lote_8h"] < 12.0


def test_resultados_no_fabricados():
    ev = json.load(open(EVJ))
    if ev["estado"] == "completada":
        assert ev["resultados"]["h_vap_100C_kJkg"] > 2600
    else:
        assert ev["verificacion"] is None       # nunca inventar numeros


def test_registro_append_only():
    lines = open(os.path.join(EV, "registro_dwsim_f84.jsonl")).read().strip().splitlines()
    e = json.loads(lines[-1])
    payload = {k: v for k, v in e.items() if k != "md5"}
    assert hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest() == e["md5"]
