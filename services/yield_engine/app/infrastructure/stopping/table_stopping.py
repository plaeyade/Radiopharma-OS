"""
Proveedor de poder de frenado desde tablas CSV precalculadas (fallback).

Tablas generadas con CATIMA/ATIMA en build-time; garantizan que el servicio
funcione incluso si el wheel de pycatima no está disponible en el contenedor.
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np


class TableStoppingPower:
    """Interpolación lineal sobre tablas ATIMA empaquetadas con el servicio."""

    _FILES = {"h2o": "proton_h2o_atima.csv", "o2": "proton_o2_atima.csv",
              "n2": "proton_n2_atima.csv", "zn68": "proton_zn68_atima.csv",
              "n15": "proton_n15_atima.csv"}

    def __init__(self, data_dir: Path) -> None:
        self._tables: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for key, fname in self._FILES.items():
            e_vals, s_vals = [], []
            with open(Path(data_dir) / fname, newline="") as fh:
                for row in csv.reader(fh):
                    if not row or row[0].startswith("#") or row[0] == "energy_MeV":
                        continue
                    e_vals.append(float(row[0]))
                    s_vals.append(float(row[1]))
            self._tables[key] = (np.array(e_vals), np.array(s_vals))

    def stopping_power(self, material_key: str, energy_mev: float) -> float:
        e, s = self._tables[material_key]
        if energy_mev <= 0.0:
            return float(s[0])
        return float(np.interp(energy_mev, e, s))

    def range_g_cm2(self, material_key: str, energy_mev: float) -> float:
        # Integración CSDA aproximada: R = ∫ dE / S(E)
        e, s = self._tables[material_key]
        mask = e <= energy_mev
        if mask.sum() < 2:
            return 0.0
        return float(np.trapezoid(1.0 / s[mask], e[mask]))

    def source_label(self) -> str:
        return "Tablas ATIMA empaquetadas (CSV)"
