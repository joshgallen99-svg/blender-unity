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


def build(name="Wheel", radius=0.43, width=0.32, rim_radius=0.255, detail=1.0, mats=None):
    tire_m, rim_m, steel_m, dark_m = mats["Tire"], mats["Rim"], mats["Steel"], mats["Trim"]
    R, w, rb = radius, width, rim_radius
    hw = w / 2
    seg = max(16, int(40 * detail))
    lug_h = 0.024
    core = R - lug_h * 0.6

    # Tyre carcass: rounded shoulders, closed against the rim.
    profile = [(-hw + 0.01, rb), (-hw, rb + 0.04), (-hw, core - 0.07), (-hw + 0.025, core - 0.02),
               (-hw + 0.07, core), (hw - 0.07, core), (hw - 0.025, core - 0.02), (hw, core - 0.07),
               (hw, rb + 0.04), (hw - 0.01, rb)]
    parts = [_revolve(name + "_tyre", profile, seg, tire_m)]

    # Aggressive tread: staggered centre lugs + shoulder blocks wrapping the sidewall.
    lugs = max(12, int(22 * detail))
    step = 2 * math.pi / lugs
    parts.append(_ring_of_boxes(name + "_lugA", lugs, (0.115, 0.075, lug_h * 2), core, -0.065, tire_m, 0.0, 0.18))
    parts.append(_ring_of_boxes(name + "_lugB", lugs, (0.115, 0.075, lug_h * 2), core, 0.065, tire_m, step / 2, -0.18))
    if detail >= 0.75:
        parts.append(_ring_of_boxes(name + "_shA", lugs, (0.035, 0.06, 0.09), core - 0.04, -hw + 0.008, tire_m, step / 2))
        parts.append(_ring_of_boxes(name + "_shB", lugs, (0.035, 0.06, 0.09), core - 0.04, hw - 0.008, tire_m, 0.0))

    # Rim: barrel, recessed dark centre, spokes, beadlock ring with bolts, hub.
    parts.append(C.cylinder(name + "_barrel", rb, w - 0.04, (-0.01, 0, 0), "X", seg, rim_m))
    parts.append(C.cylinder(name + "_well", rb - 0.035, 0.02, (hw - 0.05, 0, 0), "X", seg, dark_m))
    ring = _revolve(name + "_bead", [(hw - 0.035, rb - 0.045), (hw - 0.005, rb - 0.04), (hw - 0.005, rb + 0.012),
                                      (hw - 0.035, rb + 0.012)], seg, rim_m)
    parts.append(ring)
    spokes = 6
    for i in range(spokes):
        a = 2 * math.pi * i / spokes
        p0 = Vector((hw - 0.04, 0.05 * math.cos(a), 0.05 * math.sin(a)))
        p1 = Vector((hw - 0.025, (rb - 0.04) * math.cos(a), (rb - 0.04) * math.sin(a)))
        spoke = C.tube(f"{name}_spoke{i}", p0, p1, 0.024, rim_m, 8)
        parts.append(spoke)
    parts.append(C.cylinder(name + "_hub", 0.075, 0.07, (hw - 0.03, 0, 0), "X", 20, rim_m, radius2=0.06))
    parts.append(C.cylinder(name + "_cap", 0.035, 0.03, (hw + 0.005, 0, 0), "X", 16, steel_m))
    if detail >= 0.75:
        parts.append(_ring_of_boxes(name + "_bolts", 16, (0.016, 0.014, 0.014), rb - 0.015, hw - 0.002, steel_m))
        parts.append(_ring_of_boxes(name + "_nuts", 6, (0.02, 0.018, 0.018), 0.05, hw + 0.006, steel_m,
                                    math.pi / 6))

    wheel = C.join(parts, name)
    C.smooth_by_angle(wheel, 40)
    return wheel


def transform(obj, matrix):
    obj.data.transform(matrix)
    obj.data.update()
    return obj
