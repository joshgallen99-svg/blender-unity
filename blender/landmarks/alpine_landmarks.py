"""Highline Pass landmarks: the stone hut, summit cairns and sign, the old silver mine and the weather station.

Run:  python blender/landmarks/alpine_landmarks.py
Writes: Assets/Models/Landmarks/AlpineLandmarks.fbx
Objects (origin at the base centre, front facing Blender -Y / Unity +Z):
  StoneHut        dry-stone mountain hut with a red tin roof, chimney, shutters and a bench
  Cairn           stacked flat stones (~1.7 m)
  SummitSign      timber post with the pass sign and a summit-register box
  MineAdit        timber-framed mine entrance set into a rock knoll, with a spoil heap
  OreCart         rusty ore cart; Rails  8 m of narrow-gauge track on sleepers
  WeatherStation  lattice mast with anemometer and vane, solar panel, instrument screen, fenced pad
Camp props (Tent, FireRing, Crates, Signpost) come from DesertLandmarks.fbx; WoodPile/LogPile from ForestLandmarks.fbx.
"""
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

import bpy  # noqa: E402,F401
import bmesh  # noqa: E402
from mathutils import Vector, noise  # noqa: E402

from lib import common as C  # noqa: E402


def palette():
    m = C.material
    return {
        "AlpineRock": m("AlpineRock", (0.25, 0.25, 0.26), 0.0, 0.85),
        "HutStone": m("HutStone", (0.30, 0.30, 0.30), 0.0, 0.85),
        "RoofRed": m("RoofRed", (0.32, 0.05, 0.035), 0.3, 0.55),
        "Wood": m("Wood", (0.45, 0.39, 0.32), 0.0, 0.85),
        "WoodDark": m("WoodDark", (0.25, 0.20, 0.16), 0.0, 0.9),
        "Galvanized": m("Galvanized", (0.55, 0.57, 0.58), 0.7, 0.45),
        "Rust": m("Rust", (0.30, 0.13, 0.06), 0.3, 0.8),
        "Steel": m("Steel", (0.07, 0.07, 0.075), 0.6, 0.45),
        "Trim": m("Trim", (0.035, 0.035, 0.037), 0.0, 0.78),
        "Glass": m("Glass", (0.02, 0.03, 0.035), 0.0, 0.04),
        "PaintRoof": m("PaintRoof", (0.80, 0.77, 0.69), 0.0, 0.38),
        "Accent": m("Accent", (0.85, 0.36, 0.06), 0.0, 0.4),
    }


def finish(obj, smooth=35, uv_scale=1.0):
    C.box_uv(obj, uv_scale)
    C.smooth_by_angle(obj, smooth)
    return obj


def stone(name, seed, size, center, mat, subdiv=2, flat=1.0):
    """A rough, flattened stone (lumpy icosphere clipped by a couple of planes)."""
    rnd = random.Random(seed)
    off = Vector((rnd.uniform(-50, 50), rnd.uniform(-50, 50), rnd.uniform(-50, 50)))
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    cuts = [(Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.3, 0.3))).normalized(), rnd.uniform(0.6, 0.85))
            for _ in range(3)]
    for v in bm.verts:
        p = v.co * (1 + 0.15 * noise.noise(v.co * 1.3 + off))
        for n, d in cuts:
            e = p.dot(n) - d
            if e > 0:
                p -= n * e
        p.z = max(min(p.z, 0.75 * flat), -0.75 * flat)
        v.co = Vector((p.x * size[0], p.y * size[1], p.z * size[2])) + Vector(center)
    return C.from_bmesh(name, bm, mat)


def gable_roof(M, W, D, eave_z, ridge_z, over, thick, mat):
    parts = []
    roof_len = D + over * 2
    for s in (-1, 1):
        ex, ez = s * (W / 2 + over), eave_z
        rx, rz = 0.0, ridge_z
        y0, y1 = -roof_len / 2, roof_len / 2
        bottom = [(ex, y0, ez), (rx, y0, rz), (rx, y1, rz), (ex, y1, ez)]
        topp = [(x, y, z + thick) for x, y, z in bottom]
        if s < 0:
            bottom, topp = bottom[::-1], topp[::-1]
        parts.append(C.hull("roof", bottom, topp, mat))
    return parts


def stone_hut(M):
    W, D, Hh = 8.0, 6.0, 2.9
    parts = [C.box("plinth", (W + 0.6, D + 0.6, 0.6), (0, 0, 0.0), M["HutStone"], 0.1)]
    parts.append(C.box("walls", (W, D, Hh), (0, 0, Hh / 2 + 0.2), M["HutStone"], 0.12))
    ridge = Hh + 0.2 + 2.3
    # Stone gables.
    for s in (-1, 1):
        y = s * D / 2
        tri_b = [(-W / 2, y, Hh + 0.2), (W / 2, y, Hh + 0.2), (0.1, y, ridge - 0.1), (-0.1, y, ridge - 0.1)]
        a = [(x, y - 0.3 * s, z) for x, _, z in tri_b]
        b = [(x, y, z) for x, _, z in tri_b]
        parts.append(C.hull("gable", a if s > 0 else b, b if s > 0 else a, M["HutStone"]))
    parts += gable_roof(M, W, D, Hh + 0.0, ridge, 0.55, 0.12, M["RoofRed"])
    parts.append(C.box("ridgecap", (0.3, D + 1.1, 0.14), (0, 0, ridge + 0.1), M["RoofRed"], 0.02))
    parts.append(C.box("chimney", (0.8, 0.8, 2.2), (W / 2 - 1.4, 1.2, ridge - 0.3), M["HutStone"], 0.06))
    parts.append(C.box("chimcap", (1.0, 1.0, 0.12), (W / 2 - 1.4, 1.2, ridge + 0.85), M["Steel"], 0.02))
    # Front: door, two shuttered windows, bench; a side window.
    fy = -D / 2
    parts.append(C.box("door", (1.0, 0.14, 2.0), (-1.6, fy - 0.03, 1.2), M["WoodDark"], 0.02))
    parts.append(C.box("doorframe", (1.25, 0.1, 2.2), (-1.6, fy - 0.0, 1.25), M["Wood"], 0.02))
    for x in (0.9, 2.8):
        parts.append(C.box("window", (0.9, 0.1, 0.9), (x, fy - 0.04, 1.75), M["Glass"], 0.01))
        parts.append(C.box("frame", (1.05, 0.08, 1.05), (x, fy - 0.02, 1.75), M["PaintRoof"], 0.01))
        for sx in (-1, 1):
            parts.append(C.box("shutter", (0.5, 0.06, 1.0), (x + sx * 0.78, fy - 0.1, 1.75), M["RoofRed"], 0.01))
    parts.append(C.box("bench", (2.2, 0.45, 0.08), (1.9, fy - 0.55, 0.65), M["Wood"], 0.02))
    for x in (1.0, 2.8):
        parts.append(C.box("benchleg", (0.08, 0.4, 0.45), (x, fy - 0.55, 0.42), M["WoodDark"], 0.01))
    parts.append(C.box("sign", (1.6, 0.06, 0.4), (-1.6, fy - 0.08, 2.65), M["Wood"], 0.02))
    parts.append(C.box("sidewin", (0.1, 0.8, 0.8), (W / 2 + 0.03, -0.8, 1.8), M["Glass"], 0.01))
    obj = C.join(parts, "StoneHut")
    return finish(obj, 30, 1.0)


def cairn(M):
    rnd = random.Random(7)
    parts = []
    z = 0.0
    r = 0.75
    k = 0
    while r > 0.16:
        t = r * rnd.uniform(0.38, 0.5)
        parts.append(stone(f"c{k}", 20 + k, (r, r * rnd.uniform(0.8, 1.0), t), (rnd.uniform(-0.06, 0.06), rnd.uniform(-0.06, 0.06), z + t * 0.6),
                           M["HutStone"], 2))
        z += t * 1.25
        r *= rnd.uniform(0.78, 0.88)
        k += 1
    obj = C.join(parts, "Cairn")
    return finish(obj, 40, 0.5)


def summit_sign(M):
    parts = [C.box("post", (0.16, 0.16, 2.6), (0, 0, 1.0), M["Wood"], 0.02)]
    parts.append(C.box("board", (1.5, 0.07, 0.45), (0, -0.12, 2.0), M["Wood"], 0.02))
    parts.append(C.box("board2", (1.1, 0.07, 0.3), (0.1, -0.12, 1.5), M["WoodDark"], 0.02))
    parts.append(C.box("register", (0.32, 0.22, 0.26), (0, -0.2, 1.05), M["Galvanized"], 0.02))
    for k in range(5):
        a = k * 2 * math.pi / 5
        parts.append(stone(f"s{k}", 40 + k, (0.35, 0.3, 0.2), (math.cos(a) * 0.32, math.sin(a) * 0.32, 0.05), M["HutStone"], 1))
    obj = C.join(parts, "SummitSign")
    return finish(obj, 35, 0.6)


def mine_adit(M):
    """Rock knoll with a timber-framed tunnel mouth facing -Y, and a spoil heap beside it."""
    parts = []
    knoll = stone("knoll", 61, (7.5, 6.5, 6.0), (0, 7.2, 0.4), M["AlpineRock"], 4, flat=1.2)
    parts.append(knoll)
    parts.append(C.box("void", (2.0, 1.6, 2.4), (0, 0.6, 1.2), M["Trim"], 0.02))
    for sx in (-1, 1):
        parts.append(C.box("post", (0.28, 0.28, 2.7), (sx * 1.15, -1.1, 1.25), M["WoodDark"], 0.02))
        parts.append(C.box("post2", (0.24, 0.24, 2.6), (sx * 1.1, -0.1, 1.25), M["WoodDark"], 0.02))
    parts.append(C.box("lintel", (2.9, 0.34, 0.32), (0, -1.1, 2.7), M["WoodDark"], 0.02))
    parts.append(C.box("lintel2", (2.7, 0.3, 0.28), (0, -0.1, 2.6), M["WoodDark"], 0.02))
    for k in range(5):
        parts.append(C.box("lagging", (2.6, 0.3, 0.1), (0, -1.0 + k * 0.35, 2.9), M["Wood"], 0.01))
    parts.append(C.box("plank", (1.6, 0.06, 0.32), (0, -1.3, 3.15), M["Wood"], 0.01))
    # Spoil heap: a fan of broken rock to one side.
    for k in range(9):
        rnd = random.Random(70 + k)
        parts.append(stone(f"sp{k}", 70 + k, (rnd.uniform(1.2, 2.4), rnd.uniform(1.0, 2.0), rnd.uniform(0.5, 1.0)),
                           (4.0 + rnd.uniform(-1.5, 2.5), -2.0 + rnd.uniform(-2.0, 1.5), 0.0), M["AlpineRock"], 2))
    obj = C.join(parts, "MineAdit")
    return finish(obj, 35, 1.0)


def ore_cart(M):
    parts = [C.box("tub", (0.9, 1.5, 0.75), (0, 0, 0.85), M["Rust"], 0.05)]
    parts.append(C.box("chassis", (0.7, 1.4, 0.12), (0, 0, 0.42), M["Steel"], 0.02))
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(C.cylinder("wheel", 0.2, 0.08, (sx * 0.38, sy * 0.48, 0.22), axis="X", verts=12, mat=M["Steel"]))
    parts.append(C.box("ore", (0.75, 1.3, 0.2), (0, 0, 1.2), M["AlpineRock"], 0.05))
    obj = C.join(parts, "OreCart")
    return finish(obj, 35, 0.8)


def rails(M):
    parts = []
    L = 8.0
    for sx in (-1, 1):
        parts.append(C.box("rail", (0.06, L, 0.1), (sx * 0.3, 0, 0.17), M["Steel"], 0.01))
    for k in range(12):
        parts.append(C.box("sleeper", (1.0, 0.18, 0.12), (0, -L / 2 + 0.35 + k * (L - 0.7) / 11, 0.06), M["WoodDark"], 0.01))
    obj = C.join(parts, "Rails")
    return finish(obj, 35, 1.0)


def weather_station(M):
    parts = [C.box("pad", (5.0, 5.0, 0.3), (0, 0, 0.0), M["AlpineRock"], 0.05)]
    H = 6.0
    for k in range(3):
        a = k * 2 * math.pi / 3
        p0 = (math.cos(a) * 0.3, math.sin(a) * 0.3, 0.1)
        p1 = (math.cos(a) * 0.12, math.sin(a) * 0.12, H)
        parts.append(C.tube("leg", p0, p1, 0.03, M["Galvanized"], 6))
    for z in range(1, 6):
        parts.append(C.cylinder("ring", 0.3 - 0.03 * z, 0.04, (0, 0, z * 1.0), axis="Z", verts=10, mat=M["Galvanized"]))
    parts.append(C.tube("arm", (-0.8, 0, H), (0.8, 0, H), 0.025, M["Galvanized"], 6))
    for k in range(3):                                            # anemometer cups
        a = k * 2 * math.pi / 3
        c = (0.8 + math.cos(a) * 0.18, math.sin(a) * 0.18, H + 0.25)
        parts.append(C.tube("cuparm", (0.8, 0, H + 0.25), c, 0.01, M["Galvanized"], 4))
        parts.append(C.sphere("cup", 0.06, c, M["PaintRoof"], 1))
    parts.append(C.tube("vanepost", (0.8, 0, H), (0.8, 0, H + 0.2), 0.02, M["Galvanized"], 6))
    parts.append(C.box("vane", (0.04, 0.5, 0.2), (-0.8, 0.15, H + 0.2), M["Accent"], 0.01))
    parts.append(C.box("panel", (1.0, 0.06, 0.7), (0, -0.45, 3.0), M["Glass"], 0.01))
    parts.append(C.box("panelframe", (1.08, 0.04, 0.78), (0, -0.42, 3.0), M["Galvanized"], 0.01))
    # Instrument screen (louvred box) on a post, and a logger cabinet.
    parts.append(C.box("screenpost", (0.08, 0.08, 1.4), (1.6, -1.2, 0.8), M["Galvanized"], 0.01))
    parts.append(C.box("screen", (0.6, 0.5, 0.55), (1.6, -1.2, 1.6), M["PaintRoof"], 0.02))
    for z in range(4):
        parts.append(C.box("louvre", (0.62, 0.52, 0.03), (1.6, -1.2, 1.38 + z * 0.13), M["PaintRoof"], 0.0))
    parts.append(C.box("cabinet", (0.6, 0.4, 0.9), (-0.6, -0.5, 0.6), M["PaintRoof"], 0.02))
    # Low fence round the pad.
    for k in range(12):
        a = k * 2 * math.pi / 12
        parts.append(C.box("fpost", (0.07, 0.07, 1.1), (math.cos(a) * 2.3, math.sin(a) * 2.3, 0.55), M["Galvanized"], 0.01))
    for k in range(12):
        a0, a1 = k * 2 * math.pi / 12, (k + 1) * 2 * math.pi / 12
        if k == 9:
            continue                                               # gate gap
        for z in (0.5, 1.0):
            parts.append(C.tube("wire", (math.cos(a0) * 2.3, math.sin(a0) * 2.3, z), (math.cos(a1) * 2.3, math.sin(a1) * 2.3, z), 0.01, M["Galvanized"], 4))
    obj = C.join(parts, "WeatherStation")
    return finish(obj, 35, 1.0)


def build():
    C.reset_scene()
    M = palette()
    return [stone_hut(M), cairn(M), summit_sign(M), mine_adit(M), ore_cart(M), rails(M), weather_station(M)]


if __name__ == "__main__":
    objs = build()
    for o in objs:
        print(f"{o.name:16s} tris={C.tri_count(o):6d}  size={tuple(round(d, 2) for d in o.dimensions)}")
    C.export_fbx(objs, C.path_in_repo("Assets", "Models", "Landmarks", "AlpineLandmarks.fbx"))
