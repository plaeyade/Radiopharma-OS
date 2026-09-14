"""Proveedor de poder de frenado con promociones externas (EDS 19.10).

Envuelve al proveedor base (ATIMA empaquetado) y consulta, material a
material, si existe una tabla externa CALIBRADA y PROMOVIDA por el
usuario (con motivo registrado, append-only). Si la hay, el cómputo usa
esa tabla real dentro de su rango validado; si no, el proveedor base.

Honestidad: la fuente efectiva se declara en ``source_label`` y en
``estado()``; fuera del rango de la tabla promovida nunca se extrapola —
el almacén lanza error declarado (49.11).
"""
from __future__ import annotations

from app.infrastructure.stopping.external_tables import ExternalStoppingTables


class PromotedStoppingPower:
    """Proveedor activo = base, salvo materiales con tabla promovida."""

    def __init__(self, base, tablas: ExternalStoppingTables,
                 mapa_clave_a_externo: dict[str, str]) -> None:
        self._base = base
        self._tablas = tablas
        self._mapa = dict(mapa_clave_a_externo)

    def _externo_promovido(self, material_key: str):
        material = self._mapa.get(material_key)
        if material is None:
            return None
        return self._tablas.activa(material)

    def stopping_power(self, material_key: str, energy_mev: float) -> float:
        entrada = self._externo_promovido(material_key)
        if entrada is not None:
            return float(self._tablas.interpolar(
                entrada["material"], energy_mev))
        return float(self._base.stopping_power(material_key, energy_mev))

    def range_g_cm2(self, material_key: str, energy_mev: float) -> float:
        entrada = self._externo_promovido(material_key)
        if entrada is not None:
            return float(self._tablas.alcance_g_cm2(
                entrada["material"], energy_mev))
        return float(self._base.range_g_cm2(material_key, energy_mev))

    def source_label(self) -> str:
        vigentes = [self._tablas.activa(m) for m in self._mapa.values()]
        vigentes = [e for e in vigentes if e is not None]
        base_label = self._base.source_label()
        if not vigentes:
            return base_label
        detalle = "; ".join(
            f"{e['material']} v{e['version']} ({e['fuente']})"
            for e in vigentes)
        return f"{base_label} + tablas externas promovidas: {detalle}"

    def estado(self) -> dict:
        """Estado declarativo por material (para /providers)."""
        man = {m: self._tablas.activa(m) for m in self._mapa.values()}
        por_clave = {}
        for clave, material in self._mapa.items():
            entrada = man.get(material)
            if entrada is None:
                por_clave[clave] = {
                    "proveedor": "base",
                    "fuente": self._base.source_label(),
                }
            else:
                por_clave[clave] = {
                    "proveedor": "externa_promovida",
                    "material_externo": material,
                    "version": entrada["version"],
                    "fuente": entrada["fuente"],
                    "sha256": entrada["sha256"],
                    "estado_tabla": entrada["estado"],
                }
        return {"proveedor_base": self._base.source_label(),
                "materiales": por_clave,
                "promociones": self._tablas.promociones()}
