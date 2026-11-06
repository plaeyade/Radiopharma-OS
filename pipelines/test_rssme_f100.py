import json, os, sys
sys.path.insert(0, "/mnt/agents/work/rpos25/pipelines")
import rssme_f100 as r


def test_monitor_vinculado_asset_36_6():
    mm = r.MonitorManager(["RED-01"])
    m = mm.registrar("RAD-1", "bunker", "centelleo_area", "RED-01")
    assert m["activo_vinculado"] == "RED-01"
    try:
        mm.registrar("RAD-2", "x", "gm_contaminacion", "NO_EXISTE")
        assert False
    except ValueError:
        pass


def test_validacion_36_20_cuatro_verificaciones():
    mm = r.MonitorManager(["A"])
    det = mm.registrar("RAD-1", "bunker", "centelleo_area", "A")
    m = r.medicion("RAD-1", "bunker", 0.5)
    assert r.validar_medicion(m, det, "centelleo_area") == []
    assert any("comunicacion" in e for e in
               r.validar_medicion(m, det, "centelleo_area", comunicacion_ok=False))
    m_fuera = r.medicion("RAD-1", "bunker", 1e9)
    assert any("rango" in e for e in r.validar_medicion(m_fuera, det, "centelleo_area"))
    m_retro = dict(m); m_retro["timestamp_utc"] = "2020-01-01T00:00:00+00:00"
    assert any("temporal" in e for e in
               r.validar_medicion(m_retro, det, "centelleo_area", True, m["timestamp_utc"]))
    det2 = dict(det); det2["estado"] = "fuera_servicio"
    assert any("estado_detector" in e for e in
               r.validar_medicion(m, det2, "centelleo_area"))


def test_medicion_36_12_campos():
    m = r.medicion("RAD-1", "cuarto_yodo", 0.05)
    assert all(k in m for k in ("timestamp_utc", "detector", "ubicacion",
                                "valor_uSv_h", "calidad"))


def test_run_evidencia_filosofia_auditoria():
    assert r.run() == 0
    d = json.load(open(os.path.join(r.EV_DIR, "rssme_f100.json"), encoding="utf-8"))
    assert d["capitulo_canonico"] == 36
    assert len(d["componentes_36_5"]) == 8
    assert "no sustituye" in d["filosofia_36_3"]
    assert d["validacion_36_20"]["aceptada_sin_errores"]
    assert d["validacion_36_20"]["eventos_revision"]
    assert d["shielding_manager_36_7"]["bunker_ciclotron"]["criterio"] == "NCRP-144"
    assert d["area_classification_36_8"]["total"] > 0
    assert "pendiente" in d["dosimetry_manager_36_10"]["ocupacional"]
    lines = [json.loads(l) for l in open(os.path.join(r.EV_DIR, "registro_rssme_f100.jsonl"),
                                         encoding="utf-8") if l.strip()]
    assert all("md5" in e and "area" in e for e in lines)
    assert lines[-1]["prev_md5"] == lines[-2]["md5"]
