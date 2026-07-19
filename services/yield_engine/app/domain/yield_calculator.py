"""
Núcleo físico del Yield Engine.

Rendimiento de blanco grueso para reacciones (p,n) de producción de
radionúclidos PET, con propagación de incertidumbres por cuadratura.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np

from app.domain.entities import (
    Beam, MB_PER_CM2, PROTONS_PER_SECOND_PER_UA, TargetMaterial, YieldResult)
from app.domain.interfaces import ReactionDataProvider, StoppingPowerProvider

# Incertidumbres sistemáticas por defecto (1 sigma), EDS Vol. II cap. 17 (Calibration Layer):
DEFAULT_STOPPING_UNC: float = 0.03   # ATIMA/SRIM vs experimento ~3%
DEFAULT_CURRENT_UNC: float = 0.01    # medición de corriente integrada ~1%
MIN_SIGMA_REL_UNC: float = 0.04      # piso sistemático de la evaluación IAEA (4%)


class YieldCalculator:
    """Calcula actividades de producción integrando sigma(E)/S(E)."""

    def __init__(
        self,
        stopping: StoppingPowerProvider,
        reaction_data: ReactionDataProvider,
        n_points: int = 4000,
    ) -> None:
        self._sp = stopping
        self._rxn = reaction_data
        self._n = n_points

    # ------------------------------------------------------------------
    def saturation_yield_mbq_ua(
        self,
        reaction_id: str,
        target: TargetMaterial,
        beam_energy_mev: float,
    ) -> tuple[float, float, float]:
        """
        Actividad a saturación por µA, la integral numérica y su
        incertidumbre relativa (solo componentes sigma + stopping).
        """
        energies, sigmas, dsigmas = self._rxn.get_excitation_function(reaction_id)
        threshold = self._rxn.get_threshold(reaction_id)
        e_lo = max(threshold, min(energies))
        if beam_energy_mev <= e_lo:
            return 0.0, 0.0, 1.0

        grid = np.linspace(e_lo, beam_energy_mev, self._n)
        sigma_grid = np.interp(grid, energies, sigmas, left=0.0, right=0.0) * MB_PER_CM2
        s_grid = np.array([self._sp.stopping_power(target.stopping_material, float(e)) for e in grid])
        s_grid = np.maximum(s_grid, 1e-9)

        integrand = sigma_grid / s_grid
        integral = float(np.trapezoid(integrand, grid))

        a_sat_bq = PROTONS_PER_SECOND_PER_UA * target.nuclei_per_gram * integral
        a_sat_mbq = a_sat_bq / 1e6

        # --- incertidumbre: cuadratura de sigma(E) sobre la integral ---
        if any(d is not None for d in dsigmas):
            ds_grid = np.interp(grid, energies,
                                [d if d is not None else 0.0 for d in dsigmas],
                                left=0.0, right=0.0) * MB_PER_CM2
            rel = ds_grid / np.maximum(sigma_grid, 1e-30)
            rel = np.maximum(rel, MIN_SIGMA_REL_UNC)
        else:
            rel = np.full_like(grid, MIN_SIGMA_REL_UNC)
        # pesos normalizados del integrando (suman 1): contribución de cada tramo
        # a la integral. Con errores correlacionados (evaluación única IAEA),
        # la incertidumbre de la integral es el promedio ponderado de rel(E).
        d_e = grid[1] - grid[0]
        weights = integrand * d_e / max(integral, 1e-30)
        sigma_unc = float(np.sum(weights * rel))
        sigma_unc = float(np.clip(sigma_unc, MIN_SIGMA_REL_UNC, 0.30))
        total_unc = math.sqrt(sigma_unc ** 2 + DEFAULT_STOPPING_UNC ** 2)
        return a_sat_mbq, integral, total_unc

    # ------------------------------------------------------------------
    def compute_production(
        self,
        reaction_id: str,
        product_nuclide: str,
        beam: Beam,
        target: TargetMaterial,
        irradiation_time_min: float,
        exit_energy_mev: Optional[float] = None,
    ) -> YieldResult:
        """Caso de uso completo: actividad EOB para un lote de irradiación."""
        a_sat, integral, unc = self.saturation_yield_mbq_ua(
            reaction_id, target, beam.energy_mev)

        lam = self._rxn.get_decay_constant(product_nuclide)      # s^-1
        t_s = irradiation_time_min * 60.0
        sat_factor = 1.0 - math.exp(-lam * t_s)

        eob_mbq = a_sat * beam.current_ua * sat_factor
        total_unc = math.sqrt(unc ** 2 + DEFAULT_CURRENT_UNC ** 2)

        e_exit = exit_energy_mev if exit_energy_mev is not None else self._rxn.get_threshold(reaction_id)

        return YieldResult(
            reaction_id=reaction_id,
            product_nuclide=product_nuclide,
            beam_energy_mev=beam.energy_mev,
            exit_energy_mev=e_exit,
            current_ua=beam.current_ua,
            irradiation_time_min=irradiation_time_min,
            saturation_yield_mbq_ua=a_sat,
            eob_activity_gbq=eob_mbq / 1000.0,
            yield_gbq_ua=(a_sat * sat_factor) / 1000.0,
            saturation_factor=sat_factor,
            integrated_sigma_over_s=integral,
            relative_uncertainty=total_unc,
            dataset_id=self._rxn.get_dataset_id(reaction_id),
            stopping_source=self._sp.source_label(),
        )
