"""Tests F87 - STAE Cap. 27 (stdlib + pytest)."""
_RPOS_RAIZ = __import__("os").environ.get("RPOS_AGENTS_ROOT", "/mnt/agents")  # raíz de evidencia/datos externos
_RPOS_REPO = str(__import__("pathlib").Path(__file__).resolve().parents[1])  # raíz de este repo
import json, os, subprocess, sys, hashlib

EV = f"{_RPOS_RAIZ}/work/evidencia_v072/fase87"
EVJ = os.path.join(EV, "stae_f87.json")
PIPE = f"{_RPOS_REPO}/pipelines/stae_f87.py"


def setup_module(module):
    if not os.path.exists(EVJ):
        subprocess.run([sys.executable, PIPE], check=True, capture_output=True, text=True)


def test_validacion_rechaza_inconsistentes():
    ev = json.load(open(EVJ))
    r = ev["resultados"]
    assert r["invalido_duplicado"]["rechazado"] and "duplicados" in r["invalido_duplicado"]["errores"]
    assert r["invalido_pendiente"]["rechazado"]
    assert any("pendiente" in e for e in r["invalido_pendiente"]["errores"])


def test_spc_detecta_fuera_de_control():
    ev = json.load(open(EVJ))
    r = ev["resultados"]
    reglas_ooc = {a["regla"] for a in r["fuera_de_control"]["spc"]["alertas"]}
    assert "WE1_fuera_3sigma" in reglas_ooc
    reglas_corrida = {a["regla"] for a in r["corrida"]["spc"]["alertas"]}
    assert "WE4_8_mismo_lado" in reglas_corrida
    # serie estable: sin alertas
    assert r["estable"]["spc"]["alertas"] == []


def test_tendencia_y_kpis():
    ev = json.load(open(EVJ))
    r = ev["resultados"]
    assert r["tendencia"]["tendencia"]["tendencia"] == "creciente"
    assert r["tendencia"]["tendencia"]["z"] > 1.96
    assert r["estable"]["tendencia"]["tendencia"] == "sin_tendencia_significativa"
    k = r["estable"]["kpis"]
    assert k["pct_aprobacion"] == 100.0 and k["n_lotes"] == 24
    assert k["cpk"] is not None and k["cpk"] > 0


def test_registro_append_only():
    lines = open(os.path.join(EV, "registro_stae_f87.jsonl")).read().strip().splitlines()
    e = json.loads(lines[-1])
    payload = {k: v for k, v in e.items() if k != "md5"}
    assert hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest() == e["md5"]
    assert e["algoritmo"] and e["version"]
