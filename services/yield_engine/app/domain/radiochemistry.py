"""Modelado radioquímico (Informe 19.14).

Cadena post-EOB de cada producto: módulo de síntesis, eficiencia química,
pérdidas, purificación, formulación → actividad estimada al EOS
(End Of Synthesis).

    A_EOS = A_EOB · Π(eficiencias) · exp(−λ · t_total)

La constante de decaimiento λ es REAL (biblioteca nuclear del servicio).
Cada etapa exige **fuente citada** para su eficiencia (literatura, SOP
validado o ficha del módulo) — una eficiencia inventada produce una
actividad inventada (49.11). Proceso versionado: nunca se sobrescribe;
cada cambio crea versión con motivo (ALCOA+). La estimación es teórica
declarada — nunca un valor medido de producción.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone


class ProcesoInvalido(ValueError):
    """Etapa o proceso radioquímico inválido."""


ETAPAS_VALIDAS = ("sintesis", "transferencia", "purificacion", "formulacion")


@dataclass(frozen=True)
class EtapaRadioquimica:
    tipo: str                       # ETAPAS_VALIDAS
    nombre: str
    eficiencia: float               # (0, 1]
    duracion_min: float             # ≥ 0
    fuente: str                     # eficiencia solo con referencia citada


@dataclass(frozen=True)
class ProcesoRadioquimico:
    proceso_id: str
    producto: str                   # p. ej. "FDG", "NaF-F18"
    nucleido: str                   # p. ej. "F-18" (biblioteca nuclear)
    etapas: tuple[EtapaRadioquimica, ...]
    version: int
    motivo_version: str
    registrado_por: str
    registrado_en: str


class ProcesoRadioquimicoRegistry:
    """Registro versionado por producto — nunca sobrescribe."""

    def __init__(self) -> None:
        self._por_producto: dict[str, list[ProcesoRadioquimico]] = {}
        self._seq = 0

    def registrar(self, producto: str, nucleido: str,
                  etapas: list[EtapaRadioquimica], registrado_por: str,
                  motivo_version: str = "registro inicial") -> ProcesoRadioquimico:
        if not producto.strip() or not nucleido.strip():
            raise ProcesoInvalido("producto y nucleido obligatorios")
        if not etapas:
            raise ProcesoInvalido("el proceso exige al menos una etapa")
        for e in etapas:
            if e.tipo not in ETAPAS_VALIDAS:
                raise ProcesoInvalido(
                    f"etapa inválida '{e.tipo}'; válidas: {list(ETAPAS_VALIDAS)}")
            if not (0.0 < e.eficiencia <= 1.0):
                raise ProcesoInvalido(
                    f"eficiencia de '{e.nombre}' fuera de (0, 1]")
            if e.duracion_min < 0:
                raise ProcesoInvalido(
                    f"duración de '{e.nombre}' no puede ser negativa")
            if not e.fuente.strip():
                raise ProcesoInvalido(
                    f"etapa '{e.nombre}' sin fuente: la eficiencia solo se "
                    f"registra con literatura/SOP/ficha citada — nunca se "
                    f"inventa (49.11)")
        clave = producto.strip().lower()
        versiones = self._por_producto.setdefault(clave, [])
        version = len(versiones) + 1
        if version > 1 and not motivo_version.strip():
            raise ProcesoInvalido(
                "una nueva versión exige motivo — nunca se sobrescribe")
        self._seq += 1
        p = ProcesoRadioquimico(
            proceso_id=f"RQ-{self._seq:04d}", producto=producto.strip(),
            nucleido=nucleido.strip(), etapas=tuple(etapas), version=version,
            motivo_version=motivo_version.strip(),
            registrado_por=registrado_por.strip() or "desconocido",
            registrado_en=datetime.now(timezone.utc).isoformat())
        versiones.append(p)
        return p

    def obtener(self, proceso_id: str,
                version: int | None = None) -> ProcesoRadioquimico:
        for versiones in self._por_producto.values():
            if versiones and versiones[0].proceso_id == proceso_id:
                if version is None:
                    return versiones[-1]
                for p in versiones:
                    if p.version == version:
                        return p
                raise ProcesoInvalido(
                    f"versión {version} inexistente para {proceso_id}")
        raise ProcesoInvalido(f"proceso desconocido: {proceso_id}")

    def listar(self) -> list[ProcesoRadioquimico]:
        return [v[-1] for v in self._por_producto.values()]

    def versiones(self, proceso_id: str) -> list[ProcesoRadioquimico]:
        self.obtener(proceso_id)
        for versiones in self._por_producto.values():
            if versiones and versiones[0].proceso_id == proceso_id:
                return list(versiones)
        return []  # unreachable


def actividad_eos(proceso: ProcesoRadioquimico, eob_gbq: float,
                  lambda_s: float) -> dict:
    """A_EOS = A_EOB · Π(eficiencias) · exp(−λ·t_total) — modelo real.

    ``lambda_s`` debe venir de la biblioteca nuclear (constante de
    decaimiento real del nucleido), nunca de un valor tecleado.
    """
    if eob_gbq < 0:
        raise ProcesoInvalido("actividad EOB no puede ser negativa")
    eficiencia_total = 1.0
    t_total_min = 0.0
    for e in proceso.etapas:
        eficiencia_total *= e.eficiencia
        t_total_min += e.duracion_min
    factor_decaimiento = math.exp(-lambda_s * t_total_min * 60.0)
    return {
        "proceso_id": proceso.proceso_id, "version": proceso.version,
        "producto": proceso.producto, "nucleido": proceso.nucleido,
        "eob_gbq": round(eob_gbq, 3),
        "eficiencia_total": round(eficiencia_total, 5),
        "tiempo_proceso_min": round(t_total_min, 2),
        "factor_decaimiento": round(factor_decaimiento, 5),
        "eos_gbq": round(eob_gbq * eficiencia_total * factor_decaimiento, 3),
        "nota_honestidad": (
            "estimación teórica 19.14 con λ de la biblioteca nuclear y "
            "eficiencias registradas con fuente citada — nunca un valor "
            "medido de producción"),
    }
