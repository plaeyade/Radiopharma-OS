"""Fase 51 — Blindaje as-built: método TVL sobre la geometría real BIND.

Combina:
  - la transmisión REAL medida del muro este (1,70 m, estimado_sobre_plano)
    a partir del tally OpenMC bind_real de F42b (30k historias, 3 semillas);
  - TVL de referencia citados (49.11): Biggs 2010 (basado en NCRP 151) para
    neutrones rápidos en concreto 2,35 g/cm³ y la regla de ajuste por
    densidad (el TVL escala en razón inversa a la densidad — misma
    densidad área);
  - las densidades de las cotizaciones reales de F39 (2,5 y 3,5 g/cm³).

Honestidad canónica:
  - El TVL efectivo empírico se marca ``empirico_tally_f42b`` con sus
    caveats (tally de flujo sin S(α,β), 30k historias, paredes no oeste
    estimadas, estadística de penetración profunda limitada).
  - Biggs 2010 corresponde a fotoneutrones de linac 18 MV — se usa como
    contraste citado, NO como valor del ciclotrón (espectro distinto).
  - La conversión flujo→dosis (coeficientes ICRP 74) queda
    ``pendiente_fuente``: el módulo trabaja en transmisión/TVL, no en Sv.
  - Resultado: material de decisión, no recomendación operativa (18.10).
"""
from __future__ import annotations

import math

FUENTES = {
    "BIGGS2010": ("Biggs PJ, «Radiation Shielding for Megavoltage Photon "
                  "Therapy Machines», 2010 (valores de NCRP 151): TVL "
                  "neutrones rápidos concreto 2,35 g/cm³ = 20,3 cm; "
                  "polietileno = 10,2 cm; ajuste de TVL por densidad"),
    "NCRP151": ("NCRP Report No. 151 (2005): objetivo de diseño "
                "P = 20 µSv/semana en áreas no controladas; punto de "
                "ocupación a 0,3 m de la cara externa de la barrera"),
    "F42B_TALLY": ("Tally OpenMC real bind_real, 3×10k historias "
                   "(evidencia_v072/fase42b/combinado_bind_f42b.json)"),
    "F38_PLANO": ("Plano BIND 02-10-26: muro oeste 2,11 m medido; muro "
                  "este 1,70 m estimado_sobre_plano"),
}

# Transmisión real del muro este (1,70 m) medida en el tally F42b:
# media de 3 semillas, cara interior de bóveda vs slab ocupado exterior.
TRANSMISION_MURO_ESTE = {
    "valor": 0.0282,
    "sigma_semillas": 0.0022,
    "espesor_m": 1.70,
    "estado_espesor": "estimado_sobre_plano",
    "estado": "empirico_tally_f42b",
    "caveats": ["tally de flujo (no dosis), sin S(α,β)",
                "30k historias — penetración profunda con estadística "
                "limitada",
                "paredes no-oeste estimadas (sin alzados en el DWG)"],
}

RHO_REF = 2.35          # g/cm³ concreto ordinario (Biggs 2010 / NCRP 151)
TVL_REF_N_CM = 20.3     # Biggs 2010, neutrones rápidos (linac) — contraste


def tvl_efectivo_empirico(transmision: float = TRANSMISION_MURO_ESTE["valor"],
                          espesor_m: float = TRANSMISION_MURO_ESTE["espesor_m"]
                          ) -> dict:
    """TVL efectivo derivado del tally real (flujo), con caveats."""
    if not (0 < transmision < 1):
        raise ValueError("transmisión fuera de (0,1)")
    n_tvl = math.log10(1.0 / transmision)
    return {"n_tvl_en_espesor": n_tvl,
            "tvl_efectivo_m": espesor_m / n_tvl,
            "estado": "empirico_tally_f42b",
            "caveats": TRANSMISION_MURO_ESTE["caveats"]}


def tvl_por_densidad(rho_g_cm3: float, tvl_m_ref: float,
                     rho_ref: float = RHO_REF) -> dict:
    """Escala un TVL de referencia a otra densidad (misma densidad área).

    Regla citada (Biggs 2010 / NCRP 151): el TVL se ajusta con la
    densidad — t(ρ) = t_ref · ρ_ref/ρ.
    """
    if rho_g_cm3 <= 0:
        raise ValueError("densidad no positiva")
    return {"rho_g_cm3": rho_g_cm3,
            "tvl_m": tvl_m_ref * rho_ref / rho_g_cm3,
            "fuente_regla": "BIGGS2010"}


def espesor_para_transmision(t_objetivo: float, tvl_m: float) -> float:
    """Espesor necesario para alcanzar una transmisión objetivo."""
    if not (0 < t_objetivo < 1):
        raise ValueError("transmisión objetivo fuera de (0,1)")
    return tvl_m * math.log10(1.0 / t_objetivo)


def evaluar_opciones(t_objetivo: float = 1e-4,
                     densidades=(2.5, 3.5)) -> dict:
    """Espesor requerido por opción de densidad, con los dos TVL.

    Devuelve el espesor con el TVL empírico del tally (nuestro espectro,
    caveat declarado) y con el TVL citado de Biggs 2010 (contraste,
    espectro linac). t_objetivo por defecto 1e-4 es un ESCENARIO
    declarado: la transmisión objetivo real exige la conversión
    flujo→dosis (ICRP 74), pendiente_fuente.
    """
    emp = tvl_efectivo_empirico()
    opciones = {}
    for rho in densidades:
        t_emp = tvl_por_densidad(rho, emp["tvl_efectivo_m"])
        t_big = tvl_por_densidad(rho, TVL_REF_N_CM / 100.0)
        opciones[f"{rho:g}"] = {
            "espesor_m_empirico": espesor_para_transmision(
                t_objetivo, t_emp["tvl_m"]),
            "espesor_m_biggs2010_contraste": espesor_para_transmision(
                t_objetivo, t_big["tvl_m"]),
        }
    return {"t_objetivo_escenario": t_objetivo,
            "nota_objetivo": ("escenario declarado 1e-4; el objetivo real "
                              "exige flujo→dosis ICRP 74: pendiente_fuente"),
            "tvl_efectivo_empirico_m": emp["tvl_efectivo_m"],
            "opciones": opciones,
            "nota_1810": ("material de decisión, no recomendación "
                          "operativa (18.10)")}
