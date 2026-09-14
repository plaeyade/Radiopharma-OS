"""Proveedor de poder de frenado PSTAR/NIST para ventanas del blanco (19.10).

Tablas oficiales NIST PSTAR (Stopping-Power & Range Tables for Protons),
descargadas del servicio web del NIST y versionadas en el repo con fuente,
URL y fecha — nunca valores inventados. Cada CSV declara su procedencia en
la cabecera (trazabilidad ALCOA+ de los datos).

Uso canónico: degradación de la energía del haz al atravesar la ventana
del blanco antes de entrar en el medio enriquecido (cadena haz → SRIM/
PSTAR → blanco, Informe §501).
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

# materiales con tabla PSTAR versionada en data/stopping/pstar/
MATERIALES_PSTAR = {"water": "proton_water_pstar.csv",
                    "iron": "proton_iron_pstar.csv",
                    "copper": "proton_cu_pstar.csv"}

# densidades de referencia declaradas (g/cm³) — solo para convertir
# espesores; se documentan como supuesto explícito del usuario
DENSIDADES_REF = {"water": 1.0, "iron": 7.874,
                  "havar_aprox": 8.3,  # proxy declarado: Havar ≈ Fe en S(E)
                  "copper": 8.96}


class VentanaInvalida(ValueError):
    """Ventana no registrada o haz detenido en la ventana."""


class PstarTables:
    """Interpolación sobre tablas PSTAR versionadas (S total y rango CSDA)."""

    def __init__(self, data_dir: Path) -> None:
        self._tablas: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        base = Path(data_dir)
        for key, fname in MATERIALES_PSTAR.items():
            e_vals, s_vals, r_vals = [], [], []
            with open(base / fname, newline="") as fh:
                for row in csv.reader(fh):
                    if not row or row[0].startswith("#") or row[0] == "energy_MeV":
                        continue
                    e_vals.append(float(row[0]))
                    s_vals.append(float(row[1]))
                    r_vals.append(float(row[2]))
            self._tablas[key] = (np.array(e_vals), np.array(s_vals),
                                 np.array(r_vals))

    def materiales(self) -> list[str]:
        return sorted(self._tablas)

    def stopping_power(self, material: str, energy_mev: float) -> float:
        e, s, _ = self._tablas[material]
        if energy_mev <= e[0]:
            return float(s[0])
        if energy_mev >= e[-1]:
            return float(s[-1])
        # S(E) varía órdenes de magnitud: interpolación log-log
        return float(np.exp(np.interp(np.log(energy_mev), np.log(e),
                                      np.log(s))))

    def range_g_cm2(self, material: str, energy_mev: float) -> float:
        """Rango CSDA tabulado por el NIST (no integración propia)."""
        e, _, r = self._tablas[material]
        if energy_mev <= e[0]:
            return float(r[0])
        if energy_mev >= e[-1]:
            return float(r[-1])
        return float(np.exp(np.interp(np.log(energy_mev), np.log(e),
                                      np.log(r))))

    def degradar(self, material: str, espesor_g_cm2: float,
                 energia_in_mev: float) -> float:
        """Energía tras atravesar la ventana: R(E_out) = R(E_in) − x.

        Si el espesor supera el rango del haz, el haz se DETIENE en la
        ventana — se declara error, nunca se inventa una energía de salida.
        """
        if espesor_g_cm2 < 0:
            raise VentanaInvalida("espesor de ventana negativo")
        if espesor_g_cm2 == 0:
            return float(energia_in_mev)
        e, _, r = self._tablas[material]
        r_in = self.range_g_cm2(material, energia_in_mev)
        r_out = r_in - espesor_g_cm2
        if r_out <= 0:
            raise VentanaInvalida(
                f"haz detenido en la ventana: rango CSDA a {energia_in_mev} MeV "
                f"en {material} = {r_in:.4f} g/cm² < espesor {espesor_g_cm2} g/cm²")
        # invertir R(E) por interpolación log-log
        if r_out >= r[-1]:
            return float(e[-1])
        return float(np.exp(np.interp(np.log(r_out), np.log(r), np.log(e))))

    def source_label(self) -> str:
        return "NIST PSTAR (physics.nist.gov/PhysRefData/Star) — tablas versionadas"
