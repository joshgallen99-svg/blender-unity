"""One-off desert landmarks and camp props.

Run:  python blender/landmarks/desert_landmarks.py
Writes: Assets/Models/Landmarks/DesertLandmarks.fbx
Objects (origin at the base centre, front facing Blender -Y / Unity +Z):
  NeedlesEye      natural sandstone arch (~28 m span)
  BalancedRock    boulder perched on a slender pedestal
  Windmill        steel lattice water-pump windmill (rotor separate)
  Windmill_Rotor  the bladed wheel; its location is the hub, spun in Unity about its forward axis
  WaterTank       corrugated stock tank
  Shack           prospector's plank shack with a tin roof and porch
  Wreck           rusted-out 1950s-style pickup
  Tent, FireRing, Crates, Cairn, Signpost   camp and trail props
"""
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "props"))

import bpy  # noqa: E402,F401
import bmesh  # noqa: E402
from mathutils import Matrix, Vector, noise  # noqa: E402

import desert_props as DP  # noqa: E402
from lib import common as C  # noqa: E402


def palette():
    m = C.material
    M = DP.palette()
    M.update({
        "Wood": m("Wood", (0.45, 0.39, 0.32), 0.0, 0.85),
        "WoodDark": m("WoodDark", (0.25, 0.20, 0.16), 0.0, 0.9),
        "Rust": m("Rust", (0.40, 0.18, 0.08), 0.3, 0.8),
        "Galvanized": m("Galvanized", (0.55, 0.57, 0.58), 0.7, 0.45),
        "Canvas": m("Canvas", (0.75, 0.38, 0.15), 0.0, 0.9),
        "Trim": m("Trim", (0.035, 0.035, 0.037), 0.0, 0.78),
        "Ash": m("Ash", (0.05, 0.045, 0.04), 0.0, 0.95),
    })
    return M


def finish(obj, smooth=35, uv_scale=1.0):
    C.box_uv(obj, uv_scale)
    C.smooth_by_angle(obj, smooth)
    return obj


# ---------------------------------------------------------------------------- natural landmarks

def needles_eye(M, span=28.0, height=16.0):
    rnd = random.Random(7)
    off = Vector((rnd.uniform(-40, 40), rnd.uniform(-40, 40), rnd.uniform(-40, 40)))
    R = span / 2
    rings, seg = 56, 18
    bm = bmesh.new()
    rows = []
    for k in range(rings + 1):
        t = k / rings
        th = math.pi * (1.1 - 1.2 * t)                 # legs continue below the ground
        c = Vector((R * math.cos(th), 0.0, height * math.sin(th)))
        tangent = Vector((-R * math.sin(th), 0.0, height * math.cos(th))).normalized()
        nrm = tangent.cross(Vector((0, 1, 0))).normalized()
        crown = math.sin(math.pi * min(max(t, 0), 1)) ** 1.5
        legw = 1.0 + 0.35 * (1 - t)                    # left leg heavier than the right
        a = (4.8 - 2.6 * crown) * legw                 # thickness in the arch plane
        b = (6.5 - 2.4 * crown) * legw                 # depth across the arch
        row = []
        for i in range(seg):
            ph = 2 * math.pi * i / seg
            cs, sn = math.cos(ph), math.sin(ph)
            # Squarish (superellipse) cross-section: slab-like sandstone, not a tube.
            cs = math.copysign(abs(cs) ** 0.45, cs)
            sn = math.copysign(abs(sn) ** 0.45, sn)
            dirv = (nrm * cs + Vector((0, 1, 0)) * sn).normalized()
            p = c + nrm * a * cs + Vector((0, b * sn, 0))
            d = 1 + 0.26 * DP.fbm(p * 0.11 + off, 3) + 0.08 * DP.fbm(p * 0.45 + off, 2)
            p = c + (p - c) * d
            band = (p.z * 0.55) % 1.0
            p += dirv * 0.6 * max(0.0, (band - 0.7) / 0.3) ** 2             # bedding lips
            row.append(bm.verts.new(p))
        rows.append(row)
    for k in range(rings):
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((rows[k][i], rows[k][j], rows[k + 1][j], rows[k + 1][i]))
    bm.faces.new(rows[0][::-1])
    bm.faces.new(rows[-1])
    arch = C.from_bmesh("NeedlesEye", bm, M["RockSandstone"])
    parts = [arch]
    # The fin the arch eroded out of, continuing behind the left leg.
    fin = DP.sandstone("arch_fin", 210, (9.0, 5.0, 7.0), M["RockSandstone"], subdiv=5, ratio=0.25, lumpy=0.3,
                       ledges=0.7, layers=4)
    for v in fin.data.vertices:
        v.co += Vector((-R - 6.0, 1.0, -0.8))
    parts.append(fin)
    for i, (x, y, s) in enumerate(((-R - 3, 4, 1.6), (-R + 1, -5, 1.2), (R + 2.5, -3, 1.8), (R - 1, 5, 1.0),
                                   (R + 5, 2, 0.9), (-R - 6, -1, 1.1))):
        b = DP.sandstone(f"arch_rubble{i}", 200 + i, (1.4 * s, 1.1 * s, 0.9 * s), M["RockSandstone"], subdiv=4, ratio=0.3)
        for v in b.data.vertices:
            v.co += Vector((x, y, -0.3))
        parts.append(b)
    obj = C.join(parts, "NeedlesEye")
    return finish(obj, 40)


def balanced_rock(M):
    ped = DP.hoodoo("br_ped", 333, 7.5, M)
    # Slim the pedestal and replace its cap with a much bigger perched boulder.
    for v in ped.data.vertices:
        if v.co.z < 7.0:
            v.co.x *= 0.62
            v.co.y *= 0.62
    top = DP.sandstone("br_top", 334, (3.4, 2.8, 2.3), M["RockPale"], subdiv=5, ratio=0.15)
    for v in top.data.vertices:
        v.co += Vector((0.6, 0.3, 6.9))
    base = DP.sandstone("br_base", 335, (3.0, 2.6, 0.9), M["RockSandstone"], subdiv=4, ratio=0.3)
    obj = C.join([ped, top, base], "BalancedRock")
    return finish(obj, 38)


# ---------------------------------------------------------------------------- man-made landmarks

def windmill(M):
    parts = []
    H = 9.0
    base, top = 1.35, 0.32
    corners = [(1, 1), (-1, 1), (-1, -1), (1, -1)]
    leg = lambda sx, sy, z: Vector((sx * (base + (top - base) * z / H), sy * (base + (top - base) * z / H), z))  # noqa
    for sx, sy in corners:
        parts.append(C.tube("leg", leg(sx, sy, 0), leg(sx, sy, H), 0.055, M["Galvanized"], 8))
        parts.append(C.box("footing", (0.45, 0.45, 0.35), (sx * base, sy * base, 0.05), M["RockPale"], 0.04))
    levels = [0.4, 2.6, 4.8, 6.8, 8.6]
    for z in levels:
        for i in range(4):
            a, b = corners[i], corners[(i + 1) % 4]
            parts.append(C.tube("girt", leg(*a, z), leg(*b, z), 0.03, M["Galvanized"], 6))
    for z0, z1 in zip(levels[:-1], levels[1:]):
        for i in range(4):
            a, b = corners[i], corners[(i + 1) % 4]
            parts.append(C.tube("brace", leg(*a, z0), leg(*b, z1), 0.018, M["Galvanized"], 5))
            parts.append(C.tube("brace", leg(*b, z0), leg(*a, z1), 0.018, M["Galvanized"], 5))
    # Platform, head, tail vane, pump rod.
    for i in range(6):
        y = -0.75 + i * 0.3
        parts.append(C.box("plank", (1.7, 0.26, 0.05), (0, y, 8.62), M["Wood"]))
    parts.append(C.box("head", (0.45, 0.9, 0.45), (0, -0.05, H + 0.3), M["Rust"], 0.05))
    parts.append(C.tube("boom", (0, 0.3, H + 0.35), (0, 2.6, H + 0.55), 0.04, M["Galvanized"], 6))
    parts.append(C.box("vane", (0.04, 1.4, 1.0), (0, 3.0, H + 0.6), M["Rust"], 0.01))
    parts.append(C.tube("rod", (0, 0, 0.3), (0, 0, H), 0.02, M["Galvanized"], 5))
    tower = C.join(parts, "Windmill")
    finish(tower, 40)

    # Rotor: built around its own hub, axis along Y (Blender forward axis).
    rp = []
    blades = 18
    for i in range(blades):
        a = 2 * math.pi * i / blades
        blade = C.box("blade", (0.34, 0.03, 1.45), (0, 0, 1.1), M["Galvanized"])
        blade.data.transform(Matrix.Rotation(math.radians(28), 4, "Z"))          # blade pitch
        blade.data.transform(Matrix.Rotation(a, 4, "Y"))
        rp.append(blade)
    for r in (0.75, 1.75):
        ring = []
        n = 36
        for i in range(n):
            a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
            ring.append(C.tube("ring", (r * math.cos(a0), 0, r * math.sin(a0)), (r * math.cos(a1), 0, r * math.sin(a1)),
                               0.025, M["Galvanized"], 5))
        rp.extend(ring)
    rp.append(C.cylinder("hub", 0.22, 0.3, (0, 0, 0), "Y", 16, M["Rust"]))
    rotor = C.join(rp, "Windmill_Rotor")
    finish(rotor, 40)
    rotor.location = (0, -0.65, H + 0.3)
    return [tower, rotor]


def water_tank(M):
    bm = bmesh.new()
    seg, R, h = 64, 1.7, 2.0
    bottom, topr = [], []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        r = R + (0.035 if i % 2 else -0.035)               # corrugations
        bottom.append(bm.verts.new((r * math.cos(a), r * math.sin(a), 0.25)))
        topr.append(bm.verts.new((r * math.cos(a), r * math.sin(a), 0.25 + h)))
    for i in range(seg):
        j = (i + 1) % seg
        bm.faces.new((bottom[i], bottom[j], topr[j], topr[i]))
    bm.faces.new(bottom[::-1])
    tank = C.from_bmesh("tankwall", bm, M["Galvanized"])
    water = C.cylinder("water", R - 0.05, 0.02, (0, 0, h * 0.8), "Z", 48, M["Glass"] if "Glass" in M else M["Trim"])
    rim = C.cylinder("rim", R + 0.06, 0.08, (0, 0, 0.25 + h), "Z", 48, M["Rust"])
    rim_hole = C.cylinder("rimhole", R - 0.05, 0.3, (0, 0, 0.25 + h), "Z", 48)
    C.boolean_cut(rim, [rim_hole])
    base = C.cylinder("base", R + 0.1, 0.25, (0, 0, 0.125), "Z", 32, M["RockPale"])
    pipe = C.tube_path("pipe", [(R - 0.2, 0, h + 0.4), (R + 0.35, 0, h + 0.4), (R + 0.35, 0, 0.6)], 0.05, M["Rust"])
    obj = C.join([tank, water, rim, base, pipe], "WaterTank")
    return finish(obj, 30)


def shack(M):
    W, D, Hh = 4.4, 3.4, 2.5
    t = 0.12
    walls = [C.box_between("wf", -W / 2, W / 2, -D / 2, -D / 2 + t, 0.3, 0.3 + Hh, M["Wood"]),
             C.box_between("wb", -W / 2, W / 2, D / 2 - t, D / 2, 0.3, 0.3 + Hh + 0.5, M["Wood"]),
             C.box_between("wl", -W / 2, -W / 2 + t, -D / 2, D / 2, 0.3, 0.3 + Hh, M["Wood"]),
             C.box_between("wr", W / 2 - t, W / 2, -D / 2, D / 2, 0.3, 0.3 + Hh, M["Wood"])]
    door = C.box_between("door", -0.5, 0.5, -D / 2 - 0.5, -D / 2 + 0.5, 0.35, 2.3)
    win1 = C.box_between("win", 0.9, 1.7, -D / 2 - 0.5, -D / 2 + 0.5, 1.3, 2.1)
    win2 = C.box_between("win2", -W / 2 - 0.5, -W / 2 + 0.5, -0.4, 0.4, 1.3, 2.0)
    C.boolean_cut(walls[0], [door, win1])
    C.boolean_cut(walls[2], [win2])
    parts = walls
    # Back wall taller: give it a sloped top by cutting with a rotated box.
    parts.append(C.box_between("floor", -W / 2 - 1.5, W / 2, -D / 2 - 1.6, D / 2, 0.15, 0.3, M["WoodDark"]))
    for x, y in ((-W / 2, -D / 2), (W / 2, -D / 2), (-W / 2, D / 2), (W / 2, D / 2), (-W / 2 - 1.4, -D / 2 - 1.5),
                 (0.8, -D / 2 - 1.5)):
        parts.append(C.box("post", (0.16, 0.16, 3.4), (x, y, 1.6), M["WoodDark"]))
    # Single-slope tin roof with porch overhang, one rusted panel.
    roof = C.hull("roof", [(-W / 2 - 1.7, -D / 2 - 1.8, 2.75), (W / 2 + 0.3, -D / 2 - 1.8, 2.75),
                           (W / 2 + 0.3, D / 2 + 0.4, 3.45), (-W / 2 - 1.7, D / 2 + 0.4, 3.45)],
                  [(-W / 2 - 1.7, -D / 2 - 1.8, 2.8), (W / 2 + 0.3, -D / 2 - 1.8, 2.8),
                   (W / 2 + 0.3, D / 2 + 0.4, 3.5), (-W / 2 - 1.7, D / 2 + 0.4, 3.5)], M["Galvanized"])
    patch = C.hull("patch", [(0.4, -0.6, 3.21), (1.9, -0.6, 3.21), (1.9, 1.4, 3.6), (0.4, 1.4, 3.6)],
                   [(0.4, -0.6, 3.24), (1.9, -0.6, 3.24), (1.9, 1.4, 3.63), (0.4, 1.4, 3.63)], M["Rust"])
    parts += [roof, patch]
    parts.append(C.tube("chimney", (1.6, 1.0, 2.0), (1.6, 1.0, 4.4), 0.11, M["Rust"], 10))
    parts.append(C.box("step", (1.2, 0.4, 0.15), (0, -D / 2 - 1.8, 0.07), M["WoodDark"]))
    parts.append(C.box("barrel", (0.6, 0.6, 0.9), (-W / 2 - 1.0, -D / 2 - 0.8, 0.75), M["Rust"], 0.08))
    obj = C.join(parts, "Shack")
    return finish(obj, 30)


def wreck(M):
    parts = []
    r = M["Rust"]
    parts.append(C.box_between("frame", -0.85, 0.85, -2.4, 2.4, 0.35, 0.55, r))
    parts.append(C.box_between("cab", -0.85, 0.85, -0.6, 0.6, 0.55, 1.75, r, bevel=0.12, segments=3))
    win = C.box_between("cabwin", -1.0, 1.0, -0.45, 0.45, 1.15, 1.6)
    wins = C.box_between("cabwin2", -0.7, 0.7, -0.9, 0.9, 1.15, 1.6)
    C.boolean_cut(parts[-1], [win, wins])
    parts.append(C.box_between("hood", -0.75, 0.75, -2.3, -0.6, 0.55, 1.25, r, bevel=0.15, segments=3))
    parts.append(C.box_between("grille", -0.6, 0.6, -2.38, -2.28, 0.6, 1.15, M["Trim"], bevel=0.03))
    for s in (1, -1):
        parts.append(C.box_between("bedside", *sorted((s * 0.82, s * 0.9)), 0.65, 2.45, 0.55, 1.1, r))
        f = C.cylinder("fender", 0.48, 0.32, (s * 0.85, -1.55, 0.6), "X", 20, r)
        cut = C.box_between("fcut", -2, 2, -3, 0, -1, 0.6)
        C.boolean_cut(f, [cut])
        parts.append(f)
        for y in (-1.55, 1.6):
            parts.append(C.cylinder("rim", 0.3, 0.2, (s * 0.85, y, 0.3), "X", 16, r))
    parts.append(C.box_between("bedfloor", -0.82, 0.82, 0.65, 2.45, 0.55, 0.62, r))
    parts.append(C.box_between("tailgate", -0.82, 0.82, 2.4, 2.47, 0.55, 1.05, r))
    for s in (1, -1):
        parts.append(C.cylinder("lamp", 0.11, 0.08, (s * 0.55, -2.33, 1.05), "Y", 12, M["Trim"]))
    obj = C.join(parts, "Wreck")
    return finish(obj, 35)


def tent(M):
    L, Wt, Ht = 2.4, 2.0, 1.4
    bm = bmesh.new()
    v = [bm.verts.new(p) for p in ((-Wt / 2, -L / 2, 0), (Wt / 2, -L / 2, 0), (0, -L / 2, Ht),
                                   (-Wt / 2, L / 2, 0), (Wt / 2, L / 2, 0), (0, L / 2, Ht))]
    bm.faces.new((v[0], v[3], v[5], v[2]))
    bm.faces.new((v[1], v[2], v[5], v[4]))
    bm.faces.new((v[3], v[4], v[5]))
    body = C.from_bmesh("tentbody", bm, M["Canvas"])
    door = C.hull("flap", [(-0.6, -L / 2 - 0.02, 0), (0, -L / 2 - 0.02, 0), (0, -L / 2 - 0.02, 0), (-0.6, -L / 2 - 0.02, 0)],
                  [(-0.55, -L / 2 - 0.45, 0.05), (0, -L / 2 - 0.02, Ht - 0.05), (0, -L / 2 - 0.02, Ht - 0.05),
                   (-0.55, -L / 2 - 0.45, 0.05)], M["Canvas"])
    parts = [body, door]
    for y in (-L / 2 - 0.05, L / 2 + 0.05):
        parts.append(C.tube("pole", (0, y, 0), (0, y, Ht + 0.15), 0.02, M["WoodDark"], 6))
        parts.append(C.tube("rope", (0, y, Ht + 0.1), (0, y * 1.9, 0), 0.006, M["Trim"], 4))
    obj = C.join(parts, "Tent")
    return finish(obj, 60, 2.0)


def fire_ring(M):
    parts = []
    for i in range(11):
        a = 2 * math.pi * i / 11
        s = DP.small_rock(f"fr{i}", 500 + i, (0.22, 0.18, 0.16), M["RockPale"])
        for v in s.data.vertices:
            v.co += Vector((math.cos(a) * 0.62, math.sin(a) * 0.62, 0))
        parts.append(s)
    parts.append(C.cylinder("ash", 0.55, 0.03, (0, 0, 0.01), "Z", 20, M["Ash"]))
    for i in range(3):
        a = i * 2.1
        parts.append(C.tube("log", (math.cos(a) * 0.45, math.sin(a) * 0.45, 0.06),
                            (math.cos(a + math.pi) * 0.1, math.sin(a + math.pi) * 0.1, 0.25), 0.07, M["WoodDark"], 8))
    obj = C.join(parts, "FireRing")
    return finish(obj, 40)


def crates(M):
    parts = []
    for i, (x, y, z, s, rot) in enumerate(((0, 0, 0, 0.7, 0.1), (0.8, 0.1, 0, 0.6, -0.2), (0.3, 0.05, 0.7, 0.55, 0.4))):
        b = C.box(f"crate{i}", (s, s, s), (0, 0, s / 2), M["Wood"], 0.02)
        b.data.transform(Matrix.Translation((x, y, z)) @ Matrix.Rotation(rot, 4, "Z"))
        parts.append(b)
    for i in range(2):
        parts.append(C.box(f"can{i}", (0.18, 0.36, 0.46), (-0.6, -0.15 + i * 0.25, 0.23), M["Rust"], 0.02))
    obj = C.join(parts, "Crates")
    return finish(obj, 40)


def cairn(M):
    parts = []
    z = 0.0
    rnd = random.Random(9)
    for i in range(6):
        s = 0.55 - i * 0.07
        h = 0.2 + rnd.uniform(-0.03, 0.04)
        st = DP.small_rock(f"c{i}", 600 + i, (s, s * 0.85, h * 0.9), M["RockPale"])
        DP.ground(st)
        for v in st.data.vertices:
            v.co += Vector((rnd.uniform(-0.05, 0.05), rnd.uniform(-0.05, 0.05), z))
        parts.append(st)
        z += h * 0.85
    obj = C.join(parts, "Cairn")
    return finish(obj, 40)


def signpost(M):
    parts = [C.box("post", (0.14, 0.14, 2.6), (0, 0, 1.2), M["WoodDark"])]
    for i, (z, ang) in enumerate(((2.25, 20), (1.9, 150), (1.55, 260))):
        board = C.hull("arrow", [(0.05, -0.04, z - 0.12), (1.0, -0.04, z - 0.12), (1.0, 0.04, z - 0.12), (0.05, 0.04, z - 0.12)],
                       [(0.05, -0.04, z + 0.12), (1.0, -0.04, z + 0.12), (1.0, 0.04, z + 0.12), (0.05, 0.04, z + 0.12)], M["Wood"])
        tip = C.hull("tip", [(1.0, -0.04, z - 0.18), (1.25, -0.04, z), (1.25, 0.04, z), (1.0, 0.04, z - 0.18)],
                     [(1.0, -0.04, z + 0.18), (1.25, -0.04, z + 0.0001), (1.25, 0.04, z + 0.0001), (1.0, 0.04, z + 0.18)], M["Wood"])
        for o in (board, tip):
            o.data.transform(Matrix.Rotation(math.radians(ang), 4, "Z"))
        parts += [board, tip]
    obj = C.join(parts, "Signpost")
    return finish(obj, 40, 0.5)


def build():
    C.reset_scene()
    M = palette()
    objs = [needles_eye(M), balanced_rock(M)]
    objs += windmill(M)
    objs += [water_tank(M), shack(M), wreck(M), tent(M), fire_ring(M), crates(M), cairn(M), signpost(M)]
    return objs


if __name__ == "__main__":
    objs = build()
    for o in objs:
        print(f"{o.name:16s} tris={C.tri_count(o):6d} size={tuple(round(d, 1) for d in o.dimensions)} loc={tuple(round(c, 2) for c in o.location)}")
    C.export_fbx(objs, C.path_in_repo("Assets", "Models", "Landmarks", "DesertLandmarks.fbx"))
