"""
Servicio de aplicación: casos de uso de producción de radionúclidos.
"""
from __future__ import annotations

from typing import Optional

from app.application.target_catalog import TARGET_CATALOG
from app.domain.burnup_calculator import BurnupCalculator
from app.domain.burnup_zones import (DEFAULT_XS_MAX_MB,
                                     BurnupMultizoneCalculator)
from app.domain.entities import Beam, TargetMaterial, YieldResult
from app.domain.interfaces import ReactionDataProvider, StoppingPowerProvider
from app.domain.yield_calculator import YieldCalculator

# Metadatos de reacciones soportadas por el MVP
REACTIONS: dict[str, dict] = {
    "o18_p_n_f18": {"notation": "18O(p,n)18F", "product": "18F",
                    "targets": ["h2_18o", "o2_18"]},
    "n14_p_a_c11": {"notation": "14N(p,alpha)11C", "product": "11C",
                    "targets": ["n2_gas"]},
    "n15_p_n_o15": {"notation": "15N(p,n)15O", "product": "15O",
                    "targets": ["n15_gas"]},
    "zn68_p_n_ga68": {"notation": "68Zn(p,n)68Ga", "product": "68Ga",
                      "targets": ["zn68"]},
}


class ProductionService:
    """Fachada de casos de uso del Yield Engine."""

    def __init__(self, stopping: StoppingPowerProvider, rxn: ReactionDataProvider) -> None:
        self._calc = YieldCalculator(stopping, rxn)
        self._stopping = stopping
        self._rxn = rxn
        self._burnup_mz = BurnupMultizoneCalculator(stopping, rxn)

    def burnup_multizone(
        self,
        reaction_id: str,
        target_id: str,
        beam_energy_mev: float,
        current_ua: float,
        irradiation_time_min: float,
        beam_spot_cm2: float,
        n_zones: int = 10,
        burnup_xs_max_mb: float = DEFAULT_XS_MAX_MB,
    ) -> dict:
        """Burnup Engine 1D: depleción por capas a lo largo del haz."""
        if reaction_id not in REACTIONS:
            raise ValueError(f"Reacción no soportada: {reaction_id}")
        if target_id not in REACTIONS[reaction_id]["targets"]:
            raise ValueError(
                f"Blanco {target_id} incompatible con {reaction_id}")
        target = TARGET_CATALOG[target_id]
        mz = self._burnup_mz.compute(
            reaction_id=reaction_id, target=target,
            beam_energy_mev=beam_energy_mev, current_ua=current_ua,
            irradiation_time_min=irradiation_time_min,
            beam_spot_cm2=beam_spot_cm2, n_zones=n_zones,
            xs_max_mb=burnup_xs_max_mb)
        return {
            "reaction_id": reaction_id,
            "product_nuclide": REACTIONS[reaction_id]["product"],
            "beam_energy_mev": beam_energy_mev,
            "current_ua": current_ua,
            "irradiation_time_min": irradiation_time_min,
            "beam_spot_cm2": beam_spot_cm2,
            "burnup_xs_max_mb": burnup_xs_max_mb,
            "n_zones": mz.n_zones,
            "zones": [z.__dict__ for z in mz.zones],
            "burnup_rate_max_s": mz.burnup_rate_max_s,
            "depletion_weighted": mz.depletion_weighted,
            "depletion_max": mz.depletion_max,
            "eob_no_burnup_gbq": mz.eob_no_burnup_gbq,
            "eob_with_burnup_gbq": mz.eob_with_burnup_gbq,
            "loss_gbq": mz.loss_gbq,
            "model": "multizone axial depletion (1D)",
        }

    def compute(
        self,
        reaction_id: str,
        target_id: str,
        beam_energy_mev: float,
        current_ua: float,
        irradiation_time_min: float,
        enrichment: Optional[float] = None,
    ) -> YieldResult:
        if reaction_id not in REACTIONS:
            raise ValueError(f"Reacción no soportada: {reaction_id}")
        if target_id not in TARGET_CATALOG:
            raise ValueError(f"Blanco no soportado: {target_id}")
        if target_id not in REACTIONS[reaction_id]["targets"]:
            raise ValueError(
                f"Blanco {target_id} incompatible con {reaction_id}")

        target = TARGET_CATALOG[target_id]
        if enrichment is not None:
            target = TargetMaterial(
                material_id=target.material_id, label=target.label,
                stopping_material=target.stopping_material,
                target_nuclide=target.target_nuclide,
                molar_mass_g_mol=target.molar_mass_g_mol,
                mass_fraction=target.mass_fraction, enrichment=enrichment)

        beam = Beam(energy_mev=beam_energy_mev, current_ua=current_ua)
        return self._calc.compute_production(
            reaction_id=reaction_id,
            product_nuclide=REACTIONS[reaction_id]["product"],
            beam=beam, target=target, irradiation_time_min=irradiation_time_min)

    def stopping_curve(self, material_key: str, e_min: float, e_max: float, step: float):
        e = e_min
        out = []
        while e <= e_max + 1e-9:
            out.append({"energy_mev": round(e, 4),
                        "stopping_power_mev_cm2_g": round(
                            self._stopping.stopping_power(material_key, e), 5)})
            e += step
        return out

    def target_range(self, material_key: str, energy_mev: float) -> float:
        return self._stopping.range_g_cm2(material_key, energy_mev)

    def burnup_compare(
        self,
        reaction_id: str,
        target_id: str,
        beam_energy_mev: float,
        current_ua: float,
        irradiation_time_min: float,
        beam_spot_cm2: float,
        burnup_xs_mb: float,
    ) -> dict:
        """Caso de uso Burnup Engine: EOB con/sin depleción de blanco."""
        base = self.compute(reaction_id, target_id, beam_energy_mev,
                            current_ua, irradiation_time_min)
        lam = self._rxn.get_decay_constant(base.product_nuclide)
        result = BurnupCalculator().compare(
            a_sat_mbq_ua=base.saturation_yield_mbq_ua,
            current_ua=current_ua,
            irradiation_time_min=irradiation_time_min,
            decay_constant_s=lam,
            beam_spot_cm2=beam_spot_cm2,
            burnup_xs_mb=burnup_xs_mb)
        result.update({
            "reaction_id": reaction_id,
            "product_nuclide": base.product_nuclide,
            "beam_energy_mev": beam_energy_mev,
            "current_ua": current_ua,
            "irradiation_time_min": irradiation_time_min,
            "beam_spot_cm2": beam_spot_cm2,
            "burnup_xs_mb": burnup_xs_mb,
            "model": "single-group uniform depletion (MVP)",
        })
        return result
