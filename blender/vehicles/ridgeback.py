""""Ridgeback": a short-wheelbase expedition 4x4 (original design).

Run:  python blender/vehicles/ridgeback.py
Writes: Assets/Models/Vehicles/Ridgeback.fbx  (objects: Body, Wheel, WheelFL/FR/RL/RR empties)

Front faces Blender -Y (Unity +Z). Vehicle left is Blender +X (Unity -X).
Origin is on the ground, midway between the axles.
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import bpy  # noqa: E402,F401  (makes mathutils importable)
from mathutils import Matrix  # noqa: E402

from lib import common as C  # noqa: E402
from lib import wheel as W  # noqa: E402

# Key dimensions (metres). Unity reads the wheel empties, so keep these in sync only here.
WHEEL_R = 0.43
WHEEL_W = 0.32
TRACK_X = 0.86          # wheel centre offset from the centreline
FRONT_Y, REAR_Y = -1.25, 1.25
WHEEL_Z = WHEEL_R       # at rest
ARCH_R = 0.53


def palette():
    m = C.material
    return {
        "Paint": m("Paint", (0.055, 0.25, 0.27), 0.0, 0.32),
        "PaintRoof": m("PaintRoof", (0.80, 0.77, 0.69), 0.0, 0.38),
        "Paint2": m("Paint2", (0.24, 0.28, 0.14), 0.0, 0.5),
        "Accent": m("Accent", (0.85, 0.36, 0.06), 0.0, 0.4),
        "Trim": m("Trim", (0.035, 0.035, 0.037), 0.0, 0.78),
        "Steel": m("Steel", (0.07, 0.07, 0.075), 0.6, 0.45),
        "Chassis": m("Chassis", (0.02, 0.02, 0.02), 0.0, 0.85),
        "Chrome": m("Chrome", (0.6, 0.6, 0.6), 1.0, 0.18),
        "Glass": m("Glass", (0.02, 0.03, 0.035), 0.0, 0.04),
        "Lights": m("Lights", (0.95, 0.93, 0.88), 0.0, 0.1, (1.0, 0.95, 0.85), 3.0),
        "TailLights": m("TailLights", (0.5, 0.02, 0.02), 0.0, 0.2, (1.0, 0.05, 0.03), 1.0),
        "Amber": m("Amber", (0.9, 0.42, 0.05), 0.0, 0.2, (1.0, 0.45, 0.05), 0.6),
        "Canvas": m("Canvas", (0.45, 0.38, 0.26), 0.0, 0.9),
        "Tire": m("Tire", (0.03, 0.03, 0.03), 0.0, 0.92),
        "Rim": m("Rim", (0.36, 0.27, 0.15), 0.85, 0.35),
    }


def sx(s, a, b):
    """Sorted pair of x values mirrored to side s (+1 left, -1 right)."""
    return tuple(sorted((s * a, s * b)))


def fender_flare(name, cy, side, mat):
    import bmesh
    bm = bmesh.new()
    r0, r1 = ARCH_R, ARCH_R + 0.11
    xi, xo, xo_top = side * 0.84, side * 1.045, side * 1.0
    a0, a1, steps = 0.28, math.pi - 0.28, 18
    rings = []
    for k in range(steps + 1):
        a = a0 + (a1 - a0) * k / steps
        ca, sa = math.cos(a), math.sin(a)
        pts = [(xi, r0), (xo, r0), (xo_top, r1), (xi, r1)]
        rings.append([bm.verts.new((x, cy + r * ca, WHEEL_Z + r * sa)) for x, r in pts])
    for k in range(steps):
        a, b = rings[k], rings[k + 1]
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    obj = C.from_bmesh(name, bm, mat)
    C.add_bevel(obj, 0.012, 2)
    return obj


def build_body(M):
    P = []
    add = P.append

    # --- Main tub with wheel arches cut out.
    tub = C.box_between("tub", -0.90, 0.90, -2.00, 1.98, 0.66, 1.24, M["Paint"], bevel=0.05, segments=3)
    cutters = [C.cylinder(f"arch{i}", ARCH_R, 2.4, (0, y, WHEEL_Z), "X", 40) for i, y in enumerate((FRONT_Y, REAR_Y))]
    C.boolean_cut(tub, cutters)
    add(tub)
    for s in (1, -1):
        for y in (FRONT_Y, REAR_Y):
            add(fender_flare("flare", y, s, M["Trim"]))

    # --- Cabin (raked windscreen, tapered sides) with two-tone roof.
    cb = [(-0.88, -0.62, 1.24), (0.88, -0.62, 1.24), (0.88, 1.92, 1.24), (-0.88, 1.92, 1.24)]
    ct = [(-0.80, -0.22, 1.98), (0.80, -0.22, 1.98), (0.80, 1.86, 1.98), (-0.80, 1.86, 1.98)]
    add(C.hull("cabin", cb, ct, M["Paint"], bevel=0.045, segments=3))
    inside = (0, 0.7, 1.6)
    add(C.face_panel("roof", ct, 0.03, 0.97, 0.03, 0.97, 0.0, 0.014, M["PaintRoof"], inward=inside))
    add(C.face_panel("windscreen", (cb[0], cb[1], ct[1], ct[0]), 0.07, 0.93, 0.10, 0.90, 0.001, 0.01,
                     M["Glass"], inward=inside))
    add(C.face_panel("rearglass", (cb[2], cb[3], ct[3], ct[2]), 0.16, 0.84, 0.22, 0.88, 0.001, 0.01,
                     M["Glass"], inward=inside))
    for s in (1, -1):
        side = ((s * 0.88, -0.62, 1.24), (s * 0.88, 1.92, 1.24), (s * 0.80, 1.86, 1.98), (s * 0.80, -0.22, 1.98))
        add(C.face_panel("doorglass", side, 0.06, 0.42, 0.14, 0.90, 0.001, 0.01, M["Glass"], inward=inside))
        add(C.face_panel("sideglass", side, 0.47, 0.95, 0.14, 0.90, 0.001, 0.01, M["Glass"], inward=inside))
        # Door shut lines, handle, accent stripe.
        for y in (-0.52, 0.50):
            add(C.box_between("seam", *sx(s, 0.898, 0.908), y - 0.005, y + 0.005, 0.70, 1.22, M["Trim"]))
        add(C.box_between("handle", *sx(s, 0.90, 0.925), 0.28, 0.42, 1.10, 1.135, M["Trim"], bevel=0.008))
        add(C.box_between("stripe", *sx(s, 0.899, 0.906), -1.90, 1.90, 1.13, 1.165, M["Accent"]))
        # Mirror.
        add(C.tube("mirrorarm", (s * 0.86, -0.46, 1.32), (s * 1.0, -0.52, 1.40), 0.015, M["Trim"], 8))
        add(C.box_between("mirror", *sx(s, 0.97, 1.10), -0.57, -0.50, 1.33, 1.47, M["Trim"], bevel=0.015))
        # Rock slider, mud flaps.
        add(C.tube_path("slider", [(s * 0.90, -0.62, 0.71), (s * 0.97, -0.55, 0.66), (s * 0.97, 0.55, 0.66),
                                    (s * 0.90, 0.62, 0.71)], 0.035, M["Steel"]))
        for y in (FRONT_Y, REAR_Y):
            add(C.box_between("flap", *sx(s, 0.70, 1.00), y + 0.50, y + 0.52, 0.30, 0.66, M["Trim"]))

    # --- Bonnet details.
    add(C.box_between("bulge", -0.46, 0.46, -1.96, -0.80, 1.22, 1.28, M["Paint"], bevel=0.025))
    for x in (-0.22, 0.22):
        add(C.box_between("vent", x - 0.12, x + 0.12, -1.55, -1.20, 1.275, 1.29, M["Trim"]))
    add(C.box_between("cowl", -0.86, 0.86, -0.72, -0.60, 1.23, 1.27, M["Trim"]))

    # --- Front: grille, lamps, bumper, winch, bull bar, skid plate.
    add(C.box_between("grille", -0.50, 0.50, -2.02, -1.99, 0.84, 1.18, M["Trim"], bevel=0.01))
    for z in (0.89, 0.95, 1.01, 1.07, 1.13):
        add(C.box_between("slat", -0.46, 0.46, -2.035, -2.015, z - 0.012, z + 0.012, M["Chrome"]))
    for s in (1, -1):
        add(C.box_between("bezel", *sx(s, 0.56, 0.82), -2.03, -1.99, 0.90, 1.14, M["Trim"], bevel=0.012))
        add(C.cylinder("lampring", 0.1, 0.02, (s * 0.69, -2.035, 1.02), "Y", 24, M["Chrome"]))
        add(C.cylinder("lamp", 0.085, 0.02, (s * 0.69, -2.045, 1.02), "Y", 24, M["Lights"]))
        add(C.box_between("indicator", *sx(s, 0.60, 0.78), -2.03, -1.995, 0.78, 0.84, M["Amber"]))
        add(C.box_between("towhook", *sx(s, 0.58, 0.66), -2.32, -2.24, 0.60, 0.70, M["Accent"], bevel=0.01))
        add(C.box_between("taillight", *sx(s, 0.76, 0.86), 1.975, 2.005, 0.86, 1.16, M["TailLights"], bevel=0.008))
    add(C.box_between("fbumper", -0.98, 0.98, -2.26, -1.98, 0.54, 0.80, M["Steel"], bevel=0.02))
    add(C.box_between("winch", -0.24, 0.24, -2.34, -2.24, 0.60, 0.74, M["Trim"], bevel=0.015))
    add(C.box_between("fairlead", -0.10, 0.10, -2.36, -2.33, 0.63, 0.71, M["Chrome"]))
    add(C.tube_path("bullbar", [(-0.55, -2.22, 0.80), (-0.45, -2.20, 1.10), (0.45, -2.20, 1.10), (0.55, -2.22, 0.80)],
                    0.035, M["Steel"]))
    add(C.hull("skid", [(-0.6, -2.0, 0.48), (0.6, -2.0, 0.48), (0.6, -1.4, 0.52), (-0.6, -1.4, 0.52)],
               [(-0.6, -2.0, 0.53), (0.6, -2.0, 0.53), (0.6, -1.4, 0.57), (-0.6, -1.4, 0.57)], M["Steel"]))

    # --- Rear: bumper, hitch, spare wheel on a bracket.
    add(C.box_between("rbumper", -0.95, 0.95, 1.96, 2.16, 0.56, 0.78, M["Steel"], bevel=0.02))
    add(C.box_between("hitch", -0.06, 0.06, 2.16, 2.30, 0.58, 0.66, M["Steel"]))
    add(C.box_between("sparemount", -0.07, 0.07, 1.98, 2.04, 0.95, 1.32, M["Steel"]))
    spare = W.build("spare", WHEEL_R - 0.02, WHEEL_W, detail=0.6, mats=M)
    W.transform(spare, Matrix.Translation((0, 2.20, 1.13)) @ Matrix.Rotation(math.radians(90), 4, "Z"))
    add(spare)

    # --- Underside: frame rails and belly pan (kept inside the wheels).
    for s in (1, -1):
        add(C.box_between("rail", *sx(s, 0.50, 0.62), -1.95, 1.95, 0.50, 0.66, M["Chassis"]))
    add(C.box_between("pan", -0.50, 0.50, -1.98, 1.96, 0.58, 0.67, M["Chassis"]))

    # --- Roof rack, light bar and cargo.
    z = 2.06
    add(C.tube_path("rack", [(-0.74, -0.12, z), (0.74, -0.12, z), (0.74, 1.78, z), (-0.74, 1.78, z),
                             (-0.74, -0.12, z)], 0.022, M["Steel"], 10))
    for y in (0.45, 1.10):
        add(C.tube("crossbar", (-0.74, y, z), (0.74, y, z), 0.018, M["Steel"], 8))
    for s in (1, -1):
        for y in (-0.05, 0.85, 1.72):
            add(C.box_between("rackleg", *sx(s, 0.71, 0.77), y - 0.03, y + 0.03, 1.97, z, M["Steel"]))
    add(C.box_between("lightbar", -0.62, 0.62, -0.20, -0.10, 2.06, 2.15, M["Trim"], bevel=0.012))
    for i in range(8):
        x = -0.54 + i * 0.154
        add(C.box_between("barlamp", x - 0.062, x + 0.062, -0.207, -0.195, 2.075, 2.135, M["Lights"]))
    for x in (0.30, 0.52):
        add(C.box_between("jerrycan", x - 0.09, x + 0.09, 1.20, 1.66, 2.08, 2.42, M["Paint2"], bevel=0.02))
        add(C.cylinder("cancap", 0.03, 0.04, (x, 1.25, 2.44), "Z", 10, M["Trim"]))
    add(C.box_between("case", -0.68, -0.08, 0.95, 1.70, 2.08, 2.30, M["Trim"], bevel=0.025))
    add(C.cylinder("tarp", 0.09, 1.2, (0, 0.28, 2.17), "X", 16, M["Canvas"], bevel=0.02))

    # --- Snorkel up the right A-pillar, antenna on the left rear.
    add(C.tube_path("snorkel", [(-0.97, -1.15, 1.12), (-0.97, -0.72, 1.22), (-0.93, -0.50, 1.55),
                                (-0.86, -0.32, 1.95), (-0.86, -0.30, 2.08)], 0.045, M["Trim"]))
    add(C.box_between("snorkelhead", -0.93, -0.79, -0.44, -0.22, 2.05, 2.20, M["Trim"], bevel=0.02))
    add(C.tube("antenna", (0.80, 1.82, 1.98), (0.80, 1.88, 2.85), 0.006, M["Trim"], 6))

    body = C.join(P, "Body")
    C.smooth_by_angle(body, 32)
    return body


def build():
    C.reset_scene()
    M = palette()
    body = build_body(M)
    wheel = W.build("Wheel", WHEEL_R, WHEEL_W, mats=M)
    empties = [C.empty(n, (s * TRACK_X, y, WHEEL_Z)) for n, s, y in
               (("WheelFL", 1, FRONT_Y), ("WheelFR", -1, FRONT_Y), ("WheelRL", 1, REAR_Y), ("WheelRR", -1, REAR_Y))]
    return body, wheel, empties


if __name__ == "__main__":
    body, wheel, empties = build()
    print(f"Body tris: {C.tri_count(body)}  Wheel tris: {C.tri_count(wheel)}")
    C.export_fbx([body, wheel] + empties, C.path_in_repo("Assets", "Models", "Vehicles", "Ridgeback.fbx"))
