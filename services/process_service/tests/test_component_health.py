"""Tests Fase 27 — Salud de Componentes Consumibles (cap. 34 ext.).

Cubre: registro honesto (49.11), consumo solo con origen, cálculo de
desgaste, proyección honesta `sin_historial`, reemplazo como decisión
operativa registrada (18.10) con tramos append-only, marcador de umbral
sin fuente externa y auditoría ALCOA+.
"""
from __future__ import annotations

import pytest

from app.domain.component_health import (ComponentHealth,
                                         ComponentHealthInvalido, Componente,
                                         EventoUso, Reemplazo)
from app.domain.facility_twin import Activo, FacilityTwin


@pytest.fixture()
def ch() -> ComponentHealth:
    twin = FacilityTwin()
    twin.registrar_activo(Activo(activo_id="CYC-1", tipo="equipo",
                                 nombre="Ciclotrón 18 MeV"), "test")
    h = ComponentHealth(twin)
    h.registrar_componente(
        Componente(componente_id="FOIL-001", tipo="havar_foil",
                   serie="HAV-2026-0007", activo_id="CYC-1",
                   umbral_vida=10000.0,
                   fuente_umbral="declaración interna — pendiente hoja "
                                 "del fabricante (Hamilton/Goodfellow)",
                   motivo="registro inicial Fase 27",
                   fuente_externa=False), "test")
    return h


def test_registro_valido_unidad_por_tipo(ch):
    s = ch.salud("FOIL-001")
    assert s["unidad_vida"] == "uA_h"
    assert s["vida_consumida"] == 0.0
    assert s["vida_pct"] == 0.0
    assert s["estado_desgaste"] == "verde"


def test_umbral_sin_fuente_externa_queda_marcado(ch):
    assert ch.salud("FOIL-001")["estado_umbral"] == \
        "declarado_interno_pendiente_fuente"


def test_registro_duplicado_rechazado(ch):
    with pytest.raises(ComponentHealthInvalido):
        ch.registrar_componente(
            Componente(componente_id="FOIL-001", tipo="havar_foil",
                       serie="X", activo_id="CYC-1", umbral_vida=1.0,
                       fuente_umbral="f"), "test")


def test_registro_sin_fuente_umbral_rechazado(ch):
    with pytest.raises(ComponentHealthInvalido):
        ch.registrar_componente(
            Componente(componente_id="F-2", tipo="havar_foil", serie="X",
                       activo_id="CYC-1", umbral_vida=1.0,
                       fuente_umbral="  "), "test")


def test_registro_activo_inexistente_rechazado(ch):
    with pytest.raises(ComponentHealthInvalido):
        ch.registrar_componente(
            Componente(componente_id="F-3", tipo="cuerpo_blanco", serie="X",
                       activo_id="NO-EXISTE", umbral_vida=100.0,
                       fuente_umbral="f"), "test")


def test_uso_sin_origen_rechazado(ch):
    with pytest.raises(ComponentHealthInvalido):
        ch.registrar_uso("FOIL-001", EventoUso(cantidad=50.0, origen=" "),
                         "test")


def test_consumo_real_acumulado(ch):
    ch.registrar_uso("FOIL-001",
                     EventoUso(cantidad=50.0,
                               origen="corrida FDG 60min 50µA evidencia_v072"),
                     "test")
    ch.registrar_uso("FOIL-001",
                     EventoUso(cantidad=50.0, origen="corrida FDG #2"), "test")
    s = ch.salud("FOIL-001")
    assert s["vida_consumida"] == 100.0
    assert s["vida_pct"] == 1.0
    assert s["estado_desgaste"] == "verde"


def test_proyeccion_honesta_sin_historial(ch):
    assert ch.salud("FOIL-001")["eventos_restantes_proyectados"] == \
        "sin_historial"


def test_proyeccion_con_historial(ch):
    for _ in range(2):
        ch.registrar_uso("FOIL-001",
                         EventoUso(cantidad=50.0, origen="corrida FDG"),
                         "test")
    # restan 9900 µA·h, media 50 → 198 eventos
    assert ch.salud("FOIL-001")["eventos_restantes_proyectados"] == 198.0


def test_estados_y_recomendacion_1810(ch):
    ch.registrar_uso("FOIL-001",
                     EventoUso(cantidad=9500.0, origen="campaña"), "test")
    s = ch.salud("FOIL-001")
    assert s["estado_desgaste"] == "rojo"
    assert "RECOMENDACIÓN" in s["recomendacion"]
    assert "18.10" in s["recomendacion"]


def test_reemplazo_exige_responsable_y_motivo(ch):
    with pytest.raises(ComponentHealthInvalido):
        ch.registrar_reemplazo(
            "FOIL-001",
            Reemplazo(motivo="", responsable="op", nueva_serie="HAV-8"),
            "test")
    with pytest.raises(ComponentHealthInvalido):
        ch.registrar_reemplazo(
            "FOIL-001",
            Reemplazo(motivo="desgaste", responsable=" ", nueva_serie="HAV-8"),
            "test")


def test_reemplazo_abre_tramo_nuevo_sin_borrar_historial(ch):
    ch.registrar_uso("FOIL-001", EventoUso(cantidad=9000.0, origen="c"),
                     "test")
    rep = ch.registrar_reemplazo(
        "FOIL-001",
        Reemplazo(motivo="vida útil alcanzada", responsable="jefe.turno",
                  nueva_serie="HAV-2026-0008"), "test")
    assert rep["serie_retirada"] == "HAV-2026-0007"
    assert rep["consumo_al_retiro"] == 9000.0
    s = ch.salud("FOIL-001")
    assert s["vida_consumida"] == 0.0          # tramo nuevo en cero
    assert s["serie"] == "HAV-2026-0008"
    assert s["historial_eventos_total"] == 1   # historial NO borrado
    assert len(s["reemplazos"]) == 1
    # el tramo nuevo acumula de forma independiente
    ch.registrar_uso("FOIL-001", EventoUso(cantidad=50.0, origen="c2"), "test")
    assert ch.salud("FOIL-001")["vida_consumida"] == 50.0


def test_auditoria_alcoa(ch):
    ch.registrar_uso("FOIL-001", EventoUso(cantidad=1.0, origen="x"), "op1")
    acciones = [a["accion"] for a in ch.auditoria()]
    assert "registrar_componente" in acciones
    assert "registrar_uso" in acciones
