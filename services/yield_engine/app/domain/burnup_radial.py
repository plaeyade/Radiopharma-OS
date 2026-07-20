"""
Burnup Engine radial 2D (EDS v2.0, Vol. II cap. 16 — extensión F2):
depleción no uniforme del blanco bajo un haz con perfil gaussiano.

Modelo
------
El modelo 1D (BurnupMultizoneCalculator) reparte la depleción axialmente
pero asume flujo uniforme en la sección del haz. Los haces reales de
ciclotrón tienen perfil aproximadamente gaussiano:

    φ(r) = φ_peak · exp(−r² / 2σ_b²)      sobre el disco del spot (radio R)

La normalización es exacta: el flujo medio sobre el spot coincide con el
del modelo 1D (misma corriente y misma área), de modo que el resultado
radial es comparable con el EOB 1D punto a punto.

    φ_mean = P / (πR²)  =  φ_peak · (2σ_b²/R²) · (1 − exp(−R²/2σ_b²))

El spot se divide en N anillos concéntricos. En cada anillo j:
    w_j  = fracción de la producción total (∝ ∫_anillo φ dA, forma cerrada)
    k_j  = σ_b,eff · φ_j        (tasa de quemado local del anillo)
    A_j  = w_j · R_p · (1 − exp(−(λ + k_j)t)) / (λ + k_j)

donde σ_b,eff es la sección eficaz de quemado media ponderada por
producción del perfil axial 1D (misma física, aislada la dimensión
radial) y R_p la tasa de producción total sin quemado.

Propiedades físicas que deben cumplirse (verificadas en tests):
    * EOB_2D ≤ EOB_1D: la depleción se concentra en el eje (φ_peak > φ_mean),
      y la pérdida crece con la no uniformidad (desigualdad de Jensen).
    * n_rings = 1 reproduce el modelo uniforme (φ constante).
    * Σ w_j = 1 exactamente (forma cerrada de la gaussiana truncada).

Este perfil radial de depleción, junto con el axial del modelo 1D, es la
entrada del acoplamiento FEM (Elmer) para el cálculo térmico 2D real.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.domain.entities import MB_PER_CM2, PROTONS_PER_SECOND_PER_UA
from app.domain.interfaces import ReactionDataProvider

# Fracción mínima de σ_b/R admisible para evitar geometrías degeneradas
_MIN_SIGMA_FRAC: float = 1e-3


@dataclass(frozen=True)
class RadialRing:
    """Estado de un anillo concéntrico del blanco."""
    index: int
    r_in_cm: float
    r_out_cm: float
    r_mean_cm: float
    flux_rel: float              # φ_j / φ_peak (perfil gaussiano)
    production_weight: float     # w_j: fracción de la producción total
    burnup_rate_s: float         # k_j [s^-1]
    depletion_fraction: float    # 1 − exp(−k_j · t)


@dataclass(frozen=True)
class BurnupRadial:
    """Resultado agregado del cálculo radial 2D."""
    n_rings: int
    spot_radius_cm: float
    beam_sigma_cm: float
    flux_peak_cm2_s: float
    flux_mean_cm2_s: float
    burnup_xs_eff_mb: float      # σ_b,eff ponderada por producción (perfil 1D)
    rings: tuple[RadialRing, ...]
    burnup_rate_max_s: float     # eje del haz (anillo central)
    depletion_weighted: float    # depleción media ponderada por producción
    depletion_max: float         # depleción máxima local (eje)
    eob_ideal_gbq: float         # sin quemado
    eob_1d_gbq: float            # modelo 1D (flujo uniforme, axial)
    eob_2d_gbq: float            # modelo radial gaussiano
    loss_vs_ideal_gbq: float
    loss_vs_1d_gbq: float        # corrección radial respecto al 1D


def gaussian_peak_factor(spot_radius_cm: float, beam_sigma_cm: float) -> float:
    """Factor φ_peak/φ_mean de la gaussiana truncada en el radio del spot.

    Forma cerrada: A_spot / ∫_spot exp(−r²/2σ²) dA = R² / (2σ²(1−e^{−R²/2σ²})).
    Tiende a 1 cuando σ >> R (perfil casi plano).
    """
    r2 = spot_radius_cm * spot_radius_cm
    s2 = beam_sigma_cm * beam_sigma_cm
    return r2 / (2.0 * s2 * (1.0 - math.exp(-r2 / (2.0 * s2))))


class BurnupRadialCalculator:
    """Depleción radial bajo haz gaussiano, coherente con el modelo 1D."""

    def __init__(self, reaction_data: ReactionDataProvider) -> None:
        self._rxn = reaction_data

    def compute(
        self,
        reaction_id: str,
        beam_energy_mev: float,
        current_ua: float,
        irradiation_time_min: float,
        beam_spot_cm2: float,
        beam_sigma_cm: float,
        n_rings: int,
        burnup_xs_eff_mb: float,
        eob_ideal_gbq: float,
        eob_1d_gbq: float,
    ) -> BurnupRadial:
        """El llamador (application) aporta EOB ideal y EOB 1D del modelo
        multizona con los mismos parámetros, garantizando coherencia, y la
        σ_b,eff ponderada por producción del perfil axial."""
        from app.application.production_service import REACTIONS

        if beam_spot_cm2 <= 0.0:
            raise ValueError("beam_spot_cm2 debe ser > 0")
        if n_rings < 1:
            raise ValueError("n_rings debe ser >= 1")
        if burnup_xs_eff_mb < 0.0:
            raise ValueError("burnup_xs_eff_mb debe ser >= 0")
        if eob_ideal_gbq < 0.0 or eob_1d_gbq < 0.0:
            raise ValueError("los EOB de referencia deben ser >= 0")

        spot_r = math.sqrt(beam_spot_cm2 / math.pi)
        if beam_sigma_cm <= _MIN_SIGMA_FRAC * spot_r:
            raise ValueError(
                f"beam_sigma_cm debe ser >= {_MIN_SIGMA_FRAC}·R_spot "
                f"({spot_r:.4f} cm)")
        # σ > R es físicamente válido (haz más ancho que el colimador):
        # la forma cerrada del factor de pico tiende a 1 (perfil plano).
        sigma = beam_sigma_cm

        product = REACTIONS[reaction_id]["product"]
        lam = self._rxn.get_decay_constant(product)
        t_s = irradiation_time_min * 60.0
        phi_mean = PROTONS_PER_SECOND_PER_UA * current_ua / beam_spot_cm2
        peak_factor = gaussian_peak_factor(spot_r, sigma)
        phi_peak = phi_mean * peak_factor

        # Tasa de producción total sin quemado [GBq/s] (del EOB ideal)
        if eob_ideal_gbq <= 0.0 or t_s <= 0.0:
            prod_rate = 0.0
        else:
            prod_rate = eob_ideal_gbq * lam / (1.0 - math.exp(-lam * t_s))

        edges = [spot_r * j / n_rings for j in range(n_rings + 1)]
        s2 = sigma * sigma
        norm = 1.0 - math.exp(-spot_r * spot_r / (2.0 * s2))
        rings: list[RadialRing] = []
        eob_2d = 0.0
        for j in range(n_rings):
            r_in, r_out = edges[j], edges[j + 1]
            # Peso del anillo: integral cerrada de la gaussiana truncada
            w = (math.exp(-r_in * r_in / (2.0 * s2))
                 - math.exp(-r_out * r_out / (2.0 * s2))) / norm
            # Flujo medio del anillo: w·(flujo total) / área del anillo
            area_frac = (r_out * r_out - r_in * r_in) / (spot_r * spot_r)
            phi_j = phi_mean * w / area_frac if area_frac > 0 else phi_peak
            k = burnup_xs_eff_mb * MB_PER_CM2 * phi_j
            if prod_rate > 0.0:
                eob_2d += (w * prod_rate
                           * (1.0 - math.exp(-(lam + k) * t_s)) / (lam + k))
            rings.append(RadialRing(
                index=j, r_in_cm=r_in, r_out_cm=r_out,
                r_mean_cm=0.5 * (r_in + r_out),
                flux_rel=phi_j / phi_peak,
                production_weight=w, burnup_rate_s=k,
                depletion_fraction=1.0 - math.exp(-k * t_s)))

        dep_weighted = sum(r.production_weight * r.depletion_fraction
                           for r in rings)
        return BurnupRadial(
            n_rings=n_rings, spot_radius_cm=spot_r, beam_sigma_cm=sigma,
            flux_peak_cm2_s=phi_peak, flux_mean_cm2_s=phi_mean,
            burnup_xs_eff_mb=burnup_xs_eff_mb, rings=tuple(rings),
            burnup_rate_max_s=rings[0].burnup_rate_s,
            depletion_weighted=dep_weighted,
            depletion_max=rings[0].depletion_fraction,
            eob_ideal_gbq=eob_ideal_gbq, eob_1d_gbq=eob_1d_gbq,
            eob_2d_gbq=eob_2d,
            loss_vs_ideal_gbq=eob_ideal_gbq - eob_2d,
            loss_vs_1d_gbq=eob_1d_gbq - eob_2d)
