"""Servicio de neutrones de producción (EDS 19.12/19.14/19.24).

Cadena REAL: TALYS (espectro (p,xn) de emisión, ejecución real cacheada
como dato versionado) → integración de blanco grueso con el poder de
frenado ACTIVO (mismo formalismo que el EOB: ∫ σ_n/S dE, nunca un
factor inventado) → tasa n/(µA·s) → termalización SOLO por transporte
MC con OpenGATE/Geant4 (FTFP_BERT_HP + G4NDL reales).

Honestidad: sin TALYS → 503 `sin_runtime`; sin OpenGATE o sin G4NDL →
tally `no_demostrable` declarado. Las bandas del espectro fuente se
reportan siempre; los térmicos moderados jamás se estiman analíticamente.
"""
from __future__ import annotations

import math
import re

from app.application.target_catalog import TARGET_CATALOG
from app.infrastructure.gate.neutron_tally import (NeutronTallyRunner,
                                                   TallyGateError,
                                                   TallyGateUnavailable,
                                                   bandas_desde_espectro_fuente,
                                                   build_case)
from app.infrastructure.talys_spectra import (TalysError, TalysSpectraRunner,
                                              TalysUnavailable)

PROTONES_POR_S_POR_UA = 6.24146e12      # 1 µA / e (constante física)
MB_A_CM2 = 1e-27


def _parse_nuclide(nuclide: str) -> tuple[str, int]:
    m = re.match(r"^(\d+)([A-Za-z]+)$", nuclide)
    if not m:
        raise TalysError(f"núclido blanco no parseable: {nuclide}")
    return m.group(2).lower(), int(m.group(1))


class NeutronService:
    def __init__(self, spectra: TalysSpectraRunner, stopping,
                 tally: NeutronTallyRunner, reactions_meta: dict) -> None:
        self._spectra = spectra
        self._stopping = stopping
        self._tally = tally
        self._meta = reactions_meta

    def status(self) -> dict:
        return {
            "talys": {"disponible": self._spectra.available(),
                      "nota": "sin runtime → 503 sin_runtime (nunca se "
                              "simula el espectro)"},
            "opengate": {"disponible": self._tally.check(),
                         "nota": "sin runtime o sin G4NDL → tally "
                                 "no_demostrable (nunca estimado)"},
        }

    def _sigma_n_grid(self, element: str, mass: int, e_min: float,
                      e_max: float, paso: float) -> list[tuple[float, float]]:
        """σ_n,total(E) de TALYS real en una malla (cada punto cacheado)."""
        puntos = []
        e = e_min
        while e < e_max - 1e-9:
            reg = self._spectra.espectro(element, mass, round(e, 3))
            puntos.append((round(e, 3), reg["sigma_n_total_mb"]))
            e += paso
        reg = self._spectra.espectro(element, mass, round(e_max, 3))
        puntos.append((round(e_max, 3), reg["sigma_n_total_mb"]))
        return puntos

    def produccion(self, reaction_id: str, target_id: str,
                   beam_energy_mev: float, current_ua: float,
                   paso_mev: float = 1.0) -> dict:
        if reaction_id not in self._meta:
            raise TalysError(f"reacción desconocida: {reaction_id}")
        if target_id not in TARGET_CATALOG:
            raise TalysError(f"blanco desconocido: {target_id}")
        target = TARGET_CATALOG[target_id]
        element, mass = _parse_nuclide(target.target_nuclide)
        umbral = float(self._meta[reaction_id]["threshold_mev"])
        if beam_energy_mev <= umbral:
            raise TalysError(
                f"energía {beam_energy_mev} MeV bajo el umbral "
                f"({umbral} MeV) — producción neutrónica nula real")
        e_min = math.ceil(umbral / paso_mev) * paso_mev
        grid = self._sigma_n_grid(element, mass, e_min, beam_energy_mev,
                                  paso_mev)
        # Integración de blanco grueso real: Y_n = n_t ∫ σ_n(E)/S(E) dE
        nt = target.nuclei_per_gram
        y_n = 0.0
        for (e0, s0), (e1, s1) in zip(grid, grid[1:]):
            st0 = self._stopping.stopping_power(target.stopping_material, e0)
            st1 = self._stopping.stopping_power(target.stopping_material, e1)
            y_n += 0.5 * (s0 / st0 + s1 / st1) * (e1 - e0)
        y_n *= nt * MB_A_CM2
        tasa = y_n * current_ua * PROTONES_POR_S_POR_UA
        espectro_e0 = self._spectra.espectro(element, mass,
                                             beam_energy_mev)
        return {
            "reaccion": self._meta[reaction_id]["notation"],
            "blanco": target_id,
            "energia_mev": beam_energy_mev,
            "corriente_ua": current_ua,
            "neutrones_por_proton": y_n,
            "tasa_neutrones_s": tasa,
            "malla_talys_mev": [g[0] for g in grid],
            "sigma_n_mb": [g[1] for g in grid],
            "bandas_fuente": bandas_desde_espectro_fuente(
                espectro_e0["espectro"]),
            "componentes_mb": espectro_e0["componentes_mb"],
            "stopping_source": self._stopping.source_label(),
            "fuente": espectro_e0["fuente"],
            "nota_honestidad": (
                "producción neutrónica de blanco grueso con σ_n(E) de "
                "TALYS real y stopping activo; el espectro fuente es de "
                "emisión (rápidos/epitérmicos) — los térmicos requieren "
                "transporte MC (endpoint transport-tally), nunca se "
                "estiman analíticamente"),
        }

    def tally(self, reaction_id: str, target_id: str,
              beam_energy_mev: float, current_ua: float,
              radio_moderador_cm: float, n_histories: int,
              seed: int = 12345,
              material_g4: str = "G4_WATER") -> dict:
        """Termalización real por MC: bandas tras moderador esférico."""
        target = TARGET_CATALOG[target_id]
        element, mass = _parse_nuclide(target.target_nuclide)
        espectro_e0 = self._spectra.espectro(element, mass,
                                             beam_energy_mev)
        prod = self.produccion(reaction_id, target_id, beam_energy_mev,
                               current_ua)
        import tempfile as _tf
        from pathlib import Path as _P
        with _tf.TemporaryDirectory(prefix="gate_ntally_") as tmp:
            script = build_case(_P(tmp), espectro_e0["espectro"],
                                radio_moderador_cm, n_histories,
                                material_g4, seed)
            bandas = self._tally.run(_P(tmp))
        total_reg = bandas["total_registrados"] or 1
        tasa = prod["tasa_neutrones_s"]
        fraccion_fuga = total_reg / n_histories
        return {
            "reaccion": prod["reaccion"], "blanco": target_id,
            "energia_mev": beam_energy_mev, "corriente_ua": current_ua,
            "moderador": {"material_g4": material_g4,
                          "radio_cm": radio_moderador_cm,
                          "geometria": "esfera centrada en la fuente — "
                                       "modelo de screening declarado"},
            "n_histories": n_histories, "seed": seed,
            "bandas_por_neutron_fuente": {
                "termicos": bandas["termicos_lt_0.4eV"] / n_histories,
                "epitermicos": bandas["epitermicos"] / n_histories,
                "rapidos": bandas["rapidos_ge_100keV"] / n_histories,
            },
            "tasa_neutrones_s": {
                "termicos": tasa * bandas["termicos_lt_0.4eV"] / n_histories,
                "epitermicos": tasa * bandas["epitermicos"] / n_histories,
                "rapidos": tasa * bandas["rapidos_ge_100keV"] / n_histories,
                "total": tasa,
            },
            "fraccion_fuga_moderador": fraccion_fuga,
            "fuente_espectro": espectro_e0["fuente"],
            "nota_honestidad": (
                "tally MC real (OpenGATE/Geant4 FTFP_BERT_HP + G4NDL): "
                "bandas de neutrones que SALEN del moderador por neutrón "
                "fuente, escaladas con la tasa de producción TALYS real; "
                "bandas declaradas: térmicos <0.4 eV, epitérmicos "
                "0.4 eV–100 keV, rápidos ≥100 keV"),
        }
