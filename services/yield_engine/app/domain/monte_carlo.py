"""
Dominio del Monte Carlo Interface (cap. 19): validación y métricas.

- Validación previa (19.21): geometría, materiales, física seleccionada
  y consistencia de la fuente se verifican antes de ejecutar; las
  simulaciones incompletas no se incorporan al Data Lake.
- Gestión de incertidumbre (19.20): número de historias, incertidumbre
  estadística (lotes independientes) y criterio de convergencia.
- Comparación con el Yield/Thermal Engine (19.14): la energía
  depositada por historia se convierte a potencia con la corriente del
  ciclotrón y se contrasta con el modelo determinista; las diferencias
  alimentan validación y calibración (19.16) — nunca se aplican
  automáticamente.
"""
from __future__ import annotations

from app.infrastructure.gate.gate_case import (
    N_HIST_MAX,
    N_HIST_MIN,
    PHYSICS_LISTS_VALIDAS,
    U_REL_CONVERGENCIA,
    MonteCarloTargetCase,
)

MEV_J = 1.602176634e-13  # J por MeV
UA_PROTONES_S = 6.241509074e12  # 1 µA = 1e-6 C/s / e


def validar_caso(case: MonteCarloTargetCase) -> list[str]:
    """Verificaciones 19.21. Devuelve la lista de incumplimientos (vacía = OK)."""
    reasons: list[str] = []
    if case.particle != "proton":
        reasons.append(f"partícula no admitida en el MVP: {case.particle!r} (19.10)")
    if not (1.0 <= case.beam_energy_mev <= 250.0):
        reasons.append(f"energía de haz fuera de rango físico del servicio: {case.beam_energy_mev} MeV")
    if case.beam_radius_cm <= 0 or case.beam_radius_cm > case.target_radius_cm:
        reasons.append(
            f"radio de haz ({case.beam_radius_cm} cm) inconsistente con el blanco "
            f"(radio {case.target_radius_cm} cm): la fuente debe illuminar el blanco (19.8/19.21)"
        )
    if case.target_radius_cm <= 0 or case.target_thickness_cm <= 0:
        reasons.append("geometría del blanco inválida: radio y espesor deben ser positivos (19.6/19.21)")
    if not (0.5 <= case.target_density_g_cm3 <= 2.0):
        reasons.append(f"densidad de material no física para H2-18O: {case.target_density_g_cm3} g/cm3 (19.7)")
    if case.physics_list not in PHYSICS_LISTS_VALIDAS:
        reasons.append(
            f"lista de física no registrada: {case.physics_list!r}; "
            f"admitidas (19.9): {', '.join(PHYSICS_LISTS_VALIDAS)}"
        )
    if not (N_HIST_MIN <= case.n_histories <= N_HIST_MAX):
        reasons.append(
            f"n_histories={case.n_histories} fuera de [{N_HIST_MIN}, {N_HIST_MAX}] "
            "(coste computacional acotado, 19.3/19.25)"
        )
    if case.n_batches < 2:
        reasons.append("se requieren ≥2 lotes para la incertidumbre estadística (19.20)")
    if case.n_histories // case.n_batches < N_HIST_MIN // 2:
        reasons.append("historias por lote insuficientes para estimar la incertidumbre (19.20)")
    return reasons


def evaluar_resultados(results: dict, umbral: float = U_REL_CONVERGENCIA) -> dict:
    """Métricas 19.20 sobre la salida del runner.

    convergence_ok exige incertidumbre relativa ≤ umbral; validation_ok
    (19.21) exige además historias completas y deposición positiva.
    """
    n_total = int(results.get("n_histories_total") or 0)
    case_n = int((results.get("case") or {}).get("n_histories") or 0)
    edep_hist = results.get("edep_mev_per_history")
    u_rel = results.get("statistical_uncertainty_rel")
    checks = {
        "histories_complete": n_total == case_n and n_total > 0,
        "edep_positive": bool(edep_hist is not None and edep_hist > 0),
        "uncertainty_available": u_rel is not None,
    }
    convergence_ok = bool(u_rel is not None and u_rel <= umbral)
    validation_ok = all(checks.values())
    return {
        "checks": checks,
        "n_histories": n_total,
        "statistical_uncertainty_rel": u_rel,
        "umbral_convergencia_rel": umbral,
        "convergence_ok": convergence_ok,
        "validation_ok": validation_ok,
        "review_required": (not validation_ok) or (not convergence_ok),
    }


def comparar_con_determinista(edep_mev_per_history: float, current_ua: float,
                              beam_power_determinista_w: float) -> dict:
    """Integración Yield Engine (19.14): potencia MC vs determinista.

    La potencia MC asume deposición completa por historia escalada a la
    corriente del haz; la desviación relativa se reporta como referencia
    independiente para validación/calibración (19.16), sin aplicarla.
    """
    power_mc_w = edep_mev_per_history * MEV_J * (current_ua * UA_PROTONES_S)
    desv_rel = (power_mc_w - beam_power_determinista_w) / beam_power_determinista_w
    return {
        "power_mc_w": power_mc_w,
        "power_determinista_w": beam_power_determinista_w,
        "desviacion_rel": desv_rel,
        "desviacion_pct": desv_rel * 100.0,
        "nota": "referencia independiente MC vs determinista (19.14/19.16); no se aplica automáticamente",
    }
