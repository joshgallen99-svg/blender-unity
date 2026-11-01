"""Granite landforms for the forest river valley, built as signed distance fields (shares the toolkit
in sandstone_formations.py) and meshed with marching cubes.

Run:  python blender/formations/granite_formations.py
Writes: Assets/Models/Formations/GraniteFormations.fbx (each piece also as <name>_LOD1 at ~25%)
  Dome_0..1    exfoliating granite domes with one sheer, glacier-cut face (Half Dome in miniature)
  Crag_0..2    blocky, jointed cliffs: stepped blocks split by vertical and sheeting joints
  Tor_0..1     stacks of rounded boulders
  Falls_0      a curved cliff band with a notch for the waterfall to pour through
Material: "Granite" -> Offroad/ForestRock (triplanar granite, moss on top, blends into the forest floor).
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

from lib import common as C  # noqa: E402
from sandstone_formations import Grid, ellipsoid, fbm3, lod, mesh_from_sdf, noise3, rounded_box, smax, smin  # noqa: E402


def weather(g, sd, seed, joint_spacing=7.0, joint_depth=1.0, sheet_spacing=0.0, sheet_depth=0.0, warp=1.4, knobs=0.35):
    """Granite weathering: soft bulges, crossing vertical joints, optional horizontal sheeting joints."""
    v = g.voxel
    sd = sd + warp * fbm3(g.shape, 6.0 / v, seed, 3)
    sd = sd + knobs * fbm3(g.shape, 1.6 / v, seed + 3, 2)
    wob = 1.2 * noise3(g.shape, 9.0 / v, seed + 7)
    for ang in (0.2, 1.75):
        u = (g.x * math.cos(ang) + g.y * math.sin(ang) + wob) / joint_spacing
        groove = np.clip(1.0 - np.abs(u - np.round(u)) / 0.06, 0, 1) ** 2
        sd = sd + groove * joint_depth * (g.z > -0.5)
    if sheet_depth > 0:
        t = (g.z + 0.6 * noise3(g.shape, 7.0 / v, seed + 11)) / sheet_spacing
        sheet = np.clip(1.0 - np.abs(t - np.round(t)) / 0.08, 0, 1) ** 2
        sd = sd + sheet * sheet_depth
    return sd


def dome(seed, radius, height, face_angle):
    rng = np.random.default_rng(seed)
    g = Grid((radius + 6, radius + 6, height + 4), 0.75)
    sd = ellipsoid(g.x, g.y, g.z, (0, 0, -height * 0.15), (radius, radius * 0.85, height * 1.15))
    # Sheer face: a steep plane on one side, as if a glacier sheared it off.
    n = np.array([math.cos(face_angle), math.sin(face_angle)])
    plane = g.x * n[0] + g.y * n[1] - radius * 0.35 + 0.08 * np.clip(g.z, 0, None)
    sd = smax(sd, plane, 3.0)
    # Exfoliation: concentric shells peeling off the rounded side.
    r = np.sqrt(g.x ** 2 + g.y ** 2 + (g.z * 1.2) ** 2)
    shell = r / 4.5 + 0.5 * noise3(g.shape, 10.0 / g.voxel, seed + 1)
    sd = sd + np.clip(1.0 - np.abs(shell - np.round(shell)) / 0.1, 0, 1) * 0.7
    sd = smax(sd, -(g.z + 3.0), 1.0)
    return g, weather(g, sd, seed, joint_spacing=14.0, joint_depth=1.4, warp=1.8)


def crag(seed, size):
    rng = np.random.default_rng(seed)
    g = Grid((size[0] / 2 + 5, size[1] / 2 + 5, size[2] + 4), 0.55)
    sd = np.full(g.shape, 1e3)
    bx, by = 5.5, 5.0
    nx, ny = int(size[0] / bx), int(size[1] / by)
    for i in range(nx):
        for j in range(ny):
            cx = (i + 0.5) * bx - size[0] / 2 + rng.uniform(-0.8, 0.8)
            cy = (j + 0.5) * by - size[1] / 2 + rng.uniform(-0.8, 0.8)
            edge = 1 - max(abs(cx) / (size[0] / 2), abs(cy) / (size[1] / 2))
            h = size[2] * (0.35 + 0.65 * edge ** 0.4) * rng.uniform(0.75, 1.1)
            if h < 1.5:
                continue
            sd = smin(sd, rounded_box(g.x, g.y, g.z, (cx, cy, h / 2 - 1.5), (bx * 0.55, by * 0.55, h / 2 + 1.5), 1.2), 0.9)
    sd = smax(sd, -(g.z + 3.0), 1.0)
    return g, weather(g, sd, seed, joint_spacing=5.5, joint_depth=0.9, sheet_spacing=4.5, sheet_depth=0.6, warp=0.9, knobs=0.3)


def tor(seed, count, size):
    rng = np.random.default_rng(seed)
    g = Grid((size + 4, size + 4, size * 1.8 + 3), 0.45)
    sd = np.full(g.shape, 1e3)
    z = -1.0
    for k in range(count):
        r = size * (0.65 - 0.08 * k) * rng.uniform(0.85, 1.1)
        rz = r * rng.uniform(0.45, 0.6)
        c = (rng.uniform(-0.25, 0.25) * size, rng.uniform(-0.25, 0.25) * size, z + rz)
        sd = smin(sd, ellipsoid(g.x, g.y, g.z, c, (r, r * rng.uniform(0.75, 0.95), rz)), 0.5)
        z += rz * 1.75
    sd = smax(sd, -(g.z + 2.5), 1.0)
    return g, weather(g, sd, seed, joint_spacing=30.0, joint_depth=0.0, warp=0.6, knobs=0.25)


def falls(seed, width, height, notch_w):
    """Curved cliff band (concave toward -Y, the pool side) with a notch at the top centre."""
    rng = np.random.default_rng(seed)
    g = Grid((width / 2 + 6, 22, height + 8), 0.6)
    bow = (g.x / (width / 2)) ** 2 * 8.0                    # curves back at the ends
    face = -(g.y - bow + 2.0 * noise3(g.shape, 6.0 / g.voxel, seed + 2))
    top = g.z - height - 4.0 * fbm3(g.shape, 12.0 / g.voxel, seed + 4, 2)
    sd = np.maximum(face, top)
    sd = np.maximum(sd, g.y - 20)
    sd = smax(sd, np.abs(g.x) - width / 2, 6.0)
    # The notch the river pours through, worn smooth.
    notch = np.maximum(np.abs(g.x) - notch_w / 2, -(g.z - height + 3.5))
    sd = smax(sd, -notch, 1.5)
    sd = smax(sd, -(g.z + 3.0), 1.0)
    return g, weather(g, sd, seed, joint_spacing=6.5, joint_depth=1.1, sheet_spacing=3.8, sheet_depth=0.5, warp=1.0)


SPECS = [
    ("Dome_0", dome, (701, 42, 38, 0.6), 16000),
    ("Dome_1", dome, (702, 30, 26, 2.4), 13000),
    ("Crag_0", crag, (711, (34, 16, 18)), 14000),
    ("Crag_1", crag, (712, (24, 14, 12)), 11000),
    ("Crag_2", crag, (713, (46, 18, 24)), 16000),
    ("Tor_0", tor, (721, 4, 6.0), 6000),
    ("Tor_1", tor, (722, 3, 4.5), 5000),
    ("Falls_0", falls, (731, 64, 22, 9), 16000),
]


def build(only=None):
    C.reset_scene()
    mat = C.material("Granite", (0.45, 0.45, 0.45), 0.0, 0.85)
    objs = []
    for name, fn, args, budget in SPECS:
        if only and name not in only:
            continue
        g, sd = fn(*args)
        obj = mesh_from_sdf(name, g, sd, mat, budget)
        objs.append(obj)
        objs.append(lod(obj, 0.25))
        print(f"{name:10s} tris={C.tri_count(obj):6d} lod1={C.tri_count(objs[-1]):5d} "
              f"size={tuple(round(d, 1) for d in obj.dimensions)}", flush=True)
    return objs


if __name__ == "__main__":
    objs = build(sys.argv[1].split(",") if len(sys.argv) > 1 else None)
    C.export_fbx(objs, C.path_in_repo("Assets", "Models", "Formations", "GraniteFormations.fbx"))
