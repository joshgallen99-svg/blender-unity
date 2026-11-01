"""Off-road wheel: lugged tyre + beadlock-style rim.

Built around the origin with the axle along X; the rim's show face points +X.
"""
import math

import bpy  # noqa: F401
import bmesh
from mathutils import Matrix, Vector

from . import common as C


def _revolve(name, profile, segments, mat):
    """Revolve a closed (x, r) profile around the X axis."""
    bm = bmesh.new()
    rings = []
    for s in range(segments):
        a = 2 * math.pi * s / segments
        ca, sa = math.cos(a), math.sin(a)
        rings.append([bm.verts.new((x, r * ca, r * sa)) for x, r in profile])
    n = len(profile)
    for s in range(segments):
        r0, r1 = rings[s], rings[(s + 1) % segments]
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    return C.from_bmesh(name, bm, mat)


def _ring_of_boxes(name, count, size, radius, x, mat, phase=0.0, tilt=0.0):
    """`count` boxes spaced around the X axis at `radius`; size = (along X, tangential, radial)."""
    bm = bmesh.new()
    for i in range(count):
        a = 2 * math.pi * i / count + phase
        geom = bmesh.ops.create_cube(bm, size=1.0)
        vs = geom["verts"]
        bmesh.ops.scale(bm, vec=size, verts=vs)
        if tilt:
            bmesh.ops.rotate(bm, verts=vs, matrix=Matrix.Rotation(tilt, 3, "Z"))
        bmesh.ops.translate(bm, vec=(x, 0, radius), verts=vs)
        bmesh.ops.rotate(bm, verts=vs, matrix=Matrix.Rotation(a, 3, "X"))
    return C.from_bmesh(name, bm, mat)


def build(name="Wheel", radius=0.43, width=0.32, rim_radius=0.255, detail=1.0, mats=None, style="at"):
    """style: "at" all-terrain (bronze beadlock), "mt" mud/crawler (big blocks, black steel),
    "dune" sand floater (wide balloon tyre, paddle ribs, white spokes)."""
    tire_m, steel_m, dark_m = mats["Tire"], mats["Steel"], mats["Trim"]
    rim_m = mats.get({"at": "Rim", "mt": "RimBlack", "dune": "RimWhite"}[style], mats["Rim"])
    R, w, rb = radius, width, rim_radius
    hw = w / 2
    seg = max(16, int(40 * detail))
    lug_h = {"at": 0.024, "mt": 0.034, "dune": 0.012}[style]
    core = R - lug_h * 0.6
    sh = 0.07 if style != "dune" else 0.11          # rounder shoulders on the balloon tyre

    profile = [(-hw + 0.01, rb), (-hw, rb + 0.04), (-hw, core - sh), (-hw + sh * 0.35, core - sh * 0.3),
               (-hw + sh, core), (hw - sh, core), (hw - sh * 0.35, core - sh * 0.3), (hw, core - sh),
               (hw, rb + 0.04), (hw - 0.01, rb)]
    parts = [_revolve(name + "_tyre", profile, seg, tire_m)]

    if style == "at":
        lugs = max(12, int(22 * detail))
        step = 2 * math.pi / lugs
        parts.append(_ring_of_boxes(name + "_lugA", lugs, (0.115, 0.075, lug_h * 2), core, -0.065, tire_m, 0.0, 0.18))
        parts.append(_ring_of_boxes(name + "_lugB", lugs, (0.115, 0.075, lug_h * 2), core, 0.065, tire_m, step / 2, -0.18))
        if detail >= 0.75:
            parts.append(_ring_of_boxes(name + "_shA", lugs, (0.035, 0.06, 0.09), core - 0.04, -hw + 0.008, tire_m, step / 2))
            parts.append(_ring_of_boxes(name + "_shB", lugs, (0.035, 0.06, 0.09), core - 0.04, hw - 0.008, tire_m, 0.0))
    elif style == "mt":
        lugs = max(10, int(16 * detail))
        step = 2 * math.pi / lugs
        parts.append(_ring_of_boxes(name + "_lugA", lugs, (0.14, 0.11, lug_h * 2), core, -0.07, tire_m, 0.0, 0.32))
        parts.append(_ring_of_boxes(name + "_lugB", lugs, (0.14, 0.11, lug_h * 2), core, 0.07, tire_m, step / 2, -0.32))
        if detail >= 0.75:
            parts.append(_ring_of_boxes(name + "_shA", lugs, (0.05, 0.09, 0.13), core - 0.05, -hw + 0.01, tire_m, step / 2))
            parts.append(_ring_of_boxes(name + "_shB", lugs, (0.05, 0.09, 0.13), core - 0.05, hw - 0.01, tire_m, 0.0))
    else:
        ribs = max(12, int(18 * detail))
        parts.append(_ring_of_boxes(name + "_ribA", ribs, (w * 0.45, 0.03, lug_h * 2), core, -w * 0.22, tire_m, 0.0, 0.5))
        parts.append(_ring_of_boxes(name + "_ribB", ribs, (w * 0.45, 0.03, lug_h * 2), core, w * 0.22, tire_m, 0.0, -0.5))

    # Rim barrel and recessed centre (shared), then a style-specific face.
    parts.append(C.cylinder(name + "_barrel", rb, w - 0.04, (-0.01, 0, 0), "X", seg, rim_m))
    parts.append(C.cylinder(name + "_well", rb - 0.035, 0.02, (hw - 0.05, 0, 0), "X", seg, dark_m))
    if style == "at":
        parts.append(_revolve(name + "_bead", [(hw - 0.035, rb - 0.045), (hw - 0.005, rb - 0.04), (hw - 0.005, rb + 0.012),
                                                (hw - 0.035, rb + 0.012)], seg, rim_m))
        spokes, spoke_r = 6, 0.024
    elif style == "mt":
        parts.append(C.cylinder(name + "_disc", rb - 0.03, 0.025, (hw - 0.045, 0, 0), "X", seg, rim_m))
        for i in range(8):     # steel-wheel holes (dark insets)
            a = 2 * math.pi * i / 8
            parts.append(C.cylinder(f"{name}_hole{i}", 0.032, 0.03, (hw - 0.03, 0.16 * math.cos(a), 0.16 * math.sin(a)),
                                    "X", 12, dark_m))
        spokes, spoke_r = 0, 0
    else:
        spokes, spoke_r = 5, 0.04
    for i in range(spokes):
        a = 2 * math.pi * i / spokes
        p0 = Vector((hw - 0.04, 0.05 * math.cos(a), 0.05 * math.sin(a)))
        p1 = Vector((hw - 0.025, (rb - 0.04) * math.cos(a), (rb - 0.04) * math.sin(a)))
        parts.append(C.tube(f"{name}_spoke{i}", p0, p1, spoke_r, rim_m, 8))
    parts.append(C.cylinder(name + "_hub", 0.075, 0.07, (hw - 0.03, 0, 0), "X", 20, rim_m, radius2=0.06))
    parts.append(C.cylinder(name + "_cap", 0.035, 0.03, (hw + 0.005, 0, 0), "X", 16, steel_m))
    if detail >= 0.75:
        if style == "at":
            parts.append(_ring_of_boxes(name + "_bolts", 16, (0.016, 0.014, 0.014), rb - 0.015, hw - 0.002, steel_m))
        parts.append(_ring_of_boxes(name + "_nuts", 6, (0.02, 0.018, 0.018), 0.05, hw + 0.006, steel_m, math.pi / 6))

    wheel = C.join(parts, name)
    C.smooth_by_angle(wheel, 40)
    return wheel


def transform(obj, matrix):
    obj.data.transform(matrix)
    obj.data.update()
    return obj
