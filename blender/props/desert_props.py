"""Desert scenery: boulders, rocks, scrub bushes, yuccas and dead trees.

Run:  python blender/props/desert_props.py
Writes: Assets/Models/Props/DesertProps.fbx
Objects: Boulder_0..4, Rock_0..4, Scrub_0..2, Yucca_0..1, DeadTree_0..1 (origin at the base centre).
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import bpy  # noqa: E402,F401
import bmesh  # noqa: E402
from mathutils import Matrix, Vector, noise  # noqa: E402

from lib import common as C  # noqa: E402


def palette():
    m = C.material
    return {
        "RockRed": m("RockRed", (0.42, 0.19, 0.11), 0.0, 0.88),
        "RockPale": m("RockPale", (0.62, 0.42, 0.29), 0.0, 0.9),
        "RockDust": m("RockDust", (0.78, 0.55, 0.36), 0.0, 0.95),
        "Foliage": m("Foliage", (0.26, 0.31, 0.15), 0.0, 0.8),
        "FoliageDry": m("FoliageDry", (0.45, 0.39, 0.22), 0.0, 0.85),
        "Yucca": m("Yucca", (0.25, 0.36, 0.27), 0.0, 0.6),
        "Bark": m("Bark", (0.33, 0.28, 0.23), 0.0, 0.9),
    }


def decimate(obj, ratio):
    mod = obj.modifiers.new("Dec", "DECIMATE")
    mod.ratio = ratio
    C.apply_modifiers(obj)


def rock(name, seed, size, M, base_mat, subdiv=3, ratio=0.3, lumpy=0.38, strata=0.0):
    rnd = random.Random(seed)
    off = Vector((rnd.uniform(-50, 50), rnd.uniform(-50, 50), rnd.uniform(-50, 50)))
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    sx_, sy_, sz_ = size
    floor = -0.3
    for v in bm.verts:
        p = v.co.copy()
        d = 1 + lumpy * noise.noise(p * 1.2 + off) + 0.12 * noise.noise(p * 3.5 + off)
        if strata:
            d += strata * math.sin(p.z * 9 + noise.noise(p * 2 + off) * 2) * 0.5
        p *= d
        p.z = max(p.z, floor)
        v.co = Vector((p.x * sx_, p.y * sy_, (p.z - floor) * sz_))
    obj = C.from_bmesh(name, bm)
    decimate(obj, ratio)
    obj.data.materials.append(base_mat)
    obj.data.materials.append(M["RockDust"])
    for poly in obj.data.polygons:  # sandy dusting on upward faces
        poly.material_index = 1 if poly.normal.z > 0.82 else 0
    C.smooth_by_angle(obj, 18)
    return obj


def scrub(name, seed, M, dry=False):
    rnd = random.Random(seed)
    parts = []
    mat = M["FoliageDry"] if dry else M["Foliage"]
    for i in range(rnd.randint(6, 9)):
        a = rnd.uniform(0, 2 * math.pi)
        r = rnd.uniform(0.0, 0.45)
        rad = rnd.uniform(0.25, 0.42)
        c = (math.cos(a) * r, math.sin(a) * r, rad * 0.7 + rnd.uniform(0, 0.25))
        s = C.sphere(f"{name}_b{i}", rad, c, mat, 1)
        for v in s.data.vertices:
            v.co += Vector(v.co - Vector(c)) * 0.25 * noise.noise(v.co * 4 + Vector((seed, i, 0)))
        parts.append(s)
    for i in range(4):
        a = i * math.pi / 2 + rnd.uniform(-0.3, 0.3)
        parts.append(C.tube(f"{name}_st{i}", (0, 0, 0), (math.cos(a) * 0.3, math.sin(a) * 0.3, 0.35), 0.03,
                            M["Bark"], 5))
    obj = C.join(parts, name)
    C.smooth_by_angle(obj, 25)
    return obj


def leaf(bm, base, direction, length, width, twist):
    """Thin tapered blade (triangular prism) from base along direction."""
    d = direction.normalized()
    side = d.cross(Vector((0, 0, 1)))
    if side.length < 1e-3:
        side = Vector((1, 0, 0))
    side.normalize()
    side = Matrix.Rotation(twist, 3, d) @ side
    thick = side.cross(d).normalized() * width * 0.25
    b0 = bm.verts.new(base + side * width)
    b1 = bm.verts.new(base - side * width)
    b2 = bm.verts.new(base + thick)
    tip = bm.verts.new(base + d * length)
    for f in ((b0, b1, tip), (b1, b2, tip), (b2, b0, tip), (b0, b2, b1)):
        bm.faces.new(f)


def yucca(name, seed, M, stalk=False):
    rnd = random.Random(seed)
    bm = bmesh.new()
    height = rnd.uniform(0.3, 0.6)
    for i in range(46):
        a = i * 2.399963 + rnd.uniform(-0.1, 0.1)       # golden angle
        tilt = 0.15 + 1.25 * (i / 46) ** 0.8              # inner leaves upright, outer spread
        d = Vector((math.cos(a) * math.sin(tilt), math.sin(a) * math.sin(tilt), math.cos(tilt)))
        leaf(bm, Vector((0, 0, height)), d, rnd.uniform(0.55, 0.85), 0.035, rnd.uniform(-0.4, 0.4))
    leaves = C.from_bmesh(name + "_leaves", bm, M["Yucca"])
    parts = [leaves, C.cylinder(name + "_trunk", 0.09, height + 0.05, (0, 0, (height + 0.05) / 2), "Z", 8, M["Bark"],
                                radius2=0.07)]
    if stalk:
        parts.append(C.tube(name + "_stalk", (0, 0, height), (0.05, 0.02, height + 1.6), 0.018, M["Bark"], 5))
        for k in range(7):
            z = height + 1.0 + k * 0.09
            parts.append(C.sphere(f"{name}_fl{k}", 0.055, (0.03 + 0.05 * math.sin(k * 2.1), 0.05 * math.cos(k * 2.1), z),
                                  M["RockDust"], 0))
    obj = C.join(parts, name)
    C.smooth_by_angle(obj, 30)
    return obj


def dead_tree(name, seed, M):
    rnd = random.Random(seed)
    parts = []

    def branch(p, d, length, radius, depth):
        end = p + d.normalized() * length
        end += Vector((rnd.uniform(-0.15, 0.15), rnd.uniform(-0.15, 0.15), 0)) * length
        parts.append(C.tube(f"{name}_{len(parts)}", p, end, radius, M["Bark"], 6 if depth < 2 else 5))
        parts.append(C.sphere(f"{name}_k{len(parts)}", radius * 1.02, end, M["Bark"], 0))
        if depth >= 3 or radius < 0.025:
            return
        for _ in range(rnd.randint(2, 3)):
            nd = (d.normalized() + Vector((rnd.uniform(-0.9, 0.9), rnd.uniform(-0.9, 0.9), rnd.uniform(0.0, 0.6))))
            branch(end, nd, length * rnd.uniform(0.55, 0.75), radius * 0.62, depth + 1)

    branch(Vector((0, 0, -0.1)), Vector((rnd.uniform(-0.2, 0.2), rnd.uniform(-0.2, 0.2), 1)), rnd.uniform(1.6, 2.2),
           0.16, 0)
    obj = C.join(parts, name)
    C.smooth_by_angle(obj, 40)
    return obj


def build():
    C.reset_scene()
    M = palette()
    objs = []
    for i in range(5):
        base = M["RockPale"] if i % 3 == 2 else M["RockRed"]
        objs.append(rock(f"Boulder_{i}", 10 + i, (1.0 + 0.3 * (i % 2), 0.9, 0.75 + 0.15 * i), M, base,
                         subdiv=3, ratio=0.6, strata=0.12 if i in (1, 3) else 0.0))
    for i in range(5):
        base = M["RockPale"] if i % 2 else M["RockRed"]
        objs.append(rock(f"Rock_{i}", 30 + i, (0.4, 0.35, 0.22 + 0.06 * i), M, base, subdiv=2, ratio=0.75))
    for i in range(3):
        objs.append(scrub(f"Scrub_{i}", 50 + i, M, dry=(i == 2)))
    for i in range(2):
        objs.append(yucca(f"Yucca_{i}", 60 + i, M, stalk=(i == 1)))
    for i in range(2):
        objs.append(dead_tree(f"DeadTree_{i}", 70 + i, M))
    return objs


if __name__ == "__main__":
    objs = build()
    for o in objs:
        print(f"{o.name:12s} tris={C.tri_count(o)}")
    C.export_fbx(objs, C.path_in_repo("Assets", "Models", "Props", "DesertProps.fbx"))
