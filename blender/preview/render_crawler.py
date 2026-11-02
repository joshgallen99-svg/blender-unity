"""Preview render of the rock crawler, articulated: front-left wheel stuffed, rear-left drooped.

Poses the separate axle, link and coilover parts the same way the game's SolidAxleVisuals does, so
this doubles as a check that the parts line up.

Usage: python blender/preview/render_crawler.py [out.png] [samples]
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "vehicles"))

import bpy  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402

import fleet as F  # noqa: E402
from lib import common as C  # noqa: E402

out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/crawler.png"
samples = int(sys.argv[2]) if len(sys.argv) > 2 else 48

objs = {o.name: o for o in F.build()}
for o in objs.values():
    o.hide_render = True

# Mount points (Blender space: front = -Y, left = +X). Must match SolidAxleVisuals.cs.
LINKS = [  # (chassis point, axle-local point) per side, mirrored in X
    ((0.48, 0.95, 0.72), (0.33, 0.0, -0.08)),    # lower links run back from the axle (+Y for the front axle)
    ((0.26, 0.70, 1.02), (0.20, 0.0, 0.17)),     # upper links
]
COIL = ((0.66, -0.10, 1.34), (0.60, 0.0, 0.10))
TRAVEL = {"WheelFL": 0.30, "WheelFR": -0.05, "WheelRL": -0.25, "WheelRR": 0.10}


def inst(src, name, parent=None):
    o = bpy.data.objects.new(name, objs[src].data)
    bpy.context.scene.collection.objects.link(o)
    o.parent = parent
    return o


def stretch(src, a, b):
    """Place a 1 m unit part (along -Y) from a to b."""
    o = inst(src, src + "_i")
    d = b - a
    o.location = a
    o.rotation_euler = d.to_track_quat("-Y", "Z").to_euler()
    o.scale = (1, d.length, 1)
    return o


show = ["Body_Crawler", "RoofRack_Crawler", "BullBar_Crawler", "Snorkel_Crawler"]
for n in show:
    inst(n, n + "_i")
centres = {}
for n in TRAVEL:
    e = objs[f"Crawler_{n}"]
    c = e.location.copy()
    c.z += TRAVEL[n]
    centres[n] = c
    w = inst("Wheel_Bead", n)
    w.location = c
    if c.x < 0:
        w.rotation_euler = Euler((0, 0, math.pi))
sp = inst("Wheel_Bead", "spare")
sp.location = objs["Crawler_Spare"].location
sp.rotation_euler = Euler((0, 0, math.radians(90)))

for axle, (l, r) in {"front": ("WheelFL", "WheelFR"), "rear": ("WheelRL", "WheelRR")}.items():
    a, b = centres[l], centres[r]
    mid = (a + b) / 2
    xdir = (a - b).normalized()                      # toward the left wheel = +X
    roll = math.atan2(xdir.z, xdir.x)
    ax = inst("Axle_Housing", "axle_" + axle)
    ax.location = mid
    ax.rotation_euler = Euler((0, -roll, 0))
    sign = 1 if axle == "front" else -1             # links run toward the middle of the vehicle
    for s in (1, -1):
        for chassis, local in LINKS:
            cp = Vector((s * chassis[0], mid.y + sign * chassis[1], chassis[2]))
            ap = mid + Vector((s * local[0] * math.cos(roll), 0, s * local[0] * math.sin(roll) + local[2]))
            stretch("Link_Unit", ap, cp)
        top = Vector((s * COIL[0][0], mid.y + sign * COIL[0][1], COIL[0][2]))
        bot = mid + Vector((s * COIL[1][0] * math.cos(roll), 0, s * COIL[1][0] * math.sin(roll) + COIL[1][2]))
        stretch("Coilover_Unit", top, bot)

bpy.ops.mesh.primitive_plane_add(size=80)
bpy.context.active_object.data.materials.append(C.material("Ground", (0.42, 0.40, 0.36), 0.0, 0.95))
world = bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.color = (0.6, 0.66, 0.75)
sun_d = bpy.data.lights.new("Sun", "SUN")
sun_d.energy = 4.0
sun_d.color = (1.0, 0.88, 0.72)
sun = bpy.data.objects.new("Sun", sun_d)
sun.rotation_euler = Euler((math.radians(55), 0, math.radians(35)))
bpy.context.scene.collection.objects.link(sun)
cam_d = bpy.data.cameras.new("Cam")
cam_d.lens = 32
cam = bpy.data.objects.new("Cam", cam_d)
bpy.context.scene.collection.objects.link(cam)
cam.location = Vector((5.2, -6.4, 2.4))
cam.rotation_euler = (Vector((0.0, -0.2, 1.0)) - cam.location).to_track_quat("-Z", "Y").to_euler()
sc = bpy.context.scene
sc.camera = cam
sc.render.engine = "CYCLES"
sc.cycles.samples = samples
sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 1200, 800
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
print("Saved", out)
