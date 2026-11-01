"""Composition preview of the whole region in Blender: terrain (coloured like the ground shader),
formations, highway and big props. Usage: python render_scene.py out_prefix [samples]
Renders <prefix>_spawn.png (player's first view up the highway) and <prefix>_aerial.png.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402
from PIL import Image  # noqa: E402

from lib import common as C  # noqa: E402
from strata_material import strata_material  # noqa: E402

prefix = sys.argv[1]
samples = int(sys.argv[2]) if len(sys.argv) > 2 else 24
SRC = os.path.join(C.REPO, "Assets", "Terrain", "Source~")
info = json.load(open(os.path.join(SRC, "desert_info.json")))
N, SIZE, H = info["resolution"], info["size"], info["height"]
hm = np.fromfile(os.path.join(SRC, "desert_height.r16"), "<u2").reshape(N, N) / 65535 * H
mask = np.asarray(Image.open(os.path.join(C.REPO, "Assets", "Terrain", "Masks", "desert_mask.png"))).astype(float)[::-1] / 255


def height(x, z):
    fx, fz = np.clip(x / SIZE * (N - 1), 0, N - 1.001), np.clip(z / SIZE * (N - 1), 0, N - 1.001)
    x0, z0 = int(fx), int(fz)
    tx, tz = fx - x0, fz - z0
    return ((hm[z0, x0] * (1 - tx) + hm[z0, x0 + 1] * tx) * (1 - tz) + (hm[z0 + 1, x0] * (1 - tx) + hm[z0 + 1, x0 + 1] * tx) * tz)


def B(x, y, z):
    """Unity (x, y up, z) -> Blender (x, y, z up), matching the FBX export mapping."""
    return Vector((x, z, y))


C.reset_scene()

# Terrain mesh, vertex-coloured: sand / mud / pavement from the mask, strata-coloured rock on slopes.
STEP = 4
xs = np.arange(0, SIZE + 0.1, STEP)
verts, cols = [], []
pal = np.array([[0.30, 0.05, 0.02], [0.50, 0.11, 0.035], [0.68, 0.24, 0.09], [0.74, 0.38, 0.19], [0.80, 0.59, 0.36]])
sand_c, mud_c, pave_c = np.array([0.62, 0.36, 0.22]), np.array([0.62, 0.48, 0.34]), np.array([0.36, 0.22, 0.14])
for z in xs:
    for x in xs:
        y = height(x, z)
        verts.append(B(x, y, z))
        gx = (height(x + 2, z) - height(x - 2, z)) / 4
        gz = (height(x, z + 2) - height(x, z - 2)) / 4
        ny = 1 / math.sqrt(1 + gx * gx + gz * gz)
        mi = mask[min(int(z / SIZE * 1023), 1023), min(int(x / SIZE * 1023), 1023)]
        ground = sand_c * mi[0] + mud_c * mi[1] + pave_c * mi[2]
        rockw = max(mi[3], min(1, max(0, (1 - ny - 0.24) / 0.18)))
        band = pal[int(abs(math.floor(y * 0.33 + 0.4 * math.sin(x * 0.02)))) % len(pal)]
        c = ground * (1 - rockw) + band * rockw
        cols.append((*c, 1))
n = len(xs)
faces = [(j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i) for j in range(n - 1) for i in range(n - 1)]
me = bpy.data.meshes.new("Terrain")
me.from_pydata(verts, [], faces)
ca = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
for k, c in enumerate(cols):
    ca.data[k].color = c
for p in me.polygons:
    p.use_smooth = True
terrain = bpy.data.objects.new("Terrain", me)
bpy.context.scene.collection.objects.link(terrain)
tm = bpy.data.materials.new("TerrainMat")
try:
    tm.use_nodes = True
except Exception:
    pass
vc = tm.node_tree.nodes.new("ShaderNodeVertexColor")
vc.layer_name = "Col"
tm.node_tree.links.new(vc.outputs["Color"], tm.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
tm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.95
me.materials.append(tm)

# Road ribbon.
road = list(zip(info["roadX"], info["roadZ"]))
rv, rf = [], []
for k, (x, z) in enumerate(road):
    x2, z2 = road[min(k + 1, len(road) - 1)]
    x1, z1 = road[max(k - 1, 0)]
    tx, tz = x2 - x1, z2 - z1
    ln = math.hypot(tx, tz) or 1
    rx, rz = tz / ln * 4, -tx / ln * 4
    y = height(x, z) + 0.08
    rv += [B(x - rx, y, z - rz), B(x + rx, y, z + rz)]
    if k:
        a = (k - 1) * 2
        rf.append((a, a + 1, a + 3, a + 2))
rme = bpy.data.meshes.new("Road")
rme.from_pydata(rv, [], rf)
robj = bpy.data.objects.new("Road", rme)
bpy.context.scene.collection.objects.link(robj)
rme.materials.append(C.material("Asphalt", (0.05, 0.05, 0.05), 0.0, 0.7))

# Formations and big props from the exported FBX files.
strata = strata_material()
bpy.ops.import_scene.fbx(filepath=os.path.join(C.REPO, "Assets", "Models", "Formations", "Formations.fbx"))
bpy.ops.import_scene.fbx(filepath=os.path.join(C.REPO, "Assets", "Models", "Props", "DesertProps.fbx"))
bpy.ops.import_scene.fbx(filepath=os.path.join(C.REPO, "Assets", "Models", "Landmarks", "DesertLandmarks.fbx"))
src = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
for o in src.values():
    if o.name not in ("Terrain", "Road"):
        o.hide_render = True
        if o.name.split("_")[0] in ("Mound", "Fin", "Butte", "Spire", "Ledge", "Arch", "Boulder", "Slab", "Hoodoo",
                                    "Rock", "NeedlesEye", "BalancedRock"):
            o.data.materials.clear()
            o.data.materials.append(strata)


def place(name, x, z, yaw, scale, sink):
    s = src.get(name)
    if not s:
        return
    o = bpy.data.objects.new(name + "_i", s.data)
    bpy.context.scene.collection.objects.link(o)
    o.location = B(x, height(x, z) - sink * scale, z)
    o.rotation_euler = Euler((0, 0, -math.radians(yaw)))
    o.scale = (scale, scale, scale)


for f in info["formations"]:
    place(f["model"], f["x"], f["z"], f["yaw"], f["scale"], f["sink"])
for p in json.load(open(os.path.join(SRC, "desert_scatter.json")))["props"]:
    if p["kind"] in ("Boulder", "Hoodoo", "Slab", "DeadTree", "Rock"):
        place(f'{p["kind"]}_{p["variant"]}', p["x"], p["z"], p["yaw"], p["scale"], p["sink"])
for L in info["landmarks"]:
    for pc in L["pieces"]:
        place(pc["model"], pc["x"], pc["z"], pc["yaw"], 1.0, pc["sink"])

# Sky and sun.
world = bpy.data.worlds.new("W")
bpy.context.scene.world = world
try:
    world.use_nodes = True
except Exception:
    pass
wn = world.node_tree
sky = wn.nodes.new("ShaderNodeTexSky")
for attr, val in (("sky_type", "NISHITA"), ("sun_elevation", math.radians(38)), ("sun_rotation", math.radians(200))):
    try:
        setattr(sky, attr, val)
    except Exception:
        pass
wn.nodes["Background"].inputs["Strength"].default_value = 0.35
wn.links.new(sky.outputs["Color"], wn.nodes["Background"].inputs["Color"])
sun_d = bpy.data.lights.new("Sun", "SUN")
sun_d.energy = 4.0
sun_d.color = (1.0, 0.9, 0.76)
sun_d.angle = math.radians(1)
sun = bpy.data.objects.new("Sun", sun_d)
sun.rotation_euler = Euler((math.radians(52), 0, math.radians(200 - 180)))
bpy.context.scene.collection.objects.link(sun)

sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.samples = samples
sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
try:
    sc.view_settings.view_transform = "AgX"
except Exception:
    pass
cam_d = bpy.data.cameras.new("Cam")
cam_d.clip_end = 6000
cam = bpy.data.objects.new("Cam", cam_d)
bpy.context.scene.collection.objects.link(cam)
sc.camera = cam

sp = info["spawn"]
yaw = math.radians(sp["yaw"])
fwd = (math.sin(yaw), math.cos(yaw))
cx, cz = sp["x"] - fwd[0] * 9, sp["z"] - fwd[1] * 9
cam_d.lens = 22
cam.location = B(cx, height(cx, cz) + 2.8, cz)
tgt = B(sp["x"] + fwd[0] * 80, height(sp["x"], sp["z"]) + 3, sp["z"] + fwd[1] * 80)
cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
sc.render.filepath = prefix + "_spawn.png"
bpy.ops.render.render(write_still=True)

cam_d.lens = 24
cam.location = B(SIZE * 0.5, 520, -260)
cam.rotation_euler = (B(SIZE * 0.5, 0, SIZE * 0.55) - cam.location).to_track_quat("-Z", "Y").to_euler()
sc.render.filepath = prefix + "_aerial.png"
bpy.ops.render.render(write_still=True)
print("Saved", prefix)
