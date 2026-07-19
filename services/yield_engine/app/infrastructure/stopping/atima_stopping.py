"""
Proveedor de poder de frenado vía CATIMA/ATIMA (pycatima).

Sustituto abierto de SRIM (EDS v2.0, decisión de arquitectura):
SRIM es software de escritorio Windows sin API; CATIMA ofrece las mismas
tablas ATIMA (GSI) como librería automatizable en Linux/Docker.
"""
from __future__ import annotations

from pycatima import Material, Projectile, calculate, dedx

_MATERIALS = {
    "h2o": {"elements": [[1, 1, 2], [16, 8, 1]], "density": 1.0},
    "o2": {"elements": [[16, 8, 2]], "density": 1.0},
    "n2": {"elements": [[14, 7, 2]], "density": 1.0},
    "zn68": {"elements": [[68, 30, 1]], "density": 1.0},
    "n15": {"elements": [[15, 7, 2]], "density": 1.0},
}


class AtimaStoppingPower:
    """Stopping power másico y rango CSDA con ATIMA."""

    def __init__(self) -> None:
        self._mats = {
            k: Material(v["elements"], density=v["density"]) for k, v in _MATERIALS.items()}

    def stopping_power(self, material_key: str, energy_mev: float) -> float:
        mat = self._mats[material_key]
        return float(dedx(Projectile(1, 1, 1, float(energy_mev)), mat))

    def range_g_cm2(self, material_key: str, energy_mev: float) -> float:
        mat = self._mats[material_key]
        return float(calculate(Projectile(1, 1, 1, float(energy_mev)), mat).range)

    def source_label(self) -> str:
        return "CATIMA/ATIMA (pycatima 1.981)"
