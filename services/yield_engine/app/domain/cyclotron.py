"""Dominio del ciclotrón (Informe §1558; EDS 5.9).

Entidades canónicas:

- **Ciclotrón**: fabricante, modelo, energía máxima, corriente máxima,
  estado operativo. Toda especificación de proveedor exige ``fuente``
  citada — una capacidad jamás se inventa; si no es demostrable, el
  ciclotrón no se registra (49.11).
- **Registro versionado**: un (fabricante, modelo) ya registrado NO se
  sobrescribe — una nueva especificación crea una versión nueva con
  motivo obligatorio (trazabilidad ALCOA+).
- **Irradiación**: lote append-only con parámetros de haz (energía,
  corriente, tiempo) validados contra los límites de la máquina —
  la física nunca acepta una corrida que la máquina no puede dar.
- **Stopping power / SRIM (19.10)**: se reporta el proveedor real
  configurado (ATIMA/CATIMA); SRIM propietario se declara honestamente
  ``no_configurado``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


class CiclotronInvalido(ValueError):
    """Especificación o irradiación inválida (límite de máquina, fuente…)."""


ESTADOS_OPERATIVOS = ("operativo", "mantenimiento", "fuera_de_servicio",
                      "proyectado")


@dataclass(frozen=True)
class Ciclotron:
    ciclotron_id: str
    fabricante: str
    modelo: str
    energia_max_mev: float
    corriente_max_ua: float
    estado_operativo: str
    fuente: str                      # referencia citada de las specs
    version: int
    motivo_version: str
    registrado_por: str
    registrado_en: str


@dataclass(frozen=True)
class Irradiacion:
    irradiacion_id: str
    ciclotron_id: str
    ciclotron_version: int
    energia_mev: float
    corriente_ua: float
    tiempo_min: float
    reaccion_id: str
    blanco_id: str
    registrada_en: str


class CiclotronRegistry:
    """Registro versionado de ciclotrones — nunca sobrescribe."""

    def __init__(self) -> None:
        self._por_id: dict[str, list[Ciclotron]] = {}
        self._irradiaciones: list[Irradiacion] = []
        self._seq = 0

    # ------------------------------------------------------------------
    def registrar(self, fabricante: str, modelo: str,
                  energia_max_mev: float, corriente_max_ua: float,
                  estado_operativo: str, fuente: str,
                  registrado_por: str,
                  motivo_version: str = "registro inicial") -> Ciclotron:
        if not fabricante.strip() or not modelo.strip():
            raise CiclotronInvalido("fabricante y modelo son obligatorios")
        if energia_max_mev <= 0 or corriente_max_ua <= 0:
            raise CiclotronInvalido(
                "energía y corriente máximas deben ser positivas")
        if estado_operativo not in ESTADOS_OPERATIVOS:
            raise CiclotronInvalido(
                f"estado inválido; válidos: {list(ESTADOS_OPERATIVOS)}")
        if not fuente.strip():
            raise CiclotronInvalido(
                "fuente obligatoria: las especificaciones del proveedor "
                "exigen referencia citada — nunca se inventan (49.11)")
        base = f"{fabricante.strip().lower()}::{modelo.strip().lower()}"
        if base not in self._por_id:
            self._seq += 1
            self._por_id[base] = []
        versiones = self._por_id[base]
        version = len(versiones) + 1
        if version > 1 and not motivo_version.strip():
            raise CiclotronInvalido(
                "una nueva versión exige motivo — el registro nunca "
                "sobrescribe (ALCOA+)")
        c = Ciclotron(
            ciclotron_id=f"CYC-{self._seq:04d}",
            fabricante=fabricante.strip(), modelo=modelo.strip(),
            energia_max_mev=float(energia_max_mev),
            corriente_max_ua=float(corriente_max_ua),
            estado_operativo=estado_operativo, fuente=fuente.strip(),
            version=version, motivo_version=motivo_version.strip(),
            registrado_por=registrado_por.strip() or "desconocido",
            registrado_en=datetime.now(timezone.utc).isoformat())
        versiones.append(c)
        return c

    # ------------------------------------------------------------------
    def obtener(self, ciclotron_id: str,
                version: Optional[int] = None) -> Ciclotron:
        for versiones in self._por_id.values():
            if versiones and versiones[0].ciclotron_id == ciclotron_id:
                if version is None:
                    return versiones[-1]          # vigente = última
                for c in versiones:
                    if c.version == version:
                        return c
                raise CiclotronInvalido(
                    f"versión {version} inexistente para {ciclotron_id}")
        raise CiclotronInvalido(f"ciclotrón desconocido: {ciclotron_id}")

    def listar(self) -> list[Ciclotron]:
        return [v[-1] for v in self._por_id.values()]

    def versiones(self, ciclotron_id: str) -> list[Ciclotron]:
        self.obtener(ciclotron_id)
        for versiones in self._por_id.values():
            if versiones and versiones[0].ciclotron_id == ciclotron_id:
                return list(versiones)
        return []  # unreachable

    # ------------------------------------------------------------------
    def registrar_irradiacion(self, ciclotron_id: str, energia_mev: float,
                              corriente_ua: float, tiempo_min: float,
                              reaccion_id: str, blanco_id: str) -> Irradiacion:
        """Lote append-only validado contra los límites REALES declarados."""
        c = self.obtener(ciclotron_id)
        if c.estado_operativo == "fuera_de_servicio":
            raise CiclotronInvalido(
                f"{ciclotron_id} está fuera_de_servicio: no puede irradiar")
        if energia_mev <= 0 or energia_mev > c.energia_max_mev:
            raise CiclotronInvalido(
                f"energía {energia_mev} MeV fuera de rango: la máquina "
                f"{c.fabricante} {c.modelo} llega a {c.energia_max_mev} MeV")
        if corriente_ua <= 0 or corriente_ua > c.corriente_max_ua:
            raise CiclotronInvalido(
                f"corriente {corriente_ua} µA fuera de rango: la máquina "
                f"{c.fabricante} {c.modelo} llega a {c.corriente_max_ua} µA")
        if tiempo_min <= 0:
            raise CiclotronInvalido("tiempo de irradiación debe ser positivo")
        irr = Irradiacion(
            irradiacion_id=f"IRR-{len(self._irradiaciones) + 1:05d}",
            ciclotron_id=ciclotron_id, ciclotron_version=c.version,
            energia_mev=float(energia_mev), corriente_ua=float(corriente_ua),
            tiempo_min=float(tiempo_min), reaccion_id=reaccion_id,
            blanco_id=blanco_id,
            registrada_en=datetime.now(timezone.utc).isoformat())
        self._irradiaciones.append(irr)
        return irr

    def irradiaciones(self, ciclotron_id: str | None = None) -> list[Irradiacion]:
        if ciclotron_id is None:
            return list(self._irradiaciones)
        return [i for i in self._irradiaciones
                if i.ciclotron_id == ciclotron_id]
