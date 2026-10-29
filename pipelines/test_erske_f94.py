#!/usr/bin/env python3
"""F94 — V&V del ERSKE (cap. 45). 4 pruebas."""
import json, os, sys

sys.path.insert(0, "/mnt/agents/work/rpos25/pipelines")
import erske_f94 as f

EV = "/mnt/agents/work/evidencia_v072/fase94/erske_f94.json"


def test_registry_y_validacion_45_21():
    reg = []
    d1 = f.registrar_documento(reg, "a", "Doc A", "/x/a.txt", "txt", "dom", "autor")
    assert f.validar_documento(d1, "contenido válido de prueba", reg) == []
    d1["md5_bak"] = d1["md5"]; reg.append(d1)
    d2 = f.registrar_documento(reg, "b", "Doc B", "/x/b.txt", "txt", "dom", "autor")
    assert f.validar_documento(d2, "contenido válido de prueba distinto", reg) == []
    reg.append(d2)
    d3 = f.registrar_documento(reg, "c", "Doc C", "/x/c.txt", "txt", "dom", "autor")
    errs_dup = f.validar_documento(d3, "contenido válido de prueba distinto", reg)
    assert any("duplicado_de:b" in e for e in errs_dup) and d3["estado"] == "en_revision"
    d4 = f.registrar_documento(reg, "d", "", "/x/d.pdf", "pdf", "", "autor")
    errs4 = f.validar_documento(d4, "   ", reg)
    assert any("integridad" in e for e in errs4)
    assert any("formato_no_soportado" in e for e in errs4)
    assert any("metadatos" in e for e in errs4)
    assert d4["estado"] == "en_revision"


def test_parser_y_embedding_reproducible():
    frags = f.parsear("palabra " * 500)
    assert len(frags) >= 3 and all(len(x) > 40 for x in frags)
    v1 = f.embed("ciclotrón blindaje losa hormigón")
    v2 = f.embed("ciclotrón blindaje losa hormigón")
    assert v1 == v2  # determinista/reproducible (45.8)
    assert abs(sum(x * x for x in v1) - 1.0) < 1e-9
    assert f.EMBEDDING_MODEL["declarado"]  # honestidad: no neuronal


def test_retrieval_ranking_y_citas():
    idx = f.Indice()
    d1 = {"id": "d1", "dominio": "fisica"}
    d2 = {"id": "d2", "dominio": "economia"}
    idx.agregar(d1, ["el blindaje del ciclotrón usa hormigón de alta densidad ncrp"])
    idx.agregar(d2, ["el vpn y la tir del escenario económico en pesos mxn"])
    r = f.recuperar(idx, "espesor blindaje ciclotrón hormigón", k=2)
    assert r[0]["doc_id"] == "d1"
    r_f = f.recuperar(idx, "blindaje", k=2, filtro_dominio="economico")
    assert r_f == []  # filtro por dominio (45.10)
    reg = [{"id": "d1", "titulo": "T1", "version": "1.0", "origen": "/x"}]
    citas = f.citar(r, reg)
    assert citas[0]["fuente"]["titulo"] == "T1"  # 45.11 vinculación a fuente


def test_evidencia_consultas_y_auditoria():
    assert os.path.exists(EV)
    ev = json.load(open(EV, encoding="utf-8"))
    assert ev["documentos_indexados"] >= 10
    assert all(c["top1_correcto"] for c in ev["consultas_demostradas"])
    assert any("duplicado" in e for e in ev["eventos_validacion_45_21"])
    for c in ev["consultas_demostradas"]:
        assert c["cita_top1"]["fuente"]["origen"]  # trazabilidad 45.10/45.11
    reg = [json.loads(l) for l in
           open("/mnt/agents/work/evidencia_v072/fase94/registro_erske_f94.jsonl",
                encoding="utf-8").read().splitlines() if l.strip()]
    acciones = [r["accion"] for r in reg]
    assert acciones.count("consultar") == 3  # 45.23: cada consulta registrada
    for prev, cur in zip(reg, reg[1:]):
        assert cur["prev_md5"] == prev["md5"]
