"""Tests F83 - blindaje ciclotron Zumaya (stdlib + pytest)."""
import json, os, subprocess, sys, hashlib

EV = "/mnt/agents/work/evidencia_v072/fase83"
EVJ = os.path.join(EV, "blindaje_ciclotron_f83.json")
PIPE = "/mnt/agents/work/rpos25/pipelines/blindaje_ciclotron_f83.py"


def setup_module(module):
    if not os.path.exists(EVJ):
        subprocess.run([sys.executable, PIPE], check=True)


def test_fuente_y_regimen():
    ev = json.load(open(EVJ))
    assert ev["fase"] == "F83"
    assert len(ev["fuente"]["md5"]) == 32
    c = ev["ciclotron"]["carga_trabajo"]
    assert c["energia_MeV"] == 18 and c["corriente_uA"] == 300
    assert c["horas_irradiacion_dia"] == 8
    assert ev["ciclotron"]["criterio"].startswith("NCRP-144")


def test_espesores():
    ev = json.load(open(EVJ))
    l = ev["ciclotron"]["losa_bunker"]["espesor_m"]
    assert l == [2.3, 2.5]
    assert ev["ciclotron"]["densidad_blindaje_g_cm3"] == 3.5
    assert ev["ciclotron"]["muros_adicionales_cm"]["espesor"] == 30
    assert ev["ciclotron"]["pendiente_declarado"] == "simulacion Monte Carlo"


def test_cotejo():
    ev = json.load(open(EVJ))
    cot = {c["check"]: c for c in ev["cotejo_interno"]}
    a = cot["losa_IBA_g_cm2_vs_muro_F70"]
    assert abs(a["losa_IBA_g_cm2"][0] - 805.0) < 1e-9
    assert abs(a["muro_F70_g_cm2"] - 495.85) < 0.1
    assert 1.5 < a["razon"] < 1.7


def test_registro_append_only():
    lines = open(os.path.join(EV, "registro_blindaje_ciclotron_f83.jsonl")).read().strip().splitlines()
    e = json.loads(lines[-1])
    payload = {k: v for k, v in e.items() if k != "md5"}
    assert hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest() == e["md5"]
