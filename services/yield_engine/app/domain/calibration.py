"""
Calibration Layer (Informe Maestro EDS v2.0, Vol. II): ajuste del Physics
Twin contra el rendimiento EOB real medido en producción.

Modelo: factor de calibración multiplicativo C por (reacción, equipo) tal que
    EOB_real ≈ C · EOB_predicho

Ajuste: mínimos cuadrados ponderados (WLS) sobre los cocientes
r_i = medido_i / predicho_i con pesos w_i = 1/u_i² (incertidumbre de la
medida; si falta, se toma la dispersión muestral). La bondad del ajuste se
controla con χ² por grado de libertad.

Criterios de aceptación (cultura GMP, datos 100 % trazables):
  - "investigar": χ²_ndf > 2.5 (medidas inconsistentes entre sí) o
    |C − 1| > 0.35 (desviación inaceptable del modelo);
  - "observado": C difiere de 1 con significación > 2σ o |C − 1| > 0.10;
  - "vigente": en otro caso.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

CHI2_NDF_MAX: float = 2.5
DESVIACION_INACEPTABLE: float = 0.35
DESVIACION_OBSERVADA: float = 0.10


@dataclass(frozen=True)
class Measurement:
    """Una medida de EOB real contra su predicción del Physics Twin."""
    fecha: str                       # ISO 8601 (fecha del lote)
    eob_predicho_gbq: float
    eob_medido_gbq: float
    incertidumbre_gbq: float = 0.0   # u del medido (0 → se estima de la muestra)


@dataclass(frozen=True)
class FitResult:
    factor: float
    factor_uncertainty: float
    n_points: int
    chi2_ndf: float
    status: str                      # vigente | observado | investigar


def fit_factor(medidas: list[Measurement]) -> FitResult:
    """Ajusta C por WLS sobre los cocientes medido/predicho."""
    if len(medidas) < 2:
        raise ValueError("Se requieren al menos 2 medidas para calibrar")
    ratios, weights = [], []
    for m in medidas:
        if m.eob_predicho_gbq <= 0.0:
            raise ValueError("eob_predicho_gbq debe ser > 0")
        if m.eob_medido_gbq <= 0.0:
            raise ValueError("eob_medido_gbq debe ser > 0")
        r = m.eob_medido_gbq / m.eob_predicho_gbq
        ratios.append(r)
        if m.incertidumbre_gbq > 0.0:
            u_rel = m.incertidumbre_gbq / m.eob_medido_gbq
            weights.append(1.0 / (u_rel ** 2))
        else:
            weights.append(-1.0)               # marcador: peso uniforme

    if any(w < 0.0 for w in weights):
        # sin incertidumbres individuales: media + dispersión muestral
        n = len(ratios)
        mean = sum(ratios) / n
        var = (sum((r - mean) ** 2 for r in ratios) / (n - 1))
        u_factor = math.sqrt(var / n)
        factor = mean
        chi2_ndf = 1.0                         # dispersión por construcción
    else:
        sw = sum(weights)
        factor = sum(w * r for w, r in zip(weights, ratios)) / sw
        u_factor = math.sqrt(1.0 / sw)
        chi2 = sum(w * (r - factor) ** 2 for w, r in zip(weights, ratios))
        chi2_ndf = chi2 / (len(ratios) - 1)

    return FitResult(
        factor=round(factor, 6),
        factor_uncertainty=round(u_factor, 6),
        n_points=len(ratios),
        chi2_ndf=round(chi2_ndf, 4),
        status=classify(factor, u_factor, chi2_ndf),
    )


def classify(factor: float, u_factor: float, chi2_ndf: float) -> str:
    """Estado GMP del modelo calibrado."""
    if chi2_ndf > CHI2_NDF_MAX or abs(factor - 1.0) > DESVIACION_INACEPTABLE:
        return "investigar"
    significativo = (u_factor > 0.0
                     and abs(factor - 1.0) > 2.0 * u_factor + 1e-12)
    if significativo or abs(factor - 1.0) > DESVIACION_OBSERVADA:
        return "observado"
    return "vigente"
