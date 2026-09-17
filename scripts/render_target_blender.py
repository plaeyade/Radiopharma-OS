"""Renderizador Blender Cycles del blanco irradiado — Fase 34.

Render de COMUNICACIÓN de la geometría GDML real del blanco seleccionable
(gdml_target.py) con el haz primario parametrizado (beam_model.py) y la
etiqueta del espectro de neutrones TALYS real (nspec_*.tot). El JSON de
entrada lo emite scripts/export_target_render_data.py.

REGLA CANÓNICA (igual que Fase 25): este render NUNCA genera física.
Geometría, densidades, potencia del haz y energía media del espectro
provienen del JSON trazable; si falta una clave, el script aborta.

Uso (headless):
    blender -b -P scripts/render_target_blender.py -- \
        --data render_data_f18.json --salida blanco_f18.png
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy  # type: ignore  # solo existe dentro de Blender


def _parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--salida", required=True)
    p.add_argument("--res", default="1600x900")
    p.add_argument("--muestras", type=int, default=96)
    return p.parse_args(argv)


def _mat(nombre, color, metallic=0.0, rough=0.4, alpha=1.0):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    b.inputs["Alpha"].default_value = alpha
    if alpha < 1.0:
        m.surface_render_method = "DITHERED"
    return m


def _emisivo(nombre, color, fuerza):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1.0)
    em.inputs["Strength"].default_value = fuerza
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return m


_COLOR_CUERPO = {
    "Ag": (0.75, 0.76, 0.80), "Nb": (0.45, 0.55, 0.75),
    "Ta": (0.35, 0.42, 0.55), "Al": (0.70, 0.72, 0.74),
    "Ni": (0.62, 0.65, 0.58),
}
_COLOR_CONTENIDO = {
    "agua18": (0.10, 0.45, 0.85), "agua": (0.10, 0.45, 0.85),
    "gas": (0.55, 0.80, 0.95), "solido": (0.85, 0.55, 0.15),
}


def _color_contenido(blanco_id: str):
    for k, v in _COLOR_CONTENIDO.items():
        if blanco_id.startswith(k):
            return v
    return (0.5, 0.5, 0.9)


def _cilindro(nombre, radio_m, largo_m, z, mat, vertices=96):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices, radius=radio_m, depth=largo_m, location=(0, 0, z))
    ob = bpy.context.active_object
    ob.name = nombre
    ob.data.materials.append(mat)
    return ob


def _texto(nombre, cuerpo, loc, tam, mat, rot=(math.pi / 2, 0, 0)):
    bpy.ops.object.text_add(location=loc, rotation=rot)
    t = bpy.context.active_object
    t.name = nombre
    t.data.body = cuerpo
    t.data.size = tam
    t.data.align_x = "CENTER"
    t.data.materials.append(mat)
    return t


def main() -> None:
    a = _parse_args()
    datos = json.loads(Path(a.data).read_text())

    # Abortar si falta cualquier dato trazable (no_demostrable)
    for clave in ("isotopo", "blanco_id", "geometria_gdml", "haz",
                  "espectro_neutrones"):
        if clave not in datos:
            raise SystemExit(f"no_demostrable: falta '{clave}' en {a.data}")
    g = datos["geometria_gdml"]
    haz = datos["haz"]
    esp = datos["espectro_neutrones"]

    # Escala: el blanco es de mm; trabajamos en "unidades Blender = mm"
    # y colocamos la cámara en consecuencia (evita problemas de clip).
    r = g["radio_mm"]
    L = max(g["espesor_mm"], 0.2 * r)  # visibilidad: exageración declarada
    # NOTA DE COMUNICACIÓN: si el espesor real es < 20 % del radio, se dibuja
    # a 0,2·r SOLO para que el corte sea legible (se etiqueta en pantalla).
    L_real = g["espesor_mm"]
    exagerado = L > L_real
    foil = max(g["foil_havar_um"] / 1000.0, 0.04 * r)
    wall = 0.1 * r  # respaldo declarado (proporción visual)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    escena = bpy.context.scene
    escena.render.engine = "CYCLES"
    escena.cycles.samples = a.muestras
    escena.cycles.use_denoising = True
    try:
        escena.cycles.device = "CPU"
    except Exception:
        pass
    w, h = (int(x) for x in a.res.split("x"))
    escena.render.resolution_x = w
    escena.render.resolution_y = h

    # Materiales — colores por material del catálogo (etiquetado visual)
    mat_cuerpo = _mat(f"Cuerpo_{g['material_cuerpo']}",
                      _COLOR_CUERPO.get(g["material_cuerpo"], (0.6, 0.6, 0.6)),
                      metallic=0.55, rough=0.35)
    mat_contenido = _mat("Contenido", _color_contenido(datos["blanco_id"]),
                         metallic=0.0, rough=0.15, alpha=0.9)
    _pb = mat_contenido.node_tree.nodes["Principled BSDF"]
    _pb.inputs["Emission Color"].default_value = (*_color_contenido(datos["blanco_id"]), 1.0)
    _pb.inputs["Emission Strength"].default_value = 1.2
    mat_foil = _mat("Havar", (0.85, 0.70, 0.30), metallic=0.95, rough=0.2)
    mat_haz = _emisivo("Haz", (0.30, 0.75, 1.0), 9.0)
    mat_txt = _emisivo("Texto", (1.0, 1.0, 1.0), 3.0)
    mat_txt_am = _emisivo("TextoAmbar", (1.0, 0.8, 0.3), 3.0)

    # Geometría GDML: cuerpo hueco (cilindro exterior) + contenido + foil.
    # Corte longitudinal (media luna booleana) para ver el interior.
    cuerpo = _cilindro("cuerpo_blanco", r + wall, L + 2 * wall, 0, mat_cuerpo)
    cav = _cilindro("cavidad_contenido", r, L, 0, mat_contenido)
    _cilindro("ventana_foil", r, foil, -(L / 2 + wall + foil / 2), mat_foil)

    # Haz primario: cilindro emisivo aguas arriba, radio = sigma declarado
    sigma = haz["sigma_mm"]
    largo_haz = 3.0 * r
    _cilindro("haz_primario", sigma, largo_haz,
              -(L / 2 + wall + foil + largo_haz / 2), mat_haz, vertices=48)

    # Corte de un cuarto del cuerpo para visualización (comunicación)
    bpy.ops.mesh.primitive_cube_add(size=8 * r, location=(4 * r, -4 * r, 0))
    corte = bpy.context.active_object
    for ob in (cuerpo, cav):
        mod = ob.modifiers.new("corte_vista", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.object = corte
    corte.hide_render = True
    corte.hide_viewport = True

    # Piso neutro
    mat_piso = _mat("Piso", (0.08, 0.09, 0.11), rough=0.9)
    bpy.ops.mesh.primitive_plane_add(size=30 * r, location=(0, 0, -2.2 * r))
    bpy.context.active_object.data.materials.append(mat_piso)

    # Etiquetas con datos REALES del JSON (nunca texto inventado)
    tit = (f"{datos['isotopo']} — blanco {datos['blanco_id']} "
           f"({g['material_cuerpo']})")
    lin2 = (f"haz {haz['energia_mev']} MeV · {haz['corriente_ua']} uA · "
            f"{haz['potencia_haz_w']:.0f} W")
    lin3 = (f"TALYS real: E_media n = {esp['e_media_mev']} MeV "
            f"({esp['bins']} bins)")
    lin4 = ("espesor visual exagerado p/ legibilidad — el real esta en el GDML"
            if exagerado else "")
    _texto("titulo", tit, (0, 0.3 * r, 1.52 * r), 0.22 * r, mat_txt)
    _texto("lin2", lin2, (0, 0.3 * r, 1.24 * r), 0.17 * r, mat_txt_am)
    _texto("lin3", lin3, (0, 0.3 * r, 1.01 * r), 0.145 * r, mat_txt)
    if lin4:
        _texto("lin4", lin4, (0, -0.5 * r, -1.35 * r), 0.14 * r, mat_txt_am)

    # Luces + mundo
    for loc, e in (((5 * r, -3 * r, 5 * r), 400.0),
                   ((-4 * r, -2 * r, 2 * r), 250.0),
                   ((0, 4 * r, 3 * r), 200.0)):
        bpy.ops.object.light_add(type="AREA", location=loc)
        luz = bpy.context.active_object
        luz.data.energy = e
        luz.data.size = 4 * r
    mundo = bpy.data.worlds.new("W")
    mundo.use_nodes = True
    mundo.node_tree.nodes["Background"].inputs[0].default_value = (
        0.02, 0.025, 0.035, 1.0)
    mundo.node_tree.nodes["Background"].inputs[1].default_value = 1.4
    escena.world = mundo

    # Cámara (encuadre por radio del blanco)
    bpy.ops.object.camera_add(location=(4.8 * r, -5.4 * r, 2.0 * r))
    cam = bpy.context.active_object
    escena.camera = cam
    direccion = -cam.location + __import__("mathutils").Vector((0, 0, 0.35 * r))
    cam.rotation_euler = direccion.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 50
    cam.data.clip_start = 0.1
    cam.data.clip_end = 200 * r

    escena.render.filepath = str(Path(a.salida).resolve())
    escena.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    print(f"RENDER-OK {escena.render.filepath}")


main()
