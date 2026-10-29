#!/usr/bin/env python3
"""F93 — V&V del KGSIE (cap. 44). 4 pruebas."""
import json, os, sys

sys.path.insert(0, "/mnt/agents/work/rpos25/pipelines")
import kgsie_f93 as f

EV = "/mnt/agents/work/evidencia_v072/fase93/kgsie_f93.json"
u = f.urn


def _grafo_basico():
    g = f.Grafo()
    g.agregar_entidad("radionuclido", "f18")
    g.agregar_entidad("radiofarmaco", "fdg")
    g.agregar_entidad("radiofarmaco", "fdg_dosis")
    g.agregar_relacion(u("radiofarmaco", "fdg"), "deriva_de", u("radionuclido", "f18"), "t")
    g.agregar_relacion(u("radiofarmaco", "fdg_dosis"), "deriva_de", u("radiofarmaco", "fdg"), "t")
    return g


def test_registry_unicidad_y_ontologia():
    g = f.Grafo()
    assert g.agregar_entidad("equipo", "ciclotron") is not None
    assert g.agregar_entidad("equipo", "ciclotron") is None          # duplicado
    assert g.agregar_entidad("fantasma", "x") is None                # fuera de ontología
    assert "duplicado:urn:rpos:equipo:ciclotron" in g.eventos_validacion
    assert any("tipo_fuera_de_ontologia" in e for e in g.eventos_validacion)


def test_relaciones_consultas_y_obligatorias():
    g = _grafo_basico()
    g.agregar_entidad("lote", "l1")
    eventos = g.validar()
    assert any("relacion_obligatoria_faltante" in e and "lote" in e for e in eventos)
    g.agregar_entidad("equipo", "sintetizador")
    g.agregar_relacion(u("equipo", "sintetizador"), "produce", u("lote", "l1"), "t")
    assert not any("lote" in e for e in g.validar() if "obligatoria" in e)
    r = g.consultar(predicado="deriva_de", tipo_objeto="radionuclido")
    assert len(r) == 1 and r[0]["sujeto"].endswith("fdg")
    assert g.agregar_relacion(u("lote", "l1"), "inventado",
                              u("equipo", "sintetizador")) is None


def test_reasoning_transitivo_documentado_y_camino():
    g = _grafo_basico()
    nuevas = g.inferir()
    assert len(nuevas) == 1
    inf = nuevas[0]
    assert inf["sujeto"].endswith("fdg_dosis") and inf["objeto"].endswith("f18")
    assert inf["inferida"] and inf["regla"] == "transitividad(deriva_de)"
    assert inf["documentada"]  # 44.10
    cam = g.camino(u("radiofarmaco", "fdg_dosis"), u("radionuclido", "f18"))
    assert cam is not None and len(cam) == 1  # arista inferida directa
    assert g.camino(u("radiofarmaco", "fdg"), u("lote", "inexistente")) is None


def test_evidencia_sync_export_y_auditoria():
    assert os.path.exists(EV)
    ev = json.load(open(EV, encoding="utf-8"))
    st = ev["estadisticas"]
    assert st["entidades"] >= 30 and st["relaciones"] >= 20
    assert st["inferidas_documentadas"] >= 1
    assert any("duplicado" in e for e in ev["eventos_validacion_44_21"])
    assert any("tipo_fuera_de_ontologia" in e for e in ev["eventos_validacion_44_21"])
    assert any("predicado_fuera_de_ontologia" in e for e in ev["eventos_validacion_44_21"])
    assert ev["consulta_demostrada"]["camino"]  # agente→…→f18 multi-dominio
    grafo = json.load(open("/mnt/agents/work/evidencia_v072/fase93/grafo_f93.json",
                           encoding="utf-8"))
    assert len(grafo["nodos"]) == st["entidades"]
    assert len(grafo["aristas"]) == st["relaciones"]
    reg = [json.loads(l) for l in
           open("/mnt/agents/work/evidencia_v072/fase93/registro_kgsie_f93.jsonl",
                encoding="utf-8").read().splitlines() if l.strip()]
    for prev, cur in zip(reg, reg[1:]):
        assert cur["prev_md5"] == prev["md5"]
