import json, os, sys
sys.path.insert(0, "/mnt/agents/work/rpos25/pipelines")
import facility_f97 as f


def test_registry_unico_y_historial():
    r = f.AssetRegistry()
    r.registrar("A1", "hvac", "azotea", "equipo_mayor", "operativo")
    r.actualizar_estado("A1", "mantenimiento", "preventivo_programado")
    assert r.activos["A1"]["estado"] == "mantenimiento"
    assert r.activos["A1"]["historial"][0]["estado_anterior"] == "operativo"
    try:
        r.registrar("A1", "hvac", "azotea", "equipo_mayor", "operativo")
        assert False
    except ValueError:
        pass


def test_validacion_33_22_rechaza_incompletos():
    assert "ubicacion:faltante" in f.validar_activo(
        {"id": "X", "tipo": "t", "ubicacion": "", "clasificacion": "c"})
    assert f.validar_activo({"id": "X", "tipo": "t", "ubicacion": "lab",
                             "clasificacion": "c"}) == []


def test_sincronizacion_evidencia_real():
    ed = f.construir_modelo_edificio()
    assert any("bunker_ciclotron" in n["areas"] for n in ed["niveles"])
    u = f.cargar_utilidades()
    assert u["total_costo_mxn_lote"] == 455.55
    a = f.cargar_ambiental()
    assert a["total"] > 0 and all(z["medicion_tiempo_real"].startswith("pendiente") for z in a["zonas"])


def test_run_evidencia_y_auditoria():
    assert f.run() == 0
    d = json.load(open(os.path.join(f.EV_DIR, "facility_f97.json"), encoding="utf-8"))
    assert d["capitulo_canonico"] == 33
    assert len(d["componentes_33_5"]) == 8
    assert d["activos"]["rechazados_33_22"][0]["errores"]
    assert "no ejecuta producción" in d["filosofia_33_3"]
    lines = [json.loads(l) for l in open(os.path.join(f.EV_DIR, "registro_facility_f97.jsonl"),
                                         encoding="utf-8") if l.strip()]
    assert len(lines) >= 3 and all("md5" in e and "motivo" in e for e in lines)
    assert lines[-1]["prev_md5"] == lines[-2]["md5"]
