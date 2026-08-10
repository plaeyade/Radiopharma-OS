"""Normalización de datos SCADA (EDS 31.13).

Las lecturas crudas de los conectores (OPC UA 31.6, MQTT 31.7,
Modbus 31.8) se normalizan a unidades de ingeniería mediante un
mapa versionado de tags: escala, offset, unidad y rango válido.
Los valores fuera de rango generan evento de auditoría y se
rechazan (calidad de datos 6.23) — nunca se corrigen en silencio.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


class NormalizacionInvalida(ValueError):
    """Lectura fuera de rango o tag no registrado (31.13/6.23)."""


@dataclass(frozen=True)
class TagMap:
    """Definición versionada de un tag industrial (31.13)."""
    serie: str
    unidad: str
    escala: float = 1.0
    offset: float = 0.0
    rango_min: float | None = None
    rango_max: float | None = None


def normalizar(valor_crudo: float, tag: TagMap) -> dict:
    """Crudo → unidades de ingeniería con validación de rango."""
    valor = valor_crudo * tag.escala + tag.offset
    fuera = ((tag.rango_min is not None and valor < tag.rango_min)
             or (tag.rango_max is not None and valor > tag.rango_max))
    if fuera:
        raise NormalizacionInvalida(
            f"{tag.serie}: {valor:.4f} {tag.unidad} fuera de rango "
            f"[{tag.rango_min}, {tag.rango_max}] — evento de auditoría "
            "generado (6.23); el valor se rechaza, nunca se corrige "
            "en silencio")
    return {"serie": tag.serie, "valor": round(valor, 6),
            "unidad": tag.unidad,
            "ts": datetime.now(timezone.utc).isoformat(),
            "fuente": "normalización SCADA (31.13)"}
