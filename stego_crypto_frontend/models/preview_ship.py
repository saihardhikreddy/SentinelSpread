"""Render quick Workbench previews of the exported ship (geometry check, no web needed).

Run:  blender --background --factory-startup --python models/preview_ship.py -- <ship.glb> <out_prefix>
"""

import math
import sys

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
GLB, OUT = args[0], args[1]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)

scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "MATERIAL"
scene.display.shading.show_cavity = True
scene.display.shading.cavity_type = "BOTH"
scene.display.shading.show_shadows = True
scene.render.resolution_x, scene.render.resolution_y = 1400, 860
scene.render.film_transparent = False
scene.world = bpy.data.worlds.new("w")
scene.display.shading.background_type = "VIEWPORT"

cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
scene.collection.objects.link(cam)
scene.camera = cam


def shoot(name, pos, target, lens=35):
    cam.location = pos
    cam.rotation_euler = (Vector(target) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    scene.render.filepath = f"{OUT}_{name}.png"
    bpy.ops.render.render(write_still=True)


# Blender is Z-up here (the importer converts back from glTF's Y-up).
shoot("wide", (22, -20, 14), (0, 0, 0), 30)
shoot("hubtop", (6.5, -2.6, 6.2), (0.8, 0.7, 3.6), 44)
shoot("hubside", (3.2, -9.5, 3.4), (0, 0, 2.2), 40)
shoot("command", (13.5, 3.5, 1.5), (9.5, 0, -0.2), 40)
shoot("hub", (5, -5, 5), (0, 0, 2), 35)
