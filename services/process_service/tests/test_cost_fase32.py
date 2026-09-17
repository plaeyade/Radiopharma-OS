# -*- coding: utf-8 -*-
"""Tests Fase 32: regiones CFE, componentes adicionales, todos los ciclotrones."""
import pytest

from app.domain.cost_engine import (
    CICLOTRONES, COMPONENTES_ADICIONALES, REGIONES_CFE, CorridaCosto, CostEngine,
)


def _engine(tmp_path):
    return CostEngine(tmp_path / "corridas.json")


def _corrida_base(rid="F32-001", **kw):
    d = dict(
        corrida_id=rid, isotopo="F-18", ciclotron_id="iba_cyclone_kiube",
        tarifa_id="GDMTO", t_irradiacion_min=120.0, t_standby_min=30.0,
        potencia_haz_kw=55.0, proveedor_agua_id="chempep_98",
        agua_cargada_g=2.0, fraccion_recuperada=0.85,
        fuente_reciclaje="escenario declarado, pendiente de validación operativa",
        actividad_producida_gb=100.0, n_dosis=20,
        costo_desgaste_mxn=500.0, fuente_desgaste="escenario declarado Fase 27",
        costo_consumibles_mxn=300.0, fuente_consumibles="escenario declarado",
        motivo="prueba F32", responsable="tester",
    )
    d.update(kw)
    return CorridaCosto(**d)


def test_once_ciclotrones_seleccionables():
    assert len(CICLOTRONES) == 12  # 2 originales + 10 Fase 32
    for cid in ("ge_pettrace_890", "ge_minitrace_qilin", "best_b6_15", "lbt_20"):
        assert cid in CICLOTRONES


def test_once_regiones_catalogadas():
    assert len(REGIONES_CFE) == 11
    assert REGIONES_CFE["sureste_tab"]["tarifa_mxn_kwh_gdmto"] == 1.21
    pend = [r for r, v in REGIONES_CFE.items() if v["tarifa_mxn_kwh_gdmto"] is None]
    assert len(pend) == 10


def test_diez_componentes_adicionales():
    assert len(COMPONENTES_ADICIONALES) == 10
    assert "gestion_residuos_radiactivos" in COMPONENTES_ADICIONALES


def test_region_pendiente_sin_fuente_rechazada(tmp_path):
    with pytest.raises(ValueError, match="pendiente_fuente"):
        _engine(tmp_path).registrar_corrida(_corrida_base(region_id="centro"))


def test_region_pendiente_con_tarifa_declarada(tmp_path):
    rec = _engine(tmp_path).registrar_corrida(_corrida_base(
        region_id="centro", tarifa_declarada_mxn_kwh=1.35,
        fuente_tarifa_declarada="CFE app.cfe.mx división Centro, consulta usuario 2026-09"))
    assert rec["estado_region"] == "tarifa_regional_declarada_usuario_con_fuente"
    # 111.5 kWh × 1.35
    assert rec["costo_electrico_mxn"] == pytest.approx(150.52, abs=0.01)


def test_region_sureste_usa_tarifa_citada(tmp_path):
    rec = _engine(tmp_path).registrar_corrida(_corrida_base(region_id="sureste_tab"))
    assert rec["estado_region"] == "fuente_externa_citada"
    assert rec["costo_electrico_mxn"] == pytest.approx(134.92, abs=0.01)


def test_ciclotron_sin_potencia_citada_acepta_declarada(tmp_path):
    rec = _engine(tmp_path).registrar_corrida(_corrida_base(
        ciclotron_id="ge_pettrace_890", potencia_haz_kw=40.0))
    assert "declarada_usuario_pendiente_fuente" in rec["estado_potencia"]
    assert rec["kwh_haz"] == pytest.approx(80.0, abs=0.01)
    assert rec["kwh_standby"] == 0.0  # standby None → 0 declarado


def test_componentes_extra_suman_al_total(tmp_path):
    rec = _engine(tmp_path).registrar_corrida(_corrida_base(
        componentes_extra_mxn={"personal_operacion": 400.0,
                               "control_calidad_liberacion": 250.0},
        fuente_componentes_extra="nómina y contrato QC declarados (escenario)"))
    assert rec["costo_componentes_extra_mxn"] == 650.0
    assert rec["costo_total_mxn"] == pytest.approx(952.91 + 650.0, abs=0.02)


def test_componente_extra_desconocido_rechazado(tmp_path):
    with pytest.raises(ValueError, match="desconocido"):
        _engine(tmp_path).registrar_corrida(_corrida_base(
            componentes_extra_mxn={"yate_corporativo": 1.0},
            fuente_componentes_extra="x"))


def test_componente_extra_sin_fuente_rechazado(tmp_path):
    with pytest.raises(ValueError, match="fuente"):
        _engine(tmp_path).registrar_corrida(_corrida_base(
            componentes_extra_mxn={"seguros": 100.0}))


def test_compatibilidad_corrida_sin_campos_nuevos(tmp_path):
    rec = _engine(tmp_path).registrar_corrida(_corrida_base())
    assert rec["estado_region"] is None
    assert rec["costo_total_mxn"] == pytest.approx(952.91, abs=0.02)
