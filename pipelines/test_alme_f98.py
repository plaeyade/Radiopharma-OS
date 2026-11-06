import json, os, sys
sys.path.insert(0, "/mnt/agents/work/rpos25/pipelines")
import alme_f98 as m


def test_ciclo_vida_34_7():
    a = m.ALME()
    a.registrar_activo("X1", "fab", "mod", "s1", "lab", "2026-01-01")
    for e in ["instalacion", "puesta_en_servicio", "operacion"]:
        a.transicion("X1", e, "op", "vv")
    assert a.activos["X1"]["estado"] == "operacion"
    assert len(a.activos["X1"]["transiciones"]) == 3
    try:
        a.transicion("X1", "estado_inventado", "op", "vv")
        assert False
    except ValueError:
        pass
    try:
        a.registrar_activo("X1", "f", "m", "s", "u", "f")
        assert False
    except ValueError:
        pass


def test_validacion_34_22_bloquea_cierre_inconsistente():
    a = m.ALME()
    a.registrar_activo("Y1", "f", "m", "s", "u", "f")
    iv = a.abrir_intervencion("Y1", "correctivo", "op", "reparacion")
    r = a.cerrar_intervencion("Y1", iv["id"], None, False, [])
    assert not r["cerrada"]
    assert set(r["errores"]) == {"integridad_documental:sin_documentos",
                                 "resultados:faltantes", "aprobacion:faltante"}
    r2 = a.cerrar_intervencion("Y1", iv["id"], "ok", True, ["doc.pdf"])
    assert r2["cerrada"]


def test_calibracion_inmutable_y_confiabilidad():
    a = m.ALME()
    a.registrar_activo("Z1", "f", "m", "s", "u", "f")
    a.registrar_calibracion("Z1", "2026-10-30", "lab", "proc", "ok", 180)
    n = len(a.calibraciones)
    a.registrar_calibracion("Z1", "2027-04-30", "lab", "proc", "ok", 180)
    assert len(a.calibraciones) == n + 1  # append-only, nunca se elimina
    c = a.confiabilidad("Z1", 1000.0, 100.0, 4)
    assert abs(c["disponibilidad"] - 1000 / 1100) < 1e-4
    assert c["mtbf_h"] == 250.0


def test_refacciones_evidencia_auditoria():
    a = m.ALME()
    a.registrar_refaccion("K1", "foil", 1, 2, ["K1"])
    assert len(a.alertas_refacciones()) == 1
    assert m.run() == 0
    d = json.load(open(os.path.join(m.EV_DIR, "alme_f98.json"), encoding="utf-8"))
    assert d["capitulo_canonico"] == 34
    assert len(d["componentes_34_5"]) == 8
    assert d["mantenimiento"]["intervencion_cerrada_ok"]["cerrada"]
    assert not d["mantenimiento"]["intervencion_bloqueada_34_22"]["cerrada"]
    lines = [json.loads(l) for l in open(os.path.join(m.EV_DIR, "registro_alme_f98.jsonl"),
                                         encoding="utf-8") if l.strip()]
    assert all("md5" in e and "motivo" in e for e in lines)
    assert lines[-1]["prev_md5"] == lines[-2]["md5"]
