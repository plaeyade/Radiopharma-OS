"""Analítica GMP del Data Lake: *trending* del rendimiento de producción.

Las revisiones periódicas de producto (APR/PQR) exigen demostrar que el
proceso permanece en estado de control: hay que vigilar la deriva del
rendimiento antes de que un lote caiga fuera de especificación.

Este servicio construye la serie cronológica de lotes y aplica un
**gráfico de control de Shewhart** sobre la actividad EOB normalizada
(`eob_per_uah` = GBq por µA·h de haz — así se comparan corridas con
distinta corriente y duración):

- límites de aviso a ±2σ y de control a ±3σ sobre la media,
- *run rule*: 6 o más puntos consecutivos al mismo lado de la media,
- **regresión lineal** contra el tiempo para clasificar la tendencia
  (estable / creciente / decreciente) con pendiente relativa y R².

Los lotes anulados (voided) quedan fuera del cálculo por defecto — no son
evidencia del proceso — pero pueden incluirse marcados.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..domain.entities import BatchRecord, BatchStatus
from ..domain.interfaces import BatchRepository

_RUN_RULE = 6                       # puntos consecutivos al mismo lado
_SLOPE_PCT_SIGNIFICATIVO = 0.5      # %/día para declarar deriva
_R2_MINIMO = 0.30                   # ajuste mínimo para fiar la pendiente


@dataclass(frozen=True)
class TrendPoint:
    batch_id: str
    created_at: datetime
    eob_activity_gbq: float
    eob_per_uah: float
    saturation_yield_mbq_ua: float
    status: str
    release_status: str
    warning: bool = False
    out_of_control: bool = False


@dataclass(frozen=True)
class EobTrend:
    reaction_id: Optional[str]
    n_batches: int
    points: tuple[TrendPoint, ...]
    mean: Optional[float]
    std: Optional[float]
    ucl: Optional[float]            # +3σ
    lcl: Optional[float]            # −3σ
    uwl: Optional[float]            # +2σ (aviso)
    lwl: Optional[float]            # −2σ (aviso)
    slope_pct_per_day: Optional[float]
    r_squared: Optional[float]
    direction: str                  # stable | improving | declining
    alerts: tuple[str, ...] = field(default_factory=tuple)


class AnalyticsService:
    def __init__(self, batches: BatchRepository) -> None:
        self._batches = batches

    async def eob_trend(self, reaction_id: Optional[str] = None,
                        limit: int = 50,
                        include_voided: bool = False) -> EobTrend:
        lotes = await self._batches.list(reaction_id=reaction_id,
                                         limit=max(limit, 200))
        cron = sorted(lotes, key=lambda b: b.created_at)
        if not include_voided:
            cron = [b for b in cron if b.status is not BatchStatus.VOIDED]
        cron = cron[-limit:]
        pts = [_punto(b) for b in cron]
        if len(pts) < 2:
            return EobTrend(reaction_id=reaction_id, n_batches=len(pts),
                            points=tuple(pts), mean=None, std=None,
                            ucl=None, lcl=None, uwl=None, lwl=None,
                            slope_pct_per_day=None, r_squared=None,
                            direction="stable",
                            alerts=() if pts else
                            ("sin lotes suficientes para trending",))

        vals = [p.eob_per_uah for p in pts]
        # Fase I (SPC): detección de valores atípicos con límites
        # leave-one-out a 3σ — con límites inclusivos un solo outlier infla σ
        # y "enmascara" su propia desviación. Los avisos (2σ) se evalúan
        # luego contra los límites limpios, sin amplificación por n pequeño.
        outliers: set[int] = set()
        if len(vals) >= 3:
            for i, v in enumerate(vals):
                resto = vals[:i] + vals[i + 1:]
                m = sum(resto) / len(resto)
                s = math.sqrt(sum((x - m) ** 2 for x in resto) / len(resto))
                if s > 0 and abs(v - m) > 3 * s:
                    outliers.add(i)
        limpios = [v for i, v in enumerate(vals) if i not in outliers]
        base = limpios if len(limpios) >= 2 else vals
        mean = sum(base) / len(base)
        std = math.sqrt(sum((v - mean) ** 2 for v in base) / len(base))
        ucl, lcl = mean + 3 * std, mean - 3 * std
        uwl, lwl = mean + 2 * std, mean - 2 * std

        marcados = []
        for i, p in enumerate(pts):
            fuera = i in outliers
            aviso = (not fuera) and std > 0 and \
                abs(p.eob_per_uah - mean) > 2 * std
            marcados.append(TrendPoint(**{**p.__dict__,
                                          "warning": aviso,
                                          "out_of_control": fuera}))

        # Regresión sobre los puntos *limpios* (sin outliers) — un valor
        # atípico no debe arrastrar la pendiente. La dirección también se
        # declara por run rule monótona (regla clásica: 6+ puntos seguidos
        # subiendo o bajando = deriva, aunque el ajuste global no sea lineal).
        limpios_pts = [p for i, p in enumerate(pts) if i not in outliers]
        slope_pct, r2 = _regresion(limpios_pts, mean)
        racha_mono = _racha_monotona([p.eob_per_uah for p in limpios_pts])
        if (r2 >= _R2_MINIMO and slope_pct <= -_SLOPE_PCT_SIGNIFICATIVO) \
                or racha_mono == "down":
            direccion = "declining"
        elif (r2 >= _R2_MINIMO and slope_pct >= _SLOPE_PCT_SIGNIFICATIVO) \
                or racha_mono == "up":
            direccion = "improving"
        else:
            direccion = "stable"

        return EobTrend(reaction_id=reaction_id, n_batches=len(marcados),
                        points=tuple(marcados), mean=mean, std=std,
                        ucl=ucl, lcl=lcl, uwl=uwl, lwl=lwl,
                        slope_pct_per_day=slope_pct, r_squared=r2,
                        direction=direccion,
                        alerts=tuple(_alertas(marcados, mean, std,
                                              direccion, slope_pct)))


def _punto(b: BatchRecord) -> TrendPoint:
    horas = max(b.beam.irradiation_time_min, 1e-9) / 60.0
    per_uah = b.results.eob_activity_gbq / (b.beam.current_ua * horas)
    return TrendPoint(batch_id=b.batch_id, created_at=b.created_at,
                      eob_activity_gbq=b.results.eob_activity_gbq,
                      eob_per_uah=per_uah,
                      saturation_yield_mbq_ua=b.results.saturation_yield_mbq_ua,
                      status=b.status.value,
                      release_status=b.release_status.value)


def _regresion(pts: list[TrendPoint], mean: float) -> tuple[float, float]:
    """Pendiente relativa (%/día respecto a la media) y R² contra el tiempo."""
    t0 = pts[0].created_at.timestamp()
    xs = [(p.created_at.timestamp() - t0) / 86400.0 for p in pts]  # días
    ys = [p.eob_per_uah for p in pts]
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0 or mean == 0:
        return 0.0, 0.0
    slope = sxy / sxx                      # unidades/día
    r = sxy / math.sqrt(sxx * syy)
    return (slope / mean) * 100.0, r * r


def _racha_monotona(vals: list[float]) -> str | None:
    """Regla de racha monótona: la serie termina con 6+ puntos todos
    crecientes o todos decrecientes = deriva del proceso (regla clásica
    de control charts)."""
    if len(vals) < _RUN_RULE:
        return None
    signo = None
    pasos = 0
    for i in range(len(vals) - 1, 0, -1):
        d = vals[i] - vals[i - 1]
        if d == 0:
            break
        s = 1 if d > 0 else -1
        if signo is None:
            signo = s
        elif s != signo:
            break
        pasos += 1
    # `pasos` diferencias consecutivas del mismo signo = pasos+1 puntos
    if pasos >= _RUN_RULE - 1 and signo is not None:
        return "up" if signo > 0 else "down"
    return None


def _alertas(pts: list[TrendPoint], mean: float, std: float,
             direccion: str, slope_pct: float) -> list[str]:
    out: list[str] = []
    for p in pts:
        if p.out_of_control:
            sigma = "superior" if p.eob_per_uah > mean else "inferior"
            out.append(f"{p.batch_id} fuera del límite de control {sigma} "
                       f"(3σ): {p.eob_per_uah:.2f} GBq/µA·h")
        elif p.warning:
            out.append(f"{p.batch_id} en zona de aviso (2σ): "
                       f"{p.eob_per_uah:.2f} GBq/µA·h")
    # run rule: racha final de N puntos al mismo lado de la media
    if std > 0 and len(pts) >= _RUN_RULE:
        lado = [p.eob_per_uah > mean for p in pts]
        racha = 1
        for i in range(len(lado) - 1, 0, -1):
            if lado[i] == lado[i - 1]:
                racha += 1
            else:
                break
        if racha >= _RUN_RULE:
            donde = "por encima" if lado[-1] else "por debajo"
            out.append(f"racha de {racha} lotes consecutivos {donde} de la "
                       f"media — posible deriva del proceso")
    if direccion != "stable":
        signo = "creciente" if direccion == "improving" else "decreciente"
        out.append(f"tendencia {signo}: {slope_pct:+.2f} %/día en EOB "
                   f"normalizado")
        racha = _racha_monotona([p.eob_per_uah for p in pts])
        if racha is not None:
            sentido = "crecientes" if racha == "up" else "decrecientes"
            out.append(f"racha monótona: los últimos lotes son {sentido} "
                       f"consecutivos — deriva del proceso (run rule)")
    return out
