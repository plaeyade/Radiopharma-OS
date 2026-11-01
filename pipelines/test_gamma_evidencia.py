import copy
import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import gamma_evidencia as G  # noqa: E402
import plan_produccion as P  # noqa: E402
import tablero_produccion as T  # noqa: E402
from test_tablero_produccion import PLAN, QcFalso, lote  # noqa: E402

PAQUETE = json.loads(G.PAQUETE_DEF.read_text(encoding="utf-8"))


def test_paquete_versionado_verifica_y_trae_pagina():
    p = G.PaqueteGamma(PAQUETE)
    assert p.errores == [] and p.incluye_en_revision
    for cid, c in p.consultas.items():
        assert c["citas"], cid
        assert all(x["pagina"] for x in c["citas"])
    ref = p.referencias("kiube_corriente")[0]
    assert ref["pagina"] and "no apta para firma" in ref["texto"] and ref["fuente"]


def test_cita_alterada_se_rechaza():
    datos = copy.deepcopy(PAQUETE)
    datos["consultas"][0]["evidencia"]["citas"][0]["texto"] += " (editado)"
    p = G.PaqueteGamma(datos)
    assert any("alterado" in e for e in p.errores)
    assert p.consultas[datos["consultas"][0]["id"]]["citas"] == []


def test_evidencia_no_puede_declararse_validada():
    ev = copy.deepcopy(PAQUETE["consultas"][0]["evidencia"])
    ev["no_apto_para_firma"] = False
    citas, err = G.verificar_evidencia(ev)
    assert citas == [] and err


def test_fichas_del_plan_por_isotopo():
    fichas = P.fichas_evidencia(G.PaqueteGamma(PAQUETE))
    assert set(fichas) == {"F18", "Ga68", "Cu64", "ciclotron"}
    assert all(f["referencias"] for f in fichas.values())
    sin = P.fichas_evidencia(FileNotFoundError("x"))
    assert sin["F18"]["referencias"] == [] and "sin paquete" in sin["F18"]["pendiente"]


def test_tablero_muestra_fichas_citadas():
    plan = dict(PLAN, fichas_evidencia=P.fichas_evidencia(G.PaqueteGamma(PAQUETE)))
    t = T.tablero([lote()], plan, QcFalso())
    assert set(t["fichas_evidencia"]) == {"F18", "ciclotron"}
    assert "Fichas: evidencia citada por GAMMA-AI" in T.a_html(t) and ", p. " in T.a_html(t)


def test_consulta_en_vivo():
    ev = PAQUETE["consultas"][0]["evidencia"]

    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    urls = []

    def abrir(url, timeout):
        urls.append(url)
        return R(json.dumps(ev).encode())

    citas, err = G.consultar("dual beam", k=2, revision=True, url="http://127.0.0.1:8765/", abrir=abrir)
    assert err == [] and citas and urls[0].endswith("/v1/ecosistema/evidencia?q=dual+beam&k=2&revision=1")
    assert G.consultar("x", url="")[1][0].startswith("GAMMA no configurado")

    def caido(url, timeout):
        raise urllib.error.URLError("refused")

    assert "no disponible" in G.consultar("x", url="http://g", abrir=caido)[1][0]


@pytest.mark.parametrize("malo", [{}, {"contrato": "otro"}])
def test_paquete_invalido(malo):
    with pytest.raises(ValueError):
        G.PaqueteGamma(malo)
