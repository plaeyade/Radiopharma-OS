"""Detección de desviaciones de proceso (Operational Twin F2).

GMP exige documentar las desviaciones de proceso durante la fabricación
(p. ej. caída del caudal de enfriamiento, sobrepresión del blanco,
inestabilidad del haz). Este módulo evalúa la telemetría de una corrida
contra reglas de rango por serie y devuelve *eventos* de desviación:
rachas de puntos consecutivos fuera de límite, agrupadas y caracterizadas
(inicio, fin, nº de puntos, valor extremo, lado violado).

Los límites se agrupan en *packs* precargados (perfil de corrida nominal
del centro); el llamante puede sobreescribirlos con reglas propias. La
fracción inicial de la corrida (`grace_fraction`, rampa del haz) se
excluye por defecto: la corriente sube de 0 durante la rampa y no es una
desviación.

Los eventos detectados deben registrarse en el Data Lake como eventos de
auditoría del lote (POST /api/v1/batches/{id}/events) para quedar en el
eBR — esa integración la ejecuta el llamante (consola o CLI).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..domain.entities import TelemetryPoint


@dataclass(frozen=True)
class DeviationRule:
    series: str
    low: float
    high: float
    unit: str
    description: str


@dataclass(frozen=True)
class DeviationPack:
    name: str
    description: str
    grace_fraction: float
    rules: tuple[DeviationRule, ...]


@dataclass(frozen=True)
class DeviationEvent:
    series: str
    started_at: datetime
    ended_at: datetime
    n_points: int
    extreme_value: float
    limit: float
    side: str           # "low" | "high"
    unit: str

    def describe(self) -> str:
        direccion = "por debajo de" if self.side == "low" else "por encima de"
        return (f"{self.series} {direccion} {self.limit:g} {self.unit} "
                f"(extremo {self.extreme_value:g} {self.unit}, "
                f"{self.n_points} puntos entre {self.started_at.isoformat()} "
                f"y {self.ended_at.isoformat()})")


PACKS: dict[str, DeviationPack] = {
    # Perfil nominal del simulador / corrida FDG típica: haz 40 µA en meseta
    # (deriva térmica ≤1 %), blanco H2[18O] a ~345 psi, enfriamiento ~12 lpm.
    "cyclotron_generic": DeviationPack(
        name="cyclotron_generic",
        description="Límites de proceso para corrida nominal de ciclotrón "
                    "(haz 40 µA, blanco líquido) — verificar contra la receta "
                    "del lote antes de uso regulatorio",
        grace_fraction=0.06,
        rules=(
            DeviationRule("beam_current_ua", 38.0, 42.0, "µA",
                          "estabilidad de corriente de haz en meseta"),
            DeviationRule("target_pressure_psi", 335.0, 355.0, "psi",
                          "presión del blanco (fuga / calentamiento)"),
            DeviationRule("cooling_flow_lpm", 10.0, 13.5, "lpm",
                          "caudal de enfriamiento del blanco"),
        )),
}

DEFAULT_PACK = "cyclotron_generic"


def get_pack(name: str) -> DeviationPack:
    try:
        return PACKS[name]
    except KeyError:
        raise ValueError(f"Pack de desviaciones desconocido: {name!r} "
                         f"(disponibles: {', '.join(sorted(PACKS))})")


def evaluate(points: list[TelemetryPoint],
             rules: tuple[DeviationRule, ...] | list[DeviationRule],
             grace_fraction: float = 0.0) -> list[DeviationEvent]:
    """Agrupa los puntos fuera de rango en eventos de desviación.

    `grace_fraction` excluye la fracción inicial del intervalo observado
    (rampa del haz) de *todas* las reglas evaluadas.
    """
    if not 0.0 <= grace_fraction < 0.5:
        raise ValueError("grace_fraction debe estar en [0, 0.5)")
    por_serie: dict[str, list[TelemetryPoint]] = {}
    for p in points:
        por_serie.setdefault(p.series, []).append(p)

    eventos: list[DeviationEvent] = []
    for regla in rules:
        pts = sorted(por_serie.get(regla.series, []), key=lambda p: p.ts)
        if len(pts) < 2:
            continue
        t0, t1 = pts[0].ts.timestamp(), pts[-1].ts.timestamp()
        grace_hasta = t0 + grace_fraction * (t1 - t0)
        violaciones = []
        for p in pts:
            if p.ts.timestamp() < grace_hasta:
                continue
            if p.value < regla.low:
                violaciones.append((p, "low", regla.low))
            elif p.value > regla.high:
                violaciones.append((p, "high", regla.high))
        eventos.extend(_agrupar(violaciones, regla))
    return sorted(eventos, key=lambda e: (e.started_at, e.series))


def _agrupar(violaciones: list[tuple[TelemetryPoint, str, float]],
             regla: DeviationRule) -> list[DeviationEvent]:
    """Rachas consecutivas (misma serie y lado) → un evento cada una."""
    if not violaciones:
        return []
    eventos: list[DeviationEvent] = []
    grupo = [violaciones[0]]
    for v in violaciones[1:]:
        mismo_lado = v[1] == grupo[-1][1]
        consecutivo = (v[0].ts.timestamp() - grupo[-1][0].ts.timestamp()) \
            <= _gap_max(grupo)
        if mismo_lado and consecutivo:
            grupo.append(v)
        else:
            eventos.append(_evento(grupo, regla))
            grupo = [v]
    eventos.append(_evento(grupo, regla))
    return eventos


def _gap_max(grupo: list[tuple[TelemetryPoint, str, float]]) -> float:
    """Hueco temporal máximo dentro de una racha (5× el paso típico)."""
    if len(grupo) < 2:
        return float("inf")
    pasos = [grupo[i + 1][0].ts.timestamp() - grupo[i][0].ts.timestamp()
             for i in range(len(grupo) - 1)]
    return 5.0 * (sum(pasos) / len(pasos))


def _evento(grupo: list[tuple[TelemetryPoint, str, float]],
            regla: DeviationRule) -> DeviationEvent:
    lado = grupo[0][1]
    valores = [p.value for p, _, _ in grupo]
    extremo = min(valores) if lado == "low" else max(valores)
    return DeviationEvent(
        series=regla.series, started_at=grupo[0][0].ts,
        ended_at=grupo[-1][0].ts, n_points=len(grupo),
        extreme_value=extremo, limit=grupo[0][2], side=lado,
        unit=regla.unit)
