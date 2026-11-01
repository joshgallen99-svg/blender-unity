"""Preview render of the generated desert region around the spawn point, from a chase-camera view.

Usage: python blender/preview/render_region.py out.png [samples]
Uses the same terrain data, scatter list and models as Unity, so it is a quick check of
scale and composition (not a match for Unity's final look).
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "vehicles"))
sys.path.insert(0, os.path.join(HERE, "..", "props"))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402

import desert_props as DP  # noqa: E402
import ridgeback as RB  # noqa: E402
from lib import common as C  # noqa: E402

out = sys.argv[1]
samples = int(sys.argv[2]) if len(sys.argv) > 2 else 32
SRC = os.path.join(C.REPO, "Assets", "Terrain", "Source~")
info = json.load(open(os.path.join(SRC, "desert_info.json")))
N, SIZE, H = info["resolution"], info["size"], info["height"]
hm = np.fromfile(os.path.join(SRC, "desert_height.r16"), "<u2").reshape(N, N) / 65535 * H
sp = info["spawn"]

# Unity (x, y, z) with z north -> Blender (x, y, z) with y north... Unity +Z is Blender -Y in our FBX
# convention, but for this preview we simply map Unity x->Blender -x, Unity z->Blender -y? Keep it
# simple: build everything in "Unity space rotated into Blender": bx = -ux, by = -uz, bz = uy.
def to_b(ux, uy, uz):
    return Vector((-ux, -uz, uy))


def height(ux, uz):
    fx, fz = ux / SIZE * (N - 1), uz / SIZE * (N - 1)
    x0, z0 = int(fx), int(fz)
    tx, tz = fx - x0, fz - z0
    h00, h10 = hm[z0, x0], hm[z0, min(x0 + 1, N - 1)]
    h01, h11 = hm[min(z0 + 1, N - 1), x0], hm[min(z0 + 1, N - 1), min(x0 + 1, N - 1)]
    return (h00 * (1 - tx) + h10 * tx) * (1 - tz) + (h01 * (1 - tx) + h11 * tx) * tz


# Props first (build() resets the scene), then the vehicle into the same scene.
props = {o.name: o for o in DP.build()}
for o in props.values():
    o.hide_render = True
    o.hide_viewport = True
body, wheel, empties = RB.build_body(RB.palette()), None, None
wheel = RB.W.build("Wheel", RB.WHEEL_R, RB.WHEEL_W, mats=RB.palette())
wheel.hide_render = True

# Terrain mesh: a window around the spawn, coloured from the splat map.
from PIL import Image  # noqa: E402
splat = np.asarray(Image.open(os.path.join(SRC, "desert_splat.png"))).astype(float)[::-1] / 255
cols = np.array([[0.78, 0.50, 0.30], [0.50, 0.38, 0.29], [0.66, 0.47, 0.33], [0.45, 0.20, 0.12]]) ** 2.2 * 1.0
R, STEP = 380, 2
x0, x1 = max(0, sp["x"] - R), min(SIZE - 1, sp["x"] + R)
z0, z1 = max(0, sp["z"] - R), min(SIZE - 1, sp["z"] + R)
xs = np.arange(x0, x1, STEP)
zs = np.arange(z0, z1, STEP)
verts, faces, vcols = [], [], []
for j, uz in enumerate(zs):
    for i, ux in enumerate(xs):
        verts.append(to_b(ux, height(ux, uz), uz))
        sx, sz = int(ux / SIZE * (splat.shape[1] - 1)), int(uz / SIZE * (splat.shape[0] - 1))
        vcols.append(tuple((splat[sz, sx, :, None] * cols).sum(0)) + (1.0,))
nx = len(xs)
for j in range(len(zs) - 1):
    for i in range(nx - 1):
        a = j * nx + i
        faces.append((a, a + 1, a + nx + 1, a + nx))
mesh = bpy.data.meshes.new("Terrain")
mesh.from_pydata(verts, [], faces)
attr = mesh.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
for k, c in enumerate(vcols):
    attr.data[k].color = c
for p in mesh.polygons:
    p.use_smooth = True
terrain = bpy.data.objects.new("Terrain", mesh)
bpy.context.scene.collection.objects.link(terrain)
tm = bpy.data.materials.new("TerrainMat")
try:
    tm.use_nodes = True
except Exception:
    pass
nt = tm.node_tree
vc = nt.nodes.new("ShaderNodeVertexColor")
vc.layer_name = "Col"
nt.links.new(vc.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
nt.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.95
terrain.data.materials.append(tm)

# Props near the spawn as linked duplicates.
scatter = json.load(open(os.path.join(SRC, "desert_scatter.json")))["props"]
placed = 0
for p in scatter:
    if abs(p["x"] - sp["x"]) > R or abs(p["z"] - sp["z"]) > R:
        continue
    src = props.get(f'{p["kind"]}_{p["variant"]}')
    if not src:
        continue
    o = bpy.data.objects.new(src.name + "_i", src.data)
    bpy.context.scene.collection.objects.link(o)
    s = p["scale"]
    o.location = to_b(p["x"], height(p["x"], p["z"]) - p["sink"] * s, p["z"])
    o.scale = (s, s, s)
    o.rotation_euler = Euler((0, 0, math.radians(p["yaw"])))
    placed += 1
print("placed", placed)

# Vehicle at spawn facing the spawn yaw (Unity yaw about +Y; in Blender space rotate about Z).
yaw = math.radians(sp["yaw"])
fwd_u = Vector((math.sin(yaw), 0, math.cos(yaw)))
pos_u = Vector((sp["x"], height(sp["x"], sp["z"]), sp["z"]))
veh_rot = Euler((0, 0, -yaw))   # model faces Blender -Y; Unity +Z maps to Blender -Y here
body.location = to_b(*pos_u)
body.rotation_euler = veh_rot
for name, sx_, y in (("FL", 1, RB.FRONT_Y), ("FR", -1, RB.FRONT_Y), ("RL", 1, RB.REAR_Y), ("RR", -1, RB.REAR_Y)):
    w = bpy.data.objects.new("W" + name, wheel.data)
    bpy.context.scene.collection.objects.link(w)
    w.parent = body
    w.location = (sx_ * RB.TRACK_X, y, RB.WHEEL_Z)
    if sx_ < 0:
        w.rotation_euler = Euler((0, 0, math.pi))

# Golden-hour sun matching the Unity scene (Euler(22, 19, 0) in Unity = light pointing that way).
light_u = Vector((math.sin(math.radians(19)) * math.cos(math.radians(22)), -math.sin(math.radians(22)),
                  math.cos(math.radians(19)) * math.cos(math.radians(22))))
light_b = to_b(*light_u)
sun_d = bpy.data.lights.new("Sun", "SUN")
sun_d.energy = 4.2
sun_d.color = (1.0, 0.78, 0.58)
sun_d.angle = math.radians(1.5)
sun = bpy.data.objects.new("Sun", sun_d)
sun.rotation_euler = light_b.to_track_quat("-Z", "Y").to_euler()
bpy.context.scene.collection.objects.link(sun)

world = bpy.data.worlds.new("W")
bpy.context.scene.world = world
try:
    world.use_nodes = True
except Exception:
    pass
wn = world.node_tree
sky = wn.nodes.new("ShaderNodeTexSky")
for attr_, val in (("sky_type", "NISHITA"), ("sun_elevation", math.radians(22)),
                   ("sun_rotation", math.atan2(-light_b.x, -light_b.y))):
    try:
        setattr(sky, attr_, val)
    except Exception:
        pass
bg = wn.nodes["Background"]
bg.inputs["Strength"].default_value = 0.3
wn.links.new(sky.outputs["Color"], bg.inputs["Color"])

# Chase camera: behind and above the vehicle.
cam_d = bpy.data.cameras.new("Cam")
cam_d.lens = 28
cam_d.clip_end = 2000
cam = bpy.data.objects.new("Cam", cam_d)
bpy.context.scene.collection.objects.link(cam)
cam_u = pos_u - fwd_u * 7.5 + Vector((0, 2.8, 0))
cam.location = to_b(*cam_u)
look_u = pos_u + fwd_u * 6 + Vector((0, 1.0, 0))
cam.rotation_euler = (to_b(*look_u) - cam.location).to_track_quat("-Z", "Y").to_euler()
sc = bpy.context.scene
sc.camera = cam
# Distance haze.
sc.render.engine = "CYCLES"
sc.cycles.samples = samples
sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
try:
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
print("Saved", out)
