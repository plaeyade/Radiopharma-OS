"""Configuración de enfriamiento del blanco (EDS 5.10 cooling_configuration).

El coeficiente de película h y la geometría de enfriamiento condicionan el
FEM térmico: un h inventado produce una temperatura inventada. Por eso
toda configuración exige **fuente citada** — literatura científica
especializada o ficha técnica real del proveedor, aportada con su
referencia completa (49.11). Registro versionado que nunca sobrescribe:
cada cambio crea versión con motivo obligatorio (ALCOA+).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


class CoolingInvalido(ValueError):
    """Configuración de enfriamiento inválida (sin fuente, h no física…)."""


@dataclass(frozen=True)
class CoolingConfig:
    config_id: str
    blanco_id: str
    h_w_cm2_k: float                # coeficiente de película
    geometria: str                  # descripción de la geometría de enfriamiento
    fuente: str                     # literatura / ficha técnica citada
    version: int
    motivo_version: str
    registrado_por: str
    registrado_en: str


class CoolingRegistry:
    """Registro versionado por blanco — nunca sobrescribe."""

    def __init__(self) -> None:
        self._por_blanco: dict[str, list[CoolingConfig]] = {}
        self._seq = 0

    def registrar(self, blanco_id: str, h_w_cm2_k: float, geometria: str,
                  fuente: str, registrado_por: str,
                  motivo_version: str = "registro inicial") -> CoolingConfig:
        if not blanco_id.strip():
            raise CoolingInvalido("blanco_id obligatorio")
        if not (1e-4 < h_w_cm2_k < 100.0):
            raise CoolingInvalido(
                f"h={h_w_cm2_k} W/cm²·K fuera del rango físico de "
                f"enfriamiento convectivo de blancos (1e-4, 100)")
        if not geometria.strip():
            raise CoolingInvalido(
                "geometría de enfriamiento obligatoria (descripción)")
        if not fuente.strip():
            raise CoolingInvalido(
                "fuente obligatoria: h y geometría solo se registran con "
                "literatura citada o ficha técnica del proveedor — nunca "
                "se inventan (49.11)")
        versiones = self._por_blanco.setdefault(blanco_id, [])
        version = len(versiones) + 1
        if version > 1 and not motivo_version.strip():
            raise CoolingInvalido(
                "una nueva versión exige motivo — el registro nunca "
                "sobrescribe (ALCOA+)")
        self._seq += 1
        c = CoolingConfig(
            config_id=f"COOL-{self._seq:04d}", blanco_id=blanco_id,
            h_w_cm2_k=float(h_w_cm2_k), geometria=geometria.strip(),
            fuente=fuente.strip(), version=version,
            motivo_version=motivo_version.strip(),
            registrado_por=registrado_por.strip() or "desconocido",
            registrado_en=datetime.now(timezone.utc).isoformat())
        versiones.append(c)
        return c

    def vigente(self, blanco_id: str) -> CoolingConfig:
        versiones = self._por_blanco.get(blanco_id)
        if not versiones:
            raise CoolingInvalido(
                f"sin configuración de enfriamiento registrada para "
                f"'{blanco_id}' — no_demostrable (registrar con fuente)")
        return versiones[-1]

    def version(self, blanco_id: str, version: int) -> CoolingConfig:
        versiones = self._por_blanco.get(blanco_id, [])
        for c in versiones:
            if c.version == version:
                return c
        raise CoolingInvalido(
            f"versión {version} inexistente para '{blanco_id}'")

    def versiones(self, blanco_id: str) -> list[CoolingConfig]:
        return list(self._por_blanco.get(blanco_id, []))
