"""Catálogo de módulos de síntesis por proveedor (Informe 19.14).

Análogo al registro de ciclotrones (Informe §1558): cada módulo se
registra con fabricante, modelo y nucleidos soportados, y su rendimiento
SOLO con fuente citada (ficha técnica real del proveedor o literatura
especializada) — un rendimiento inventado produce una actividad al EOS
inventada (49.11). Registro versionado que nunca sobrescribe; cada
versión exige motivo (ALCOA+).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


class ModuloInvalido(ValueError):
    """Módulo de síntesis inválido."""


@dataclass(frozen=True)
class ModuloSintesis:
    modulo_id: str
    fabricante: str                 # p. ej. IBA, Trasis, GE HealthCare
    modelo: str                     # p. ej. Synthera, AllinOne, FASTlab 2
    nucleidos_soportados: tuple[str, ...]
    fuente: str                     # ficha técnica o literatura citada
    version: int
    motivo_version: str
    registrado_por: str
    registrado_en: str


class ModuloSintesisRegistry:
    """Registro versionado por (fabricante, modelo) — nunca sobrescribe."""

    def __init__(self) -> None:
        self._por_clave: dict[str, list[ModuloSintesis]] = {}
        self._por_id: dict[str, str] = {}
        self._seq = 0

    def registrar(self, fabricante: str, modelo: str,
                  nucleidos_soportados: list[str], fuente: str,
                  registrado_por: str,
                  motivo_version: str = "registro inicial") -> ModuloSintesis:
        if not fabricante.strip() or not modelo.strip():
            raise ModuloInvalido("fabricante y modelo obligatorios")
        if not nucleidos_soportados:
            raise ModuloInvalido("el módulo debe soportar al menos un nucleido")
        if not fuente.strip():
            raise ModuloInvalido(
                "fuente obligatoria: las capacidades del módulo solo se "
                "registran con ficha técnica o literatura citada — nunca "
                "se inventan (49.11)")
        clave = f"{fabricante.strip().lower()}::{modelo.strip().lower()}"
        versiones = self._por_clave.setdefault(clave, [])
        version = len(versiones) + 1
        if version > 1 and not motivo_version.strip():
            raise ModuloInvalido(
                "una nueva versión exige motivo — nunca se sobrescribe")
        if clave not in self._por_id:
            self._seq += 1
            self._por_id[clave] = f"MOD-{self._seq:04d}"
        m = ModuloSintesis(
            modulo_id=self._por_id[clave], fabricante=fabricante.strip(),
            modelo=modelo.strip(),
            nucleidos_soportados=tuple(n.strip() for n in nucleidos_soportados),
            fuente=fuente.strip(), version=version,
            motivo_version=motivo_version.strip(),
            registrado_por=registrado_por.strip() or "desconocido",
            registrado_en=datetime.now(timezone.utc).isoformat())
        versiones.append(m)
        return m

    def obtener(self, modulo_id: str) -> ModuloSintesis:
        for versiones in self._por_clave.values():
            if versiones and versiones[0].modulo_id == modulo_id:
                return versiones[-1]
        raise ModuloInvalido(f"módulo desconocido: {modulo_id}")

    def listar(self) -> list[ModuloSintesis]:
        return [v[-1] for v in self._por_clave.values()]
