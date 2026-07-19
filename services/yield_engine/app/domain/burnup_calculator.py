"""
Burnup Engine (EDS v2.0, Vol. II cap. 16): depleción del blanco enriquecido.

Modelo de grupo único con depleción uniforme (MVP):
    dN_t/dt = -k * N_t           (consumo del núclido blanco)
    dN_p/dt = R0 * e^{-k t} - λ * N_p

con k = σ_burnup * φ (tasa de quemado), φ = flujo de protones [p/cm²/s].
Solución analítica (N_p(0) = 0):
    A_EOB(t) = λ * N_p = A_sat * I * λ/(λ-k) * (e^{-k t} - e^{-λ t})

Límites: k→0 recupera el modelo sin quemado; k=λ tiene forma límite
A = A_sat * I * λ t e^{-λ t}.

Nota física: para blancos líquidos/gaseosos de ciclotrones médicos el
quemado global por lote es típicamente <1 % (k ~ 1e-10 s^-1); el efecto
relevante es local (región del pico de Bragg), previsto para una versión
2D acoplada al Elmer FEM Service.
"""
from __future__ import annotations

import math

from app.domain.entities import PROTONS_PER_SECOND_PER_UA

# σ_burnup efectiva por defecto (estimación de literatura para sección
# eficaz total no-elástica de p + blanco ligero a 10-20 MeV).
DEFAULT_BURNUP_XS_MB: float = 500.0
MB_TO_CM2: float = 1e-27


class BurnupCalculator:
    """Corrección de rendimiento por quemado del núclido blanco."""

    @staticmethod
    def burnup_rate_per_s(
        current_ua: float,
        beam_spot_cm2: float,
        burnup_xs_mb: float = DEFAULT_BURNUP_XS_MB,
    ) -> float:
        """k = σ_b · φ  [s^-1]."""
        if beam_spot_cm2 <= 0.0:
            raise ValueError("beam_spot_cm2 debe ser > 0")
        flux = PROTONS_PER_SECOND_PER_UA * current_ua / beam_spot_cm2
        return burnup_xs_mb * MB_TO_CM2 * flux

    @staticmethod
    def eob_with_burnup(
        a_sat_mbq_ua: float,
        current_ua: float,
        irradiation_time_min: float,
        decay_constant_s: float,
        burnup_rate_s: float,
    ) -> float:
        """Actividad EOB [MBq] considerando depleción del blanco."""
        lam = decay_constant_s
        k = burnup_rate_s
        t = irradiation_time_min * 60.0
        r0 = a_sat_mbq_ua * current_ua            # MBq a saturación (sin quemado)
        if k <= 0.0:
            return r0 * (1.0 - math.exp(-lam * t))
        if abs(lam - k) < 1e-12:                  # caso límite λ = k
            return r0 * lam * t * math.exp(-lam * t)
        return r0 * lam / (lam - k) * (math.exp(-k * t) - math.exp(-lam * t))

    def compare(
        self,
        a_sat_mbq_ua: float,
        current_ua: float,
        irradiation_time_min: float,
        decay_constant_s: float,
        beam_spot_cm2: float,
        burnup_xs_mb: float = DEFAULT_BURNUP_XS_MB,
    ) -> dict:
        """Comparativa con/sin quemado para un lote."""
        k = self.burnup_rate_per_s(current_ua, beam_spot_cm2, burnup_xs_mb)
        eob_sin = self.eob_with_burnup(
            a_sat_mbq_ua, current_ua, irradiation_time_min, decay_constant_s, 0.0)
        eob_con = self.eob_with_burnup(
            a_sat_mbq_ua, current_ua, irradiation_time_min, decay_constant_s, k)
        depletion_fraction = 1.0 - math.exp(-k * irradiation_time_min * 60.0)
        return {
            "burnup_rate_s-1": k,
            "target_depletion_fraction": depletion_fraction,
            "eob_no_burnup_gbq": eob_sin / 1000.0,
            "eob_with_burnup_gbq": eob_con / 1000.0,
            "loss_gbq": (eob_sin - eob_con) / 1000.0,
            "loss_percent": (1.0 - eob_con / eob_sin) * 100.0 if eob_sin > 0 else 0.0,
        }
