"""Perfil de irradiación como entidad versionada (EDS 5.9:
beam_parameters, current_profile, energy_profile).

El conjunto COMPLETO de parámetros de una corrida (energía, corriente,
tiempo, blanco, reacción, ventana PSTAR, perfil de haz) es una entidad de
dominio versionada — nunca un puñado de argumentos sueltos. Un perfil
registrado NO se sobrescribe: cualquier cambio crea versión con motivo
obligatorio, y toda versión queda disponible para reproducir corridas
históricas (ALCOA+, 58.10).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


class PerfilInvalido(ValueError):
    """Perfil de irradiación inválido."""


@dataclass(frozen=True)
class VentanaPerfil:
    material: str                   # clave PSTAR versionada
    espesor_g_cm2: float
    descripcion: str = ""           # supuesto declarado (p. ej. Havar≈Fe)


@dataclass(frozen=True)
class PerfilHaz:
    """Perfil espacial del haz sobre el blanco (supuesto declarado)."""
    forma: str = "gaussiano"        # gaussiano | uniforme | raster
    sigma_cm: float | None = 0.5
    notas: str = ""


@dataclass(frozen=True)
class PerfilIrradiacion:
    perfil_id: str
    nombre: str
    reaccion_id: str
    blanco_id: str
    energia_mev: float
    corriente_ua: float
    tiempo_min: float
    ventana: VentanaPerfil | None
    haz: PerfilHaz
    version: int
    motivo_version: str
    registrado_por: str
    registrado_en: str


class PerfilIrradiacionRegistry:
    """Registro versionado por nombre — nunca sobrescribe."""

    def __init__(self) -> None:
        self._por_nombre: dict[str, list[PerfilIrradiacion]] = {}
        self._seq = 0

    def registrar(self, nombre: str, reaccion_id: str, blanco_id: str,
                  energia_mev: float, corriente_ua: float, tiempo_min: float,
                  ventana: VentanaPerfil | None, haz: PerfilHaz | None,
                  registrado_por: str,
                  motivo_version: str = "registro inicial") -> PerfilIrradiacion:
        if not nombre.strip():
            raise PerfilInvalido("nombre de perfil obligatorio")
        if energia_mev <= 0:
            raise PerfilInvalido("energía debe ser positiva")
        if corriente_ua <= 0:
            raise PerfilInvalido("corriente debe ser positiva")
        if tiempo_min <= 0:
            raise PerfilInvalido("tiempo debe ser positivo")
        if ventana is not None and ventana.espesor_g_cm2 <= 0:
            raise PerfilInvalido("espesor de ventana debe ser positivo")
        clave = nombre.strip().lower()
        versiones = self._por_nombre.setdefault(clave, [])
        version = len(versiones) + 1
        if version > 1 and not motivo_version.strip():
            raise PerfilInvalido(
                "una nueva versión exige motivo — el registro nunca "
                "sobrescribe (ALCOA+)")
        self._seq += 1
        p = PerfilIrradiacion(
            perfil_id=f"PRF-{self._seq:04d}", nombre=nombre.strip(),
            reaccion_id=reaccion_id, blanco_id=blanco_id,
            energia_mev=float(energia_mev), corriente_ua=float(corriente_ua),
            tiempo_min=float(tiempo_min), ventana=ventana,
            haz=haz or PerfilHaz(), version=version,
            motivo_version=motivo_version.strip(),
            registrado_por=registrado_por.strip() or "desconocido",
            registrado_en=datetime.now(timezone.utc).isoformat())
        versiones.append(p)
        return p

    def obtener(self, perfil_id: str,
                version: int | None = None) -> PerfilIrradiacion:
        for versiones in self._por_nombre.values():
            if versiones and versiones[0].perfil_id == perfil_id:
                if version is None:
                    return versiones[-1]
                for p in versiones:
                    if p.version == version:
                        return p
                raise PerfilInvalido(
                    f"versión {version} inexistente para {perfil_id}")
        raise PerfilInvalido(f"perfil desconocido: {perfil_id}")

    def listar(self) -> list[PerfilIrradiacion]:
        return [v[-1] for v in self._por_nombre.values()]

    def versiones(self, perfil_id: str) -> list[PerfilIrradiacion]:
        self.obtener(perfil_id)
        for versiones in self._por_nombre.values():
            if versiones and versiones[0].perfil_id == perfil_id:
                return list(versiones)
        return []  # unreachable
