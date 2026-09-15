"""Renderizador fotorrealista Blender Cycles — Fase 25.

Renderiza la geometría REAL de un caso Monte Carlo (GATE/OpenGATE) de
Radiopharma OS: esfera moderadora + capas de blindaje concéntricas +
puntos de salida de neutrones (dispersión medida por PhaseSpaceActor,
coloreados por banda energética térmica/epitérmica/rápida).

REGLA CANÓNICA: este render es COMUNICACIÓN visual de resultados MC reales.
NUNCA genera física: toda posición, energía y geometría proviene del
case.json / tally real. Si falta el dato, el script aborta (no hay
marcador "bonito" que valga).

Uso (headless):
    blender -b -P scripts/render_blender.py -- \
        --data neutrones_data.json --salida render.png \
        [--video render.mp4 --frames 72 --res-video 960x540]

El JSON de entrada es el emitido por el endpoint /neutrons/transport-tally
con blindajes (claves: moderador_material, blindajes_geometria[{material,
rmin_mm, rmax_mm}], dispersion{y_mm,z_mm,e_mev,radio_moderador_mm}).
Si faltan, se aborta con error (geometría no_demostrable).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy  # type: ignore  # solo existe dentro de Blender


def _parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True, help="JSON del tally real")
    p.add_argument("--salida", required=True, help="PNG de salida")
    p.add_argument("--video", default=None, help="MP4 turntable opcional")
    p.add_argument("--frames", type=int, default=72)
    p.add_argument("--res", default="1920x1080")
    p.add_argument("--res-video", default="960x540")
    p.add_argument("--muestras", type=int, default=96)
    p.add_argument("--muestras-video", type=int, default=32)
    return p.parse_args(argv)


def _mat_principled(nombre: str, color, metallic=0.0, rough=0.4, alpha=1.0, transmission=0.0):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Alpha"].default_value = alpha
    if "Transmission Weight" in bsdf.inputs:
        bsdf.inputs["Transmission Weight"].default_value = transmission
    if alpha < 1.0 or transmission > 0.0:
        m.surface_render_method = "DITHERED"
    return m


def _mat_emision(nombre: str, color, fuerza=8.0):
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


def _esfera_hueca(nombre: str, r_min_m: float, r_max_m: float, material, corte=True):
    """Casca esférica con cuarto de corte (booleana) para ver el interior."""
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r_max_m, segments=96, ring_count=48, location=(0, 0, 0))
    ext = bpy.context.active_object
    ext.name = f"{nombre}_ext"
    if r_min_m > 0:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r_min_m, segments=96, ring_count=48, location=(0, 0, 0))
        int_ = bpy.context.active_object
        mod = ext.modifiers.new("hueco", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.object = int_
        bpy.context.view_layer.objects.active = ext
        bpy.ops.object.modifier_apply(modifier="hueco")
        bpy.data.objects.remove(int_)
    if corte:
        lado = 2.2 * r_max_m
        bpy.ops.mesh.primitive_cube_add(size=lado, location=(lado / 2, -lado / 2, 0))
        cutter = bpy.context.active_object
        mod = ext.modifiers.new("corte", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.object = cutter
        bpy.context.view_layer.objects.active = ext
        bpy.ops.object.modifier_apply(modifier="corte")
        bpy.data.objects.remove(cutter)
    ext.data.materials.append(material)
    for poly in ext.data.polygons:
        poly.use_smooth = True
    return ext


def main() -> None:
    a = _parse_args()
    data = json.loads(Path(a.data).read_text())

    geom = data.get("blindajes_geometria")
    if not geom:
        raise SystemExit(
            "no_demostrable: el JSON no trae 'blindajes_geometria' "
            "(radios reales del case.json). No se renderiza geometría inventada."
        )
    disp = data.get("dispersion") or {}
    y_mm, z_mm, e_mev = disp.get("y_mm"), disp.get("z_mm"), disp.get("e_mev")
    if not (y_mm and z_mm and e_mev):
        raise SystemExit("no_demostrable: falta dispersion del tally real.")
    r_mod_mm = disp.get("radio_moderador_mm")
    if not r_mod_mm:
        raise SystemExit("no_demostrable: falta radio_moderador_mm.")

    # --- escena limpia
    bpy.ops.wm.read_factory_settings(use_empty=True)
    esc = bpy.context.scene
    esc.render.engine = "CYCLES"
    esc.cycles.samples = a.muestras
    esc.cycles.use_denoising = True
    esc.cycles.device = "CPU"
    esc.render.film_transparent = False

    # --- materiales (NIST del caso, mapeados a apariencia PBR declarada)
    mat_agua = _mat_principled("G4_WATER", (0.18, 0.38, 0.62), rough=0.05, transmission=1.0, alpha=0.3)
    mats = {"G4_WATER": mat_agua}
    for capa in geom:
        mat = capa["material"]
        if mat in mats:
            continue
        if "CONCRETE" in mat:
            mats[mat] = _mat_principled(mat, (0.3, 0.29, 0.27), rough=0.95)
        elif mat in ("G4_Pb", "G4_LEAD"):
            mats[mat] = _mat_principled(mat, (0.1, 0.12, 0.16), metallic=0.85, rough=0.5)
        elif "Fe" in mat or "STEEL" in mat or "IRON" in mat:
            mats[mat] = _mat_principled(mat, (0.5, 0.52, 0.55), metallic=0.95, rough=0.3)
        else:
            mats[mat] = _mat_principled(mat, (0.6, 0.6, 0.62), rough=0.6)

    # --- geometría: moderador sólido (sin corte) + capas con corte
    _esfera_hueca("moderador", 0.0, r_mod_mm / 1000.0, mat_agua, corte=False)
    radio_ext_m = r_mod_mm / 1000.0
    for i, capa in enumerate(sorted(geom, key=lambda c: c["rmin_mm"])):
        _esfera_hueca(f"blindaje_{i}", capa["rmin_mm"] / 1000.0, capa["rmax_mm"] / 1000.0, mats[capa["material"]], corte=True)
        radio_ext_m = capa["rmax_mm"] / 1000.0

    # --- neutrones de salida (puntos reales del phsp, sobre la superficie del moderador)
    m_ter = _mat_emision("n_termico", (0.15, 0.45, 1.0))
    m_epi = _mat_emision("n_epitermico", (1.0, 0.55, 0.05))
    m_rap = _mat_emision("n_rapido", (1.0, 0.08, 0.08))
    r_m = r_mod_mm / 1000.0
    r_punto = max(r_m * 0.016, 0.0025)
    n_max = 1500  # límite de instancias para tiempos de render razonables
    paso = max(1, len(y_mm) // n_max)
    for y, z, e in zip(y_mm[::paso], z_mm[::paso], e_mev[::paso]):
        yy, zz = y / 1000.0, z / 1000.0
        xx2 = r_m * r_m - yy * yy - zz * zz
        if xx2 < 0:
            continue
        xx = -math.sqrt(xx2)  # cara visible desde la cámara (-X)
        e_ev = e * 1e6
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=r_punto, location=(xx, yy, zz))
        o = bpy.context.active_object
        if e_ev < 0.4:
            o.data.materials.append(m_ter)
        elif e_ev < 1e5:
            o.data.materials.append(m_epi)
        else:
            o.data.materials.append(m_rap)

    # --- suelo
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, -radio_ext_m * 1.02))
    suelo = bpy.context.active_object
    suelo.data.materials.append(_mat_principled("suelo", (0.08, 0.08, 0.1), rough=0.35, metallic=0.1))

    # --- iluminación de estudio
    mundo = bpy.data.worlds.new("estudio")
    mundo.use_nodes = True
    bg = mundo.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.02, 0.025, 0.04, 1.0)
    bg.inputs["Strength"].default_value = 0.15
    esc.world = mundo
    for loc, energia, tam in [((4, -4, 5), 900, 3.0), ((-5, -2, 3), 550, 2.5), ((0, 5, 4), 400, 2.0)]:
        bpy.ops.object.light_add(type="AREA", location=loc)
        luz = bpy.context.active_object
        luz.data.energy = energia
        luz.data.shape = "DISK"
        luz.data.size = tam

    # --- cámara
    bpy.ops.object.camera_add(location=(radio_ext_m * 3.4, -radio_ext_m * 3.4, radio_ext_m * 2.2))
    cam = bpy.context.active_object
    esc.camera = cam

    from mathutils import Vector

    def apuntar(obj, punto=(0, 0, 0)):
        direccion = Vector(punto) - obj.location
        obj.rotation_euler = direccion.to_track_quat("-Z", "Y").to_euler()

    apuntar(cam)
    for luz in [o for o in esc.objects if o.type == "LIGHT"]:
        apuntar(luz)

    # --- still
    w, h = map(int, a.res.split("x"))
    esc.render.resolution_x, esc.render.resolution_y = w, h
    esc.render.filepath = str(Path(a.salida).resolve())
    esc.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    print(f"RENDER_STILL_OK {esc.render.filepath}")

    # --- video turntable opcional
    if a.video:
        wv, hv = map(int, a.res_video.split("x"))
        esc.render.resolution_x, esc.render.resolution_y = wv, hv
        esc.cycles.samples = a.muestras_video
        esc.frame_start, esc.frame_end = 1, a.frames
        esc.render.fps = 12
        esc.render.filepath = str(Path(a.video).resolve())
        esc.render.image_settings.file_format = "FFMPEG"
        esc.render.ffmpeg.format = "MPEG4"
        esc.render.ffmpeg.codec = "H264"
        esc.render.ffmpeg.constant_rate_factor = "HIGH"
        centro = Vector((0, 0, 0))
        radio_cam = (cam.location - centro).length
        for f in range(1, a.frames + 1):
            ang = 2 * math.pi * (f - 1) / a.frames + math.radians(225)
            cam.location = Vector((radio_cam * math.cos(ang) * 0.83, radio_cam * math.sin(ang) * 0.83, radio_ext_m * 2.2))
            apuntar(cam, centro)
            esc.frame_set(f)
        bpy.ops.render.render(animation=True)
        print(f"RENDER_VIDEO_OK {esc.render.filepath}")


main()
