import json, math, os, sys
sys.path.insert(0, "/mnt/agents/work/rpos25/pipelines")
import burnup_f96 as b


def test_fisica_burnup_y_saturacion():
    """Burnup pequeño pero positivo; curva F-18 coincide con el límite sin
    agotamiento dentro de tolerancia (burnup despreciable a 120 min)."""
    blanco = b.componer_blanco()
    res = b._simular_rk4(blanco, 300.0, 120.0, 1.0, 0.52, 0.003)
    assert 0 < res["fraccion_agotada"] < 1e-5
    lam = math.log(2) / (109.77 * 60)
    k = res["k_reaccion_s"]
    n0 = blanco["n_o18_inicial"]
    a_lim = k * n0 * (1 - math.exp(-lam * 7200)) / 1e9
    assert abs(res["actividad_f18_eob_GBq"] - a_lim) / a_lim < 1e-3


def test_conservacion_y_convergencia():
    blanco = b.componer_blanco()
    r1 = b._simular_rk4(blanco, 300.0, 120.0, 1.0, 0.52, 0.003)
    r2 = b._simular_rk4(blanco, 300.0, 120.0, 0.5, 0.52, 0.003)
    assert b.validar_simulacion(blanco, r1, r2, 1.0) == []
    # rechaza resultado inconsistente (n18 creció)
    r1_mal = dict(r1)
    r1_mal["final"] = [blanco["n_o18_inicial"] * 2, 0, 0]
    assert any("conservacion" in e for e in b.validar_simulacion(blanco, r1_mal, r2, 1.0))


def test_impurezas_e_incertidumbre():
    blanco = b.componer_blanco()
    res = b._simular_rk4(blanco, 300.0, 120.0, 1.0, 0.52, 0.003)
    assert res["actividad_n13_eob_MBq"] > 0
    assert res["actividad_n13_eob_MBq"] / 1e3 < res["actividad_f18_eob_GBq"] * 0.01
    inc = b.incertidumbre(res["actividad_f18_eob_GBq"], [0.08, 0.01, 0.02, 0.005])
    assert abs(inc["u_relativa"] - math.sqrt(0.08**2 + 0.01**2 + 0.02**2 + 0.005**2)) < 1e-4


def test_vida_util_evidencia_y_auditoria(tmp_path):
    vida = b.vida_util(1e-9)
    assert vida["irradiaciones_estimadas"] == 0.05 / 1e-9
    assert b.run() == 0
    ev = os.path.join(b.EV_DIR, "burnup_f96.json")
    reg = os.path.join(b.EV_DIR, "registro_burnup_f96.jsonl")
    assert os.path.exists(ev) and os.path.exists(reg)
    d = json.load(open(ev, encoding="utf-8"))
    assert d["capitulo_canonico"] == 16
    assert d["validacion_16_22"]["errores"] == []
    assert "intacto" in d["yield_engine_original"]
    lines = [json.loads(l) for l in open(reg, encoding="utf-8") if l.strip()]
    assert lines[-1]["prev_md5"] == lines[-2]["md5"] if len(lines) > 1 else True
    assert all("md5" in e and "operador" in e for e in lines)
