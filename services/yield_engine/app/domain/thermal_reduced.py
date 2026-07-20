"""
Modelo térmico reducido del blanco (solución analítica estacionaria).

Cadena de transferencia de calor del blanco líquido/gaseoso de ciclotrón:

    haz (potencia P) → depósito volumétrico en el blanco → conducción
    axial a través del espesor del blanco (ΔT = q''·t/k) → película de
    convección al refrigerante (ΔT = q''/h)

El haz gaussiano concentra la potencia en el eje: el pico de densidad de
flujo térmico es q''_peak = f_pico · P/A, con f_pico la forma cerrada de
la gaussiana truncada (misma normalización que el Burnup radial).

Unidades: W, cm, K. La conductividad k se expresa en W/(cm·K) y el
coeficiente de película h en W/(cm²·K) para mantener coherencia con las
unidades del dominio (spot en cm²).

Este modelo es la referencia exacta del acoplamiento FEM: Elmer resuelve
la ecuación del calor 2D axisimétrica sobre el mismo caso, y el test de
comparación exige acuerdo con este modelo reducido (solución analítica).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.domain.burnup_radial import gaussian_peak_factor

# 1 MeV · 1 µA = 1 W exactamente (1e6 eV × 1.602e-19 C × 1e-6 C/s)
W_PER_MEV_UA: float = 1.0


@dataclass(frozen=True)
class ThermalReduced:
    """Resultado del modelo térmico reducido."""
    beam_power_w: float
    spot_area_cm2: float
    heat_flux_mean_w_cm2: float     # q'' medio sobre el spot
    heat_flux_peak_w_cm2: float     # q'' pico (eje del haz gaussiano)
    peak_factor: float              # q''_peak / q''_mean
    delta_t_conduction_k: float     # q''_peak · espesor / k
    delta_t_film_k: float           # q''_peak / h
    t_peak_k: float                 # T refrigerante + ΔT total (eje)
    t_mean_k: float                 # T en el flujo medio
    t_limit_k: float
    margin_k: float                 # t_limit − t_peak (> 0 → seguro)
    within_limit: bool
    max_current_ua: float           # corriente que satura el límite térmico


def beam_power_w(energy_mev: float, current_ua: float) -> float:
    """Potencia depositada por el haz [W] (1 MeV·µA = 1 W)."""
    if energy_mev <= 0.0 or current_ua < 0.0:
        raise ValueError("energy_mev > 0 y current_ua >= 0 requeridos")
    return energy_mev * current_ua * W_PER_MEV_UA


def thermal_reduced(
    beam_energy_mev: float,
    current_ua: float,
    beam_spot_cm2: float,
    target_thickness_cm: float,
    conductivity_w_cm_k: float,
    film_coeff_w_cm2_k: float,
    coolant_temp_k: float,
    t_limit_k: float,
    beam_sigma_cm: float | None = None,
) -> ThermalReduced:
    """Solución analítica estacionaria: conducción 1D + película, con pico
    gaussiano si se aporta beam_sigma_cm (si no, perfil uniforme)."""
    if beam_spot_cm2 <= 0.0:
        raise ValueError("beam_spot_cm2 debe ser > 0")
    if target_thickness_cm <= 0.0:
        raise ValueError("target_thickness_cm debe ser > 0")
    if conductivity_w_cm_k <= 0.0:
        raise ValueError("conductivity_w_cm_k debe ser > 0")
    if film_coeff_w_cm2_k <= 0.0:
        raise ValueError("film_coeff_w_cm2_k debe ser > 0")
    if t_limit_k <= coolant_temp_k:
        raise ValueError("t_limit_k debe ser > coolant_temp_k")

    power = beam_power_w(beam_energy_mev, current_ua)
    q_mean = power / beam_spot_cm2
    if beam_sigma_cm is not None:
        spot_r = math.sqrt(beam_spot_cm2 / math.pi)
        factor = gaussian_peak_factor(spot_r, beam_sigma_cm)
    else:
        factor = 1.0
    q_peak = q_mean * factor

    # Resistencia térmica serie: conducción + película [K·cm²/W]
    r_th = target_thickness_cm / conductivity_w_cm_k + 1.0 / film_coeff_w_cm2_k
    d_cond = q_peak * target_thickness_cm / conductivity_w_cm_k
    d_film = q_peak / film_coeff_w_cm2_k
    t_peak = coolant_temp_k + q_peak * r_th
    t_mean = coolant_temp_k + q_mean * r_th
    margin = t_limit_k - t_peak
    # Corriente que hace T_peak = T_limit (potencia proporcional a I)
    q_limit = (t_limit_k - coolant_temp_k) / r_th
    power_limit = q_limit * beam_spot_cm2 / factor
    max_current = power_limit / (beam_energy_mev * W_PER_MEV_UA)

    return ThermalReduced(
        beam_power_w=power, spot_area_cm2=beam_spot_cm2,
        heat_flux_mean_w_cm2=q_mean, heat_flux_peak_w_cm2=q_peak,
        peak_factor=factor, delta_t_conduction_k=d_cond, delta_t_film_k=d_film,
        t_peak_k=t_peak, t_mean_k=t_mean, t_limit_k=t_limit_k,
        margin_k=margin, within_limit=margin >= 0.0,
        max_current_ua=max_current)
