#!/usr/bin/env python3
"""F92 — V&V del MADSE (cap. 43). 4 pruebas."""
import json, os, sys

sys.path.insert(0, "/mnt/agents/work/rpos25/pipelines")
import madse_f92 as f

EV = "/mnt/agents/work/evidencia_v072/fase92/madse_f92.json"


def test_registry_versionado():
    reg = []
    a = f.registrar_agente(reg, "agente_economia", "economia", ["voto_trazable"])
    assert a["estado"] == "activo" and a["version"] == "1.0"
    f.registrar_agente(reg, "agente_economia", "economia", ["v2"], version="2.0")
    assert [x["version"] for x in reg] == ["1.0", "2.0"]  # versionado, no sobrescritura


def test_planner_y_orquestador():
    ctx, _ = f.construir_contexto()
    plan = f.planificar("subir a 24 lotes", lotes_objetivo=24)
    assert plan["secuencia_registrada"] and len(plan["tareas"]) == 5
    contribs = f.orquestar(plan, ctx)
    assert len(contribs) == 5
    ec = next(c for c in contribs if c["agente"] == "economia")
    assert ec["voto"] == "favorable" and "MXN" in ec["detalle"] and ec["fuente"]
    pr = next(c for c in contribs if c["agente"] == "produccion")
    assert pr["voto"] == "favorable"  # 24/30 = 80 % <= 85 %
    plan50 = f.planificar("subir a 50", lotes_objetivo=50)
    c50 = f.orquestar(plan50, ctx)
    assert next(c for c in c50 if c["agente"] == "economia")["voto"] == "desfavorable"
    plan_sin = f.planificar("consulta general")
    assert len(plan_sin["tareas"]) == 1


def test_consenso_y_trazabilidad():
    contribs = [{"agente": "a", "voto": "favorable", "detalle": "x", "fuente": "f"},
                {"agente": "b", "voto": "precaucion", "detalle": "y", "fuente": "f"},
                {"agente": "c", "voto": "precaucion", "detalle": "z", "fuente": None}]
    con = f.consenso(contribs)
    assert con["recomendacion"] == "precaucion" and abs(con["score"] - 1/3) < 1e-3
    assert len(con["contribuciones_registradas"]) == 3  # 43.9
    assert "NO sustituye" in con["marca_43_3"]
    con_fav = f.consenso([{"agente": "a", "voto": "favorable", "detalle": "", "fuente": 1},
                          {"agente": "b", "voto": "favorable", "detalle": "", "fuente": 1}])
    assert con_fav["recomendacion"] == "favorable_con_condiciones"
    con_rev = f.consenso([{"agente": "a", "voto": "revision", "detalle": "", "fuente": None}])
    assert con_rev["recomendacion"] == "revision"


def test_validacion_eventos_y_evidencia_auditoria():
    eventos = f.validar_recomendacion(
        {"faltantes": ["f87"]},
        [{"voto": "favorable"}, {"voto": "desfavorable"}, {"voto": "revision"}])
    assert "contexto_faltante:f87" in eventos
    assert "inconsistencia_entre_agentes" in eventos
    assert "agente_en_revision" in eventos
    assert os.path.exists(EV)
    ev = json.load(open(EV, encoding="utf-8"))
    assert len(ev["agentes_registrados"]) == 10  # dominios 43.7
    assert ev["conversacion"]["resultados"]["recomendacion"] in (
        "favorable_con_condiciones", "precaucion")
    reg = [json.loads(l) for l in
           open("/mnt/agents/work/evidencia_v072/fase92/registro_madse_f92.jsonl",
                encoding="utf-8").read().splitlines() if l.strip()]
    assert len(reg) >= 6
    for prev, cur in zip(reg, reg[1:]):
        assert cur["prev_md5"] == prev["md5"]
