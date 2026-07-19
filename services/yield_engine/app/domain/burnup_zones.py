"""
Burnup Engine multizona 1D (EDS v2.0, Vol. II cap. 16): depleción del blanco
resuelta axialmente a lo largo de la dirección del haz.

Modelo: el blanco grueso se divide en N capas axiales. En cada capa j:
    k_j = σ_b(E_j) · φ_j          (tasa de quemado local)
    φ_{j+1} = φ_j · exp(−σ_b(E_j) · n_areal,j)   (atenuación del flujo)

con σ_b(E) paramétrica con umbral (reacciones no elásticas p + blanco):
    σ_b(E) = σ_max · (1 − exp(−(E − E_th)/E0))

La fracción de producción de cada capa se obtiene de la misma integral
σ(E)/S(E) del YieldCalculator (misma malla de 4000 puntos), de modo que la
suma de capas sin quemado reproduce exactamente el EOB del modelo base.
Cada capa resuelve el Bateman con término de quemado (idéntico al modelo
de grupo único, aplicado localmente).

Nota física: el quemado es máximo en la entrada del blanco (σ_b crece con E)
y casi nulo cerca del umbral; el perfil axial resultante es la entrada del
futuro acoplamiento 2D con Elmer FEM Service.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from app.domain.entities import (MB_PER_CM2, PROTONS_PER_SECOND_PER_UA,
                                 TargetMaterial)
from app.domain.interfaces import ReactionDataProvider, StoppingPowerProvider

# Meseta por defecto de la sección no elástica (literatura, p a 10-20 MeV)
DEFAULT_XS_MAX_MB: float = 800.0
# Escala de energía del modelo con umbral [MeV]
XS_E0_MEV: float = 5.0
# Margen sobre el umbral bajo el cual σ_b = 0 (sin canal abierto)
_E_MARGIN: float = 0.05


@dataclass(frozen=True)
class BurnupZone:
    """Estado de una capa axial del blanco."""
    index: int
    e_in_mev: float              # energía de entrada del haz en la capa
    e_out_mev: float             # energía de salida
    production_weight: float     # fracción de la producción total (σ/S)
    burnup_xs_mb: float          # σ_b evaluada a la energía media de la capa
    flux_attenuation: float      # φ_j / φ_0 a la entrada de la capa
    burnup_rate_s: float         # k_j [s^-1]
    depletion_fraction: float    # 1 − exp(−k_j · t)


@dataclass(frozen=True)
class BurnupMultizone:
    """Resultado agregado del cálculo multizona."""
    n_zones: int
    zones: tuple[BurnupZone, ...]
    burnup_rate_max_s: float     # máxima tasa de quemado (capa de entrada)
    depletion_weighted: float    # depleción media ponderada por producción
    depletion_max: float         # depleción máxima local
    eob_no_burnup_gbq: float
    eob_with_burnup_gbq: float
    loss_gbq: float


def burnup_xs_mb(energy_mev: float, threshold_mev: float,
                 xs_max_mb: float = DEFAULT_XS_MAX_MB) -> float:
    """Sección eficaz de quemado paramétrica con umbral [mb]."""
    e = energy_mev - threshold_mev
    if e <= _E_MARGIN:
        return 0.0
    return xs_max_mb * (1.0 - math.exp(-e / XS_E0_MEV))


class BurnupMultizoneCalculator:
    """Depleción por capas: pesos σ(E)/S(E), atenuación del flujo y
    Bateman con quemado por capa."""

    def __init__(
        self,
        stopping: StoppingPowerProvider,
        reaction_data: ReactionDataProvider,
        n_grid: int = 4000,
    ) -> None:
        self._sp = stopping
        self._rxn = reaction_data
        self._n = n_grid

    def compute(
        self,
        reaction_id: str,
        target: TargetMaterial,
        beam_energy_mev: float,
        current_ua: float,
        irradiation_time_min: float,
        beam_spot_cm2: float,
        n_zones: int = 10,
        xs_max_mb: float = DEFAULT_XS_MAX_MB,
    ) -> BurnupMultizone:
        # Importación diferida: evita ciclo application → domain → application
        from app.application.production_service import REACTIONS

        if beam_spot_cm2 <= 0.0:
            raise ValueError("beam_spot_cm2 debe ser > 0")
        if n_zones < 1:
            raise ValueError("n_zones debe ser >= 1")

        product = REACTIONS[reaction_id]["product"]
        lam = self._rxn.get_decay_constant(product)
        threshold = self._rxn.get_threshold(reaction_id)
        energies, sigmas, _ = self._rxn.get_excitation_function(reaction_id)
        e_lo = max(threshold, min(energies))
        t_s = irradiation_time_min * 60.0
        phi_0 = PROTONS_PER_SECOND_PER_UA * current_ua / beam_spot_cm2

        # Caso degenerado: haz por debajo del umbral → sin producción
        if beam_energy_mev <= e_lo:
            zones = tuple(
                BurnupZone(index=j, e_in_mev=beam_energy_mev,
                           e_out_mev=beam_energy_mev,
                           production_weight=1.0 / n_zones, burnup_xs_mb=0.0,
                           flux_attenuation=1.0, burnup_rate_s=0.0,
                           depletion_fraction=0.0)
                for j in range(n_zones))
            return BurnupMultizone(
                n_zones=n_zones, zones=zones, burnup_rate_max_s=0.0,
                depletion_weighted=0.0, depletion_max=0.0,
                eob_no_burnup_gbq=0.0, eob_with_burnup_gbq=0.0, loss_gbq=0.0)

        # Misma malla que YieldCalculator: los pesos por capa son coherentes
        # con la integral de producción del modelo base.
        grid = np.linspace(e_lo, beam_energy_mev, self._n)
        sigma_grid = np.interp(grid, energies, sigmas,
                               left=0.0, right=0.0) * MB_PER_CM2
        s_grid = np.array([self._sp.stopping_power(target.stopping_material,
                                                   float(e)) for e in grid])
        s_grid = np.maximum(s_grid, 1e-9)
        integrand = sigma_grid / s_grid
        integral_total = float(np.trapezoid(integrand, grid))

        # Bordes de capa: de alta a baja energía, siguiendo al haz
        edges = np.linspace(beam_energy_mev, e_lo, n_zones + 1)

        # Pesos de producción por capa (fracción de ∫σ/S dE)
        pesos: list[float] = []
        for j in range(n_zones):
            mask = (grid >= edges[j + 1]) & (grid <= edges[j])
            if not np.any(mask):
                pesos.append(0.0)
                continue
            pesos.append(float(np.trapezoid(integrand[mask], grid[mask])))
        total_p = sum(pesos)
        if total_p > 0.0:
            pesos = [p / total_p for p in pesos]
        else:
            pesos = [1.0 / n_zones] * n_zones

        # Densidad areal del núclido blanco por capa (rangos CATIMA)
        areal_g_cm2 = (
            self._sp.range_g_cm2(target.stopping_material, beam_energy_mev)
            - self._sp.range_g_cm2(target.stopping_material, e_lo))
        n_areal_capa = target.nuclei_per_gram * areal_g_cm2 / n_zones

        # Actividad a saturación total (misma fórmula que YieldCalculator)
        a_sat_total_mbq = (PROTONS_PER_SECOND_PER_UA
                           * target.nuclei_per_gram * integral_total) / 1e6

        zones: list[BurnupZone] = []
        atenuacion = 1.0
        eob_con_mbq = 0.0
        eob_sin_mbq = 0.0
        k_max = 0.0
        dep_weighted = 0.0
        dep_max = 0.0
        sat_factor = 1.0 - math.exp(-lam * t_s)

        for j in range(n_zones):
            e_hi, e_lo_j = float(edges[j]), float(edges[j + 1])
            e_mid = 0.5 * (e_hi + e_lo_j)
            xs = burnup_xs_mb(e_mid, threshold, xs_max_mb)
            k = xs * MB_PER_CM2 * phi_0 * atenuacion
            f = 1.0 - math.exp(-k * t_s) if k > 0.0 else 0.0

            a_sat_j = a_sat_total_mbq * pesos[j] * current_ua  # MBq a saturación
            a_j_sin = a_sat_j * sat_factor
            # Bateman con término de quemado (formas del modelo de grupo único)
            if k <= 0.0:
                a_j = a_j_sin
            elif abs(lam - k) < 1e-12:          # caso límite λ = k
                a_j = a_sat_j * lam * t_s * math.exp(-lam * t_s)
            else:
                a_j = (a_sat_j * lam / (lam - k)
                       * (math.exp(-k * t_s) - math.exp(-lam * t_s)))

            eob_con_mbq += a_j
            eob_sin_mbq += a_j_sin
            zones.append(BurnupZone(
                index=j, e_in_mev=round(e_hi, 4), e_out_mev=round(e_lo_j, 4),
                production_weight=pesos[j], burnup_xs_mb=xs,
                flux_attenuation=atenuacion, burnup_rate_s=k,
                depletion_fraction=f))
            k_max = max(k_max, k)
            dep_weighted += pesos[j] * f
            dep_max = max(dep_max, f)
            # El haz atenuado alimenta la capa siguiente
            atenuacion *= math.exp(-xs * MB_PER_CM2 * n_areal_capa)

        return BurnupMultizone(
            n_zones=n_zones,
            zones=tuple(zones),
            burnup_rate_max_s=k_max,
            depletion_weighted=dep_weighted,
            depletion_max=dep_max,
            eob_no_burnup_gbq=eob_sin_mbq / 1000.0,
            eob_with_burnup_gbq=eob_con_mbq / 1000.0,
            loss_gbq=(eob_sin_mbq - eob_con_mbq) / 1000.0,
        )
