"""Alpine rock for Highline Pass: jagged gneiss towers, crests and glacial erratics, built as signed
distance fields (toolkit shared with sandstone_formations.py) and meshed with marching cubes.

Run:  python blender/formations/alpine_formations.py
Writes: Assets/Models/Formations/AlpineFormations.fbx (each piece also as <name>_LOD1 at ~25%)
  Spire_0..1    tall, splintered towers of tilted slabs (Grey Tooth's summit, the Sentinels)
  Ridge_0..2    saw-toothed crests and cliff bands: slabs dipping one way, broken into pinnacles
  Erratic_0..1  big angular boulders the glacier left on the valley floor
Material: "AlpineRock" -> Offroad/ForestRock with the alpine rock, lichen and snow on ledges above the snowline.
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

from lib import common as C  # noqa: E402
from sandstone_formations import Grid, fbm3, lod, mesh_from_sdf, noise3, rounded_box, smax, smin  # noqa: E402


def foliate(g, sd, seed, spacing=2.6, depth=0.5, dip=0.6, strike=0.3, warp=0.8):
    """Gneiss weathering: inclined foliation grooves, cross joints and a little surface warp."""
    v = g.voxel
    sd = sd + warp * fbm3(g.shape, 5.0 / v, seed, 3)
    nx, ny, nz = math.cos(strike) * math.sin(dip), math.sin(strike) * math.sin(dip), math.cos(dip)
    t = (g.x * nx + g.y * ny + g.z * nz + 0.8 * noise3(g.shape, 8.0 / v, seed + 3)) / spacing
    sd = sd + np.clip(1.0 - np.abs(t - np.round(t)) / 0.1, 0, 1) ** 2 * depth
    u = (g.x * math.cos(strike + 1.4) + g.y * math.sin(strike + 1.4) + noise3(g.shape, 9.0 / v, seed + 5)) / (spacing * 2.3)
    sd = sd + np.clip(1.0 - np.abs(u - np.round(u)) / 0.06, 0, 1) ** 2 * depth * 1.2
    return sd


def slab(g, c, half, yaw, tilt_x, tilt_y, r):
    """A rounded box rotated about Z by yaw, then leaned by tilt_x / tilt_y (radians)."""
    x, y, z = g.x - c[0], g.y - c[1], g.z - c[2]
    ca, sa = math.cos(yaw), math.sin(yaw)
    x, y = x * ca - y * sa, x * sa + y * ca
    cb, sb = math.cos(tilt_x), math.sin(tilt_x)
    y, z = y * cb - z * sb, y * sb + z * cb
    cc, sc = math.cos(tilt_y), math.sin(tilt_y)
    x, z = x * cc - z * sc, x * sc + z * cc
    return rounded_box(x, y, z, (0, 0, 0), half, r)


def spire(seed, base_r, height):
    rng = np.random.default_rng(seed)
    g = Grid((base_r + 6, base_r + 6, height + 5), 0.7)
    sd = np.full(g.shape, 1e3)
    lean = rng.uniform(-0.12, 0.12, 2)
    for k in range(9):
        t = k / 8
        r = base_r * (1.0 - 0.65 * t) * rng.uniform(0.75, 1.05)
        hgt = height * (0.45 + 0.75 * (1 - abs(t - 0.2))) * rng.uniform(0.75, 1.05)
        a = rng.uniform(0, 2 * math.pi)
        off = base_r * 0.45 * t
        c = (math.cos(a) * off + lean[0] * hgt * 0.5, math.sin(a) * off + lean[1] * hgt * 0.5, hgt / 2 - 3)
        s = slab(g, c, (r * rng.uniform(0.35, 0.6), r * rng.uniform(0.3, 0.5), hgt / 2 + 3), rng.uniform(0, math.pi),
                 rng.uniform(-0.18, 0.18) + lean[1], rng.uniform(-0.18, 0.18) + lean[0], 0.5)
        sd = smin(sd, s, 1.2)
    # Pointed, faceted summit: steep planes through an apex, plus a couple of splintered cuts.
    apex = np.array([lean[0] * height * 0.5 + rng.uniform(-1, 1), lean[1] * height * 0.5 + rng.uniform(-1, 1), height])
    a0 = rng.uniform(0, 2 * math.pi)
    for k in range(5):
        a = a0 + 2 * math.pi * k / 5 + rng.uniform(-0.3, 0.3)
        t = rng.uniform(0.3, 0.5)
        n = np.array([math.cos(a) * math.sin(t), math.sin(a) * math.sin(t), math.cos(t)])
        sd = smax(sd, (g.x - apex[0]) * n[0] + (g.y - apex[1]) * n[1] + (g.z - apex[2]) * n[2], 0.5)
    for _ in range(2):
        n = np.array([rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(0.2, 0.5)])
        n /= np.linalg.norm(n)
        sd = smax(sd, (g.x - apex[0]) * n[0] + (g.y - apex[1]) * n[1] + (g.z - apex[2] * 0.8) * n[2] - base_r * 0.3, 0.4)
    sd = smax(sd, -(g.z + 3.0), 1.0)
    return g, foliate(g, sd, seed, spacing=2.4, depth=0.7, warp=0.45, dip=rng.uniform(0.3, 0.8), strike=rng.uniform(0, 3))


def ridge(seed, length, width, height):
    """A saw-toothed crest along X: slabs dipping one way, heights jumping between pinnacles and notches."""
    rng = np.random.default_rng(seed)
    g = Grid((length / 2 + 5, width / 2 + 6, height + 5), 0.65)
    sd = np.full(g.shape, 1e3)
    n = int(length / 4.2)
    dip = rng.uniform(0.35, 0.6)
    for i in range(n):
        u = (i + 0.5) / n
        x = (u - 0.5) * length + rng.uniform(-0.8, 0.8)
        env = math.sin(math.pi * u) ** 0.6
        hgt = height * env * rng.uniform(0.55, 1.05) * (1.25 if rng.random() < 0.18 else 1.0)
        if hgt < 2.0:
            continue
        w = width * (0.35 + 0.35 * env) * rng.uniform(0.8, 1.1)
        s = slab(g, (x, rng.uniform(-1.2, 1.2), hgt / 2 - 2.5), (rng.uniform(1.4, 2.4), w / 2, hgt / 2 + 2.5),
                 rng.uniform(-0.2, 0.2), rng.uniform(-0.15, 0.15), dip + rng.uniform(-0.1, 0.1), 0.7)
        sd = smin(sd, s, 1.0)
    # Talus apron along the foot.
    apron = rounded_box(g.x, g.y, g.z, (0, 0, -1.5), (length / 2, width / 2 + 2.5, 2.0), 2.0)
    sd = smin(sd, apron + 0.6 * fbm3(g.shape, 3.0 / g.voxel, seed + 9, 2), 2.5)
    sd = smax(sd, -(g.z + 3.0), 1.0)
    return g, foliate(g, sd, seed, spacing=2.2, depth=0.5, dip=dip, strike=0.0, warp=0.7)


def erratic(seed, size):
    rng = np.random.default_rng(seed)
    g = Grid((size[0] + 2, size[1] + 2, size[2] + 2.5), 0.3)
    sd = rounded_box(g.x, g.y, g.z, (0, 0, size[2] * 0.5 - 1.0), (size[0] * 0.8, size[1] * 0.8, size[2] * 0.55), 1.2)
    for _ in range(6):
        n = np.array([rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.2, 1)])
        n /= np.linalg.norm(n)
        sd = smax(sd, g.x * n[0] + g.y * n[1] + (g.z - size[2] * 0.4) * n[2] - max(size) * rng.uniform(0.45, 0.7), 0.4)
    sd = smax(sd, -(g.z + 1.0), 0.5)
    return g, foliate(g, sd, seed, spacing=1.6, depth=0.25, dip=rng.uniform(0.2, 1.2), strike=rng.uniform(0, 3), warp=0.35)


SPECS = [
    ("Spire_0", spire, (801, 12.0, 46.0), 15000),
    ("Spire_1", spire, (802, 9.0, 32.0), 12000),
    ("Ridge_0", ridge, (811, 60.0, 12.0, 20.0), 15000),
    ("Ridge_1", ridge, (812, 44.0, 10.0, 14.0), 12000),
    ("Ridge_2", ridge, (813, 80.0, 14.0, 26.0), 17000),
    ("Erratic_0", erratic, (821, (5.0, 4.0, 4.2)), 4000),
    ("Erratic_1", erratic, (822, (3.4, 3.0, 2.8)), 3000),
]


def build(only=None):
    C.reset_scene()
    mat = C.material("AlpineRock", (0.25, 0.25, 0.26), 0.0, 0.85)
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
    C.export_fbx(objs, C.path_in_repo("Assets", "Models", "Formations", "AlpineFormations.fbx"))
