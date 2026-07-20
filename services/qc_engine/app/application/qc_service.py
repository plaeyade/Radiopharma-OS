"""
Casos de uso del QC Engine.
"""
from __future__ import annotations

import os
from typing import Optional

import httpx

from app.domain.acceptance_rules import RULE_PACKS, evaluate_rules
from app.domain.decay_physics import (decay_correction,
                                      decay_correction_uncertainty,
                                      fit_half_life)
from app.domain.spc import SpcResult, shewhart_spc
from app.domain.entities import (ActivityMeasurement, HalfLifeFitResult,
                                 QcReport)

# Vidas medias de respaldo (DDEP/LiveChart, mismas del Nuclear Data Service)
_FALLBACK_HALF_LIVES = {"18F": 109.77, "11C": 20.364, "15O": 2.0373, "68Ga": 67.71}


class QcService:
    def __init__(self, nds_url: Optional[str] = None) -> None:
        self._nds = nds_url or os.environ.get("NUCLEAR_DATA_URL", "")

    def resolve_half_life(self, nuclide: str) -> float:
        """Vida media de referencia: NDS si está disponible, si no, DDEP local."""
        if self._nds:
            try:
                with httpx.Client(timeout=5.0) as http:
                    r = http.get(f"{self._nds}/api/v1/nuclides/{nuclide}/decay")
                    if r.status_code == 200:
                        return float(r.json()["half_life_s"]) / 60.0
            except httpx.HTTPError:
                pass
        if nuclide in _FALLBACK_HALF_LIVES:
            return _FALLBACK_HALF_LIVES[nuclide]
        raise ValueError(f"Vida media desconocida para {nuclide}; "
                         "proporciónela explícitamente o levante el NDS")

    # ------------------------------------------------------------------
    def decay_correct(self, nuclide: str, activity: float,
                      delta_time_min: float, to_future: bool,
                      relative_unc: float = 0.02) -> dict:
        hl = self.resolve_half_life(nuclide)
        corrected = decay_correction(activity, hl, delta_time_min, to_future)
        return {
            "nuclide": nuclide,
            "input_activity": activity,
            "delta_time_min": delta_time_min,
            "direction": "future" if to_future else "past",
            "corrected_activity": corrected,
            "relative_uncertainty": decay_correction_uncertainty(
                relative_unc, hl, delta_time_min),
            "half_life_min_used": hl,
        }

    def verify_half_life(self, nuclide: str,
                         measurements: list[ActivityMeasurement],
                         tolerance_percent: float = 5.0,
                         chi2_threshold: float = 3.0) -> HalfLifeFitResult:
        ref = self.resolve_half_life(nuclide)
        return fit_half_life(measurements, ref, tolerance_percent, chi2_threshold)

    def evaluate_product(self, product: str, nuclide: str,
                         measurements: dict,
                         half_life_series: Optional[list[ActivityMeasurement]] = None,
                         tolerance_percent: float = 5.0) -> QcReport:
        report = evaluate_rules(product, measurements, nuclide)
        if half_life_series:
            fit = self.verify_half_life(nuclide, half_life_series,
                                        tolerance_percent)
            from dataclasses import replace
            report = replace(report, half_life_fit=fit)
            if not fit.within_tolerance or fit.impurity_suspected:
                from app.domain.entities import QcStatus
                report = replace(report, overall_status=QcStatus.FAIL)
        return report

    def spc(self, values: list[float],
            labels: Optional[list[str]] = None,
            spec_low: Optional[float] = None,
            spec_high: Optional[float] = None) -> SpcResult:
        """Carta de control Shewhart + reglas WE/Nelson (trending GMP)."""
        return shewhart_spc(values, labels=labels,
                            spec_low=spec_low, spec_high=spec_high)

    @staticmethod
    def rule_packs() -> dict:
        return {k: {"label": v["label"],
                    "rules": [{"parameter": r.parameter,
                               "min": r.min_value, "max": r.max_value,
                               "unit": r.unit, "source": r.source}
                              for r in v["rules"]]}
                for k, v in RULE_PACKS.items()}
