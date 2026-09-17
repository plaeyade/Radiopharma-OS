# -*- coding: utf-8 -*-
"""Modelo de haz primario parametrizado — Fase 34 (hoja de ruta ①).

Haz de protones del ciclotrón como fuente parametrizada: energía del
modelo catalogado (citada), corriente, perfil transversal gaussiano
(σ declarado) y divergencia (declarada, pendiente de medición con haz
real — instrucción permanente: nunca bloquear por datos de haz).

Salida: parámetros listos para la fuente GenericSource de OpenGATE o el
haz del render Cycles, con su origen marcado (49.11).
"""
from __future__ import annotations

from dataclasses import dataclass

# Energías citadas del catálogo de ciclotrones (Fase 30/31).
_ENERGIAS = {
    "iba_cyclone_kiube": (18.0, "IBA KIUBE 18 MeV (ficha comercial citada)"),
    "ge_pettrace_840": (16.5, "PETtrace 16,5 MeV (data sheet PT800 citada)"),
    "ge_pettrace_860": (16.5, "PETtrace 16,5 MeV (data sheet PT800 citada)"),
    "ge_pettrace_880": (16.5, "PETtrace 16,5 MeV (data sheet PT800 citada)"),
    "ge_pettrace_890": (16.5, "PETtrace 16,5 MeV (data sheet PT800 citada)"),
    "ge_minitrace_qilin": (9.6, "MINItrace Qilin — energía declarada pendiente_fuente"),
    "abt_bg75": (7.5, "ABT BG-75 7,5 MeV (Zaman 2019 PMC6709360)"),
    "best_b100": (7.5, "Best B-100 7,5 MeV (BCS citada)"),
    "best_b6_15": (15.0, "Best B6-15 variable 6-15 MeV (BCS 2021) — toma 15"),
    "lbt_7": (7.0, "LBT 7 MeV (Preqin 2025 — modelo citado)"),
    "lbt_11": (11.0, "LBT 11 MeV (Preqin 2025 — modelo citado)"),
    "lbt_20": (20.0, "LBT 20 MeV (Preqin 2025 — modelo citado)"),
}

# Perfil y divergencia: escenario declarado pendiente de medición real.
SIGMA_DEFAULT_MM = 3.0
DIVERGENCIA_DEFAULT_MRAD = 5.0


@dataclass(frozen=True)
class HazPrimario:
    ciclotron_id: str
    energia_mev: float
    corriente_ua: float
    sigma_mm: float
    divergencia_mrad: float
    fuente_energia: str
    marcador_perfil: str

    def potencia_haz_w(self) -> float:
        """P = E·I — aritmética directa (W = MeV·µA)."""
        return self.energia_mev * self.corriente_ua

    def densidad_pico_w_mm2(self) -> float:
        """Pico del perfil gaussiano: P/(2πσ²)."""
        import math
        return self.potencia_haz_w() / (2.0 * math.pi * self.sigma_mm ** 2)


def haz_desde_ciclotron(ciclotron_id: str, corriente_ua: float,
                        sigma_mm: float = SIGMA_DEFAULT_MM,
                        divergencia_mrad: float = DIVERGENCIA_DEFAULT_MRAD
                        ) -> HazPrimario:
    """Haz parametrizado del ciclotrón elegido (energía citada)."""
    if ciclotron_id not in _ENERGIAS:
        raise ValueError(f"ciclotron_id desconocido: {ciclotron_id} "
                         f"(válidos: {sorted(_ENERGIAS)})")
    if corriente_ua <= 0 or sigma_mm <= 0 or divergencia_mrad < 0:
        raise ValueError("corriente/sigma deben ser > 0 y divergencia >= 0")
    e, fu = _ENERGIAS[ciclotron_id]
    return HazPrimario(
        ciclotron_id=ciclotron_id,
        energia_mev=e,
        corriente_ua=corriente_ua,
        sigma_mm=sigma_mm,
        divergencia_mrad=divergencia_mrad,
        fuente_energia=fu,
        marcador_perfil=("perfil gaussiano y divergencia: escenario "
                         "declarado pendiente de medición con haz real "
                         "(nunca bloquear por datos de haz)"),
    )
