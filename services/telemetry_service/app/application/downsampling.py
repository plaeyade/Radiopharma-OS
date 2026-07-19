"""Diezmado de series temporales para visualización (Operational Twin F2).

Las corridas largas acumulan decenas de miles de puntos por serie; enviar
todos a la consola es innecesario (un gráfico no distingue más de unos
cientos de pixeles horizontales) y degrada la UI. Este módulo reduce la
serie preservando su forma visual:

- **LTTB** (Largest-Triangle-Three-Buckets, Steinarsson 2014): selecciona
  un subconjunto de puntos *reales* maximizando el área triangular
  cubierta — conserva picos, valles y cambios de régimen que un promedio
  por ventana borra. Método por defecto.
- **bucket-mean**: promedio por ventana temporal uniforme (punto
  sintético en el centro de la ventana); útil para exportaciones densas
  con ruido suavizado.

El diezmado se aplica en la capa de aplicación (no en el store) para
garantizar paridad entre los backends SQLite e InfluxDB.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

from ..domain.entities import TelemetryPoint

METODOS = ("lttb", "bucket-mean")


def downsample(points: list[TelemetryPoint], max_points: int,
               method: str = "lttb") -> list[TelemetryPoint]:
    """Reduce `points` a lo sumo `max_points` preservando la forma."""
    if max_points <= 0:
        raise ValueError("max_points debe ser positivo")
    if method not in METODOS:
        raise ValueError(f"Método de diezmado desconocido: {method!r} "
                         f"(válidos: {', '.join(METODOS)})")
    ordenados = sorted(points, key=lambda p: p.ts)
    if len(ordenados) <= max_points:
        return ordenados
    if method == "lttb":
        idx = _lttb_indices(ordenados, max_points)
        return [ordenados[i] for i in idx]
    return _bucket_mean(ordenados, max_points)


def _lttb_indices(points: list[TelemetryPoint], threshold: int) -> list[int]:
    """Índices seleccionados por Largest-Triangle-Three-Buckets."""
    n = len(points)
    if threshold >= n or threshold <= 0:
        return list(range(n))
    if threshold == 1:
        return [0]
    if threshold == 2:
        return [0, n - 1]
    xs = [p.ts.timestamp() for p in points]
    ys = [p.value for p in points]

    sampled = [0]                          # siempre el primero
    every = (n - 2) / (threshold - 2)      # tamaño de bucket
    a = 0                                  # índice del último seleccionado
    for i in range(threshold - 2):
        # promedio del bucket *siguiente* (punto de referencia del triángulo)
        lo = int(math.floor((i + 1) * every)) + 1
        hi = min(int(math.floor((i + 2) * every)) + 1, n)
        cnt = hi - lo
        avg_x = sum(xs[lo:hi]) / cnt
        avg_y = sum(ys[lo:hi]) / cnt
        # punto del bucket actual que maximiza el área triangular
        b_lo = int(math.floor(i * every)) + 1
        b_hi = int(math.floor((i + 1) * every)) + 1
        ax, ay = xs[a], ys[a]
        max_area, next_a = -1.0, b_lo
        for j in range(b_lo, b_hi):
            area = abs((ax - avg_x) * (ys[j] - ay)
                       - (ax - xs[j]) * (avg_y - ay))
            if area > max_area:
                max_area, next_a = area, j
        sampled.append(next_a)
        a = next_a
    sampled.append(n - 1)                  # siempre el último
    return sampled


def _bucket_mean(points: list[TelemetryPoint], max_points: int) -> list[TelemetryPoint]:
    """Promedio por ventana temporal uniforme (punto sintético centrado)."""
    t0, t1 = points[0].ts.timestamp(), points[-1].ts.timestamp()
    ancho = (t1 - t0) / max_points
    if ancho <= 0:
        return points[:max_points]
    buckets: dict[int, list[TelemetryPoint]] = {}
    for p in points:
        k = min(int((p.ts.timestamp() - t0) / ancho), max_points - 1)
        buckets.setdefault(k, []).append(p)
    out = []
    for k in sorted(buckets):
        pts = buckets[k]
        media = sum(p.value for p in pts) / len(pts)
        ts_media = datetime.fromtimestamp(t0 + (k + 0.5) * ancho,
                                          tz=timezone.utc)
        ref = pts[0]
        out.append(TelemetryPoint(series=ref.series, ts=ts_media,
                                  value=media, tags=ref.tags))
    return out
