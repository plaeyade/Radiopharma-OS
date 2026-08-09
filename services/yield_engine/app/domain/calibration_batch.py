"""
Calibration Layer F3 — K-factor por lote (EDS cap. 17: 17.6 Experimental
Data Manager, 17.21 estrategia incremental con criterios de calidad
predefinidos, 17.22 versionado con lote/operador/algoritmo).

Cada lote de producción real puede contribuir una medida al ajuste del
factor C por (reacción, equipo), pero solo si supera la puerta de calidad
predefinida: "No todas las producciones se incorporan automáticamente"
(17.21). La puerta es determinista y sus criterios son explícitos:

  - eob_predicho_gbq > 0 y eob_medido_gbq > 0 (física básica);
  - incertidumbre relativa declarada ≤ 25 % (calidad de la medida);
  - coherencia física del cociente: 0.1 ≤ k ≤ 10 (un factor fuera de ese
    rango indica error de registro o de unidades, no física real);
  - batch_id y operador no vacíos (trazabilidad 17.22/17.25).
"""
from __future__ import annotations

from dataclasses import dataclass

K_MIN: float = 0.1
K_MAX: float = 10.0
U_REL_MAX: float = 0.25
ALGORITMO: str = "k_batch=medido/predicho; WLS en fit posterior (fit_factor)"


@dataclass(frozen=True)
class BatchMeasurement:
    """Medida de EOB real asociada a un lote de producción (17.6)."""
    batch_id: str
    fecha: str                       # ISO 8601 (fecha del lote)
    eob_predicho_gbq: float          # predicción del Physics Twin (inalterada)
    eob_medido_gbq: float            # actividad EOB medida en el lote
    incertidumbre_gbq: float = 0.0   # u experimental del medido (0 = no declarada)
    operador: str = ""               # quién registra la medida (17.22)


def batch_k_factor(eob_medido_gbq: float, eob_predicho_gbq: float) -> float:
    """k del lote: cociente medido/predicho (17.8: corrección documentada,
    nunca sustituye al modelo físico)."""
    if eob_predicho_gbq <= 0.0:
        raise ValueError("eob_predicho_gbq debe ser > 0")
    return eob_medido_gbq / eob_predicho_gbq


def quality_gate(m: BatchMeasurement) -> dict:
    """Puerta de calidad 17.21. Devuelve {"accepted": bool, "k": float|None,
    "reasons": [str]} — nunca lanza: el veredicto es dato, no excepción."""
    reasons: list[str] = []
    if not m.batch_id or not m.batch_id.strip():
        reasons.append("batch_id vacío: la medida debe quedar asociada al lote (17.6)")
    if not m.operador or not m.operador.strip():
        reasons.append("operador vacío: trazabilidad obligatoria (17.22/17.25)")
    if m.eob_predicho_gbq <= 0.0:
        reasons.append("eob_predicho_gbq debe ser > 0")
    if m.eob_medido_gbq <= 0.0:
        reasons.append("eob_medido_gbq debe ser > 0")
    if m.incertidumbre_gbq < 0.0:
        reasons.append("incertidumbre_gbq no puede ser negativa")
    k: float | None = None
    if m.eob_predicho_gbq > 0.0 and m.eob_medido_gbq > 0.0:
        k = batch_k_factor(m.eob_medido_gbq, m.eob_predicho_gbq)
        if not (K_MIN <= k <= K_MAX):
            reasons.append(
                f"k={k:.4g} fuera de coherencia física "
                f"[{K_MIN}, {K_MAX}]: revise registro/unidades")
        if m.incertidumbre_gbq > 0.0:
            u_rel = m.incertidumbre_gbq / m.eob_medido_gbq
            if u_rel > U_REL_MAX:
                reasons.append(
                    f"incertidumbre relativa {u_rel:.2%} supera el máximo "
                    f"admisible {U_REL_MAX:.0%} (calidad de la medida)")
    return {"accepted": not reasons, "k": k, "reasons": reasons}
