"""
Repositorio JSON de esquemas de decaimiento.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from app.domain.entities import DecayMode, DecayScheme, Emission


class JsonDecayRepository:
    """Implementación JSON del puerto DecayDataRepository."""

    def __init__(self, data_dir: Path) -> None:
        self._base = Path(data_dir) / "decay"

    def get_decay(self, nuclide: str) -> Optional[DecayScheme]:
        # Normalización: "18F", "f-18", "F18", "18f" -> "f18"
        m = re.match(r"^([a-z]*?)-?(\d+)$|^([0-9]+)-?([a-z]+)$", nuclide.lower())
        if m:
            if m.group(1) is not None:
                key = f"{m.group(1)}{m.group(2)}"
            else:
                key = f"{m.group(4)}{m.group(3)}"
        else:
            key = nuclide.lower().replace("-", "")
        path = self._base / f"{key}.json"
        if not path.exists():
            return None
        raw = json.loads(path.read_text())
        return DecayScheme(
            nuclide=raw["nuclide"],
            z=int(raw["Z"]),
            a=int(raw["A"]),
            half_life_s=float(raw["half_life_s"]),
            decay_constant_s=float(raw["decay_constant_s-1"]),
            decay_modes=tuple(
                DecayMode(mode=m["mode"], branching_ratio=float(m["branching_ratio"]),
                          endpoint_energy_kev=m.get("endpoint_energy_keV"))
                for m in raw["decay_modes"]),
            emissions=tuple(
                Emission(type=e["type"], energy_kev=float(e["energy_keV"]),
                         intensity_percent=float(e["intensity_%"]))
                for e in raw["emissions"]),
            dataset_id=raw["provenance"]["version"],
        )
