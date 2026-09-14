"""Línea óptica del haz (EDS 5.9 — transporte).

La línea óptica (secuencia de elementos: drifts, cuadrupolos, dipolos,
colimadores) se registra como entidad versionada vinculada a una
beamline. Los parámetros de cada elemento SOLO con fuente citada
(diseño del proveedor o medición) — nunca se inventan (49.11).

El transporte (transmisión calculada de extremo a extremo y tamaño de
haz en el blanco) lo ejecuta un motor externo real (TraceWin, CEA)
vía adaptador con detección de runtime: sin runtime → 503 honesto,
nunca se simula el transporte. Mientras no haya runtime, la
transmisión vigente sigue siendo la registrada con fuente (Fase 14).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


class LineaOpticaInvalida(ValueError):
    """Línea óptica o elemento inválido."""


ELEMENTOS_VALIDOS = ("drift", "cuadrupolo", "dipolo", "solenoide",
                     "colimador")


@dataclass(frozen=True)
class ElementoOptico:
    tipo: str                       # ELEMENTOS_VALIDOS
    nombre: str
    longitud_m: float               # > 0
    parametros: tuple[tuple[str, float], ...]  # p. ej. (("gradiente_t_m", 8.5),)
    fuente: str                     # diseño del proveedor o medición citada


@dataclass(frozen=True)
class LineaOptica:
    linea_id: str
    beamline_id: str
    elementos: tuple[ElementoOptico, ...]
    version: int
    motivo_version: str
    registrado_por: str
    registrado_en: str


class LineaOpticaRegistry:
    """Registro versionado por beamline — nunca sobrescribe."""

    def __init__(self) -> None:
        self._por_beamline: dict[str, list[LineaOptica]] = {}

    def registrar(self, beamline_id: str, elementos: list[ElementoOptico],
                  registrado_por: str,
                  motivo_version: str = "registro inicial") -> LineaOptica:
        if not beamline_id.strip():
            raise LineaOpticaInvalida("beamline_id obligatorio")
        if not elementos:
            raise LineaOpticaInvalida(
                "la línea óptica exige al menos un elemento")
        for e in elementos:
            if e.tipo not in ELEMENTOS_VALIDOS:
                raise LineaOpticaInvalida(
                    f"elemento inválido '{e.tipo}'; válidos: "
                    f"{list(ELEMENTOS_VALIDOS)}")
            if e.longitud_m <= 0:
                raise LineaOpticaInvalida(
                    f"longitud de '{e.nombre}' debe ser positiva")
            if not e.fuente.strip():
                raise LineaOpticaInvalida(
                    f"elemento '{e.nombre}' sin fuente: sus parámetros solo "
                    f"se registran con diseño del proveedor o medición "
                    f"citada — nunca se inventan (49.11)")
        versiones = self._por_beamline.setdefault(beamline_id, [])
        version = len(versiones) + 1
        if version > 1 and not motivo_version.strip():
            raise LineaOpticaInvalida(
                "una nueva versión exige motivo — nunca se sobrescribe")
        lo = LineaOptica(
            linea_id=f"OPT-{beamline_id}-v{version}",
            beamline_id=beamline_id, elementos=tuple(elementos),
            version=version, motivo_version=motivo_version.strip(),
            registrado_por=registrado_por.strip() or "desconocido",
            registrado_en=datetime.now(timezone.utc).isoformat())
        versiones.append(lo)
        return lo

    def obtener(self, beamline_id: str,
                version: int | None = None) -> LineaOptica:
        versiones = self._por_beamline.get(beamline_id)
        if not versiones:
            raise LineaOpticaInvalida(
                f"sin línea óptica registrada para {beamline_id} — "
                f"no_demostrable")
        if version is None:
            return versiones[-1]
        for lo in versiones:
            if lo.version == version:
                return lo
        raise LineaOpticaInvalida(
            f"versión {version} inexistente para {beamline_id}")
