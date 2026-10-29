"""Tests F88 - BEME Cap. 35 (stdlib + pytest)."""
import json, os, subprocess, sys, hashlib

EV = "/mnt/agents/work/evidencia_v072/fase88"
EVJ = os.path.join(EV, "beme_f88.json")
PIPE = "/mnt/agents/work/rpos25/pipelines/beme_f88.py"


def setup_module(module):
    if not os.path.exists(EVJ):
        subprocess.run([sys.executable, PIPE], check=True)


def test_zonas_y_sensores():
    ev = json.load(open(EVJ))
    assert ev["fase"] == "F88" and ev["estado"] == "completada_motor_validado"
    assert len(ev["zonas"]) == 11
    # 3 sensores por zona
    assert ev["sensores"]["total"] == 33
    assert all(s["estado"] == "pendiente_telemetria" for s in ev["sensores"]["detalle"])


def test_cascada_presiones_coherente():
    ev = json.load(open(EVJ))
    for c in ev["differential_pressure"]["coherencia_cascada"]:
        assert c["ok"], c["check"]
    dp = ev["differential_pressure"]["objetivos_declarados_Pa"]
    assert dp["N2-CUARTO-YODO"] == min(dp.values())
    assert dp["N1-CUARTO-CALIENTE-PET"] < dp["N1-PASILLO-RF"] < 0


def test_alarm_manager_vv():
    ev = json.load(open(EVJ))
    eventos = ev["alarm_manager"]["eventos_generados"]
    tipos = {e["tipo"] for e in eventos}
    assert tipos == {"desviacion_temperatura", "perdida_de_presion", "desviacion_humedad"}
    assert len(eventos) == 3  # 2 lecturas ok no generan eventos


def test_utilidades_y_registro():
    ev = json.load(open(EVJ))
    assert ev["utility_manager"]["costo_utilidades_mxn_lote"] > 0
    assert ev["hvac_manager"]["carga_cuarto_caliente_kW"] > 1.0
    lines = open(os.path.join(EV, "registro_beme_f88.jsonl")).read().strip().splitlines()
    e = json.loads(lines[-1])
    payload = {k: v for k, v in e.items() if k != "md5"}
    assert hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest() == e["md5"]
