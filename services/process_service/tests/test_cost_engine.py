"""Pruebas del Motor de Costos (Fase 29)."""
import pytest

from app.domain.cost_engine import (CostEngine, CorridaCosto, CICLOTRONES,
                                    TARIFAS_CFE, PROVEEDORES_H2O18)


def mk_engine(tmp_path):
    return CostEngine(tmp_path / "corridas.json")


def mk_corrida(**kw):
    base = dict(
        corrida_id="RUN-001", isotopo="F-18",
        ciclotron_id="iba_cyclone_kiube", tarifa_id="GDMTO",
        t_irradiacion_min=120.0, t_standby_min=30.0, potencia_haz_kw=55.0,
        proveedor_agua_id="chempep_98", agua_cargada_g=2.0,
        fraccion_recuperada=0.85,
        fuente_reciclaje="Protocolo interno de recuperación H2-18O, rev. A (declarado)",
        actividad_producida_gb=100.0, n_dosis=20,
        costo_desgaste_mxn=500.0,
        fuente_desgaste="Costeo de refacciones Fase 27, cotización interna rev. A",
        costo_consumibles_mxn=300.0,
        fuente_consumibles="Lista de consumibles de síntesis, cotización rev. A",
        motivo="Escenario base FDG 2 h", responsable="RSO",
    )
    base.update(kw)
    return CorridaCosto(**base)


def test_catalogos_tienen_fuente():
    assert all(v["fuente_potencia"] for v in CICLOTRONES.values())
    assert all(v["fuente"] for v in TARIFAS_CFE.values())
    assert all(v["fuente"] for v in PROVEEDORES_H2O18.values())


def test_kwh_aritmetica_exacta(tmp_path):
    eng = mk_engine(tmp_path)
    r = eng.registrar_corrida(mk_corrida())
    assert r["kwh_haz"] == pytest.approx(55.0 * 2.0, rel=1e-12)   # 110 kWh
    assert r["kwh_standby"] == pytest.approx(3.0 * 0.5, rel=1e-12)
    assert r["kwh_total"] == pytest.approx(111.5, rel=1e-12)
    assert r["costo_electrico_mxn"] == pytest.approx(111.5 * 1.21, abs=0.01)


def test_agua_perdida_y_costo(tmp_path):
    eng = mk_engine(tmp_path)
    r = eng.registrar_corrida(mk_corrida())
    assert r["agua_perdida_g"] == pytest.approx(0.3, rel=1e-9)   # 2.0 × 0.15
    assert r["precio_agua_por_g"] == 60.0                          # granel chempep
    assert r["costo_agua"] == pytest.approx(18.0, rel=1e-9)


def test_sin_reciclaje_cobra_toda_el_agua(tmp_path):
    eng = mk_engine(tmp_path)
    r = eng.registrar_corrida(mk_corrida(corrida_id="RUN-X",
                                         fraccion_recuperada=0.0))
    assert r["agua_perdida_g"] == pytest.approx(2.0)
    assert r["costo_agua"] == pytest.approx(120.0)


def test_costo_total_y_unitarios(tmp_path):
    eng = mk_engine(tmp_path)
    r = eng.registrar_corrida(mk_corrida())
    total = r["costo_electrico_mxn"] + r["costo_agua"] + 500.0 + 300.0
    assert r["costo_total_mxn"] == pytest.approx(total, abs=0.01)
    assert r["costo_por_gb_mxn"] == pytest.approx(total / 100.0, abs=0.01)
    assert r["costo_por_dosis_mxn"] == pytest.approx(total / 20, abs=0.01)


def test_duplicado_rechazado(tmp_path):
    eng = mk_engine(tmp_path)
    eng.registrar_corrida(mk_corrida())
    with pytest.raises(ValueError, match="duplicado"):
        eng.registrar_corrida(mk_corrida())


def test_potencia_fuera_de_rango_rechazada(tmp_path):
    eng = mk_engine(tmp_path)
    with pytest.raises(ValueError, match="rango citado"):
        eng.registrar_corrida(mk_corrida(potencia_haz_kw=100.0))
    with pytest.raises(ValueError, match="rango citado"):
        eng.registrar_corrida(mk_corrida(corrida_id="R2", potencia_haz_kw=10.0))


def test_advertencia_tarifa_excedida(tmp_path):
    eng = mk_engine(tmp_path)
    r = eng.registrar_corrida(mk_corrida(tarifa_id="PDBT"))  # límite 25 kW < 55
    assert "ADVERTENCIA" in r["estado_tarifa"]


def test_reciclaje_exige_fuente(tmp_path):
    eng = mk_engine(tmp_path)
    with pytest.raises(ValueError, match="fuente"):
        eng.registrar_corrida(mk_corrida(fuente_reciclaje=""))
    with pytest.raises(ValueError, match="fuente"):
        eng.registrar_corrida(mk_corrida(corrida_id="R3", fuente_desgaste=""))
    with pytest.raises(ValueError, match="fuente"):
        eng.registrar_corrida(mk_corrida(corrida_id="R4", fuente_consumibles=""))


def test_validaciones_generales(tmp_path):
    eng = mk_engine(tmp_path)
    with pytest.raises(ValueError, match="motivo"):
        eng.registrar_corrida(mk_corrida(motivo=""))
    with pytest.raises(ValueError, match="catálogo"):
        eng.registrar_corrida(mk_corrida(corrida_id="R5", ciclotron_id="otro"))
    with pytest.raises(ValueError, match=r"\[0,1\]"):
        eng.registrar_corrida(mk_corrida(corrida_id="R6", fraccion_recuperada=1.5))


def test_escenario_precio_granel_y_unidosis(tmp_path):
    eng = mk_engine(tmp_path)
    eng.registrar_corrida(mk_corrida())
    e1 = eng.escenario_precio("RUN-001", "granel_mxn_gb", 40.0, "Escenario comercial A")
    assert e1["precio_sugerido_mxn"] == pytest.approx(
        eng.corrida("RUN-001")["costo_por_gb_mxn"] * 1.4, abs=0.01)
    assert "RECOMENDACIÓN" in e1["naturaleza"]
    e2 = eng.escenario_precio("RUN-001", "unidosis_mxn_dosis", 25.0, "Escenario B")
    assert e2["precio_sugerido_mxn"] > e2["costo_base_mxn"]
    with pytest.raises(ValueError, match="modo"):
        eng.escenario_precio("RUN-001", "inventado", 10.0, "x")
    with pytest.raises(ValueError, match="motivo"):
        eng.escenario_precio("RUN-001", "granel_mxn_gb", 10.0, "")


def test_persistencia(tmp_path):
    eng = mk_engine(tmp_path)
    eng.registrar_corrida(mk_corrida())
    eng2 = mk_engine(tmp_path)
    assert eng2.corrida("RUN-001") is not None


def test_naturaleza_honesta(tmp_path):
    eng = mk_engine(tmp_path)
    r = eng.registrar_corrida(mk_corrida())
    assert "RECOMENDACIÓN" in r["naturaleza"]
    assert set(r["fuentes"]) == {"potencia", "tarifa", "agua",
                                 "reciclaje", "desgaste", "consumibles"}
