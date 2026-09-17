# -*- coding: utf-8 -*-
"""Escritor GDML del blanco seleccionable — Fase 34 (hoja de ruta ①).

Genera la geometría GDML del blanco elegido en `target_selector.py`
(cuerpo, cavidad con contenido, ventana foil Havar, respaldo) para usarla
en Geant4/OpenGATE (G4GDMLParser) o en visualizadores. La geometría es la
misma parametrización citada del catálogo — nunca dimensiones inventadas:
las que no existen con fuente se toman del escenario declarado del
selector y quedan marcadas en el propio GDML (comentario).

Estructura:
  world (aire)
   └─ targetBody (cilindro del material del cuerpo, p.ej. Nb)
       └─ cavity (cilindro con el contenido: H2[18O], gas N2, 64Ni...)
   └─ foilWindow (disco Havar 25 µm declarado, aguas arriba del haz)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent

from app.domain.target_selector import BLANCOS_SELECCIONABLES

# Espesor de ventana foil Havar — escenario declarado (Fase 27, desgaste).
FOIL_HAVAR_UM = 25.0
# Espesor del respaldo del cuerpo — escenario declarado.
RESPALDO_MM = 1.0

# Densidades citadas de cuerpo/ventana (g/cm³, propiedades tabuladas).
_DENSIDADES = {
    "Ag": (10.49, "Ag 10,49 g/cm3 tabulada"),
    "Nb": (8.57, "Nb 8,57 g/cm3 tabulada"),
    "Ta": (16.65, "Ta 16,65 g/cm3 tabulada"),
    "Al": (2.70, "Al 2,70 g/cm3 tabulada"),
    "Ni": (8.90, "Ni 8,90 g/cm3 tabulada"),
    "Havar": (8.30, "Havar ~8,3 g/cm3 ficha Hamilton (declarada)"),
}

# Material del cuerpo por blanco (coherente con la fuente de conductividad).
_CUERPO = {
    "agua18_ag_estandar": "Ag",
    "agua18_nirta_conical_nb": "Nb",
    "agua18_cuerpo_ta": "Ta",
    "agua_natural_n13": "Ag",
    "gas_n2_c11": "Al",
    "solido_ni64_cu64": "Ni",
}


@dataclass(frozen=True)
class GdmlTargetInfo:
    blanco_id: str
    material_cuerpo: str
    radio_mm: float
    espesor_mm: float
    densidad_contenido: float
    marcadores: tuple


def info_gdml(blanco_id: str) -> GdmlTargetInfo:
    """Parámetros GDML del blanco con marcadores de origen (49.11)."""
    if blanco_id not in BLANCOS_SELECCIONABLES:
        raise ValueError(f"blanco desconocido: {blanco_id}")
    b = BLANCOS_SELECCIONABLES[blanco_id]
    marc = [f"densidad: {b['fuente_densidad']}",
            f"foil Havar {FOIL_HAVAR_UM} um: escenario declarado",
            f"respaldo {RESPALDO_MM} mm: escenario declarado"]
    if "nota" in b:
        marc.append(b["nota"])
    return GdmlTargetInfo(
        blanco_id=blanco_id,
        material_cuerpo=_CUERPO[blanco_id],
        radio_mm=b["radio_cm"] * 10.0,
        espesor_mm=b["espesor_cm"] * 10.0,
        densidad_contenido=b["densidad_contenido_g_cm3"],
        marcadores=tuple(marc),
    )


def escribir_gdml(blanco_id: str, salida: str | Path) -> Path:
    """Escribe el GDML del blanco y devuelve la ruta."""
    info = info_gdml(blanco_id)
    den_c, fu_den_c = _DENSIDADES[info.material_cuerpo]
    den_h, _ = _DENSIDADES["Havar"]

    root = Element("gdml", {
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xsi:noNamespaceSchemaLocation":
            "http://service-spi.web.cern.ch/service-spi/app/releases/GDML/schema/gdml.xsd"})

    define = SubElement(root, "define")
    SubElement(define, "constant", {"name": "R_TGT", "value": f"{info.radio_mm}"})
    SubElement(define, "constant", {"name": "L_TGT", "value": f"{info.espesor_mm}"})
    SubElement(define, "constant", {"name": "FOIL", "value": f"{FOIL_HAVAR_UM/1000.0}"})
    SubElement(define, "constant", {"name": "WALL", "value": f"{RESPALDO_MM}"})

    mats = SubElement(root, "materials")
    mc = SubElement(mats, "material", {"name": f"Contenido_{info.blanco_id}"})
    SubElement(mc, "D", {"value": f"{info.densidad_contenido}", "unit": "g/cm3"})
    m = SubElement(mats, "material", {"name": f"Cuerpo_{info.material_cuerpo}"})
    SubElement(m, "D", {"value": f"{den_c}", "unit": "g/cm3"})
    mh = SubElement(mats, "material", {"name": "Havar"})
    SubElement(mh, "D", {"value": f"{den_h}", "unit": "g/cm3"})

    solids = SubElement(root, "solids")
    SubElement(solids, "box", {"name": "world_s", "x": "500", "y": "500",
                               "z": "500", "lunit": "mm"})
    SubElement(solids, "tube", {"name": "cuerpo_s", "rmin": "0",
                                "rmax": "R_TGT+WALL", "z": "L_TGT+2*WALL",
                                "startphi": "0", "deltaphi": "360",
                                "aunit": "deg", "lunit": "mm"})
    SubElement(solids, "tube", {"name": "cavidad_s", "rmin": "0",
                                "rmax": "R_TGT", "z": "L_TGT",
                                "startphi": "0", "deltaphi": "360",
                                "aunit": "deg", "lunit": "mm"})
    SubElement(solids, "tube", {"name": "foil_s", "rmin": "0",
                                "rmax": "R_TGT", "z": "FOIL",
                                "startphi": "0", "deltaphi": "360",
                                "aunit": "deg", "lunit": "mm"})

    struct = SubElement(root, "structure")
    vw = SubElement(struct, "volume", {"name": "world"})
    SubElement(vw, "materialref", {"ref": "G4_AIR"})
    SubElement(vw, "solidref", {"ref": "world_s"})
    vc = SubElement(struct, "volume", {"name": "cuerpo_blanco"})
    SubElement(vc, "materialref", {"ref": f"Cuerpo_{info.material_cuerpo}"})
    SubElement(vc, "solidref", {"ref": "cuerpo_s"})
    vv = SubElement(struct, "volume", {"name": "cavidad_contenido"})
    SubElement(vv, "materialref", {"ref": f"Contenido_{info.blanco_id}"})
    SubElement(vv, "solidref", {"ref": "cavidad_s"})
    vf = SubElement(struct, "volume", {"name": "ventana_foil"})
    SubElement(vf, "materialref", {"ref": "Havar"})
    SubElement(vf, "solidref", {"ref": "foil_s"})

    setup = SubElement(root, "setup", {"name": "Default", "version": "1.0"})
    SubElement(setup, "world", {"ref": "world"})

    # Marcadores de origen como comentario XML (49.11)
    from xml.etree.ElementTree import Comment
    root.insert(0, Comment(f" blanco {info.blanco_id} — " + " | ".join(info.marcadores)
                           + f" | cuerpo {info.material_cuerpo}: {fu_den_c} "))

    salida = Path(salida)
    indent(ElementTree(root).getroot(), space="  ")
    ElementTree(root).write(salida, encoding="utf-8", xml_declaration=True)
    return salida
