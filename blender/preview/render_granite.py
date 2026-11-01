"""Preview render of the granite formations. Usage: python render_granite.py out.png [names,comma] [samples]"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "formations"))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402

import granite_formations as F  # noqa: E402
from lib import common as C  # noqa: E402
from strata_material import strata_material  # noqa: E402

out = sys.argv[1]
only = set(sys.argv[2].split(",")) if len(sys.argv) > 2 and sys.argv[2] else None
samples = int(sys.argv[3]) if len(sys.argv) > 3 else 24

objs = [o for o in F.build(only) if not o.name.endswith("_LOD1")]
for o in bpy.data.objects:
    if o.name.endswith("_LOD1"):
        o.hide_render = True
mat = C.material("GraniteGrey", (0.36, 0.36, 0.35), 0.0, 0.85)
x = 0.0
for o in objs:
    o.data.materials.clear()
    o.data.materials.append(mat)
    w = o.dimensions.x
    o.location = (x + w / 2, 0, 0)
    x += w + 6
for o in objs:
    o.location.x -= x / 2

bpy.ops.mesh.primitive_plane_add(size=2000)
bpy.context.active_object.data.materials.append(C.material("Ground", (0.20, 0.26, 0.12), 0.0, 0.95))
world = bpy.data.worlds.new("W")
bpy.context.scene.world = world
world.color = (0.35, 0.5, 0.8)
sun_d = bpy.data.lights.new("Sun", "SUN")
sun_d.energy = 3.2
sun_d.color = (1.0, 0.9, 0.78)
sun = bpy.data.objects.new("Sun", sun_d)
sun.rotation_euler = Euler((math.radians(52), 0, math.radians(35)))
bpy.context.scene.collection.objects.link(sun)
cam_d = bpy.data.cameras.new("Cam")
cam_d.lens = 32
cam_d.clip_end = 5000
cam = bpy.data.objects.new("Cam", cam_d)
bpy.context.scene.collection.objects.link(cam)
span = max(x, 60)
cam.location = Vector((0, -span * 0.95, span * 0.16))
cam.rotation_euler = (Vector((0, 0, 6)) - cam.location).to_track_quat("-Z", "Y").to_euler()
sc = bpy.context.scene
sc.camera = cam
sc.render.engine = "CYCLES"
sc.cycles.samples = samples
sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 1600, 700
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
print("Saved", out)
