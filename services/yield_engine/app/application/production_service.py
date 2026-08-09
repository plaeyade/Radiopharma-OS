"""
Servicio de aplicación: casos de uso de producción de radionúclidos.
"""
from __future__ import annotations

from typing import Optional

from app.application.target_catalog import TARGET_CATALOG
from app.domain.burnup_calculator import BurnupCalculator
from app.domain.burnup_radial import BurnupRadialCalculator
from app.domain.burnup_zones import (DEFAULT_XS_MAX_MB,
                                     BurnupMultizoneCalculator)
from app.domain.entities import Beam, TargetMaterial, YieldResult
from app.domain.interfaces import ReactionDataProvider, StoppingPowerProvider
from app.domain.thermal_reduced import beam_power_w, thermal_reduced
from app.domain.yield_calculator import YieldCalculator
from app.domain.elmer_materials import get_material
from app.infrastructure.elmer.elmer_case import (ElmerThermalCase,
                                                 build_case,
                                                 build_case_thermomechanical)
from app.infrastructure.elmer.elmer_runner import (ElmerError, ElmerRunner,
                                                   ElmerUnavailable)

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

    def __init__(self, stopping: StoppingPowerProvider, rxn: ReactionDataProvider,
                 elmer: ElmerRunner | None = None) -> None:
        self._calc = YieldCalculator(stopping, rxn)
        self._stopping = stopping
        self._rxn = rxn
        self._burnup_mz = BurnupMultizoneCalculator(stopping, rxn)
        self._burnup_radial = BurnupRadialCalculator(rxn)
        self._elmer = elmer or ElmerRunner()

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

    def burnup_radial(
        self,
        reaction_id: str,
        target_id: str,
        beam_energy_mev: float,
        current_ua: float,
        irradiation_time_min: float,
        beam_spot_cm2: float,
        beam_sigma_cm: float,
        n_rings: int = 20,
        burnup_xs_max_mb: float = DEFAULT_XS_MAX_MB,
    ) -> dict:
        """Burnup Engine 2D: depleción radial bajo haz gaussiano.

        La referencia 1D (mismo haz, mismo blanco) se calcula con el
        modelo multizona axial; σ_b,eff es su media ponderada por
        producción, de modo que la única diferencia física entre ambos
        resultados es la distribución radial del flujo."""
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
            beam_spot_cm2=beam_spot_cm2, n_zones=10,
            xs_max_mb=burnup_xs_max_mb)
        xs_eff = sum(z.production_weight * z.burnup_xs_mb for z in mz.zones)
        r = self._burnup_radial.compute(
            reaction_id=reaction_id, beam_energy_mev=beam_energy_mev,
            current_ua=current_ua,
            irradiation_time_min=irradiation_time_min,
            beam_spot_cm2=beam_spot_cm2, beam_sigma_cm=beam_sigma_cm,
            n_rings=n_rings, burnup_xs_eff_mb=xs_eff,
            eob_ideal_gbq=mz.eob_no_burnup_gbq,
            eob_1d_gbq=mz.eob_with_burnup_gbq)
        return {
            "reaction_id": reaction_id,
            "product_nuclide": REACTIONS[reaction_id]["product"],
            "beam_energy_mev": beam_energy_mev,
            "current_ua": current_ua,
            "irradiation_time_min": irradiation_time_min,
            "beam_spot_cm2": beam_spot_cm2,
            "beam_sigma_cm": r.beam_sigma_cm,
            "spot_radius_cm": r.spot_radius_cm,
            "n_rings": r.n_rings,
            "burnup_xs_max_mb": burnup_xs_max_mb,
            "burnup_xs_eff_mb": xs_eff,
            "flux_peak_cm2_s": r.flux_peak_cm2_s,
            "flux_mean_cm2_s": r.flux_mean_cm2_s,
            "peak_factor": r.flux_peak_cm2_s / r.flux_mean_cm2_s
            if r.flux_mean_cm2_s > 0 else 1.0,
            "rings": [ring.__dict__ for ring in r.rings],
            "burnup_rate_max_s": r.burnup_rate_max_s,
            "depletion_weighted": r.depletion_weighted,
            "depletion_max": r.depletion_max,
            "eob_ideal_gbq": r.eob_ideal_gbq,
            "eob_1d_gbq": r.eob_1d_gbq,
            "eob_2d_gbq": r.eob_2d_gbq,
            "loss_vs_ideal_gbq": r.loss_vs_ideal_gbq,
            "loss_vs_1d_gbq": r.loss_vs_1d_gbq,
            "model": "radial gaussian depletion (2D)",
        }

    def thermal_target(
        self,
        beam_energy_mev: float,
        current_ua: float,
        beam_spot_cm2: float,
        target_thickness_cm: float,
        conductivity_w_cm_k: float,
        film_coeff_w_cm2_k: float,
        coolant_temp_k: float,
        t_limit_k: float,
        beam_sigma_cm: float | None = None,
    ) -> dict:
        """Modelo térmico reducido (analítico estacionario) del blanco."""
        t = thermal_reduced(
            beam_energy_mev=beam_energy_mev, current_ua=current_ua,
            beam_spot_cm2=beam_spot_cm2,
            target_thickness_cm=target_thickness_cm,
            conductivity_w_cm_k=conductivity_w_cm_k,
            film_coeff_w_cm2_k=film_coeff_w_cm2_k,
            coolant_temp_k=coolant_temp_k, t_limit_k=t_limit_k,
            beam_sigma_cm=beam_sigma_cm)
        return {**t.__dict__, "model": "reduced 1D conduction + film"}

    def elmer_status(self) -> dict:
        """Estado honesto del acoplamiento FEM (patrón TALYS/veraPDF)."""
        return {"available": self._elmer.available(),
                "cmd": self._elmer.cmd_label,
                "version": self._elmer.version(),
                "solver": "ElmerFEM HeatSolver (Heat Equation, axi 2D)"}

    def elmer_thermal_compare(
        self,
        reaction_id: str,
        target_id: str,
        beam_energy_mev: float,
        current_ua: float,
        irradiation_time_min: float,
        beam_spot_cm2: float,
        target_thickness_cm: float,
        conductivity_w_cm_k: float,
        film_coeff_w_cm2_k: float,
        coolant_temp_k: float,
        beam_sigma_cm: float | None = None,
        work_dir: str | None = None,
    ) -> dict:
        """Comparación FEM (Elmer) vs modelo reducido para el mismo caso.

        Puerta canónica (EDS v2.0 cap. 8.11): **no se permite ejecutar
        Elmer sin disponer previamente del cálculo de Yield y Burnup** —
        por eso el caso FEM se deriva siempre de una producción + quemado
        calculados aquí con los mismos parámetros, y la respuesta lleva
        su linaje. Elmer resuelve la ecuación del calor 2D axisimétrica;
        el modelo reducido es la solución analítica 1D (cota conservadora:
        la difusión radial del FEM solo puede reducir el pico). Si el
        binario no está disponible, ElmerUnavailable → 503."""
        import math
        import tempfile
        from pathlib import Path

        from app.domain.thermal_reduced import beam_power_w

        # Puerta Yield → Burnup (cap. 8.11) con los mismos parámetros
        y = self.compute(reaction_id=reaction_id, target_id=target_id,
                         beam_energy_mev=beam_energy_mev,
                         current_ua=current_ua,
                         irradiation_time_min=irradiation_time_min)
        b = self.burnup_multizone(reaction_id=reaction_id, target_id=target_id,
                                  beam_energy_mev=beam_energy_mev,
                                  current_ua=current_ua,
                                  irradiation_time_min=irradiation_time_min,
                                  beam_spot_cm2=beam_spot_cm2, n_zones=10)
        power = beam_power_w(beam_energy_mev, current_ua)
        reduced = thermal_reduced(
            beam_energy_mev=beam_energy_mev, current_ua=current_ua,
            beam_spot_cm2=beam_spot_cm2,
            target_thickness_cm=target_thickness_cm,
            conductivity_w_cm_k=conductivity_w_cm_k,
            film_coeff_w_cm2_k=film_coeff_w_cm2_k,
            coolant_temp_k=coolant_temp_k, t_limit_k=1.0e9,
            beam_sigma_cm=beam_sigma_cm)
        case = ElmerThermalCase(
            beam_power_w=power,
            spot_radius_cm=math.sqrt(beam_spot_cm2 / math.pi),
            target_thickness_cm=target_thickness_cm,
            conductivity_w_cm_k=conductivity_w_cm_k,
            film_coeff_w_cm2_k=film_coeff_w_cm2_k,
            coolant_temp_k=coolant_temp_k, beam_sigma_cm=beam_sigma_cm)
        if work_dir is not None:
            case_dir = Path(work_dir)
            build_case(case_dir, case)
            scalars = self._elmer.run(case_dir)
        else:
            with tempfile.TemporaryDirectory(prefix="elmer_") as tmp:
                build_case(Path(tmp), case)
                scalars = self._elmer.run(Path(tmp))
        t_max_fem, t_mean_fem = scalars[0], scalars[1]
        return {
            "pipeline": "yield→burnup→elmer",
            "reaction_id": reaction_id,
            "target_id": target_id,
            "irradiation_time_min": irradiation_time_min,
            "yield_eob_gbq": y.eob_activity_gbq,
            "burnup_eob_gbq": b["eob_with_burnup_gbq"],
            "burnup_loss_gbq": b["loss_gbq"],
            "t_peak_fem_k": t_max_fem,
            "t_mean_fem_k": t_mean_fem,
            "t_peak_reduced_k": reduced.t_peak_k,
            "t_mean_reduced_k": reduced.t_mean_k,
            "peak_rel_diff": (t_max_fem - reduced.t_peak_k)
            / reduced.t_peak_k if reduced.t_peak_k > 0 else 0.0,
            "fem_conservative_bound_ok": t_max_fem <= reduced.t_peak_k * 1.001,
            "solver": self._elmer.cmd_label,
            "model": "ElmerFEM 2D axisymmetric vs reduced 1D",
        }

    def elmer_thermomechanical(
            self, reaction_id: str, target_id: str,
            irradiation_time_min: float, beam_energy_mev: float,
            current_ua: float, material_id: str,
            beam_spot_cm2: float = 1.0, target_thickness_cm: float = 0.5,
            conductivity_w_cm_k: float = 0.006,
            film_coeff_w_cm2_k: float = 0.5, coolant_temp_k: float = 293.15,
            beam_sigma_cm: Optional[float] = None,
            work_dir: Optional[str] = None) -> dict:
        """EDS cap. 18: análisis termo-mecánico acoplado (18.13) con puerta
        canónica 8.11 (Yield→Burnup primero) y Material Library (18.8/18.14).
        Devuelve temperatura, von Mises y desplazamiento máximos (18.12)."""
        if self._elmer is None or not self._elmer.available():
            raise ElmerUnavailable(
                "binario ElmerSolver no encontrado (ELMER_CMD ni PATH)")
        import math
        from pathlib import Path

        material = get_material(material_id)   # 18.14: rechaza si incompleto
        # 8.11: puerta canónica — Yield y Burnup antes que cualquier FEM
        y = self.compute(reaction_id=reaction_id, target_id=target_id,
                         beam_energy_mev=beam_energy_mev,
                         current_ua=current_ua,
                         irradiation_time_min=irradiation_time_min)
        b = self.burnup_multizone(reaction_id=reaction_id, target_id=target_id,
                                  beam_energy_mev=beam_energy_mev,
                                  current_ua=current_ua,
                                  irradiation_time_min=irradiation_time_min,
                                  beam_spot_cm2=beam_spot_cm2, n_zones=10)
        power = beam_power_w(beam_energy_mev, current_ua)
        reduced = thermal_reduced(
            beam_energy_mev=beam_energy_mev, current_ua=current_ua,
            beam_spot_cm2=beam_spot_cm2,
            target_thickness_cm=target_thickness_cm,
            conductivity_w_cm_k=conductivity_w_cm_k,
            film_coeff_w_cm2_k=film_coeff_w_cm2_k,
            coolant_temp_k=coolant_temp_k, t_limit_k=1.0e9,
            beam_sigma_cm=beam_sigma_cm)
        case = ElmerThermalCase(
            beam_power_w=power,
            spot_radius_cm=math.sqrt(beam_spot_cm2 / math.pi),
            target_thickness_cm=target_thickness_cm,
            conductivity_w_cm_k=conductivity_w_cm_k,
            film_coeff_w_cm2_k=film_coeff_w_cm2_k,
            coolant_temp_k=coolant_temp_k, beam_sigma_cm=beam_sigma_cm)

        def _run(case_dir: Path) -> tuple[list[float], str]:
            build_case_thermomechanical(case_dir, case, material)
            scalars = self._elmer.run(case_dir)
            log = ""
            log_path = case_dir / "elmer.log"
            if log_path.is_file():
                log = log_path.read_text(encoding="utf-8", errors="replace")
            return scalars, log

        if work_dir is not None:
            scalars, log = _run(Path(work_dir))
        else:
            import tempfile
            with tempfile.TemporaryDirectory(prefix="elmer_tm_") as tmp:
                scalars, log = _run(Path(tmp))
        if len(scalars) < 4:
            raise ElmerError(
                f"scalars.dat incompleto ({len(scalars)} columnas, se "
                "esperaban 4: T_max, T_mean, vonMises, desplazamiento)")
        t_max_fem, t_mean_fem, von_mises_max_pa, disp_max = scalars[:4]
        # 18.22: validación numérica — Elmer marca el final correcto con
        # "ALL DONE"; "ERROR termination" indica fallo. Los resultados
        # dudosos se marcan para revisión, nunca se ocultan
        converged = ("all done" in log.lower()
                     and "error termination" not in log.lower())
        return {
            "pipeline": "yield→burnup→elmer(thermomechanical)",
            "reaction_id": reaction_id, "target_id": target_id,
            "irradiation_time_min": irradiation_time_min,
            "yield_eob_gbq": y.eob_activity_gbq,
            "burnup_eob_gbq": b["eob_with_burnup_gbq"],
            "burnup_loss_gbq": b["loss_gbq"],
            "material": {"material_id": material.material_id,
                         "version": material.version,
                         "referencia": material.referencia},
            "t_peak_fem_k": t_max_fem, "t_mean_fem_k": t_mean_fem,
            "t_peak_reduced_k": reduced.t_peak_k,
            "fem_conservative_bound_ok":
                t_max_fem <= reduced.t_peak_k * 1.001,
            "von_mises_max_pa": von_mises_max_pa,
            "von_mises_max_mpa": round(von_mises_max_pa / 1.0e6, 4),
            "displacement_max_m": disp_max,
            "displacement_max_mm": round(disp_max * 1000.0, 6),
            "numerical_validation_ok": converged,
            "review_required": not converged,
            "solver": self._elmer.cmd_label,
            "model": "ElmerFEM Heat→Stress axi 2D acoplado (cap. 18)",
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
