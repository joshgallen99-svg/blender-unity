"""Massive sandstone formations, sculpted as signed distance fields and meshed with marching cubes.

Run:  python blender/formations/sandstone_formations.py [--preview]
Writes: Assets/Models/Formations/Formations.fbx
Each formation is exported twice: <Name> (LOD0) and <Name>_LOD1 (~1/4 the triangles).
Origin is at ground level; every formation continues a few metres below the origin so it can be
sunk into uneven terrain.

The look follows the reference photos: Valley of Fire beehive mounds with honeycomb (tafoni)
weathering, layered fins, a flat-topped butte with a talus skirt, slender spires, flat ledges for
slickrock edges, and a natural arch. Horizontal bedding ledges are cut into every shape so the
geometry agrees with the strata colours in the shaders.
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import bpy  # noqa: E402,F401
import bmesh  # noqa: E402
import numpy as np  # noqa: E402
from scipy import ndimage  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402
from skimage import measure  # noqa: E402

from lib import common as C  # noqa: E402


# ---------------------------------------------------------------------------- SDF toolkit (numpy, z up)

def smin(a, b, k):
    """Polynomial smooth minimum (soft union)."""
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


def ellipsoid(x, y, z, c, r):
    """Approximate SDF of an axis-aligned ellipsoid (good enough for sculpting)."""
    px, py, pz = (x - c[0]) / r[0], (y - c[1]) / r[1], (z - c[2]) / r[2]
    k0 = np.sqrt(px * px + py * py + pz * pz)
    k1 = np.sqrt((px / r[0]) ** 2 + (py / r[1]) ** 2 + (pz / r[2]) ** 2)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-6)


def rounded_box(x, y, z, c, half, r):
    qx = np.abs(x - c[0]) - half[0] + r
    qy = np.abs(y - c[1]) - half[1] + r
    qz = np.abs(z - c[2]) - half[2] + r
    outside = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2 + np.maximum(qz, 0) ** 2)
    inside = np.minimum(np.maximum(qx, np.maximum(qy, qz)), 0)
    return outside + inside - r


def noise3(shape, cell, seed):
    """Smooth 3D value noise in [-1, 1] on a grid of `shape` with features about `cell` voxels wide."""
    rng = np.random.default_rng(seed)
    coarse = [max(2, int(math.ceil(s / cell)) + 3) for s in shape]
    g = rng.uniform(-1, 1, coarse)
    coords = np.meshgrid(*[np.arange(s) / cell + 1 for s in shape], indexing="ij")
    return ndimage.map_coordinates(g, coords, order=3, mode="nearest")


def fbm3(shape, cell, seed, octaves=3):
    total, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        total = total + amp * noise3(shape, max(cell / 2 ** o, 1.5), seed + o * 17)
        norm += amp
        amp *= 0.5
    return total / norm


def tafoni(x, y, z, cell, seed, rng_extent):
    """Honeycomb weathering: distance to the nearest random cell centre (small near centres)."""
    rng = np.random.default_rng(seed)
    lo = np.array([x.min(), y.min(), z.min()])
    hi = np.array([x.max(), y.max(), z.max()])
    n = int(np.prod((hi - lo) / cell)) + 1
    pts = lo + rng.random((min(n, 200000), 3)) * (hi - lo)
    d, _ = cKDTree(pts).query(np.c_[x.ravel(), y.ravel(), z.ravel()], k=2)
    f1 = d[:, 0].reshape(x.shape)
    f2 = d[:, 1].reshape(x.shape)
    return f1, f2 - f1


class Grid:
    """Sampling volume: half extents in metres (x, y, z) and voxel size."""

    def __init__(self, half, voxel, zmin=-4.0):
        self.voxel = voxel
        xs = np.arange(-half[0], half[0] + voxel, voxel)
        ys = np.arange(-half[1], half[1] + voxel, voxel)
        zs = np.arange(zmin, half[2] + voxel, voxel)
        self.origin = np.array([xs[0], ys[0], zs[0]])
        self.x, self.y, self.z = np.meshgrid(xs, ys, zs, indexing="ij")
        self.shape = self.x.shape


def bedding(z, period, depth, tilt_x=0.0, tilt_y=0.0, x=None, y=None, warp=None):
    """Horizontal ledges: harder layers stick out, softer ones recess. Returns an SDF offset."""
    t = z / period
    if x is not None:
        t = t + (x * tilt_x + y * tilt_y) / period
    if warp is not None:
        t = t + warp
    f = t - np.floor(t)
    # Sharp lip at the top of each layer, gentle recess below it.
    profile = np.where(f < 0.78, -f / 0.78, -(1 - (f - 0.78) / 0.22))
    return profile * depth


def finish_sdf(g, sd, seed, ledge_period=2.6, ledge_depth=0.45, tilt=(0.06, 0.02), taf_cell=2.2, taf_depth=0.9,
               warp_amp=2.0, joint_spacing=7.0, joint_depth=0.9, knobs=0.7):
    """Common weathering: knobby noise, vertical joints, bedding ledges and honeycomb pits."""
    v = g.voxel
    sd = sd + warp_amp * fbm3(g.shape, 5.0 / v, seed, 3)                 # large knobs and bulges
    sd = sd + knobs * fbm3(g.shape, 1.8 / v, seed + 3, 2)                # small knobbly detail
    # Vertical joints: narrow grooves along two crossing directions, wandering a little.
    wob = 1.5 * noise3(g.shape, 8.0 / v, seed + 7)
    for ang in (0.35, 1.9):
        u = (g.x * math.cos(ang) + g.y * math.sin(ang) + wob) / joint_spacing
        groove = np.clip(1.0 - np.abs(u - np.round(u)) / 0.07, 0, 1) ** 2
        sd = sd + groove * joint_depth * (g.z > -0.5)
    warp = 0.35 * noise3(g.shape, 14.0 / v, seed + 5)
    sd = sd - bedding(g.z, ledge_period, ledge_depth, tilt[0], tilt[1], g.x, g.y, warp)
    f1, edge = tafoni(g.x, g.y, g.z, taf_cell, seed + 9, None)
    pit = np.clip(1.0 - f1 / (taf_cell * 0.62), 0, 1) ** 1.5
    sd = sd + pit * taf_depth * (g.z > 0.4)
    return sd


def mesh_from_sdf(name, g, sd, mat, target_tris):
    sd = np.pad(sd, 1, constant_values=sd.max())        # close the surface at the volume edges
    verts, faces, _, _ = measure.marching_cubes(sd, level=0.0, spacing=(g.voxel,) * 3)
    verts = verts - g.voxel + g.origin
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in verts]
    for f in faces:
        try:
            bm.faces.new((vs[f[2]], vs[f[1]], vs[f[0]]))
        except ValueError:
            pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=g.voxel * 0.25)
    # Faces must wind outward (positive volume), or the engine culls the outside and shows the inside.
    if bm.calc_volume(signed=True) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(mat)
    # Light smoothing pass, then decimate to budget.
    sm = obj.modifiers.new("Smooth", "SMOOTH")
    sm.factor = 0.45
    sm.iterations = 2 if g.voxel >= 0.7 else 1
    C.apply_modifiers(obj)
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    if tris > target_tris:
        dec = obj.modifiers.new("Dec", "DECIMATE")
        dec.ratio = target_tris / tris
        C.apply_modifiers(obj)
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def lod(obj, ratio):
    dup = obj.copy()
    dup.data = obj.data.copy()
    dup.name = obj.name + "_LOD1"
    dup.data.name = dup.name
    bpy.context.scene.collection.objects.link(dup)
    dec = dup.modifiers.new("Dec", "DECIMATE")
    dec.ratio = ratio
    C.apply_modifiers(dup)
    return dup


# ---------------------------------------------------------------------------- formations

def mound(seed, size):
    """Valley of Fire beehive cluster: many knobby lumps with deep crevices, alcoves at the base."""
    rng = np.random.default_rng(seed)
    hx, hy, hz = size[0] / 2 + 5, size[1] / 2 + 5, size[2] + 4
    g = Grid((hx, hy, hz), 0.5)
    sd = np.full(g.shape, 1e3)
    for i in range(rng.integers(12, 18)):
        c = (rng.uniform(-0.42, 0.42) * size[0], rng.uniform(-0.38, 0.38) * size[1], rng.uniform(-0.1, 0.25) * size[2])
        rx = rng.uniform(0.11, 0.24) * size[0]
        ry = rng.uniform(0.13, 0.28) * size[1]
        rz = rng.uniform(0.35, 0.9) * size[2]
        sd = smin(sd, ellipsoid(g.x, g.y, g.z, c, (rx, ry, rz)), 1.8)
    for i in range(rng.integers(3, 6)):   # cavernous alcoves near the base
        a = rng.uniform(0, 2 * math.pi)
        c = (math.cos(a) * size[0] * 0.42, math.sin(a) * size[1] * 0.42, rng.uniform(0.5, 2.5))
        sd = smax(sd, -ellipsoid(g.x, g.y, g.z, c, (rng.uniform(2, 4), rng.uniform(2, 4), rng.uniform(1.5, 3))), 1.0)
    sd = smax(sd, -(g.z + 3.5), 1.0)                  # flat buried base
    return g, finish_sdf(g, sd, seed, ledge_period=2.3, ledge_depth=0.55)


def fin(seed, length, height, width):
    """Long sandstone wall with a lumpy crest and stepped sides."""
    rng = np.random.default_rng(seed)
    g = Grid((length / 2 + 4, width / 2 + 5, height + 3), 0.55)
    crest = height * (0.75 + 0.25 * np.sin(g.x / length * math.pi * rng.uniform(1.5, 3.0) + rng.uniform(0, 6)))
    crest *= np.clip(1.2 - (np.abs(g.x) / (length / 2)) ** 3, 0, 1)
    half_w = width / 2 * (1.0 - 0.45 * np.clip(g.z / np.maximum(crest, 1), 0, 1))   # tapers upward
    sd = np.maximum(np.abs(g.y) - half_w, g.z - crest)
    sd = smax(sd, np.abs(g.x) - length / 2, 4.0)
    sd = smax(sd, -(g.z + 3.5), 1.0)
    for i in range(3):   # a few lumps on the flanks
        c = (rng.uniform(-0.4, 0.4) * length, rng.choice([-1, 1]) * width * 0.4, rng.uniform(0.2, 0.5) * height)
        sd = smin(sd, ellipsoid(g.x, g.y, g.z, c, (length * 0.12, width * 0.45, height * 0.35)), 2.5)
    return g, finish_sdf(g, sd, seed, ledge_period=2.8, ledge_depth=0.7, tilt=(0.08, 0.0), joint_spacing=9.0)


def butte(seed, radius, height):
    """Flat-topped butte: lobed outline, stepped tiers narrowing upward, cap rock and a talus apron."""
    rng = np.random.default_rng(seed)
    g = Grid((radius * 1.35 + 16, radius * 1.15 + 16, height + 3), 0.75)
    r = np.sqrt(g.x ** 2 + (g.y / 0.8) ** 2)
    ang = np.arctan2(g.y / 0.8, g.x)
    ph = rng.uniform(0, 6.28, 3)
    lobes = 1 + 0.22 * np.sin(ang * 3 + ph[0]) + 0.12 * np.sin(ang * 5 + ph[1]) + 0.07 * np.sin(ang * 9 + ph[2])
    tier = np.floor(np.clip(g.z, 0, None) / (height / 3.2))
    shrink = 1 - 0.13 * tier - 0.04 * np.clip(g.z, 0, None) / height
    body = np.maximum(r - radius * lobes * shrink, g.z - height)
    cap = np.maximum(r - radius * lobes * (shrink + 0.04), np.abs(g.z - (height - 1.6)) - 1.6)   # overhanging cap rock
    body = np.minimum(body, cap)
    apron_r = radius * lobes * 1.05 + 18
    talus = np.maximum(r - apron_r + np.clip(g.z, 0, None) * 1.7, g.z - height * 0.42)
    sd = smin(body, talus, 5.0)
    sd = smax(sd, -(g.z + 3.0), 1.0)
    return g, finish_sdf(g, sd, seed, ledge_period=3.4, ledge_depth=1.0, taf_cell=3.0, taf_depth=0.45, warp_amp=2.4,
                         joint_spacing=11.0, joint_depth=1.6)


def spire(seed, height, base_r):
    """Slender tower of stacked, eroded layers with a cap."""
    rng = np.random.default_rng(seed)
    g = Grid((base_r * 2 + 3, base_r * 2 + 3, height + 4), 0.45)
    t = np.clip(g.z / height, 0, 1)
    r = base_r * (1.15 - 0.45 * t + 0.18 * np.sin(t * rng.uniform(9, 14) + rng.uniform(0, 6)))
    r = r * (1 + 0.6 * np.clip(1 - g.z / (height * 0.12), 0, 1) ** 2)        # base flare
    lean = t * t * base_r * 0.5
    d = np.sqrt((g.x - lean) ** 2 + g.y ** 2) - r
    sd = np.maximum(d, g.z - height)
    cap = ellipsoid(g.x, g.y, g.z, (base_r * 0.5, 0, height + base_r * 0.25), (base_r * 1.4, base_r * 1.2, base_r * 0.55))
    sd = smin(sd, cap, 0.8)
    sd = smax(sd, -(g.z + 3.0), 1.0)
    return g, finish_sdf(g, sd, seed, ledge_period=1.6, ledge_depth=0.4, taf_cell=1.4, taf_depth=0.45, warp_amp=0.9,
                         joint_spacing=50.0, joint_depth=0.0, knobs=0.4)


def ledge(seed, size):
    """Low flat-topped outcrop of 2-3 stepped layers, for slickrock edges and road cuts."""
    rng = np.random.default_rng(seed)
    g = Grid((size[0] / 2 + 3, size[1] / 2 + 3, size[2] + 2), 0.4)
    sd = np.full(g.shape, 1e3)
    z0 = 0.0
    for k in range(3):
        h = size[2] / 3
        sc = 1 - 0.18 * k
        c = (rng.uniform(-0.1, 0.1) * size[0], rng.uniform(-0.1, 0.1) * size[1], z0 + h / 2 - 0.5)
        sd = smin(sd, rounded_box(g.x, g.y, g.z, c, (size[0] / 2 * sc, size[1] / 2 * sc, h / 2 + 0.6), 0.9), 0.6)
        z0 += h
    sd = sd + 1.1 * fbm3(g.shape, 6.0 / g.voxel, seed, 3)
    sd = smax(sd, -(g.z + 2.0), 1.0)
    return g, finish_sdf(g, sd, seed, ledge_period=1.3, ledge_depth=0.3, taf_cell=1.3, taf_depth=0.35, warp_amp=0.6,
                         joint_spacing=4.5, joint_depth=0.5, knobs=0.35)


def arch(seed, span, height, thickness):
    """Natural arch eroded out of a fin: a fin with a window, thick legs and a slender span."""
    rng = np.random.default_rng(seed)
    g = Grid((span / 2 + 12, thickness + 6, height + 6), 0.6)
    L = span + 16
    crest = height + 2 + 2 * np.sin(g.x / L * 5 + 1)
    half_w = thickness * (1 - 0.35 * np.clip(g.z / height, 0, 1))
    body = np.maximum(np.abs(g.y) - half_w, g.z - crest)
    body = smax(body, np.abs(g.x) - L / 2, 4.0)
    # Window: an ellipse through the fin, wider at the bottom.
    wx, wz = span / 2, height * 0.72
    window = np.sqrt((g.x / wx) ** 2 + ((g.z + 1.0) / wz) ** 2) - 1.0
    sd = smax(body, -window * min(wx, wz), 2.0)
    sd = smax(sd, -(g.z + 3.0), 1.0)
    return g, finish_sdf(g, sd, seed, ledge_period=2.4, ledge_depth=0.6, tilt=(0.05, 0.0), taf_cell=1.8, taf_depth=0.6,
                         warp_amp=1.3, joint_spacing=30.0, joint_depth=0.0)


SPECS = [
    # name, builder, args, triangle budget
    ("Mound_0", mound, (101, (42, 32, 18)), 14000),
    ("Mound_1", mound, (102, (30, 26, 14)), 11000),
    ("Mound_2", mound, (103, (55, 30, 22)), 16000),
    ("Mound_3", mound, (104, (36, 24, 26)), 13000),
    ("Mound_4", mound, (105, (64, 36, 16)), 16000),
    ("Fin_0", fin, (201, 72, 22, 13), 15000),
    ("Fin_2", fin, (203, 60, 28, 16), 14000),
    ("Spire_2", spire, (403, 40, 5.0), 8000),
    ("Fin_1", fin, (202, 48, 15, 10), 11000),
    ("Butte_0", butte, (301, 30, 34), 16000),
    ("Spire_0", spire, (401, 30, 4.2), 7000),
    ("Spire_1", spire, (402, 22, 3.4), 6000),
    ("Ledge_0", ledge, (501, (16, 11, 3.2)), 5000),
    ("Ledge_1", ledge, (502, (11, 8, 2.4)), 4000),
    ("Ledge_2", ledge, (503, (22, 9, 4.0)), 6000),
    ("Arch_0", arch, (601, 26, 17, 5.5), 16000),
]


def build(only=None):
    C.reset_scene()
    mat = C.material("RockSandstone", (0.42, 0.19, 0.11), 0.0, 0.88)
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
    objs = build()
    C.export_fbx(objs, C.path_in_repo("Assets", "Models", "Formations", "Formations.fbx"))
