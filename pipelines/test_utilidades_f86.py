"""Tests F86 - utilidades completas 5.12 (stdlib + pytest)."""
_RPOS_RAIZ = __import__("os").environ.get("RPOS_AGENTS_ROOT", "/mnt/agents")  # raíz de evidencia/datos externos
_RPOS_REPO = str(__import__("pathlib").Path(__file__).resolve().parents[1])  # raíz de este repo
import json, os, subprocess, sys, hashlib

import pytest

EV = f"{_RPOS_RAIZ}/work/evidencia_v072/fase86"
EVJ = os.path.join(EV, "utilidades_completas_f86.json")
PIPE = f"{_RPOS_REPO}/pipelines/utilidades_completas_f86.py"


_ERROR_SETUP = None


def setup_module(module):
    global _ERROR_SETUP
    if not os.path.exists(EVJ):
        try:
            subprocess.run([sys.executable, PIPE], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:   # p. ej. sin evidencia F85: lo resuelve cada prueba
            _ERROR_SETUP = e


def _generada():
    if _ERROR_SETUP is not None:
        raise _ERROR_SETUP


def _completa():
    _generada()
    ev = json.load(open(EVJ))
    if ev["estado"] != "completada":
        pytest.skip(f"F86 {ev['estado']}: F85 sin resultados DWSIM en este entorno")
    return ev


def test_estructura_y_fuentes():
    ev = _completa()
    assert ev["fase"] == "F86" and ev["estado"] == "completada"
    assert "F85" in ev["fuentes"] and "F84" in ev["fuentes"]
    assert len(ev["items"]) == 8


def test_hvac_analitico():
    _generada()
    ev = json.load(open(EVJ))
    # Q = 1.2*1.005*(25*20/3600)*8 = 1.34 kW
    assert 1.2 < ev["hvac_cuarto_caliente_kW"] < 1.5


def test_totales_coherentes():
    ev = _completa()
    t = ev["totales"]
    assert t["costo_utilidades_mxn_lote"] == round(sum(i["costo_mxn_lote"] for i in ev["items"]), 2)
    assert 300 < t["costo_utilidades_mxn_lote"] < 800
    assert 18 < t["electricidad_kWh_lote"] < 28
    for i in ev["items"]:
        assert i["costo_mxn_lote"] >= 0 and i["fuente"]


def test_registro_append_only():
    _generada()
    lines = open(os.path.join(EV, "registro_f86.jsonl")).read().strip().splitlines()
    e = json.loads(lines[-1])
    payload = {k: v for k, v in e.items() if k != "md5"}
    assert hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest() == e["md5"]


def test_parcial_sin_dwsim_declara_pendientes(tmp_path):
    """F85 en «pendiente_entorno» (sin DWSIM): F86 no se rompe ni inventa cantidades."""
    f85 = tmp_path / "work/evidencia_v072/fase85"
    f85.mkdir(parents=True)
    (f85 / "nrtl_utilidades_f85.json").write_text(json.dumps({"fase": "F85", "estado": "pendiente_entorno", "utilidades": None}))
    env = dict(os.environ, RPOS_AGENTS_ROOT=str(tmp_path))
    subprocess.run([sys.executable, PIPE], check=True, capture_output=True, text=True, env=env)
    ev = json.load(open(tmp_path / "work/evidencia_v072/fase86/utilidades_completas_f86.json"))
    assert ev["estado"] == "parcial_pendiente_F85" and ev["estado_F85"] == "pendiente_entorno"
    pend = [i for i in ev["items"] if i.get("estado") == "pendiente_F85_DWSIM"]
    assert {i["concepto"] for i in pend} == set(ev["conceptos_pendientes"]) == {
        "evaporacion_agua_enriquecida", "trampa_fria_LN2", "aire_comprimido"}
    assert all(i["cantidad"] is None and i["costo_mxn_lote"] is None for i in pend)
    calculados = [i for i in ev["items"] if i["costo_mxn_lote"] is not None]
    assert ev["totales"]["costo_utilidades_mxn_lote"] == round(sum(i["costo_mxn_lote"] for i in calculados), 2)
    assert any("PARCIAL" in a for a in ev["advertencias"])
