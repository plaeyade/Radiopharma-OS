"""Gestión de inventarios (Informe 18.9, Fase 5; cap. 28.8/28.10).

Inventario dual de la planta radiofarmacéutica:
  - **lotes radiactivos**: su magnitud es la actividad, que decae con
    la vida media del radionúclido — el stock a tiempo t se calcula
    con la ley de decaimiento (nunca se almacena un valor fijo sin
    referencia temporal);
  - **consumibles/reactivos**: cantidad y caducidad (22.7).

Todo movimiento (entrada, salida, consumo, ajuste) queda auditado
con operador y motivo (28.24). Los reactivos caducados no pueden
consumirse. El inventario alimenta los indicadores y el Economic
Digital Twin (28.18).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone

TIPOS_MOVIMIENTO = ("entrada", "salida", "consumo", "ajuste")


class InventarioInvalido(ValueError):
    """Movimiento o ítem que viola las reglas de inventario."""


@dataclass
class LoteRadiactivo:
    lote_id: str
    radiopharmaceutical: str
    nuclide: str
    half_life_min: float
    actividad_gbq: float
    referencia_temporal: str  # ISO: instante al que refiere la actividad
    volumen_ml: float = 0.0
    estado: str = "disponible"  # disponible/reservado/consumido/desechado

    def actividad_a(self, instante: datetime) -> float:
        """Actividad decayada al instante dado (ley de decaimiento)."""
        t0 = datetime.fromisoformat(self.referencia_temporal)
        dt_min = (instante - t0).total_seconds() / 60.0
        lam = math.log(2.0) / self.half_life_min
        return self.actividad_gbq * math.exp(-lam * dt_min)


@dataclass
class Consumible:
    item_id: str
    nombre: str
    cantidad: float
    unidad: str
    lote: str = ""
    caducidad: str | None = None  # ISO date (22.7)


@dataclass
class Movimiento:
    tipo: str
    item_id: str
    cantidad: float
    operador: str
    motivo: str
    fecha: str


class InventoryService:
    """Inventario operativo con decaimiento y auditoría (28.24)."""

    def __init__(self) -> None:
        self._lotes: dict[str, LoteRadiactivo] = {}
        self._consumibles: dict[str, Consumible] = {}
        self._movimientos: list[Movimiento] = []

    # ------------------------------------------------------------ lotes
    def registrar_lote(self, lote: LoteRadiactivo, operador: str,
                       motivo: str) -> dict:
        if lote.lote_id in self._lotes:
            raise InventarioInvalido(
                f"el lote {lote.lote_id} ya existe: nunca se sobrescribe")
        if lote.actividad_gbq <= 0 or lote.half_life_min <= 0:
            raise InventarioInvalido("actividad y vida media deben ser > 0")
        datetime.fromisoformat(lote.referencia_temporal)  # valida ISO
        self._lotes[lote.lote_id] = lote
        self._registrar("entrada", lote.lote_id, lote.actividad_gbq,
                        operador, motivo)
        return asdict(lote)

    def cambiar_estado_lote(self, lote_id: str, estado: str, operador: str,
                            motivo: str) -> dict:
        lote = self._lote(lote_id)
        if estado not in ("disponible", "reservado", "consumido", "desechado"):
            raise InventarioInvalido(f"estado inválido: {estado}")
        lote.estado = estado
        self._registrar("salida" if estado in ("consumido", "desechado")
                        else "ajuste", lote_id, 0.0, operador, motivo)
        return asdict(lote)

    def stock_lote(self, lote_id: str, instante: datetime | None = None) -> dict:
        lote = self._lote(lote_id)
        t = instante or datetime.now(timezone.utc)
        return {"lote_id": lote.lote_id,
                "radiopharmaceutical": lote.radiopharmaceutical,
                "estado": lote.estado,
                "actividad_gbq_a": t.isoformat(),
                "actividad_gbq": round(lote.actividad_a(t), 6),
                "nota": "actividad calculada por decaimiento desde la "
                        "referencia temporal (nunca valor fijo)"}

    # ------------------------------------------------------- consumibles
    def registrar_consumible(self, item: Consumible, operador: str,
                             motivo: str) -> dict:
        if item.item_id in self._consumibles:
            raise InventarioInvalido(
                f"el consumible {item.item_id} ya existe")
        if item.cantidad < 0:
            raise InventarioInvalido("cantidad negativa")
        self._consumibles[item.item_id] = item
        self._registrar("entrada", item.item_id, item.cantidad, operador,
                        motivo)
        return asdict(item)

    def consumir(self, item_id: str, cantidad: float, operador: str,
                 motivo: str, fecha_lote: date | None = None) -> dict:
        item = self._consumible(item_id)
        if cantidad <= 0 or cantidad > item.cantidad:
            raise InventarioInvalido(
                f"cantidad inválida: {cantidad} (stock {item.cantidad})")
        if item.caducidad:
            if (fecha_lote or date.today()) > date.fromisoformat(item.caducidad):
                raise InventarioInvalido(
                    f"reactivo caducado ({item.caducidad}): no puede "
                    "consumirse (22.7)")
        item.cantidad -= cantidad
        self._registrar("consumo", item_id, cantidad, operador, motivo)
        return asdict(item)

    # ------------------------------------------------------------ consulta
    def listar_lotes(self) -> list[dict]:
        return [asdict(l) for l in self._lotes.values()]

    def listar_consumibles(self) -> list[dict]:
        return [asdict(c) for c in self._consumibles.values()]

    def movimientos(self) -> list[dict]:
        return [asdict(m) for m in self._movimientos]

    # ------------------------------------------------------------ internos
    def _lote(self, lote_id: str) -> LoteRadiactivo:
        try:
            return self._lotes[lote_id]
        except KeyError:
            raise InventarioInvalido(f"lote no encontrado: {lote_id}")

    def _consumible(self, item_id: str) -> Consumible:
        try:
            return self._consumibles[item_id]
        except KeyError:
            raise InventarioInvalido(f"consumible no encontrado: {item_id}")

    def _registrar(self, tipo: str, item_id: str, cantidad: float,
                   operador: str, motivo: str) -> None:
        if tipo not in TIPOS_MOVIMIENTO:
            raise InventarioInvalido(f"tipo de movimiento inválido: {tipo}")
        self._movimientos.append(Movimiento(
            tipo=tipo, item_id=item_id, cantidad=cantidad, operador=operador,
            motivo=motivo,
            fecha=datetime.now(timezone.utc).isoformat()))
