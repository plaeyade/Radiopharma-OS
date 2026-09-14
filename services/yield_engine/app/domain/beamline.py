"""Beamline y puesto de blanco (EDS 5.9: beamline, target_position).

Cadena canónica: ciclotrón → beamline → puesto de blanco → blanco.
La transmisión del haz por la línea (pérdidas en colimadores, ventanas
intermedias, imanes) NO se calcula con óptica de haces — no hay motor de
transporte en esta plataforma y nunca se simula uno: solo se registran
transmisiones con **fuente citada** (medición o ficha del proveedor).
Sin transmisión registrada, el factor se declara 1.0 con nota honesta
`sin_dato` — jamás una pérdida inventada.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


class BeamlineInvalido(ValueError):
    """Beamline o puesto de blanco inválido."""


@dataclass(frozen=True)
class Beamline:
    beamline_id: str
    ciclotron_id: str
    nombre: str
    transmision: float              # 0 < T ≤ 1 — solo con fuente citada
    fuente_transmision: str
    version: int
    motivo_version: str
    registrado_por: str
    registrado_en: str


@dataclass(frozen=True)
class PuestoBlanco:
    puesto_id: str
    beamline_id: str
    blanco_id: str
    posicion: str                   # p. ej. "puesto 2 — 90°"
    estado: str                     # activo | en_mantenimiento | inactivo
    registrado_en: str


class BeamlineRegistry:
    """Registro versionado de beamlines — nunca sobrescribe."""

    ESTADOS_PUESTO = ("activo", "en_mantenimiento", "inactivo")

    def __init__(self) -> None:
        self._por_nombre: dict[str, list[Beamline]] = {}
        self._por_id: dict[str, str] = {}       # beamline_id → clave
        self._puestos: list[PuestoBlanco] = []
        self._seq = 0

    def registrar(self, ciclotron_id: str, nombre: str, transmision: float,
                  fuente_transmision: str, registrado_por: str,
                  motivo_version: str = "registro inicial") -> Beamline:
        if not ciclotron_id.strip() or not nombre.strip():
            raise BeamlineInvalido("ciclotron_id y nombre obligatorios")
        if not (0.0 < transmision <= 1.0):
            raise BeamlineInvalido(
                f"transmisión {transmision} fuera de (0, 1]")
        if not fuente_transmision.strip():
            raise BeamlineInvalido(
                "fuente de la transmisión obligatoria: sin motor de "
                "óptica de haces, una pérdida solo se registra con "
                "medición o ficha citada — nunca se inventa (49.11)")
        clave = f"{ciclotron_id.strip().lower()}::{nombre.strip().lower()}"
        versiones = self._por_nombre.setdefault(clave, [])
        version = len(versiones) + 1
        if version > 1 and not motivo_version.strip():
            raise BeamlineInvalido(
                "una nueva versión exige motivo — nunca se sobrescribe")
        if clave not in self._por_id:
            self._seq += 1
            self._por_id[clave] = f"BL-{self._seq:04d}"
        b = Beamline(
            beamline_id=self._por_id[clave],
            ciclotron_id=ciclotron_id, nombre=nombre.strip(),
            transmision=float(transmision),
            fuente_transmision=fuente_transmision.strip(), version=version,
            motivo_version=motivo_version.strip(),
            registrado_por=registrado_por.strip() or "desconocido",
            registrado_en=datetime.now(timezone.utc).isoformat())
        versiones.append(b)
        return b

    def obtener(self, beamline_id: str) -> Beamline:
        for versiones in self._por_nombre.values():
            if versiones and versiones[0].beamline_id == beamline_id:
                return versiones[-1]
        raise BeamlineInvalido(f"beamline desconocida: {beamline_id}")

    def listar(self, ciclotron_id: str | None = None) -> list[Beamline]:
        todas = [v[-1] for v in self._por_nombre.values()]
        if ciclotron_id is None:
            return todas
        return [b for b in todas if b.ciclotron_id == ciclotron_id]

    def registrar_puesto(self, beamline_id: str, blanco_id: str,
                         posicion: str, estado: str = "activo") -> PuestoBlanco:
        self.obtener(beamline_id)
        if estado not in self.ESTADOS_PUESTO:
            raise BeamlineInvalido(
                f"estado inválido; válidos: {list(self.ESTADOS_PUESTO)}")
        p = PuestoBlanco(
            puesto_id=f"TP-{len(self._puestos) + 1:04d}",
            beamline_id=beamline_id, blanco_id=blanco_id,
            posicion=posicion.strip(), estado=estado,
            registrado_en=datetime.now(timezone.utc).isoformat())
        self._puestos.append(p)
        return p

    def puestos(self, beamline_id: str | None = None) -> list[PuestoBlanco]:
        if beamline_id is None:
            return list(self._puestos)
        return [p for p in self._puestos if p.beamline_id == beamline_id]
