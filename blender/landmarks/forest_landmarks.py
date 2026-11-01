"""Forest valley landmarks: ranger's cabin, fire lookout, the old timber bridge and logging-camp props.

Run:  python blender/landmarks/forest_landmarks.py
Writes: Assets/Models/Landmarks/ForestLandmarks.fbx
Objects (origin at the base centre, front facing Blender -Y / Unity +Z):
  LogCabin     log cabin with a shingled gable roof, stone chimney and a porch
  FireLookout  timber lookout tower (~13 m) with a glazed cab, catwalk and stairs
  WoodBridge   30 m timber bridge (origin = middle of the deck surface), log stringers, crib piers, rails
  LogPile      stacked logs at the logging camp
  WoodPile     split firewood stack
Camp props (Tent, FireRing, Crates, Shack, Wreck, Signpost) come from DesertLandmarks.fbx.
"""
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

import bpy  # noqa: E402,F401
from mathutils import Vector  # noqa: E402

from lib import common as C  # noqa: E402


def palette():
    m = C.material
    return {
        "Wood": m("Wood", (0.45, 0.39, 0.32), 0.0, 0.85),
        "WoodDark": m("WoodDark", (0.25, 0.20, 0.16), 0.0, 0.9),
        "BarkFir": m("BarkFir", (0.30, 0.22, 0.17), 0.0, 0.9),
        "WoodEnd": m("WoodEnd", (0.62, 0.48, 0.33), 0.0, 0.8),
        "Granite": m("Granite", (0.45, 0.45, 0.45), 0.0, 0.85),
        "Galvanized": m("Galvanized", (0.55, 0.57, 0.58), 0.7, 0.45),
        "Trim": m("Trim", (0.035, 0.035, 0.037), 0.0, 0.78),
        "Glass": m("Glass", (0.05, 0.07, 0.08), 0.0, 0.1),
    }


def finish(obj, smooth=35, uv_scale=1.0):
    C.box_uv(obj, uv_scale)
    C.smooth_by_angle(obj, smooth)
    return obj


def log_x(name, length, r, center, mat):
    return C.cylinder(name, r, length, center, axis="X", verts=10, mat=mat)


def log_y(name, length, r, center, mat):
    return C.cylinder(name, r, length, center, axis="Y", verts=10, mat=mat)


def log_cabin(M):
    rnd = random.Random(3)
    W, D, r = 7.0, 5.4, 0.16
    parts = [C.box("floor", (W + 2.4, D + 0.4, 0.5), (0, -1.0, 0.0), M["Granite"], 0.05)]
    courses = 9
    for k in range(courses):
        z = 0.35 + k * 2 * r * 0.92
        off = (k % 2) * 0.0
        for s in (-1, 1):
            parts.append(log_x("logx", W + 0.7, r * rnd.uniform(0.95, 1.05), (off, s * D / 2, z + (r if k % 2 else 0)), M["Wood"]))
            parts.append(log_y("logy", D + 0.7, r * rnd.uniform(0.95, 1.05), (s * W / 2, 0, z + (0 if k % 2 else r)), M["Wood"]))
    top = 0.35 + courses * 2 * r * 0.92
    # Gable ends (log-faced triangles) and a shingled roof.
    ridge = top + 2.1
    for s in (-1, 1):
        for k in range(6):
            z = top + k * 0.34
            half = (W / 2) * (1 - (z - top) / (ridge - top))
            if half > 0.3:
                parts.append(log_x("gable", half * 2, 0.15, (0, s * D / 2, z), M["Wood"]))
    roof_len = D + 1.4
    for s in (-1, 1):
        ex, ez = s * (W / 2 + 0.6), top - 0.25          # eave
        rx, rz = 0.0, ridge + 0.05                       # ridge
        nx, nz = -(rz - ez), (rx - ex) * -1              # outward normal of the slope (up and out)
        ln = math.hypot(nx, nz)
        nx, nz = nx / ln * 0.16 * -s, abs(nz / ln * 0.16)
        y0, y1 = -roof_len / 2, roof_len / 2
        bottom = [(ex, y0, ez), (rx, y0, rz), (rx, y1, rz), (ex, y1, ez)]
        topp = [(x + nx, y, z + nz) for x, y, z in bottom]
        if s < 0:
            bottom, topp = bottom[::-1], topp[::-1]
        parts.append(C.hull("roof", bottom, topp, M["WoodDark"]))
    parts.append(log_y("ridge", roof_len, 0.14, (0, 0, ridge + 0.08), M["WoodDark"]))
    # Stone chimney on the right gable.
    parts.append(C.box("chimney", (0.9, 0.9, ridge + 1.2), (W / 2 + 0.45, 1.2, (ridge + 1.2) / 2), M["Granite"], 0.06))
    # Door, windows, porch.
    parts.append(C.box("door", (0.95, 0.12, 2.0), (-0.8, -D / 2 - 0.12, 1.3), M["WoodDark"], 0.02))
    for x in (1.6, -2.6):
        parts.append(C.box("window", (1.0, 0.1, 0.9), (x, -D / 2 - 0.14, 1.75), M["Glass"], 0.01))
        parts.append(C.box("frame", (1.2, 0.08, 1.1), (x, -D / 2 - 0.1, 1.75), M["Trim"], 0.01))
    parts.append(C.box("porch", (W + 0.6, 2.2, 0.18), (0, -D / 2 - 1.2, 0.3), M["WoodDark"], 0.02))
    for x in (-W / 2, -W / 6, W / 6, W / 2):
        parts.append(C.box("post", (0.18, 0.18, 2.6), (x, -D / 2 - 2.15, 1.6), M["Wood"], 0.02))
    porch_roof = C.box("porchroof", (W + 0.8, 2.6, 0.12), (0, -D / 2 - 1.3, 2.95), M["WoodDark"], 0.02)
    parts.append(porch_roof)
    obj = C.join(parts, "LogCabin")
    return finish(obj)


def fire_lookout(M):
    parts = []
    H = 11.0
    base, top = 2.6, 1.7
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(C.tube("leg", (sx * base, sy * base, -0.3), (sx * top, sy * top, H), 0.14, M["Wood"], 8))
            parts.append(C.box("footing", (0.7, 0.7, 0.5), (sx * base, sy * base, 0.0), M["Granite"], 0.05))
    # Cross bracing on each face, four bays.
    bays = 4
    for b in range(bays):
        z0, z1 = H * b / bays, H * (b + 1) / bays
        w0 = base + (top - base) * b / bays
        w1 = base + (top - base) * (b + 1) / bays
        for face in range(4):
            a = face * math.pi / 2
            ca, sa = math.cos(a), math.sin(a)

            def pt(u, w, z):
                return (ca * w * u - sa * w, sa * w * u + ca * w, z)
            parts.append(C.tube("brace", pt(-1, w0, z0), pt(1, w1, z1), 0.06, M["WoodDark"], 6))
            parts.append(C.tube("brace", pt(1, w0, z0), pt(-1, w1, z1), 0.06, M["WoodDark"], 6))
            parts.append(C.tube("girt", pt(-1, w1, z1), pt(1, w1, z1), 0.07, M["Wood"], 6))
    # Stairs: a straight flight up one side (simplified), with a landing.
    for k in range(18):
        z = 0.3 + k * (H - 0.6) / 18
        y = -base - 1.2 + k * 0.0
        parts.append(C.box("tread", (0.9, 0.3, 0.06), (base + 0.8, -2.2 + k * 0.25, z), M["WoodDark"], 0.01))
    parts.append(C.tube("stringer", (base + 0.4, -2.3, 0.2), (base + 0.4, 2.2, H - 0.3), 0.06, M["Wood"], 6))
    parts.append(C.tube("stringer", (base + 1.2, -2.3, 0.2), (base + 1.2, 2.2, H - 0.3), 0.06, M["Wood"], 6))
    # Cab: deck, catwalk, glazed walls, roof.
    parts.append(C.box("deck", (5.4, 5.4, 0.2), (0, 0, H + 0.1), M["WoodDark"], 0.02))
    for x in (-2.6, 2.6):
        parts.append(C.box("rail", (0.08, 5.3, 0.08), (x, 0, H + 1.1), M["Wood"]))
        parts.append(C.box("rail", (5.3, 0.08, 0.08), (0, x, H + 1.1), M["Wood"]))
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(C.box("railpost", (0.1, 0.1, 1.0), (sx * 2.6, sy * 2.6, H + 0.6), M["Wood"]))
    parts.append(C.box("cablow", (3.6, 3.6, 0.9), (0, 0, H + 0.65), M["Wood"], 0.02))
    parts.append(C.box("glass", (3.5, 3.5, 1.3), (0, 0, H + 1.75), M["Glass"], 0.01))
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(C.box("mullion", (0.12, 0.12, 1.35), (sx * 1.78, sy * 1.78, H + 1.75), M["Trim"]))
    parts.append(C.box("cabtop", (3.7, 3.7, 0.25), (0, 0, H + 2.5), M["Wood"], 0.02))
    roof = C.hull("roof", [(-2.5, -2.5, H + 2.6), (2.5, -2.5, H + 2.6), (2.5, 2.5, H + 2.6), (-2.5, 2.5, H + 2.6)],
                  [(-0.15, -0.15, H + 3.8), (0.15, -0.15, H + 3.8), (0.15, 0.15, H + 3.8), (-0.15, 0.15, H + 3.8)],
                  M["Galvanized"])
    parts.append(roof)
    parts.append(C.tube("lightning", (0, 0, H + 3.8), (0, 0, H + 4.8), 0.02, M["Trim"], 4))
    return finish(C.join(parts, "FireLookout"))


def wood_bridge(M, L=30.0, W=4.6):
    rnd = random.Random(9)
    parts = []
    # Deck planks across the bridge (origin = middle of the deck's top surface).
    n = int(L / 0.32)
    for k in range(n):
        y = -L / 2 + (k + 0.5) * L / n
        parts.append(C.box("plank", (W * rnd.uniform(0.97, 1.0), 0.3, 0.12), (rnd.uniform(-0.05, 0.05), y, -0.06), M["Wood"]))
    # Two log stringers and curbs.
    for x in (-W * 0.3, W * 0.3):
        parts.append(log_y("stringer", L + 1.0, 0.36, (x, 0, -0.5), M["BarkFir"]))
    for s in (-1, 1):
        parts.append(C.box("curb", (0.25, L, 0.25), (s * (W / 2 - 0.15), 0, 0.12), M["WoodDark"], 0.02))
    # Railings: posts every 3 m with two rails.
    for k in range(int(L / 3) + 1):
        y = -L / 2 + k * 3
        for s in (-1, 1):
            parts.append(C.box("post", (0.2, 0.2, 1.2), (s * (W / 2 + 0.05), y, 0.6), M["WoodDark"], 0.02))
    for s in (-1, 1):
        for z in (0.55, 1.1):
            parts.append(log_y("rail", L, 0.07, (s * (W / 2 + 0.05), 0, z), M["Wood"]))
    # Crib piers in the river (stacked logs) and abutments on the banks.
    for y in (-L * 0.25, L * 0.25):
        for k in range(8):
            z = -1.0 - k * 0.42
            if k % 2:
                parts.append(log_x("crib", W * 0.9, 0.2, (0, y + 0.0, z), M["BarkFir"]))
                parts.append(log_x("crib", W * 0.9, 0.2, (0, y + 1.4, z), M["BarkFir"]))
            else:
                parts.append(log_y("crib", 1.8, 0.2, (-W * 0.35, y + 0.7, z), M["BarkFir"]))
                parts.append(log_y("crib", 1.8, 0.2, (W * 0.35, y + 0.7, z), M["BarkFir"]))
        parts.append(C.box("fill", (W * 0.8, 1.6, 3.4), (0, y + 0.7, -2.6), M["Granite"], 0.2))
    for s in (-1, 1):
        parts.append(C.box("abutment", (W + 0.6, 2.0, 3.0), (0, s * (L / 2 - 0.8), -1.6), M["Granite"], 0.1))
    return finish(C.join(parts, "WoodBridge"))


def log_pile(M):
    parts = []
    rnd = random.Random(5)
    rows = [5, 4, 3, 2]
    r = 0.33
    for j, count in enumerate(rows):
        for i in range(count):
            x = (i - (count - 1) / 2) * 2 * r
            z = r + j * r * 1.75
            length = 6.0 * rnd.uniform(0.92, 1.05)
            parts.append(log_y("log", length, r * rnd.uniform(0.9, 1.05), (x, rnd.uniform(-0.2, 0.2), z), M["BarkFir"]))
    for s in (-1, 1):
        parts.append(C.box("stake", (0.14, 0.14, 1.6), (s * 1.9, 1.5, 0.7), M["WoodDark"]))
        parts.append(C.box("stake", (0.14, 0.14, 1.6), (s * 1.9, -1.5, 0.7), M["WoodDark"]))
    return finish(C.join(parts, "LogPile"))


def wood_pile(M):
    parts = []
    rnd = random.Random(8)
    for j in range(5):
        for i in range(6):
            parts.append(C.box("split", (0.42, 0.14, 0.14), (0, (i - 2.5) * 0.17 + rnd.uniform(-0.02, 0.02), 0.08 + j * 0.15), M["WoodEnd"]))
    parts.append(C.box("roof", (0.9, 1.4, 0.06), (0, 0, 0.95), M["WoodDark"], 0.01))
    return finish(C.join(parts, "WoodPile"))


def build():
    C.reset_scene()
    M = palette()
    return [log_cabin(M), fire_lookout(M), wood_bridge(M), log_pile(M), wood_pile(M)]


if __name__ == "__main__":
    objs = build()
    for o in objs:
        print(f"{o.name:12s} tris={C.tri_count(o):6d}  size={tuple(round(d, 1) for d in o.dimensions)}")
    C.export_fbx(objs, C.path_in_repo("Assets", "Models", "Landmarks", "ForestLandmarks.fbx"))
