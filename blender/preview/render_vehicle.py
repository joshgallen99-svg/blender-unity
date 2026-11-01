"""Hero render of the Ridgeback for quick visual review (not used by the game).

Run:  python blender/preview/render_vehicle.py [out.png] [samples]
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "vehicles"))

import bpy  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402

import ridgeback as RB  # noqa: E402
from lib import common as C  # noqa: E402

out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ridgeback.png"
samples = int(sys.argv[2]) if len(sys.argv) > 2 else 96

body, wheel, empties = RB.build()
for e in empties:
    w = bpy.data.objects.new(e.name + "_mesh", wheel.data)
    bpy.context.scene.collection.objects.link(w)
    w.location = e.location
    if e.location.x < 0:  # right-hand side: show face outwards
        w.rotation_euler = Euler((0, 0, math.pi))
    w.rotation_euler.rotate_axis("X", math.radians(23 * hash(e.name) % 60))
wheel.hide_render = True

# Ground: warm desert sand.
ground_mat = C.material("Ground", (0.62, 0.40, 0.25), 0.0, 0.95)
bpy.ops.mesh.primitive_plane_add(size=60)
bpy.context.active_object.data.materials.append(ground_mat)

# Golden-hour sky + sun.
world = bpy.data.worlds.new("World")
bpy.context.scene.world = world
try:
    world.use_nodes = True
except Exception:
    pass
nt = world.node_tree
sky = nt.nodes.new("ShaderNodeTexSky")
for attr, val in (("sky_type", "NISHITA"), ("sun_elevation", math.radians(14)), ("sun_rotation", math.radians(215))):
    try:
        setattr(sky, attr, val)
    except Exception:
        pass
bg = nt.nodes.get("Background") or nt.nodes.new("ShaderNodeBackground")
bg.inputs["Strength"].default_value = 0.35
nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
out_node = nt.nodes.get("World Output") or nt.nodes.new("ShaderNodeOutputWorld")
nt.links.new(bg.outputs["Background"], out_node.inputs["Surface"])

sun_data = bpy.data.lights.new("Sun", "SUN")
sun_data.energy = 4.0
sun_data.color = (1.0, 0.82, 0.62)
sun_data.angle = math.radians(2)
sun = bpy.data.objects.new("Sun", sun_data)
sun.rotation_euler = Euler((math.radians(76), 0, math.radians(35)))
bpy.context.scene.collection.objects.link(sun)

cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 50
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
cam.location = Vector((5.6, -6.4, 1.9))
target = Vector((0, -0.2, 1.0))
cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
bpy.context.scene.camera = cam

sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.samples = samples
sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 1600, 900
try:
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
print("Saved", out)
