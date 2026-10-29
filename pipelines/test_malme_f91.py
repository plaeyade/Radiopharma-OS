#!/usr/bin/env python3
"""F91 — V&V del MALME (cap. 42). 4 pruebas."""
import json, os, sys

sys.path.insert(0, "/mnt/agents/work/rpos25/pipelines")
import malme_f91 as f

EV = "/mnt/agents/work/evidencia_v072/fase91/malme_f91.json"


def test_entrenamiento_y_metricas_reales():
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [2.0, 4.0, 6.0, 8.0, 10.0]
    m = f.entrenar_lineal(xs, ys)
    assert abs(m["pendiente"] - 2.0) < 1e-9 and abs(m["intercepto"]) < 1e-9
    met = f.metricas(m, xs, ys)
    assert met["r2"] == 1.0 and met["rmse"] == 0.0
    try:
        f.entrenar_lineal([1.0, 1.0], [2.0, 3.0])
        assert False
    except ValueError:
        pass


def test_validacion_bloquea_deficientes_y_corruptos():
    xs = [float(i) for i in range(1, 13)]
    ys = [3.0 * x for x in xs]
    bueno = {"algoritmo": "regresion_lineal_ols", "intercepto": 0.0, "pendiente": 3.0}
    reg = []
    e = f.registrar_modelo(reg, "m", "1.0", bueno, f.metricas(bueno, xs, ys), {"d": 1})
    assert f.validar_modelo(e, {"r2_min": 0.9, "rmse_max": 1.0}) == []
    assert e["estado"] == "aprobado"
    malo = {"algoritmo": "regresion_lineal_ols", "intercepto": 0.0, "pendiente": 0.0}
    e2 = f.registrar_modelo(reg, "m", "0.1", malo, f.metricas(malo, xs, ys), {"d": 1})
    errs = f.validar_modelo(e2, {"r2_min": 0.9, "rmse_max": 1.0})
    assert e2["estado"] == "en_validacion" and len(errs) >= 2
    e["md5"] = "0" * 32
    assert any("integridad" in x for x in f.validar_modelo(e, {"r2_min": 0.9, "rmse_max": 1.0}))


def test_ciclo_vida_y_gobernanza():
    xs = [float(i) for i in range(1, 13)]
    ys = [2.0 * x + 1 for x in xs]
    mod = f.entrenar_lineal(xs, ys)
    reg = []
    e = f.registrar_modelo(reg, "m", "1.0", mod, f.metricas(mod, xs, ys), {"d": 1})
    f.validar_modelo(e, {"r2_min": 0.9, "rmse_max": 1.0})
    try:
        f.aprobar_despliegue(e, "", "pol")
        assert False
    except ValueError:
        pass
    f.aprobar_despliegue(e, "responsable", "pol")
    f.desplegar(e)
    assert e["estado"] == "desplegado"
    mon = f.monitorear(e, xs, ys)
    assert mon["estabilidad"] == "ok" and mon["disponibilidad_produccion"] == "pendiente_telemetria"
    f.revertir(e, "m"); assert e["estado"] == "aprobado"
    f.retirar(e, "m"); assert e["estado"] == "retirado"
    try:
        f.desplegar(e)
        assert False
    except ValueError:
        pass


def test_evidencia_y_auditoria_md5():
    assert os.path.exists(EV)
    ev = json.load(open(EV, encoding="utf-8"))
    assert ev["modelo_aprobado"]["errores_validacion"] == []
    assert ev["modelo_deficiente"]["despliegue_bloqueado"] is True
    assert ev["modelo_deficiente"]["estado"] == "en_validacion"
    reg = [json.loads(l) for l in
           open("/mnt/agents/work/evidencia_v072/fase91/registro_malme_f91.jsonl",
                encoding="utf-8").read().splitlines() if l.strip()]
    assert len(reg) >= 8
    for prev, cur in zip(reg, reg[1:]):
        assert cur["prev_md5"] == prev["md5"]
    acciones = [r["accion"] for r in reg]
    for a in ("registrar_dataset", "entrenar", "validar", "desplegar", "retirar"):
        assert a in acciones
