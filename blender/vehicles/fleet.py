"""The expedition fleet: two original 4x4 bodies, three tyre types and bolt-on accessories.

Run:  python blender/vehicles/fleet.py
Writes: Assets/Models/Vehicles/Fleet.fbx
Objects:
  Body_Crawler     open-top rock crawler on 37s (2.6 m wheelbase): exo cage, flat fenders, sliders,
                   stubby winch bumper, tyre carrier. Its solid axles are separate parts (below).
  Body_Ridgeback   short-wheelbase 4x4 wagon (2.5 m wheelbase)
  Body_Packhorse   long-wheelbase pickup with a load bed (3.0 m wheelbase)
  Wheel_AT / Wheel_MT / Wheel_Dune / Wheel_Bead   tyre + rim, axle along X, show face toward vehicle left
  Axle_Housing     solid-axle housing with diff, centred on the origin, along X (placed between the wheels in game)
  Link_Unit, Coilover_Unit   1 m long along the vehicle's forward axis from the origin; stretched in game
                   between their chassis and axle mounts, so the suspension visibly articulates
  RoofRack_<Body>, Snorkel_<Body>, BullBar_<Body>   accessories (toggled in the garage)
  <Body>_WheelFL/FR/RL/RR, <Body>_Spare   empties: wheel centres and the spare wheel mount

Modelled facing Blender -Y with the vehicle's left at +X; common.export_fbx turns it to face Unity +Z.
Origin is on the ground, midway between the axles.
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import bpy  # noqa: E402,F401  (makes mathutils importable)
import bmesh  # noqa: E402

from lib import common as C  # noqa: E402
from lib import wheel as W  # noqa: E402

WHEEL_R = 0.43
WHEEL_W = 0.32
TRACK_X = 0.86
WHEEL_Z = WHEEL_R
ARCH_R = 0.53

BODIES = {
    # y values: axles, tub ends, cabin bottom/top front & rear. Front is -Y.
    "Ridgeback": dict(front_axle=-1.25, rear_axle=1.25, tub_front=-2.00, tub_rear=1.98,
                      cab_fb=-0.62, cab_ft=-0.22, cab_rb=1.92, cab_rt=1.86, bed=False),
    "Packhorse": dict(front_axle=-1.50, rear_axle=1.50, tub_front=-2.25, tub_rear=2.55,
                      cab_fb=-0.87, cab_ft=-0.47, cab_rb=0.62, cab_rt=0.56, bed=True),
}


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
        "RimBlack": m("RimBlack", (0.03, 0.03, 0.03), 0.6, 0.4),
        "RimWhite": m("RimWhite", (0.85, 0.85, 0.82), 0.2, 0.45),
    }


def sx(s, a, b):
    return tuple(sorted((s * a, s * b)))


def fender_flare(name, cy, side, mat):
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


def build_body(M, name, S):
    P = []
    add = P.append
    F, R = S["tub_front"], S["tub_rear"]
    FA, RA = S["front_axle"], S["rear_axle"]

    tub = C.box_between("tub", -0.90, 0.90, F, R, 0.66, 1.24, M["Paint"], bevel=0.05, segments=3)
    cutters = [C.cylinder(f"arch{i}", ARCH_R, 2.4, (0, y, WHEEL_Z), "X", 40) for i, y in enumerate((FA, RA))]
    C.boolean_cut(tub, cutters)
    add(tub)
    for s in (1, -1):
        for y in (FA, RA):
            add(fender_flare("flare", y, s, M["Trim"]))

    # Cabin with two-tone roof and glass.
    cb = [(-0.88, S["cab_fb"], 1.24), (0.88, S["cab_fb"], 1.24), (0.88, S["cab_rb"], 1.24), (-0.88, S["cab_rb"], 1.24)]
    ct = [(-0.80, S["cab_ft"], 1.98), (0.80, S["cab_ft"], 1.98), (0.80, S["cab_rt"], 1.98), (-0.80, S["cab_rt"], 1.98)]
    add(C.hull("cabin", cb, ct, M["Paint"], bevel=0.045, segments=3))
    inside = (0, (S["cab_fb"] + S["cab_rb"]) / 2, 1.6)
    add(C.face_panel("roof", ct, 0.03, 0.97, 0.03, 0.97, 0.0, 0.014, M["PaintRoof"], inward=inside))
    add(C.face_panel("windscreen", (cb[0], cb[1], ct[1], ct[0]), 0.07, 0.93, 0.10, 0.90, 0.001, 0.01, M["Glass"], inward=inside))
    add(C.face_panel("rearglass", (cb[2], cb[3], ct[3], ct[2]), 0.16, 0.84, 0.22, 0.88, 0.001, 0.01, M["Glass"], inward=inside))
    door_front = S["cab_fb"] + 0.10
    door_rear = 0.50 if not S["bed"] else S["cab_rb"] - 0.06
    for s in (1, -1):
        side = ((s * 0.88, S["cab_fb"], 1.24), (s * 0.88, S["cab_rb"], 1.24), (s * 0.80, S["cab_rt"], 1.98),
                (s * 0.80, S["cab_ft"], 1.98))
        if S["bed"]:
            add(C.face_panel("doorglass", side, 0.07, 0.88, 0.14, 0.90, 0.001, 0.01, M["Glass"], inward=inside))
        else:
            add(C.face_panel("doorglass", side, 0.06, 0.42, 0.14, 0.90, 0.001, 0.01, M["Glass"], inward=inside))
            add(C.face_panel("sideglass", side, 0.47, 0.95, 0.14, 0.90, 0.001, 0.01, M["Glass"], inward=inside))
        for y in (door_front, door_rear):
            add(C.box_between("seam", *sx(s, 0.898, 0.908), y - 0.005, y + 0.005, 0.70, 1.22, M["Trim"]))
        add(C.box_between("handle", *sx(s, 0.90, 0.925), door_rear - 0.22, door_rear - 0.08, 1.10, 1.135, M["Trim"], bevel=0.008))
        add(C.box_between("stripe", *sx(s, 0.899, 0.906), F + 0.1, R - 0.08, 1.13, 1.165, M["Accent"]))
        add(C.tube("mirrorarm", (s * 0.86, S["cab_fb"] + 0.16, 1.32), (s * 1.0, S["cab_fb"] + 0.10, 1.40), 0.015, M["Trim"], 8))
        add(C.box_between("mirror", *sx(s, 0.97, 1.10), S["cab_fb"] + 0.05, S["cab_fb"] + 0.12, 1.33, 1.47, M["Trim"], bevel=0.015))
        sl0, sl1 = FA + ARCH_R + 0.1, RA - ARCH_R - 0.1
        add(C.tube_path("slider", [(s * 0.90, sl0, 0.71), (s * 0.97, sl0 + 0.07, 0.66), (s * 0.97, sl1 - 0.07, 0.66),
                                    (s * 0.90, sl1, 0.71)], 0.035, M["Steel"]))
        for y in (FA, RA):
            add(C.box_between("flap", *sx(s, 0.70, 1.00), y + 0.50, y + 0.52, 0.30, 0.66, M["Trim"]))

    # Bonnet.
    add(C.box_between("bulge", -0.46, 0.46, F + 0.04, S["cab_fb"] - 0.18, 1.22, 1.28, M["Paint"], bevel=0.025))
    vy = (F + S["cab_fb"]) / 2
    for x in (-0.22, 0.22):
        add(C.box_between("vent", x - 0.12, x + 0.12, vy - 0.18, vy + 0.18, 1.275, 1.29, M["Trim"]))
    add(C.box_between("cowl", -0.86, 0.86, S["cab_fb"] - 0.10, S["cab_fb"] + 0.02, 1.23, 1.27, M["Trim"]))

    # Front end.
    add(C.box_between("grille", -0.50, 0.50, F - 0.02, F + 0.01, 0.84, 1.18, M["Trim"], bevel=0.01))
    for z in (0.89, 0.95, 1.01, 1.07, 1.13):
        add(C.box_between("slat", -0.46, 0.46, F - 0.035, F - 0.015, z - 0.012, z + 0.012, M["Chrome"]))
    for s in (1, -1):
        add(C.box_between("bezel", *sx(s, 0.56, 0.82), F - 0.03, F + 0.01, 0.90, 1.14, M["Trim"], bevel=0.012))
        add(C.cylinder("lampring", 0.1, 0.02, (s * 0.69, F - 0.035, 1.02), "Y", 24, M["Chrome"]))
        add(C.cylinder("lamp", 0.085, 0.02, (s * 0.69, F - 0.045, 1.02), "Y", 24, M["Lights"]))
        add(C.box_between("indicator", *sx(s, 0.60, 0.78), F - 0.03, F + 0.005, 0.78, 0.84, M["Amber"]))
        add(C.box_between("towhook", *sx(s, 0.58, 0.66), F - 0.32, F - 0.24, 0.60, 0.70, M["Accent"], bevel=0.01))
        add(C.box_between("taillight", *sx(s, 0.76, 0.86), R - 0.005, R + 0.025, 0.86, 1.16, M["TailLights"], bevel=0.008))
    add(C.box_between("fbumper", -0.98, 0.98, F - 0.26, F + 0.02, 0.54, 0.80, M["Steel"], bevel=0.02))
    add(C.box_between("winch", -0.24, 0.24, F - 0.34, F - 0.24, 0.60, 0.74, M["Trim"], bevel=0.015))
    add(C.box_between("fairlead", -0.10, 0.10, F - 0.36, F - 0.33, 0.63, 0.71, M["Chrome"]))
    add(C.hull("skid", [(-0.6, F, 0.48), (0.6, F, 0.48), (0.6, F + 0.6, 0.52), (-0.6, F + 0.6, 0.52)],
               [(-0.6, F, 0.53), (0.6, F, 0.53), (0.6, F + 0.6, 0.57), (-0.6, F + 0.6, 0.57)], M["Steel"]))

    # Rear end.
    add(C.box_between("rbumper", -0.95, 0.95, R - 0.02, R + 0.18, 0.56, 0.78, M["Steel"], bevel=0.02))
    add(C.box_between("hitch", -0.06, 0.06, R + 0.18, R + 0.32, 0.58, 0.66, M["Steel"]))
    if not S["bed"]:
        add(C.box_between("sparemount", -0.07, 0.07, R, R + 0.06, 0.95, 1.32, M["Steel"]))

    # Pickup bed.
    if S["bed"]:
        b0 = S["cab_rb"] + 0.04
        for s in (1, -1):
            add(C.box_between("bedside", *sx(s, 0.84, 0.90), b0, R, 1.20, 1.62, M["Paint"], bevel=0.02))
            add(C.tube("bedrail", (s * 0.87, b0 + 0.05, 1.66), (s * 0.87, R - 0.05, 1.66), 0.025, M["Steel"], 8))
        add(C.box_between("bedfront", -0.90, 0.90, b0, b0 + 0.06, 1.20, 1.62, M["Paint"], bevel=0.02))
        add(C.box_between("tailgate", -0.90, 0.90, R - 0.06, R, 1.20, 1.60, M["Paint"], bevel=0.02))
        add(C.box_between("bedfloor", -0.84, 0.84, b0, R - 0.06, 1.23, 1.25, M["Trim"]))
        add(C.box_between("spareclamp", -0.07, 0.07, b0 + 0.06, b0 + 0.40, 1.25, 1.33, M["Steel"]))

    # Underside.
    for s in (1, -1):
        add(C.box_between("rail", *sx(s, 0.50, 0.62), F + 0.05, R - 0.03, 0.50, 0.66, M["Chassis"]))
    add(C.box_between("pan", -0.50, 0.50, F + 0.02, R - 0.02, 0.58, 0.67, M["Chassis"]))
    add(C.tube("antenna", (0.80, S["cab_rt"] - 0.04, 1.98), (0.80, S["cab_rt"] + 0.02, 2.85), 0.006, M["Trim"], 6))

    body = C.join(P, f"Body_{name}")
    C.smooth_by_angle(body, 32)
    return body


def roof_rack(M, name, S):
    P = []
    z = 2.06
    y0, y1 = S["cab_ft"] + 0.10, S["cab_rt"] - 0.08
    P.append(C.tube_path("rack", [(-0.74, y0, z), (0.74, y0, z), (0.74, y1, z), (-0.74, y1, z), (-0.74, y0, z)],
                         0.022, M["Steel"], 10))
    n = max(1, int((y1 - y0) / 0.6))
    for k in range(1, n):
        y = y0 + (y1 - y0) * k / n
        P.append(C.tube("crossbar", (-0.74, y, z), (0.74, y, z), 0.018, M["Steel"], 8))
    for s in (1, -1):
        for y in (y0 + 0.07, (y0 + y1) / 2, y1 - 0.07):
            P.append(C.box_between("rackleg", *sx(s, 0.71, 0.77), y - 0.03, y + 0.03, 1.97, z, M["Steel"]))
    P.append(C.box_between("lightbar", -0.62, 0.62, y0 - 0.08, y0 + 0.02, 2.06, 2.15, M["Trim"], bevel=0.012))
    for i in range(8):
        x = -0.54 + i * 0.154
        P.append(C.box_between("barlamp", x - 0.062, x + 0.062, y0 - 0.087, y0 - 0.075, 2.075, 2.135, M["Lights"]))
    if y1 - y0 > 1.2:   # full-length roof: cargo
        for x in (0.30, 0.52):
            P.append(C.box_between("jerrycan", x - 0.09, x + 0.09, y1 - 0.58, y1 - 0.12, 2.08, 2.42, M["Paint2"], bevel=0.02))
        P.append(C.box_between("case", -0.68, -0.08, y1 - 0.85, y1 - 0.10, 2.08, 2.30, M["Trim"], bevel=0.025))
        P.append(C.cylinder("tarp", 0.09, 1.2, (0, y0 + 0.4, 2.17), "X", 16, M["Canvas"], bevel=0.02))
    else:
        P.append(C.cylinder("tarp", 0.09, 1.2, ((0), (y0 + y1) / 2, 2.17), "X", 16, M["Canvas"], bevel=0.02))
    obj = C.join(P, f"RoofRack_{name}")
    C.smooth_by_angle(obj, 35)
    return obj


def snorkel(M, name, S):
    fb, ft = S["cab_fb"], S["cab_ft"]
    P = [C.tube_path("snorkel", [(-0.97, fb - 0.53, 1.12), (-0.97, fb - 0.10, 1.22), (-0.93, fb + 0.12, 1.55),
                                 (-0.86, ft - 0.10, 1.95), (-0.86, ft - 0.08, 2.08)], 0.045, M["Trim"]),
         C.box_between("snorkelhead", -0.93, -0.79, ft - 0.22, ft, 2.05, 2.20, M["Trim"], bevel=0.02)]
    obj = C.join(P, f"Snorkel_{name}")
    C.smooth_by_angle(obj, 35)
    return obj


def bull_bar(M, name, S):
    F = S["tub_front"]
    P = [C.tube_path("bullbar", [(-0.55, F - 0.22, 0.80), (-0.45, F - 0.20, 1.10), (0.45, F - 0.20, 1.10), (0.55, F - 0.22, 0.80)],
                     0.035, M["Steel"]),
         C.tube("bullbar_mid", (-0.42, F - 0.20, 0.95), (0.42, F - 0.20, 0.95), 0.025, M["Steel"])]
    for s in (1, -1):
        P.append(C.cylinder("spot", 0.075, 0.08, (s * 0.32, F - 0.27, 1.17), "Y", 16, M["Trim"]))
        P.append(C.cylinder("spotlens", 0.06, 0.02, (s * 0.32, F - 0.315, 1.17), "Y", 16, M["Lights"]))
    obj = C.join(P, f"BullBar_{name}")
    C.smooth_by_angle(obj, 35)
    return obj


# ---------------------------------------------------------------------------------- rock crawler

CR = dict(front_axle=-1.30, rear_axle=1.30, track=0.94, wheel_r=0.47, tub_front=-1.98, tub_rear=1.72,
          cowl=-0.52, hoop=0.38, rear_hoop=1.52)


def build_crawler(M):
    P = []
    add = P.append
    F, R = CR["tub_front"], CR["tub_rear"]
    FA, RA, WR = CR["front_axle"], CR["rear_axle"], CR["wheel_r"]
    cowl, hoop, rhoop = CR["cowl"], CR["hoop"], CR["rear_hoop"]

    # Tub: high, with big arches cut for 37s and full articulation.
    tub = C.box_between("tub", -0.82, 0.82, F + 0.25, R, 0.95, 1.40, M["Paint"], bevel=0.035, segments=3)
    C.boolean_cut(tub, [C.cylinder(f"arch{i}", 0.68, 2.4, (0, y, WR + 0.05), "X", 40) for i, y in enumerate((FA, RA))])
    add(tub)
    # Bonnet, raked slightly, and the grille: horizontal mesh with round lamps either side.
    add(C.hull("bonnet", [(-0.80, F + 0.25, 1.36), (0.80, F + 0.25, 1.36), (0.80, cowl, 1.40), (-0.80, cowl, 1.40)],
               [(-0.78, F + 0.27, 1.43), (0.78, F + 0.27, 1.43), (0.78, cowl, 1.50), (-0.78, cowl, 1.50)],
               M["Paint"], bevel=0.02))
    add(C.box_between("grille", -0.66, 0.66, F + 0.22, F + 0.27, 0.98, 1.38, M["Trim"], bevel=0.01))
    for z in (1.04, 1.10, 1.16, 1.22, 1.28, 1.34):
        add(C.box_between("slat", -0.36, 0.36, F + 0.205, F + 0.22, z - 0.014, z + 0.014, M["Steel"]))
    for s in (1, -1):
        add(C.cylinder("lampring", 0.12, 0.03, (s * 0.52, F + 0.21, 1.20), "Y", 24, M["Steel"]))
        add(C.cylinder("lamp", 0.1, 0.03, (s * 0.52, F + 0.20, 1.20), "Y", 24, M["Lights"]))
        add(C.box_between("taillight", *sx(s, 0.66, 0.78), R - 0.005, R + 0.02, 1.12, 1.30, M["TailLights"], bevel=0.008))
        # Flat tube fenders: a flat top plus a steel tube outline, high over the tyres.
        for y in (FA, RA):
            add(C.box_between("fender", *sx(s, 0.80, 1.12), y - 0.62, y + 0.62, 1.37, 1.40, M["Trim"], bevel=0.008))
            # Tube edge along the outside of the flat fender, bending back in to the tub at each end.
            add(C.tube_path("fendertube", [(s * 0.84, y - 0.66, 1.30), (s * 1.10, y - 0.60, 1.37), (s * 1.12, y, 1.38),
                                           (s * 1.10, y + 0.60, 1.37), (s * 0.84, y + 0.66, 1.30)], 0.022, M["Steel"], 8))
            add(C.box_between("fenderliner", *sx(s, 0.80, 1.10), y + (0.6 if y < 0 else -0.62), y + (0.62 if y < 0 else -0.6),
                              1.0, 1.37, M["Trim"]))
        # Rock sliders with uprights to the frame.
        y0, y1 = FA + 0.72, RA - 0.72
        add(C.tube_path("slider", [(s * 0.80, y0 - 0.05, 0.92), (s * 0.98, y0, 0.84), (s * 0.98, y1, 0.84),
                                   (s * 0.80, y1 + 0.05, 0.92)], 0.038, M["Steel"], 10))
        add(C.tube("sliderkick", (s * 0.98, y0 + 0.1, 0.84), (s * 1.0, y0 + 0.1, 1.05), 0.028, M["Steel"], 8))
        for y in (y0 + 0.5, (y0 + y1) / 2, y1 - 0.3):
            add(C.tube("sliderleg", (s * 0.98, y, 0.84), (s * 0.55, y, 0.78), 0.026, M["Steel"], 8))
        # Exo cage: A-pillars from the cowl, roof rails, main hoop, rear hoop down to the tub corners.
        add(C.tube_path("cage", [(s * 0.80, cowl, 1.46), (s * 0.74, cowl + 0.32, 2.04), (s * 0.74, hoop, 2.06),
                                 (s * 0.74, rhoop - 0.2, 2.0), (s * 0.80, R - 0.05, 1.42)], 0.03, M["Steel"], 10))
        add(C.tube("hoopleg", (s * 0.80, hoop, 1.40), (s * 0.74, hoop, 2.06), 0.032, M["Steel"], 10))
        add(C.tube("harness", (s * 0.74, hoop, 1.70), (s * 0.30, hoop - 0.02, 1.70), 0.02, M["Steel"], 8))
        add(C.tube("aframe", (s * 0.80, cowl + 0.05, 1.46), (s * 0.82, F + 0.30, 1.44), 0.022, M["Steel"], 8))
        # Seats and a low door bar.
        add(C.box_between("seat", *sx(s, 0.12, 0.62), hoop - 0.55, hoop - 0.10, 1.10, 1.22, M["Trim"], bevel=0.03))
        add(C.box_between("seatback", *sx(s, 0.14, 0.60), hoop - 0.16, hoop - 0.04, 1.20, 1.88, M["Trim"], bevel=0.03))
        add(C.tube("doorbar", (s * 0.82, cowl + 0.1, 1.52), (s * 0.82, hoop - 0.05, 1.52), 0.022, M["Steel"], 8))
        add(C.box_between("mirror", *sx(s, 0.80, 0.94), cowl + 0.25, cowl + 0.30, 1.78, 1.88, M["Trim"], bevel=0.01))
    for y in (cowl + 0.32, hoop, rhoop - 0.2):
        add(C.tube("cagebar", (-0.74, y, 2.05), (0.74, y, 2.05), 0.028, M["Steel"], 10))
    add(C.tube("diag", (-0.74, hoop, 2.06), (0.74, hoop, 1.45), 0.026, M["Steel"], 8))
    # Upright windscreen frame and glass.
    add(C.tube_path("wsframe", [(-0.78, cowl + 0.02, 1.50), (-0.76, cowl + 0.06, 1.96), (0.76, cowl + 0.06, 1.96),
                                (0.78, cowl + 0.02, 1.50)], 0.025, M["Trim"], 8))
    add(C.hull("windscreen", [(-0.74, cowl + 0.02, 1.52), (0.74, cowl + 0.02, 1.52), (0.74, cowl + 0.035, 1.52), (-0.74, cowl + 0.035, 1.52)],
               [(-0.72, cowl + 0.055, 1.94), (0.72, cowl + 0.055, 1.94), (0.72, cowl + 0.07, 1.94), (-0.72, cowl + 0.07, 1.94)],
               M["Glass"]))
    add(C.box_between("dash", -0.76, 0.76, cowl, cowl + 0.25, 1.40, 1.58, M["Trim"], bevel=0.02))
    add(C.cylinder("wheelrim", 0.18, 0.03, (0.35, cowl + 0.32, 1.62), "Y", 20, M["Trim"]))
    # LED pods on the A-pillars and a light bar on the front cage bar.
    for s in (1, -1):
        add(C.box_between("pod", *sx(s, 0.66, 0.80), cowl + 0.12, cowl + 0.2, 1.88, 1.98, M["Trim"], bevel=0.01))
        add(C.box_between("podlens", *sx(s, 0.68, 0.78), cowl + 0.108, cowl + 0.12, 1.895, 1.965, M["Lights"]))
    add(C.box_between("lightbar", -0.6, 0.6, cowl + 0.28, cowl + 0.36, 2.09, 2.17, M["Trim"], bevel=0.01))
    add(C.box_between("lightbarlens", -0.57, 0.57, cowl + 0.272, cowl + 0.28, 2.10, 2.16, M["Lights"]))

    # Stubby winch bumper: clears the tyres for approach angle, with winch, fairlead and shackles.
    add(C.box_between("fbumper", -0.62, 0.62, F - 0.10, F + 0.24, 0.80, 1.04, M["Steel"], bevel=0.02))
    add(C.cylinder("winchdrum", 0.1, 0.5, (0, F + 0.03, 1.12), "X", 20, M["Trim"]))
    add(C.cylinder("winchmotor", 0.085, 0.16, (-0.33, F + 0.03, 1.12), "X", 16, M["Trim"]))
    add(C.box_between("fairlead", -0.12, 0.12, F - 0.13, F - 0.09, 0.86, 0.98, M["Chrome"]))
    add(C.tube_path("stinger", [(-0.5, F - 0.02, 1.04), (-0.22, F - 0.12, 1.30), (0.22, F - 0.12, 1.30), (0.5, F - 0.02, 1.04)],
                    0.03, M["Steel"], 10))
    for s in (1, -1):
        add(C.cylinder("shackle", 0.055, 0.025, (s * 0.46, F - 0.13, 0.92), "X", 16, M["Accent"]))
        add(C.box_between("fbumperwing", *sx(s, 0.62, 0.74), F + 0.0, F + 0.24, 0.86, 1.02, M["Steel"], bevel=0.015))
    # Rear bumper with a swing-out tyre carrier.
    add(C.box_between("rbumper", -0.70, 0.70, R - 0.02, R + 0.20, 0.80, 1.02, M["Steel"], bevel=0.02))
    add(C.tube_path("carrier", [(-0.62, R + 0.20, 1.0), (-0.5, R + 0.24, 1.55), (0.5, R + 0.24, 1.55), (0.62, R + 0.20, 1.0)],
                    0.03, M["Steel"], 10))
    add(C.box_between("hitch", -0.06, 0.06, R + 0.20, R + 0.32, 0.82, 0.90, M["Steel"]))
    # Frame, belly skid and engine sump guard (the underside the rocks will hit).
    for s in (1, -1):
        add(C.box_between("rail", *sx(s, 0.42, 0.52), F + 0.0, R + 0.02, 0.76, 0.90, M["Chassis"]))
    add(C.hull("skid", [(-0.5, FA + 0.55, 0.66), (0.5, FA + 0.55, 0.66), (0.5, RA - 0.6, 0.66), (-0.5, RA - 0.6, 0.66)],
               [(-0.52, FA + 0.5, 0.76), (0.52, FA + 0.5, 0.76), (0.52, RA - 0.55, 0.76), (-0.52, RA - 0.55, 0.76)], M["Steel"]))
    add(C.tube("driveshaft", (0, FA + 0.1, WR + 0.02), (0, -0.2, 0.72), 0.04, M["Chassis"], 10))
    add(C.tube("driveshaft2", (0, 0.4, 0.72), (0, RA - 0.15, WR + 0.02), 0.04, M["Chassis"], 10))
    add(C.tube("antenna", (-0.74, hoop, 2.06), (-0.74, hoop + 0.08, 3.0), 0.006, M["Trim"], 6))

    body = C.join(P, "Body_Crawler")
    C.smooth_by_angle(body, 32)
    return body


def crawler_accessories(M):
    hoop, rhoop, cowl = CR["hoop"], CR["rear_hoop"], CR["cowl"]
    F = CR["tub_front"]
    objs = []
    P = [C.tube_path("rack", [(-0.70, cowl + 0.4, 2.13), (0.70, cowl + 0.4, 2.13), (0.70, rhoop - 0.25, 2.13),
                              (-0.70, rhoop - 0.25, 2.13), (-0.70, cowl + 0.4, 2.13)], 0.02, M["Steel"], 8)]
    for y in (cowl + 0.8, hoop + 0.25, hoop + 0.7):
        P.append(C.tube("slat", (-0.7, y, 2.13), (0.7, y, 2.13), 0.016, M["Steel"], 8))
    P += [C.box_between("case", -0.62, -0.06, hoop + 0.1, hoop + 0.9, 2.15, 2.38, M["Trim"], bevel=0.025),
          C.box_between("jerry", 0.2, 0.38, hoop + 0.2, hoop + 0.7, 2.15, 2.5, M["Paint2"], bevel=0.02),
          C.cylinder("tarp", 0.09, 1.2, (0, cowl + 0.6, 2.24), "X", 16, M["Canvas"], bevel=0.02),
          C.box_between("maxtrax", 0.42, 0.66, cowl + 0.45, hoop + 0.6, 2.15, 2.2, M["Accent"], bevel=0.01)]
    rack = C.join(P, "RoofRack_Crawler")
    C.smooth_by_angle(rack, 35)
    objs.append(rack)
    sn = C.join([C.tube_path("snorkel", [(-0.84, cowl - 0.45, 1.30), (-0.86, cowl - 0.1, 1.42), (-0.84, cowl + 0.05, 1.7),
                                         (-0.80, cowl + 0.08, 2.1), (-0.80, cowl + 0.1, 2.22)], 0.045, M["Trim"]),
                 C.box_between("snorkelhead", -0.87, -0.73, cowl - 0.02, cowl + 0.2, 2.18, 2.32, M["Trim"], bevel=0.02)],
                "Snorkel_Crawler")
    C.smooth_by_angle(sn, 35)
    objs.append(sn)
    bb = [C.tube_path("hoop", [(-0.6, F - 0.05, 1.04), (-0.5, F - 0.05, 1.45), (0.5, F - 0.05, 1.45), (0.6, F - 0.05, 1.04)],
                      0.034, M["Steel"])]
    for s in (1, -1):
        bb.append(C.cylinder("spot", 0.08, 0.09, (s * 0.3, F - 0.10, 1.52), "Y", 16, M["Trim"]))
        bb.append(C.cylinder("spotlens", 0.065, 0.02, (s * 0.3, F - 0.15, 1.52), "Y", 16, M["Lights"]))
    bull = C.join(bb, "BullBar_Crawler")
    C.smooth_by_angle(bull, 35)
    objs.append(bull)
    return objs


def axle_parts(M):
    """Solid-axle housing, a suspension link and a coilover, as separate parts the game poses every frame."""
    half = CR["track"] - 0.16
    P = [C.cylinder("tube", 0.065, 2 * half, (0, 0, 0), "X", 16, M["Chassis"]),
         C.sphere("pumpkin", 0.17, (0.14, 0.02, 0.0), M["Chassis"]),
         C.cylinder("diffcover", 0.15, 0.06, (0.14, 0.15, 0.0), "Y", 20, M["Accent"]),
         C.box_between("truss", -half + 0.1, half - 0.1, -0.03, 0.03, 0.06, 0.1, M["Chassis"])]
    for s in (1, -1):
        P.append(C.cylinder("knuckle", 0.11, 0.12, (s * (half - 0.02), 0, 0), "X", 18, M["Chassis"]))
        for dy in (-0.08, 0.08):
            P.append(C.box_between("linktab", *sx(s, 0.3, 0.36), dy - 0.02, dy + 0.02, -0.12, 0.12, M["Steel"]))
    axle = C.join(P, "Axle_Housing")
    C.smooth_by_angle(axle, 40)
    # Link: rod ends at both ends (forward = Blender -Y, so the far end is at y = -1).
    link = C.join([C.tube("rod", (0, -0.04, 0), (0, -0.96, 0), 0.03, M["Steel"], 10),
                   C.cylinder("eye0", 0.045, 0.05, (0, -0.02, 0), "X", 14, M["Chassis"]),
                   C.cylinder("eye1", 0.045, 0.05, (0, -0.98, 0), "X", 14, M["Chassis"])], "Link_Unit")
    C.smooth_by_angle(link, 40)
    # Coilover: body and reservoir at the top (y = 0), spring around it, shaft down to the axle (y = -1).
    coil = [C.cylinder("body", 0.045, 0.55, (0, -0.30, 0), "Y", 14, M["Chrome"]),
            C.cylinder("reservoir", 0.03, 0.3, (0.07, -0.18, 0), "Y", 10, M["Chrome"]),
            C.tube("shaft", (0, -0.55, 0), (0, -0.98, 0), 0.016, M["Chrome"], 8),
            C.cylinder("eye", 0.035, 0.05, (0, -0.99, 0), "X", 12, M["Chassis"])]
    turns, pts = 7, []
    for i in range(turns * 12 + 1):
        a = 2 * math.pi * i / 12
        pts.append((0.075 * math.cos(a), -0.08 - 0.72 * i / (turns * 12), 0.075 * math.sin(a)))
    coil.append(C.tube_path("spring", pts, 0.012, M["Accent"], 6))
    coilover = C.join(coil, "Coilover_Unit")
    C.smooth_by_angle(coilover, 40)
    return [axle, link, coilover]


def spare_mount(S):
    if S["bed"]:
        return (0.0, S["cab_rb"] + 0.30, 1.24 + WHEEL_R + 0.02)
    return (0.0, S["tub_rear"] + 0.22, 1.13)


def build():
    C.reset_scene()
    M = palette()
    objs = [build_crawler(M)] + crawler_accessories(M) + axle_parts(M)
    for n, s, y in (("WheelFL", 1, CR["front_axle"]), ("WheelFR", -1, CR["front_axle"]),
                    ("WheelRL", 1, CR["rear_axle"]), ("WheelRR", -1, CR["rear_axle"])):
        objs.append(C.empty(f"Crawler_{n}", (s * CR["track"], y, CR["wheel_r"])))
    objs.append(C.empty("Crawler_Spare", (0.0, CR["tub_rear"] + 0.52, 1.30)))
    for name, S in BODIES.items():
        objs.append(build_body(M, name, S))
        objs += [roof_rack(M, name, S), snorkel(M, name, S), bull_bar(M, name, S)]
        for n, s, y in (("WheelFL", 1, S["front_axle"]), ("WheelFR", -1, S["front_axle"]),
                        ("WheelRL", 1, S["rear_axle"]), ("WheelRR", -1, S["rear_axle"])):
            objs.append(C.empty(f"{name}_{n}", (s * TRACK_X, y, WHEEL_Z)))
        objs.append(C.empty(f"{name}_Spare", spare_mount(S)))
    objs.append(W.build("Wheel_AT", WHEEL_R, WHEEL_W, mats=M, style="at"))
    objs.append(W.build("Wheel_MT", 0.44, 0.33, mats=M, style="mt"))
    objs.append(W.build("Wheel_Dune", 0.44, 0.40, mats=M, style="dune"))
    objs.append(W.build("Wheel_Bead", 0.47, 0.34, rim_radius=0.24, mats=M, style="bead"))
    return objs


if __name__ == "__main__":
    objs = build()
    for o in objs:
        if o.type == "MESH":
            print(f"{o.name:22s} tris={C.tri_count(o):6d} size={tuple(round(d, 2) for d in o.dimensions)}")
    C.export_fbx(objs, C.path_in_repo("Assets", "Models", "Vehicles", "Fleet.fbx"))
