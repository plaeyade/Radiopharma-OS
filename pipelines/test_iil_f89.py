"""Tests F89 - IIL Cap. 26 (stdlib + pytest)."""
_RPOS_RAIZ = __import__("os").environ.get("RPOS_AGENTS_ROOT", "/mnt/agents")  # raíz de evidencia/datos externos
_RPOS_REPO = str(__import__("pathlib").Path(__file__).resolve().parents[1])  # raíz de este repo
import json, os, subprocess, sys, hashlib

EV = f"{_RPOS_RAIZ}/work/evidencia_v072/fase89"
EVJ = os.path.join(EV, "iil_f89.json")
PIPE = f"{_RPOS_REPO}/pipelines/iil_f89.py"


def setup_module(module):
    if not os.path.exists(EVJ):
        subprocess.run([sys.executable, PIPE], check=True, capture_output=True, text=True)


def test_registry_honesto():
    ev = json.load(open(EVJ))
    inv = ev["instrument_registry"]["inventario"]
    assert len(inv) == 10
    tipos = {i["tipo"] for i in inv}
    for t in ("HPLC", "GC", "TLC_Scanner", "calibrador_dosis", "espectrometro_gamma",
              "contador_pozo", "ph_metro", "osmometro", "lector_endotoxinas", "balanza_analitica"):
        assert t in tipos
    assert all(i["estado_conexion"] == "sin_conexion_pendiente_instrumento" for i in inv)


def test_normalizacion():
    ev = json.load(open(EVJ))
    r = ev["vv_vectores_sinteticos_declarados"]["normalizacion_mCi_a_MBq"]
    assert not r["rechazado"]
    assert abs(r["resultado"]["valor"] - 740.0) < 1e-9   # 20 mCi * 37
    assert r["resultado"]["unidad"] == "MBq"
    assert r["resultado"]["instrumento"] == "DC-01" and r["resultado"]["batch"] == "BATCH-VV-001"


def test_rechazos_e_importacion():
    ev = json.load(open(EVJ))
    vv = ev["vv_vectores_sinteticos_declarados"]
    assert vv["rechazo_incompleto"]["rechazado"] and "falta_valor" in vv["rechazo_incompleto"]["errores"]
    assert vv["rechazo_fecha"]["rechazado"] and "fecha_invalida" in vv["rechazo_fecha"]["errores"]
    imp = vv["importacion_hplc_csv"]
    assert not imp["rechazado"] and imp["n"] == 2
    fdg = imp["picos"][0]
    assert abs(fdg["area_pct"] - 98.5) < 0.01


def test_registro_append_only():
    lines = open(os.path.join(EV, "registro_iil_f89.jsonl")).read().strip().splitlines()
    e = json.loads(lines[-1])
    payload = {k: v for k, v in e.items() if k != "md5"}
    assert hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest() == e["md5"]
