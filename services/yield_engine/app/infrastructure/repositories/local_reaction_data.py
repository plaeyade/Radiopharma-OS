"""
Proveedor local de datos de reacción (modo standalone).

En el despliegue completo este adaptador se sustituye por un cliente HTTP
del Nuclear Data Service (misma interfaz, patrón Anti-Corruption Layer).
"""
from __future__ import annotations

import csv, json, re
from pathlib import Path
from typing import Optional


def _normalize_nuclide(nuclide: str) -> str:
    """"18F", "f-18", "F18" -> "f18"."""
    m = re.match(r"^([a-z]*?)-?(\d+)$|^([0-9]+)-?([a-z]+)$", nuclide.lower())
    if m:
        return f"{m.group(1)}{m.group(2)}" if m.group(1) is not None else f"{m.group(4)}{m.group(3)}"
    return nuclide.lower().replace("-", "")


class LocalReactionDataProvider:
    """Lee sigma(E) y decaimiento de los datasets versionados del monorepo."""

    def __init__(self, data_dir: Path) -> None:
        self._dir = Path(data_dir)
        self._meta = json.loads((self._dir / "reactions.json").read_text())

    def get_excitation_function(self, reaction_id: str):
        rel = self._meta[reaction_id]["file"]
        e, s, ds = [], [], []
        with open(self._dir / rel, newline="") as fh:
            for row in csv.reader(fh):
                if not row or row[0].startswith("#") or row[0] == "energy_MeV":
                    continue
                e.append(float(row[0])); s.append(float(row[1]))
                ds.append(float(row[2]) if len(row) > 2 and row[2] != "" else None)
        return e, s, ds

    def get_decay_constant(self, nuclide: str) -> float:
        key = _normalize_nuclide(nuclide)
        raw = json.loads((self._dir / "decay" / f"{key}.json").read_text())
        return float(raw["decay_constant_s-1"])

    def get_threshold(self, reaction_id: str) -> float:
        return float(self._meta[reaction_id]["threshold_mev"])

    def get_dataset_id(self, reaction_id: str) -> str:
        return str(self._meta[reaction_id]["dataset_id"])
