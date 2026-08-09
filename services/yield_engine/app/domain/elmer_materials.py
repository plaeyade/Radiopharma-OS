"""
Material Library del Elmer FEM Interface (EDS 18.8): propiedades
termo-mecánicas con versión y trazabilidad. 18.14: una simulación cuyo
material no tenga TODAS las propiedades requeridas se rechaza.

Propiedades requeridas para análisis termo-mecánico acoplado (18.13):
  térmicas: conductividad, calor específico, densidad;
  mecánicas: módulo de Young, coeficiente de expansión térmica, Poisson.

Nota honesta de alcance: las propiedades son valores bibliográficos
genéricos de aleaciones habituales en ventanas/soportes de blanco
(Havar, acero 316L). Cada instalación deberá sustituirlas por las
certificadas de su material (18.8: versión y trazabilidad).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MaterialProps:
    material_id: str
    version: str                       # trazabilidad de la biblioteca (18.8)
    densidad_kg_m3: float
    calor_especifico_j_kg_k: float
    conductividad_w_m_k: float
    young_pa: float
    poisson: float
    expansion_termica_1_k: float
    referencia: str                    # fuente bibliográfica (trazabilidad)

    def completo_termomecanico(self) -> bool:
        """18.14: todas las propiedades requeridas definidas y físicas."""
        return all([
            self.densidad_kg_m3 > 0.0,
            self.calor_especifico_j_kg_k > 0.0,
            self.conductividad_w_m_k > 0.0,
            self.young_pa > 0.0,
            0.0 < self.poisson < 0.5,
            self.expansion_termica_1_k > 0.0,
        ])


_BIBLIOTECA: dict[str, MaterialProps] = {
    "havar_foil": MaterialProps(
        material_id="havar_foil", version="1.0.0",
        densidad_kg_m3=8300.0, calor_especifico_j_kg_k=420.0,
        conductividad_w_m_k=13.0, young_pa=2.0e11, poisson=0.30,
        expansion_termica_1_k=1.2e-5,
        referencia="valores típicos aleación Havar (Co-Cr-Ni-W), bibliografía genérica"),
    "acero_316l": MaterialProps(
        material_id="acero_316l", version="1.0.0",
        densidad_kg_m3=7980.0, calor_especifico_j_kg_k=500.0,
        conductividad_w_m_k=15.0, young_pa=1.93e11, poisson=0.29,
        expansion_termica_1_k=1.65e-5,
        referencia="valores típicos AISI 316L, bibliografía genérica"),
}


def get_material(material_id: str) -> MaterialProps:
    """18.14: material desconocido o incompleto → simulación rechazada."""
    try:
        m = _BIBLIOTECA[material_id]
    except KeyError:
        raise ValueError(
            f"Material no registrado en la Material Library (18.8): "
            f"{material_id}. Disponibles: {sorted(_BIBLIOTECA)}")
    if not m.completo_termomecanico():
        raise ValueError(
            f"Material {material_id} incompleto (18.14): faltan propiedades "
            "termo-mecánicas requeridas; simulación rechazada")
    return m


def list_materials() -> list[MaterialProps]:
    return list(_BIBLIOTECA.values())
