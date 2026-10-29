"""Tests F81 - plantas BIND 20-10-26 (stdlib + pytest)."""
import json, os, subprocess, sys

EV = "/mnt/agents/work/evidencia_v072/fase81"
EVJ = os.path.join(EV, "plantas_bind_f81.json")
PIPE = "/mnt/agents/work/rpos25/pipelines/plantas_bind_f81.py"


def setup_module(module):
    if not os.path.exists(EVJ):
        subprocess.run([sys.executable, PIPE], check=True)


def test_evidencia_existe_y_fuente_registrada():
    ev = json.load(open(EVJ))
    assert ev["fase"] == "F81"
    assert ev["fuente"]["md5"] == "e96af8019deb77ce8111c9f27636f734"
    assert ev["fuente"]["bytes"] == 20006885


def test_todos_los_espacios_verificados():
    ev = json.load(open(EVJ))
    noenc = ev["verificacion"]["no_encontradas"]
    assert noenc == [], f"espacios sin etiqueta: {noenc}"
    niv = ev["verificacion"]["niveles"]
    for nivel in ("planta_baja", "primer_nivel", "segundo_nivel", "tercer_nivel"):
        assert niv[nivel]["espacios"], nivel
    assert niv["cuarto_nivel"]["estado"] == "proyectado_no_construido_declarado_usuario"


def test_techos_con_soporte():
    ev = json.load(open(EVJ))
    t = ev["verificacion"]["techos"]
    assert t["ciclotron_bunker"]["soporte_dxf"]["n"] >= 1
    assert t["gamma_knife"]["soporte_dxf"]["n"] >= 1
    assert t["linac"]["soporte_dxf"]["n"] >= 1
    assert t["ciclotron_bunker"]["factor_ocupacion"].startswith("bajo")


def test_registro_append_only():
    reg = os.path.join(EV, "registro_plantas_f81.jsonl")
    assert os.path.exists(reg)
    import hashlib
    lines = open(reg).read().strip().splitlines()
    e = json.loads(lines[-1])
    payload = {k: v for k, v in e.items() if k != "md5"}
    assert hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest() == e["md5"]
