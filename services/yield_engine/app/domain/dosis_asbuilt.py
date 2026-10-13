"""Fase 53 — Dosis ocupacional as-built: flujo → dosis con coeficiente citado.

Convierte el tally real F42b en estimaciones de H*(10) fuera del muro
este (salas ocupadas: residuos radiactivos / WGHS / suministro, F38) y
compara con el objetivo de diseño NCRP 151 (P = 20 µSv/semana en áreas
no controladas).

Fuentes (49.11):
  - H_STAR_AVG: coeficiente flujo→dosis promedio de espectro
    385 pSv·cm² del ²⁵²Cf desnudo (ISO 8529-1; vía PNNL-19273, tabla
    47: 385 pSv·cm² IAEA / 378 calculado). Se usa como PROXY declarado:
    el espectro primario ¹⁸O(p,n) es Maxwelliano ~2,5 MeV (MDPI
    Appl. Sci. 15, 11946, 2025) y el ²⁵²Cf tiene E_media ≈ 2,1 MeV —
    mismo régimen. El coeficiente exacto h*(E) ICRP 74 tabulado queda
    ``pendiente_fuente`` (archivos AMB74/ICRP 74 no descargables
    públicamente; intento registrado).
  - NCRP151: P = 20 µSv/semana (área no controlada), punto a 0,3 m de
    la cara externa.
  - Q_NS: tasa de emisión del caso F32 (TALYS real), 5,9412e11 n/s.

Honestidad canónica:
  - La dosis ABSOLUTA desde el tally OpenMC queda ``no_demostrable``:
    la normalización del tally «flux» de malla difiere de la dilución
    geométrica 1/4πr² por ~3-4 órdenes de magnitud (verificado
    numéricamente en esta fase) — falta reconciliar la normalización
    del tally antes de dar Sv desde él. Las RAZONES (transmisión de
    F51) no se ven afectadas.
  - El escenario geométrico (dilución 1/4πr² + proxy espectral) es un
    cálculo analítico citado, no MC — marcado como tal.
  - 18.10: material de decisión, no recomendación operativa.
"""
from __future__ import annotations

import math

FUENTES = {
    "ISO8529_CF252": ("ISO 8529-1 / IAEA: coeficiente promedio de "
                      "espectro h*(10) = 385 pSv·cm² para ²⁵²Cf desnudo "
                      "(PNNL-19273, tabla 47, 2010)"),
    "MDPI2025": ("MDPI Appl. Sci. 15(22):11946 (2025): el espectro "
                 "primario ¹⁸O(p,n)¹⁸F es Maxwelliano ~2,5 MeV"),
    "NCRP151": ("NCRP Report No. 151 (2005): P = 20 µSv/semana área no "
                "controlada; punto de ocupación a 0,3 m de la cara "
                "externa"),
    "F32_TALYS": ("Tasa de emisión del caso F32 (espectro TALYS real "
                  "¹⁸O(p,xn) 16,5 MeV): Q = 5,9412e11 n/s"),
}

H_STAR_PSV_CM2 = 385.0      # proxy espectral ²⁵²Cf (ISO 8529-1)
P_OBJETIVO_USV_SEM = 20.0   # NCRP 151, área no controlada
Q_NS = 5.9412e11            # n/s (caso F32, TALYS real)


def flujo_geometrico(distancia_m: float, q_ns: float = Q_NS) -> float:
    """Dilución geométrica 1/4πr² de fuente puntual isotrópica."""
    if distancia_m <= 0:
        raise ValueError("distancia no positiva")
    r_cm = distancia_m * 100.0
    return q_ns / (4.0 * math.pi * r_cm * r_cm)


def dosis_usv_sem(flujo_n_cm2_s: float, horas_sem: float,
                  h_star: float = H_STAR_PSV_CM2) -> float:
    """H*(10) semanal a partir de una fluencia n/cm²/s."""
    if horas_sem < 0:
        raise ValueError("horas negativas")
    sv_s = flujo_n_cm2_s * h_star * 1e-12
    return sv_s * horas_sem * 3600.0 * 1e6  # µSv/sem


def escenario_este(distancia_m: float = 3.0, horas_sem: float = 40.0,
                   transmision_muro: float = 0.0282) -> dict:
    """Escenario analítico citado: sala ocupada tras el muro este."""
    phi_in = flujo_geometrico(distancia_m)
    d_in = dosis_usv_sem(phi_in, horas_sem)
    d_out = d_in * transmision_muro
    n_tvl_extra = (math.log10(d_out / P_OBJETIVO_USV_SEM)
                   if d_out > P_OBJETIVO_USV_SEM else 0.0)
    return {"distancia_m": distancia_m, "horas_sem": horas_sem,
            "flujo_cara_interna_n_cm2_s": phi_in,
            "dosis_interna_usv_sem": d_in,
            "transmision_muro_este": transmision_muro,
            "dosis_externa_usv_sem": d_out,
            "p_objetivo_usv_sem": P_OBJETIVO_USV_SEM,
            "tvl_adicionales_requeridos": n_tvl_extra,
            "estado": "escenario_analitico_citado",
            "nota": ("dilución 1/4πr² + proxy ²⁵²Cf + T real F51; NO es "
                     "MC ni medición")}


def verificar_normalizacion_tally(flujo_tally_cara_interna: float,
                                  distancia_m: float = 3.0) -> dict:
    """Compara el tally con el ancla geométrica 1/4πr².

    Si discrepan por órdenes de magnitud, la dosis absoluta desde el
    tally queda ``no_demostrable`` (las razones sí son válidas).
    La ancla se calcula por partícula fuente (q=1), que es la
    normalización del tally OpenMC.
    """
    ancla = flujo_geometrico(distancia_m, q_ns=1.0)
    ratio = flujo_tally_cara_interna / ancla if ancla else float("inf")
    ordenes = abs(math.log10(ratio)) if ratio > 0 else float("inf")
    return {"tally": flujo_tally_cara_interna, "ancla_1sobre4pir2": ancla,
            "ratio": ratio,
            "estado": ("consistente" if ordenes < 1.0
                       else "no_demostrable_normalizacion_tally"),
            "nota": ("el tally de malla «flux» requiere reconciliar su "
                     "normalización antes de dar Sv absolutos desde él")}
