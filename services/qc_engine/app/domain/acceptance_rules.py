"""
Motor de reglas de aceptación farmacopeica (configurable).

Los packs precargados son REFERENCIAS GENERALES para desarrollo:
deben verificarse contra la monografía vigente (USP <823> /
Ph. Eur. fludeoxyglucose (18F) injection) antes de uso GMP.
"""
from __future__ import annotations

from typing import Optional

from app.domain.entities import (AcceptanceRule, QcReport, QcStatus,
                                 RuleEvaluation)

RULE_PACKS: dict[str, dict] = {
    "fdg": {
        "label": "Fludeoxyglucosa [18F] (referencia general Ph. Eur./USP <823>)",
        "nuclide": "18F",
        "rules": [
            AcceptanceRule("ph", 4.5, 8.5, "unidades pH",
                           "Ph. Eur. FDG (verificar monografía vigente)"),
            AcceptanceRule("radiochemical_purity", 0.95, None, "fracción",
                           "Ph. Eur. FDG: pureza radioquímica >= 95%"),
            AcceptanceRule("radionuclidic_purity", 0.999, None, "fracción",
                           "USP <823>: pureza radionuclídica >= 99.9%"),
            AcceptanceRule("kryptofix_222", None, 2.2, "g/L",
                           "Ph. Eur. FDG: Kryptofix 2.2.2 <= 2.2 g/L"),
            AcceptanceRule("endotoxins_eu_ml", None, 17.5, "EU/mL",
                           "Límite interno típico (verificar USP <85>/monografía)"),
            AcceptanceRule("acetonitrile_mg_dose", None, 4.1, "mg/dosis",
                           "USP <467> clase 2 (verificar)"),
        ],
    },
    "generic_pet": {
        "label": "Radiofármaco PET genérico (referencia USP <823>)",
        "nuclide": None,
        "rules": [
            AcceptanceRule("radionuclidic_purity", 0.999, None, "fracción",
                           "USP <823>"),
            AcceptanceRule("radiochemical_purity", 0.90, None, "fracción",
                           "Referencia general (definir por producto)"),
        ],
    },
}


def evaluate_rules(product: str, measurements: dict[str, Optional[float]],
                   nuclide: str = "") -> QcReport:
    """Evalúa un conjunto de mediciones contra el pack de reglas."""
    pack = RULE_PACKS.get(product)
    if pack is None:
        raise ValueError(f"Pack de reglas desconocido: {product}. "
                         f"Disponibles: {sorted(RULE_PACKS)}")

    evaluations: list[RuleEvaluation] = []
    overall = QcStatus.PASS
    for rule in pack["rules"]:
        value = measurements.get(rule.parameter)
        if value is None:
            ev = RuleEvaluation(rule=rule, measured=None,
                                status=QcStatus.WARNING,
                                detail="sin medición reportada")
            overall = QcStatus.WARNING if overall == QcStatus.PASS else overall
        else:
            ok = True
            if rule.min_value is not None and value < rule.min_value:
                ok = False
            if rule.max_value is not None and value > rule.max_value:
                ok = False
            ev = RuleEvaluation(
                rule=rule, measured=value,
                status=QcStatus.PASS if ok else QcStatus.FAIL,
                detail="dentro de límite" if ok else "FUERA DE LÍMITE")
            if not ok:
                overall = QcStatus.FAIL
        evaluations.append(ev)

    return QcReport(product=product, nuclide=nuclide or (pack["nuclide"] or ""),
                    overall_status=overall, rule_evaluations=tuple(evaluations))
