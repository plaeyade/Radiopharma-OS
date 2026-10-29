#!/usr/bin/env python3
"""F90 — V&V del FFSAE (cap. 40). 4 pruebas."""
import json, os, sys

sys.path.insert(0, "/mnt/agents/work/rpos25/pipelines")
import ffsae_f90 as f

EV = "/mnt/agents/work/evidencia_v072/fase90/ffsae_f90.json"

ESC_BASE = dict(
    lotes_mes=18.0, dosis_por_lote=10.0, precio_dosis_mxn=3500.0,
    costo_utilidades_mxn_lote=455.55, costo_variable_dosis_mxn=450.0,
    costo_fijo_mes_mxn=280000.0, capacidad_lotes_mes=30,
    crecimiento_mensual=0.0)


def _esc(**kw):
    p = dict(ESC_BASE); p.update(kw.pop("parametros", {}))
    return f.crear_escenario(kw.pop("nombre", "t"), ["h1"], p,
                             kw.pop("horizonte_meses", 12))


def test_forecast_aritmetica_mes1():
    esc = _esc()
    m1 = f.proyectar(esc)[0]
    # ingresos = 18 lotes * 10 dosis * 3500 = 630000
    assert abs(m1["ingresos_mxn"] - 630000.0) < 0.01
    # costos = 18*455.55 + 180*450 + 280000 = 8199.9 + 81000 + 280000 = 369199.9
    assert abs(m1["costos_mxn"] - 369199.90) < 0.01
    assert abs(m1["utilidad_mxn"] - 260800.10) < 0.01
    assert m1["utilizacion_pct"] == 60.0


def test_validation_engine_rechaza_incompletos():
    ok = f.validar_escenario(_esc())
    assert ok == []
    sin_precio = _esc(parametros={"precio_dosis_mxn": None})
    errs = f.validar_escenario(sin_precio)
    assert any("precio_dosis_mxn" in e for e in errs)
    assert "horizonte_invalido" in f.validar_escenario(_esc(horizonte_meses=0))
    assert "falta_hipotesis" in f.validar_escenario(
        f.crear_escenario("x", [], ESC_BASE, 12))


def test_sensibilidad_y_riesgos_monotonicos():
    esc = _esc()
    s = f.sensibilidad(esc, "demanda")
    r = {x["variacion_pct"]: x["delta_vs_base_mxn"] for x in s["resultados"]}
    assert r[-20.0] < r[-10.0] < 0 < r[10.0] < r[20.0]
    sc = f.sensibilidad(esc, "costos")
    rc = {x["variacion_pct"]: x["delta_vs_base_mxn"] for x in sc["resultados"]}
    assert rc[20.0] < 0 < rc[-20.0]
    rz = f.analizar_riesgos(esc, [
        {"tipo": "disminucion_demanda", "magnitud_pct": 25},
        {"tipo": "indisponibilidad_equipo", "magnitud_pct": 50},
        {"tipo": "incremento_costos", "magnitud_pct": 15}])
    assert all(e["impacto_mxn"] < 0 for e in rz["eventos"])
    assert rz["orientado_a_soporte_decisiones"] is True


def test_inversion_kpis_y_evidencia():
    esc = _esc()
    inv = f.evaluar_inversion(esc, 1_200_000.0, 120_000.0)
    assert inv["vpn_mxn"] > 0 and inv["tir_anual_pct"] and inv["tir_anual_pct"] > 12.0
    inv_malo = f.evaluar_inversion(esc, 5_000_000.0, 10_000.0)
    assert inv_malo["vpn_mxn"] < 0
    k = f.kpis(esc)
    assert abs(k["rentabilidad_margen_pct"] - 100 * 260800.10 / 630000.0) < 0.05
    assert k["punto_equilibrio_dosis_mes"] and k["punto_equilibrio_dosis_mes"] < 180
    # evidencia de fase generada por run()
    assert os.path.exists(EV)
    with open(EV, encoding="utf-8") as fh:
        ev = json.load(fh)
    assert ev["escenario"]["solo_simulacion_no_modifica_registros"] is True
    assert ev["validacion_40_20"]["escenario_base_errores"] == []
    assert ev["validacion_40_20"]["escenario_incompleto_rechazado"] is True
    assert len(ev["validacion_40_20"]["errores_detectados"]) >= 3
    assert ev["costo_utilidades_mxn_lote"] > 0  # fuente F86 citada
