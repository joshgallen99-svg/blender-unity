"""Hero render of the fleet: both bodies with different tyres and accessories, plus the tyre lineup.

Usage: python blender/preview/render_vehicle.py [out.png] [samples]
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

out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/fleet.png"
samples = int(sys.argv[2]) if len(sys.argv) > 2 else 64

objs = {o.name: o for o in F.build()}
for o in objs.values():
    o.hide_render = True


def place(body, wheel, accessories, offset, yaw):
    root = bpy.data.objects.new(body + "_root", None)
    bpy.context.scene.collection.objects.link(root)
    root.location = offset
    root.rotation_euler = Euler((0, 0, math.radians(yaw)))
    show = [objs[f"Body_{body}"]] + [objs[f"{a}_{body}"] for a in accessories]
    for o in show:
        inst = bpy.data.objects.new(o.name + "_i", o.data)
        bpy.context.scene.collection.objects.link(inst)
        inst.parent = root
    for n in ("WheelFL", "WheelFR", "WheelRL", "WheelRR"):
        e = objs[f"{body}_{n}"]
        w = bpy.data.objects.new(n, objs[wheel].data)
        bpy.context.scene.collection.objects.link(w)
        w.parent = root
        w.location = e.location
        if e.location.x < 0:
            w.rotation_euler = Euler((0, 0, math.pi))
    sp = objs[f"{body}_Spare"]
    w = bpy.data.objects.new("spare", objs[wheel].data)
    bpy.context.scene.collection.objects.link(w)
    w.parent = root
    w.location = sp.location
    w.rotation_euler = Euler((0, 0, math.radians(90)))


place("Ridgeback", "Wheel_AT", ["RoofRack", "Snorkel", "BullBar"], (-2.6, 0, 0), 25)
place("Packhorse", "Wheel_MT", ["RoofRack"], (3.2, 3.5, 0), 25)
for i, wname in enumerate(("Wheel_AT", "Wheel_MT", "Wheel_Dune")):
    w = bpy.data.objects.new(wname + "_show", objs[wname].data)
    bpy.context.scene.collection.objects.link(w)
    w.location = (-3.5 + i * 1.2, -4.2, 0.45)
    w.rotation_euler = Euler((0, 0, math.radians(200)))

bpy.ops.mesh.primitive_plane_add(size=80)
bpy.context.active_object.data.materials.append(C.material("Ground", (0.62, 0.40, 0.25), 0.0, 0.95))
world = bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.color = (0.55, 0.62, 0.75)
sun_d = bpy.data.lights.new("Sun", "SUN")
sun_d.energy = 4.0
sun_d.color = (1.0, 0.84, 0.66)
sun = bpy.data.objects.new("Sun", sun_d)
sun.rotation_euler = Euler((math.radians(60), 0, math.radians(30)))
bpy.context.scene.collection.objects.link(sun)
cam_d = bpy.data.cameras.new("Cam")
cam_d.lens = 35
cam = bpy.data.objects.new("Cam", cam_d)
bpy.context.scene.collection.objects.link(cam)
cam.location = Vector((2.0, -12.5, 3.4))
cam.rotation_euler = (Vector((0.3, 0.5, 1.0)) - cam.location).to_track_quat("-Z", "Y").to_euler()
sc = bpy.context.scene
sc.camera = cam
sc.render.engine = "CYCLES"
sc.cycles.samples = samples
sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 1600, 800
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
print("Saved", out)
