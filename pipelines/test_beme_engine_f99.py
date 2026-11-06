import json, os, sys
sys.path.insert(0, "/mnt/agents/work/rpos25/pipelines")
import beme_engine_f99 as b


def test_sensor_vinculado_a_asset_registry_35_6():
    sm = b.SensorManager(["HVAC-UMA-01"])
    s = sm.registrar("S1", "lab", "temperatura_C", "HVAC-UMA-01")
    assert s["activo_vinculado"] == "HVAC-UMA-01"
    try:
        sm.registrar("S2", "lab", "temperatura_C", "ACTIVO_QUE_NO_EXISTE")
        assert False
    except ValueError:
        pass


def test_validacion_35_21_rango_calidad_temporal():
    sm = b.SensorManager(["A"])
    s = sm.registrar("S1", "lab", "temperatura_C", "A")
    m_ok = b.medicion("S1", "temperatura_C", 22.0, "vv")
    assert b.validar_medicion(m_ok, s) == []
    m_fuera = b.medicion("S1", "temperatura_C", 99.0, "vv")
    assert any("rango" in e for e in b.validar_medicion(m_fuera, s))
    m_calidad = b.medicion("S1", "temperatura_C", 22.0, "vv", calidad="sospechosa")
    assert any("calidad" in e for e in b.validar_medicion(m_calidad, s))
    m_retro = dict(m_ok); m_retro["timestamp_utc"] = "2020-01-01T00:00:00+00:00"
    assert any("temporal" in e for e in b.validar_medicion(m_retro, s, m_ok["timestamp_utc"]))


def test_medicion_35_13_campos_y_alarmas():
    m = b.medicion("S1", "humedad_pct", 45.0, "origen_vv")
    assert all(k in m for k in ("timestamp_utc", "valor", "calidad", "origen"))
    am = b.AlarmManager()
    a = am.generar("cuarto_yodo", "perdida_presion", "dP bajo")
    assert a["estado"] == "activa" and a["area"] == "cuarto_yodo"


def test_run_evidencia_filosofia_auditoria():
    assert b.run() == 0
    d = json.load(open(os.path.join(b.EV_DIR, "beme_engine_f99.json"), encoding="utf-8"))
    assert d["capitulo_canonico"] == 35
    assert len(d["componentes_35_5"]) == 8
    assert "no controla" in d["filosofia_35_3"]
    assert d["validacion_35_21"]["eventos"], "anomalía vv debe generar evento"
    assert d["alarmas_35_12"][0]["tipo"] == "perdida_presion"
    assert d["zonas_ambientales_35_11"]["total"] > 0
    lines = [json.loads(l) for l in open(os.path.join(b.EV_DIR, "registro_beme_f99.jsonl"),
                                         encoding="utf-8") if l.strip()]
    assert all("md5" in e and "area" in e for e in lines)
    assert lines[-1]["prev_md5"] == lines[-2]["md5"]
