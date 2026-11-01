"""Lineup render of the desert landmarks. Usage: python blender/preview/render_props.py out.png [samples]"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "props"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "landmarks"))
import bpy  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402

import desert_landmarks as DP  # noqa: E402
from lib import common as C  # noqa: E402

out = sys.argv[1]
samples = int(sys.argv[2]) if len(sys.argv) > 2 else 48
objs = [o for o in DP.build() if o.name != 'Windmill_Rotor']
x = 0.0
for o in objs:
    w = o.dimensions.x
    o.location = (x + w / 2, 0, 0)
    x += w + 0.4
for o in objs:
    o.location.x -= x / 2

bpy.ops.mesh.primitive_plane_add(size=80)
bpy.context.active_object.data.materials.append(C.material("Ground", (0.62, 0.40, 0.25), 0.0, 0.95))
world = bpy.data.worlds.new("W"); bpy.context.scene.world = world
world.color = (0.55, 0.62, 0.75)
sun_d = bpy.data.lights.new("Sun", "SUN"); sun_d.energy = 4.5; sun_d.color = (1.0, 0.85, 0.68)
sun = bpy.data.objects.new("Sun", sun_d); sun.rotation_euler = Euler((math.radians(60), 0, math.radians(30)))
bpy.context.scene.collection.objects.link(sun)
cam_d = bpy.data.cameras.new("Cam"); cam_d.lens = 35
cam = bpy.data.objects.new("Cam", cam_d); bpy.context.scene.collection.objects.link(cam)
cam.location = Vector((0, -x * 0.55, x * 0.2))
cam.rotation_euler = (Vector((0, 0, 4.0)) - cam.location).to_track_quat("-Z", "Y").to_euler()
sc = bpy.context.scene; sc.camera = cam
sc.render.engine = "CYCLES"; sc.cycles.samples = samples; sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 1800, 600
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
