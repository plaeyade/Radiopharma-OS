"""
Radiopharma OS - Yield Engine
Capa de dominio: entidades físicas del cálculo de rendimiento.

Modelo físico (blanco grueso, EDS v2.0 Vol. II cap. 15):
    A_sat = I_p * (N_A * w / M) * ∫ sigma(E) / S(E) dE        [Bq/µA]
    A_EOB(t) = A_sat * I * (1 - exp(-lambda * t))             [Bq]

donde S(E) es el poder de frenado másico [MeV·cm²/g],
w la fracción másica del núclido blanco y M su masa molar.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# --- Constantes físicas (CODATA 2018) ---
AVOGADRO: float = 6.02214076e23          # mol^-1
ELEMENTARY_CHARGE: float = 1.602176634e-19  # C
PROTONS_PER_SECOND_PER_UA: float = 1e-6 / ELEMENTARY_CHARGE  # 6.2415e12 p/s/µA
MB_PER_CM2: float = 1e-27                # 1 mb en cm²


@dataclass(frozen=True)
class Beam:
    """Haz de protones del ciclotrón."""
    energy_mev: float
    current_ua: float


@dataclass(frozen=True)
class TargetMaterial:
    """Material de blanco: composición para el poder de frenado y
    contenido del núclido blanco para la producción."""
    material_id: str                 # "h2_18o" | "o2_18"
    label: str
    stopping_material: str           # clave para el proveedor de stopping power
    target_nuclide: str              # "18O"
    molar_mass_g_mol: float          # masa molar del núclido blanco
    mass_fraction: float             # fracción másica del núclido blanco en el material
    enrichment: float = 1.0          # enriquecimiento isotópico [0-1]

    @property
    def nuclei_per_gram(self) -> float:
        """Núcleos blanco por gramo de material."""
        return AVOGADRO * self.mass_fraction * self.enrichment / self.molar_mass_g_mol


@dataclass(frozen=True)
class YieldResult:
    """Resultado completo de un cálculo de producción."""
    reaction_id: str
    product_nuclide: str
    beam_energy_mev: float
    exit_energy_mev: float
    current_ua: float
    irradiation_time_min: float
    saturation_yield_mbq_ua: float       # actividad a saturación por µA
    eob_activity_gbq: float              # actividad total a EOB
    yield_gbq_ua: float                  # actividad EOB por µA
    saturation_factor: float             # 1 - exp(-lambda*t)
    integrated_sigma_over_s: float       # integral numérica [g·cm²... ver docstring]
    relative_uncertainty: float          # incertidumbre relativa combinada (1 sigma)
    dataset_id: str
    stopping_source: str
    notes: tuple[str, ...] = ()
