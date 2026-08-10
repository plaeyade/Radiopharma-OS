"""Detección de anomalías sobre series temporales (EDS 6.22/6.23).

Las series temporales alimentan los modelos de detección de
anomalías (6.22). La configuración se define mediante **políticas
externas** (umbrales por política versionada, 6.20). Los datos
inválidos y las anomalías detectadas generan eventos de auditoría
(6.23): toda detección queda registrada con su política y su
serie. El detector nunca actúa sobre el proceso: reporta.
"""
from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

POLITICA_DEFAULT = "mad-v1.0.0"


@dataclass(frozen=True)
class PoliticaAnomalias:
    """Política externa versionada de detección (6.20)."""
    version: str = POLITICA_DEFAULT
    umbral_mad: float = 5.0          # desviaciones MAD robustas
    min_puntos: int = 12             # mínimo para una detección válida
    max_nan_frac: float = 0.0        # fracción de datos inválidos tolerada


@dataclass
class Anomalia:
    indice: int
    timestamp: str
    valor: float
    desviacion_mad: float


@dataclass
class ResultadoDeteccion:
    series: str
    politica: str
    n_puntos: int
    mediana: float
    mad: float
    anomalias: list[Anomalia]
    datos_invalidos: int
    auditoria: dict


class DeteccionInvalida(ValueError):
    """Serie insuficiente o política violada (6.23)."""


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def detectar_anomalias(valores: list[float | None],
                       timestamps: list[str] | None = None,
                       series: str = "",
                       politica: PoliticaAnomalias | None = None,
                       batch_id: str = "") -> ResultadoDeteccion:
    """Detección robusta por MAD (mediana + desviación absoluta).

    |x−mediana| / (1.4826·MAD) > umbral → anomalía. Robusta frente a
    outliers (a diferencia de z-score con media/desviación típica).
    """
    pol = politica or PoliticaAnomalias()
    ts = timestamps or ["" for _ in valores]
    if len(ts) != len(valores):
        raise DeteccionInvalida("timestamps y valores deben tener la "
                                "misma longitud (6.23)")
    invalidos = [i for i, v in enumerate(valores)
                 if v is None or not isinstance(v, (int, float))]
    if len(valores) > 0 and len(invalidos) / len(valores) > pol.max_nan_frac:
        raise DeteccionInvalida(
            f"{len(invalidos)} datos inválidos superan la fracción "
            f"tolerada por la política {pol.version} (6.23): se genera "
            "evento de auditoría y se rechaza la detección")
    limpios = [(i, v) for i, v in enumerate(valores)
               if isinstance(v, (int, float)) and v is not None]
    if len(limpios) < pol.min_puntos:
        raise DeteccionInvalida(
            f"serie insuficiente ({len(limpios)} < {pol.min_puntos} "
            f"puntos, política {pol.version})")
    xs = [v for _, v in limpios]
    med = statistics.median(xs)
    mad = statistics.median([abs(x - med) for x in xs])
    anomalias: list[Anomalia] = []
    if mad > 0.0:
        escala = 1.4826 * mad
        for i, v in limpios:
            d = abs(v - med) / escala
            if d > pol.umbral_mad:
                anomalias.append(Anomalia(indice=i, timestamp=ts[i],
                                          valor=float(v),
                                          desviacion_mad=round(d, 3)))
    # 6.23: toda detección genera evento de auditoría
    auditoria = {"fecha": _ahora(), "series": series, "batch_id": batch_id,
                 "politica": pol.version, "n_anomalias": len(anomalias),
                 "datos_invalidos": len(invalidos),
                 "nota": "el detector reporta; nunca actúa sobre el proceso"}
    return ResultadoDeteccion(
        series=series, politica=pol.version, n_puntos=len(limpios),
        mediana=round(med, 6), mad=round(mad, 6), anomalias=anomalias,
        datos_invalidos=len(invalidos), auditoria=auditoria)


def resultado_a_dict(r: ResultadoDeteccion) -> dict:
    d = asdict(r)
    return d
