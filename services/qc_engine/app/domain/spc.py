"""
Control estadístico de procesos (SPC) del QC Engine — trending GMP como
apoyo a la decisión (EDS v2.0 caps. 25.17 / 26.19: las recomendaciones
analíticas son apoyo, nunca sustituyen la evaluación técnica; el resultado
permanece diferenciado de los resultados medidos).

Carta de control de individuales (Shewhart I-chart) con:

    CL  = μ                      (media muestral)
    UCL/LCL = μ ± 3σ             (σ muestral, n−1)

Reglas de Western Electric / Nelson evaluadas sobre zonas (la violación
se atribuye al punto que completa el patrón):

    WE1   1 punto más allá de ±3σ
    WE2   2 de 3 consecutivos más allá de ±2σ, mismo lado
    WE3   4 de 5 consecutivos más allá de ±1σ, mismo lado
    WE4   8 consecutivos del mismo lado de la media
    TREND 6 consecutivos estrictamente crecientes o decrecientes

Capacidad de proceso (solo si se aportan límites de especificación):

    Cp  = (USL − LSL) / 6σ            Cpk = min((USL−μ)/3σ, (μ−LSL)/3σ)

El SPC no evalúa conformidad farmacopeica (eso es `acceptance_rules`):
detecta **deriva del proceso** antes de que aparezcan OOS. Con menos de
2 puntos no hay σ; con σ = 0 las reglas de zona no aplican.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SpcPoint:
    """Un punto de la carta con las reglas que viola (vacío = en control)."""
    index: int
    label: str
    value: float
    violations: tuple[str, ...]


@dataclass(frozen=True)
class SpcResult:
    """Resultado de la carta de control."""
    n: int
    mean: float
    sigma: float
    ucl: float
    lcl: float
    points: tuple[SpcPoint, ...]
    in_control: bool
    spec_low: float | None
    spec_high: float | None
    cp: float | None
    cpk: float | None


def _side(value: float, mean: float) -> int:
    return 1 if value > mean else (-1 if value < mean else 0)


def shewhart_spc(values: list[float],
                 labels: list[str] | None = None,
                 spec_low: float | None = None,
                 spec_high: float | None = None) -> SpcResult:
    """Carta I de Shewhart + reglas WE/Nelson (+ capacidad si hay specs)."""
    if len(values) < 2:
        raise ValueError("se requieren al menos 2 valores")
    if any(not math.isfinite(v) for v in values):
        raise ValueError("los valores deben ser finitos")
    if spec_low is not None and spec_high is not None \
            and spec_low >= spec_high:
        raise ValueError("spec_low debe ser < spec_high")

    n = len(values)
    mean = sum(values) / n
    sigma = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))
    ucl, lcl = mean + 3.0 * sigma, mean - 3.0 * sigma
    tags = [labels[i] if labels and i < len(labels) else f"#{i + 1}"
            for i in range(n)]

    violations: list[list[str]] = [[] for _ in range(n)]
    if sigma > 0.0:
        for i in range(n):
            if abs(values[i] - mean) > 3.0 * sigma:
                violations[i].append("WE1")
        # WE2: 2 de 3 más allá de 2σ, mismo lado
        for i in range(2, n):
            win = values[i - 2:i + 1]
            for side in (1, -1):
                hits = [j for j, v in enumerate(win)
                        if side * (v - mean) > 2.0 * sigma]
                if len(hits) >= 2:
                    violations[i - 2 + hits[-1]].append("WE2")
        # WE3: 4 de 5 más allá de 1σ, mismo lado
        for i in range(4, n):
            win = values[i - 4:i + 1]
            for side in (1, -1):
                hits = [j for j, v in enumerate(win)
                        if side * (v - mean) > 1.0 * sigma]
                if len(hits) >= 4:
                    violations[i - 4 + hits[-1]].append("WE3")
        # WE4: 8 consecutivos del mismo lado
        run_side, run_len = 0, 0
        for i in range(n):
            s = _side(values[i], mean)
            if s != 0 and s == run_side:
                run_len += 1
            else:
                run_side, run_len = s, 1 if s != 0 else 0
            if run_len >= 8:
                violations[i].append("WE4")
    # TREND: 6 consecutivos estrictamente crecientes/decrecientes
    run_sign, run_len = 0, 1
    for i in range(1, n):
        d = values[i] - values[i - 1]
        s = 1 if d > 0 else (-1 if d < 0 else 0)
        if s != 0 and s == run_sign:
            run_len += 1
        else:
            run_sign, run_len = s, 1
        if run_len >= 6:
            violations[i].append("TREND")

    points = tuple(SpcPoint(index=i + 1, label=tags[i], value=values[i],
                            violations=tuple(violations[i]))
                   for i in range(n))

    cp = cpk = None
    if sigma > 0.0 and (spec_low is not None or spec_high is not None):
        if spec_low is not None and spec_high is not None:
            cp = (spec_high - spec_low) / (6.0 * sigma)
        cands = []
        if spec_high is not None:
            cands.append((spec_high - mean) / (3.0 * sigma))
        if spec_low is not None:
            cands.append((mean - spec_low) / (3.0 * sigma))
        cpk = min(cands)

    return SpcResult(
        n=n, mean=mean, sigma=sigma, ucl=ucl, lcl=lcl, points=points,
        in_control=all(not p.violations for p in points),
        spec_low=spec_low, spec_high=spec_high, cp=cp, cpk=cpk)
