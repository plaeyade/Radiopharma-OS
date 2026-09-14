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
    """Interpolación lineal sobre tablas empaquetadas con el servicio.

    Procedencia declarada por material (49.11): ATIMA para h2o/o2/n2/
    n15/zn68; para ni64, NIST PSTAR cobre como **proxy declarado** —
    PSTAR no publica níquel (Cu, Z=29, vecino de Ni, Z=28); queda
    pendiente la tabla SRIM/ATIMA real de Ni exportada por el usuario,
    que podrá calibrarse y promoverse (19.10).
    """

    _FILES = {"h2o": "proton_h2o_atima.csv", "o2": "proton_o2_atima.csv",
              "n2": "proton_n2_atima.csv", "zn68": "proton_zn68_atima.csv",
              "n15": "proton_n15_atima.csv",
              "ni64": "pstar/proton_cu_pstar.csv"}

    _FUENTES = {"ni64": ("NIST PSTAR cobre (proxy declarado para Ni-64 — "
                         "PSTAR no publica Ni; CSV versionado en el repo)")}

    def __init__(self, data_dir: Path) -> None:
        self._tables: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        self._ranges: dict[str, np.ndarray] = {}
        for key, fname in self._FILES.items():
            e_vals, s_vals, r_vals = [], [], []
            with open(Path(data_dir) / fname, newline="") as fh:
                for row in csv.reader(fh):
                    if not row or row[0].startswith("#") or row[0] == "energy_MeV":
                        continue
                    e_vals.append(float(row[0]))
                    s_vals.append(float(row[1]))
                    # tablas PSTAR traen rango CSDA tabulado (3ª columna)
                    r_vals.append(float(row[2]) if len(row) > 2 else None)
            self._tables[key] = (np.array(e_vals), np.array(s_vals))
            if all(r is not None for r in r_vals):
                self._ranges[key] = np.array(r_vals)

    def stopping_power(self, material_key: str, energy_mev: float) -> float:
        e, s = self._tables[material_key]
        if energy_mev <= 0.0:
            return float(s[0])
        if material_key in self._ranges:
            # S(E) varía órdenes de magnitud (tabla PSTAR): log-log real
            return float(np.exp(np.interp(np.log(energy_mev), np.log(e),
                                          np.log(s))))
        return float(np.interp(energy_mev, e, s))

    def range_g_cm2(self, material_key: str, energy_mev: float) -> float:
        if material_key in self._ranges:
            # rango CSDA tabulado por el NIST (no integración propia)
            e, _ = self._tables[material_key]
            r = self._ranges[material_key]
            return float(np.exp(np.interp(np.log(energy_mev), np.log(e),
                                          np.log(r))))
        # Integración CSDA aproximada: R = ∫ dE / S(E)
        e, s = self._tables[material_key]
        mask = e <= energy_mev
        if mask.sum() < 2:
            return 0.0
        return float(np.trapezoid(1.0 / s[mask], e[mask]))

    def source_label(self) -> str:
        return ("Tablas ATIMA empaquetadas (CSV) + NIST PSTAR cobre como "
                "proxy declarado para ni64 (PSTAR no publica Ni)")
