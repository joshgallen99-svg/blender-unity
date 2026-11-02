"""Highline Pass scenery: treeline shrubs, tundra plants, angular gneiss boulders, scree and snow poles.
(The firs at the treeline are the forest firs from ForestProps.fbx, scattered smaller.)

Run:  python blender/props/alpine_props.py
Writes: Assets/Models/Props/AlpineProps.fbx
Objects (origin at the base centre, Z up in Blender):
  Krummholz_0..1   wind-stunted conifer mats, flagged away from the prevailing wind
  Tussock_0..1     tundra grass tussocks (cards)
  Cushion_0        cushion plants in flower (cards)
  SBoulder_0..3    angular, foliated gneiss boulders (+ _LOD1)
  ScreeRock_0..2   loose rock fragments for the talus fans
  SnowPole_0       orange-and-black snow pole marking the pass track
Material names map to Unity materials (Assets/Editor/MaterialLibrary.cs).
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402,F401
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

from lib import common as C  # noqa: E402
import forest_props as FP  # noqa: E402


def palette():
    m = C.material
    return {
        "BarkFir": m("BarkFir", (0.30, 0.22, 0.17), 0.0, 0.9),
        "FirNeedles": m("FirNeedles", (0.14, 0.24, 0.13), 0.0, 0.8),
        "TundraGrass": m("TundraGrass", (0.40, 0.38, 0.20), 0.0, 0.85),
        "AlpineFlowers": m("AlpineFlowers", (0.40, 0.42, 0.25), 0.0, 0.85),
        "AlpineRock": m("AlpineRock", (0.25, 0.25, 0.26), 0.0, 0.85),
        "PoleOrange": m("PoleOrange", (0.85, 0.28, 0.04), 0.0, 0.5),
        "PoleBlack": m("PoleBlack", (0.03, 0.03, 0.03), 0.0, 0.6),
    }


def krummholz(name, seed, M, width, height):
    """Low, dense mat of needle sprays on a few twisted stems, flagged toward +X (downwind)."""
    rnd = random.Random(seed)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    for s in range(3):
        base = Vector((rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), -0.1))
        tip = base + Vector((rnd.uniform(0.2, 0.6), rnd.uniform(-0.3, 0.3), height * rnd.uniform(0.6, 0.95)))
        FP.branch_tube(bm, uv, base, tip, 0.07, 0.03, 5, 0)
    for i in range(int(26 * width)):
        # Sprays sit in a flattened, lopsided dome: longer and lower on the downwind side.
        a = rnd.uniform(0, 2 * math.pi)
        r = width * 0.5 * math.sqrt(rnd.random())
        downwind = 0.5 + 0.5 * math.cos(a)
        c = Vector((math.cos(a) * r * (0.7 + 0.6 * downwind), math.sin(a) * r * 0.8, 0))
        c.z = height * (1 - (r / (width * 0.6)) ** 2) * rnd.uniform(0.55, 1.0) + 0.1
        d = Vector((math.cos(a) + 0.6, math.sin(a), rnd.uniform(-0.1, 0.4))).normalized()
        L = rnd.uniform(0.6, 1.0) * (0.8 + 0.5 * downwind)
        root = c - d * L * 0.3
        tipp = c + d * L * 0.7
        side = d.cross(Vector((0, 0, 1))).normalized()
        for tilt in (0.5, -0.5):
            sv = (side * math.cos(tilt) + Vector((0, 0, 1)) * math.sin(tilt)).normalized() * (L * 0.35)
            FP.quad(bm, uv, [root - sv * 0.4, root + sv * 0.4, tipp + sv, tipp - sv], [(0.3, 0), (0.7, 0), (1, 1), (0, 1)], 1)
    obj = FP.new_obj(name, bm, [M["BarkFir"], M["FirNeedles"]])
    FP.bent_normals(obj, 0.45, 0.55, mat_index=1)
    return obj


def gneiss(name, seed, size, mat, subdiv=4, ratio=0.3, cuts=6):
    """Angular boulder: a lumpy sphere clipped hard by several planes (broken along joints)."""
    rnd = random.Random(seed)
    off = Vector((rnd.uniform(-90, 90), rnd.uniform(-90, 90), rnd.uniform(-90, 90)))
    planes = []
    for _ in range(cuts):
        n = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.4, 1.0))).normalized()
        planes.append((n, rnd.uniform(0.5, 0.8)))
    fol = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(0.5, 1.5))).normalized()
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    for v in bm.verts:
        p = v.co.copy()
        p *= 1 + 0.12 * FP.fbm(p * 0.9 + off, 3)
        for n, dist in planes:
            d = p.dot(n) - dist
            if d > 0:
                p -= n * d
        # Foliation: faint parallel steps.
        t = p.dot(fol) * 6.0
        p += fol * (0.015 * math.sin(t * math.pi))
        p.z = max(p.z, -0.4)
        v.co = Vector((p.x * size[0], p.y * size[1], p.z * size[2]))
    obj = C.from_bmesh(name, bm, mat)
    FP.decimate(obj, ratio)
    FP.ground(obj, 0.1 * size[2])
    C.smooth_by_angle(obj, 30)
    return obj


def snow_pole(name, M):
    """2.4 m pole, black with orange bands (one material slot each)."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    z = -0.3
    bands = [(0.9, 0), (0.25, 1), (0.25, 0), (0.25, 1), (0.25, 0), (0.5, 1)]
    for length, mi in bands:
        FP.branch_tube(bm, uv, Vector((0, 0, z)), Vector((0, 0, z + length)), 0.028, 0.028, 6, mi)
        z += length
    return FP.new_obj(name, bm, [M["PoleBlack"], M["PoleOrange"]])


def build():
    C.reset_scene()
    M = palette()
    objs = []
    objs.append(krummholz("Krummholz_0", 81, M, 2.6, 1.2))
    objs.append(krummholz("Krummholz_1", 82, M, 1.8, 0.9))
    objs.append(FP.cards_plant("Tussock_0", 91, M["TundraGrass"], 8, 0.35, 0.45, 0.5, flat=0.25))
    objs.append(FP.cards_plant("Tussock_1", 92, M["TundraGrass"], 11, 0.5, 0.55, 0.6, flat=0.3))
    objs.append(FP.cards_plant("Cushion_0", 93, M["AlpineFlowers"], 7, 0.35, 0.25, 0.4, flat=0.5))
    for i, size in enumerate([(1.3, 1.0, 0.8), (2.2, 1.6, 1.3), (3.4, 2.4, 2.0), (0.9, 0.8, 0.55)]):
        b = gneiss(f"SBoulder_{i}", 100 + i, size, M["AlpineRock"], subdiv=5, ratio=0.14)
        objs += [b, FP.lod_copy(b, 0.3)]
    for i, size in enumerate([(0.45, 0.35, 0.25), (0.7, 0.5, 0.35), (0.3, 0.28, 0.2)]):
        objs.append(gneiss(f"ScreeRock_{i}", 110 + i, size, M["AlpineRock"], subdiv=2, ratio=0.6, cuts=5))
    objs.append(snow_pole("SnowPole_0", M))
    return objs


if __name__ == "__main__":
    objs = build()
    for o in objs:
        print(f"{o.name:16s} tris={C.tri_count(o):5d}  size={tuple(round(d, 2) for d in o.dimensions)}")
    C.export_fbx(objs, C.path_in_repo("Assets", "Models", "Props", "AlpineProps.fbx"))
