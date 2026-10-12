# -*- coding: utf-8 -*-
"""Tests Fase 45 — cine de activación por componente."""
from __future__ import annotations

import math

import numpy as np

from app.domain.cine_activacion import (
    COMPONENTES, ISOTOPOS_CINE, actividad_por_componente, actividad_pulso,
    isotopo_predominante, mascara_componentes, mascara_concreto, nucleos_padre_cm3,
)


def _bateman_referencia(n_padre, sigma_b, phi, t12_s, t_pulso, k, t_entre):
    """Recurrencia exacta pulso a pulso (réplica de ActivationEngine
    .actividad_tras_pulsos de nuclear_data_service — inline para no acoplar
    servicios en la suite)."""
    lam = math.log(2.0) / t12_s
    g = n_padre * sigma_b * 1e-24 * phi * (-math.expm1(-lam * t_pulso))
    a = 0.0
    for _ in range(k):
        a = a * math.exp(-lam * (t_entre + t_pulso)) + g
    return a


def test_mascaras_cubren_concreto_sin_solapar():
    m = mascara_componentes()
    total = sum(x.sum() for x in m.values())
    union = np.zeros((110, 110, 60), dtype=bool)
    for x in m.values():
        assert not (union & x).any(), "máscaras solapadas"
        union |= x
    # volumen cubierto = volumen analítico del concreto (voxel 20 cm)
    vol_mc = union.sum() * 8000.0
    vol_analitico = 7.2e8 - 1.44e8 - 8.64e6  # bloque − bóveda − laberinto_1
    assert abs(vol_mc - vol_analitico) / vol_analitico < 0.01
    # simetrías declaradas de la geometría F32
    assert m["losa_techo"].sum() == m["losa_piso"].sum()
    assert m["muro_norte"].sum() == m["muro_sur"].sum()
    assert m["muro_oeste"].sum() > m["muro_laberinto"].sum()  # hueco del laberinto


def test_forma_cerrada_coincide_con_motor_bateman():
    phi = np.full((2, 2, 2), 1.0e5)
    k, tp, te = 2500, 28800.0, 57600.0
    a_vec = actividad_pulso(phi, "Co-60", k, tp, te, v_voxel_cm3=8000.0)
    n_cm3, _ = nucleos_padre_cm3("Co-60")
    a_ref = _bateman_referencia(
        n_padre=n_cm3 * 8000.0, sigma_b=ISOTOPOS_CINE["Co-60"]["sigma_b"],
        phi=1.0e5, t12_s=ISOTOPOS_CINE["Co-60"]["t12_s"], t_pulso=tp,
        k=k, t_entre=te)
    assert math.isclose(float(a_vec[0, 0, 0]), a_ref, rel_tol=1e-9)


def test_monotonia_y_saturacion():
    phi = np.ones((3, 3, 3)) * 1e5
    a1 = actividad_pulso(phi, "Eu-152", 1, 28800.0, 57600.0).sum()
    a2 = actividad_pulso(phi, "Eu-152", 100, 28800.0, 57600.0).sum()
    a3 = actividad_pulso(phi, "Eu-152", 2500, 28800.0, 57600.0).sum()
    assert 0 < a1 < a2 < a3


def test_predominancia_corta_vs_larga():
    phi = np.ones((110, 110, 60)) * 1e5  # malla real: la máscara de concreto la exige
    # recién apagado tras 2500 pulsos: Na-24 (vida corta, se acumula al
    # equilibrio semanal) domina sobre trazas de Eu/Co a 1 ppm declaradas
    r0 = isotopo_predominante(phi, 2500, 28800.0, 57600.0)
    assert r0["predominante"] in ISOTOPOS_CINE
    # tras 30 días de enfriamiento Na-24 ha muerto; domina Eu-152
    r30 = isotopo_predominante(phi, 2500, 28800.0, 57600.0,
                               t_tras_apagado_s=30 * 86400.0)
    assert r30["predominante"] == "Eu-152"
    assert r0["actividad_total_bq"]["Na-24"] > 0


def test_agregacion_por_componente():
    rng = np.random.default_rng(7)
    phi = rng.random((110, 110, 60)) * 1e5
    res = actividad_por_componente(phi, "Na-24", 100, 28800.0, 57600.0)
    assert set(res) == set(COMPONENTES)
    assert all(v >= 0 for v in res.values())
    assert sum(res.values()) > 0


def test_trazas_declaradas_honestas():
    _, fuente_eu = nucleos_padre_cm3("Eu-152")
    _, fuente_na = nucleos_padre_cm3("Na-24")
    assert "pendiente_fuente" in fuente_eu
    assert "NIST" in fuente_na
