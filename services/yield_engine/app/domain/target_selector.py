# -*- coding: utf-8 -*-
"""Selector de blancos para los casos FEM (Elmer) y MC (OpenGATE) — Fase 32.

El caso térmico FEM y el caso Monte Carlo del blanco dejan de ser una
placa genérica fija: el usuario selecciona un blanco del catálogo y este
módulo traduce sus propiedades CITADAS a los parámetros de cada caso.

REGLAS CANÓNICAS:
- Toda propiedad proviene de fuente citada (49.11) o se marca
  `pendiente_fuente` / `declarado_calculado` (p. ej. densidad de gas por
  ley de gases ideales a presión declarada — cálculo aritmético, no
  simulación).
- La simplificación del FEM se documenta: la conductividad del caso es la
  del CUERPO/respaldo del blanco (que gobierna la extracción de calor);
  el contenido (agua/gas) entra por densidad y espesor de cavidad.
"""
from __future__ import annotations

from dataclasses import replace

from app.infrastructure.elmer.elmer_case import ElmerThermalCase
from app.infrastructure.gate.gate_case import MonteCarloTargetCase

# Conductividades térmicas citadas (tabla targetry PET, Fase 30):
# Ag 415 · Ta 57 · Nb 53,7 · Ni 90,9 W/(m·K) → W/(cm·K) dividiendo por 100.
BLANCOS_SELECCIONABLES = {
    "agua18_ag_estandar": {
        "descripcion": "Blanco líquido H2[18O], cuerpo plata (Nirta estándar)",
        "tipo": "liquido",
        "densidad_contenido_g_cm3": 1.11,
        "fuente_densidad": "Densidad agua enriquecida ~97 % 18O (catálogo Physics Twin, 19.7)",
        "conductividad_cuerpo_w_cm_k": 4.15,
        "fuente_conductividad": "Ag 415 W/(m·K) — tabla targetry PET citada (Fase 30)",
        "radio_cm": 1.0,
        "espesor_cm": 0.5,
        "isotopo_objetivo": "F-18",
    },
    "agua18_nirta_conical_nb": {
        "descripcion": "Nirta Conical Nb de alto rendimiento (IBA)",
        "tipo": "liquido",
        "densidad_contenido_g_cm3": 1.11,
        "fuente_densidad": "Densidad agua enriquecida ~97 % 18O (catálogo Physics Twin)",
        "conductividad_cuerpo_w_cm_k": 0.537,
        "fuente_conductividad": "Nb 53,7 W/(m·K) — tabla targetry PET; geometría Conical: Devillet 2013 WEPSH043",
        "radio_cm": 1.2,
        "espesor_cm": 0.8,
        "isotopo_objetivo": "F-18",
        "nota": "Cavidades 1,8–4,2 mL, 45–145 µA (Devillet 2013); radio/espesor representativos declarados",
    },
    "agua18_cuerpo_ta": {
        "descripcion": "Blanco líquido H2[18O], cuerpo tantalio",
        "tipo": "liquido",
        "densidad_contenido_g_cm3": 1.11,
        "fuente_densidad": "Densidad agua enriquecida ~97 % 18O (catálogo Physics Twin)",
        "conductividad_cuerpo_w_cm_k": 0.57,
        "fuente_conductividad": "Ta 57 W/(m·K) — tabla targetry PET (ventaja química, no térmica, Fase 30)",
        "radio_cm": 1.0,
        "espesor_cm": 0.5,
        "isotopo_objetivo": "F-18",
    },
    "agua_natural_n13": {
        "descripcion": "Blanco líquido agua natural para 13N (16O(p,a)13N)",
        "tipo": "liquido",
        "densidad_contenido_g_cm3": 1.0,
        "fuente_densidad": "Agua natural 1,0 g/cm3 (propiedad tabulada estándar)",
        "conductividad_cuerpo_w_cm_k": 4.15,
        "fuente_conductividad": "Ag 415 W/(m·K) — tabla targetry PET",
        "radio_cm": 1.0,
        "espesor_cm": 0.5,
        "isotopo_objetivo": "N-13",
    },
    "gas_n2_c11": {
        "descripcion": "Blanco gaseoso N2 (+O2 traza) para 11C (14N(p,a)11C), 20 bar",
        "tipo": "gaseoso",
        "densidad_contenido_g_cm3": 0.0224,
        "fuente_densidad": "declarado_calculado: ley de gases ideales N2 a 20 bar, 300 K (aritmética, no simulación)",
        "conductividad_cuerpo_w_cm_k": 1.67,
        "fuente_conductividad": "Al 167 W/(m·K) cuerpo aluminio — tabla targetry PET",
        "radio_cm": 1.5,
        "espesor_cm": 15.0,
        "isotopo_objetivo": "C-11",
        "nota": "Cuerpo cilíndrico largo típico de blanco gaseoso (geometría declarada)",
    },
    "solido_ni64_cu64": {
        "descripcion": "Blanco sólido 64Ni enriquecido electrodepositado para 64Cu",
        "tipo": "solido",
        "densidad_contenido_g_cm3": 8.9,
        "fuente_densidad": "Ni 8,9 g/cm3 (propiedad tabulada estándar)",
        "conductividad_cuerpo_w_cm_k": 0.909,
        "fuente_conductividad": "Ni 90,9 W/(m·K) — tabla targetry PET; ruta/TTY: IAEA Pub1717",
        "radio_cm": 0.8,
        "espesor_cm": 0.02,
        "isotopo_objetivo": "Cu-64",
        "nota": "Capa ~200 µm sobre respaldo (espesor declarado representativo)",
    },
}

# Simplificación documentada del FEM: coeficiente de película del agua de
# refrigeración y temperatura del refrigerante (escenario declarado).
FILM_COEFF_DECLARADO_W_CM2_K = 1.0
COOLANT_TEMP_DECLARADO_K = 293.15


def catalogo_blancos() -> dict:
    """Catálogo completo con fuentes (para la API y el mockup)."""
    return BLANCOS_SELECCIONABLES


def caso_fem_desde_blanco(blanco_id: str, beam_power_w: float,
                          beam_sigma_cm: float | None = None) -> ElmerThermalCase:
    """Traduce el blanco seleccionado a un caso térmico FEM (Elmer).

    La conductividad del caso es la del cuerpo/respaldo del blanco
    (gobierna la extracción de calor — simplificación documentada)."""
    if blanco_id not in BLANCOS_SELECCIONABLES:
        raise ValueError(f"blanco desconocido: {blanco_id} "
                         f"(válidos: {sorted(BLANCOS_SELECCIONABLES)})")
    b = BLANCOS_SELECCIONABLES[blanco_id]
    return ElmerThermalCase(
        beam_power_w=beam_power_w,
        spot_radius_cm=b["radio_cm"],
        target_thickness_cm=b["espesor_cm"],
        conductivity_w_cm_k=b["conductividad_cuerpo_w_cm_k"],
        film_coeff_w_cm2_k=FILM_COEFF_DECLARADO_W_CM2_K,
        coolant_temp_k=COOLANT_TEMP_DECLARADO_K,
        beam_sigma_cm=beam_sigma_cm,
    )


def caso_mc_desde_blanco(blanco_id: str, beam_energy_mev: float = 16.5,
                         n_histories: int = 50_000) -> MonteCarloTargetCase:
    """Traduce el blanco seleccionado a un caso Monte Carlo (OpenGATE):
    densidad del contenido, radio y espesor de la cavidad del blanco."""
    if blanco_id not in BLANCOS_SELECCIONABLES:
        raise ValueError(f"blanco desconocido: {blanco_id} "
                         f"(válidos: {sorted(BLANCOS_SELECCIONABLES)})")
    b = BLANCOS_SELECCIONABLES[blanco_id]
    return replace(
        MonteCarloTargetCase(),
        beam_energy_mev=beam_energy_mev,
        target_radius_cm=b["radio_cm"],
        target_thickness_cm=b["espesor_cm"],
        target_density_g_cm3=b["densidad_contenido_g_cm3"],
        n_histories=n_histories,
    )
