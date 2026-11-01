"""Fire Canyon: the desert region, designed around its rock formations.

Run:  python tools/terrain/generate_desert.py
Needs numpy, scipy, pillow.

Layout (x east, z north, metres):
  * An old two-lane highway winds north through a valley lined with sandstone formations,
    leaving the region through gaps cut in the cliffs at both ends. Base camp sits beside it.
  * A dry wash runs from the western cliffs across the valley and drains into a playa (dry lake)
    of cracked mud in the east. Prospector's Well sits on the playa's western shore.
  * West: "The Wave", a basin of undulating striped slickrock ringed by spires.
  * South-west: "The Chimneys" hoodoo field around Balanced Rock.
  * South-east: dunes, with the Rustbucket half-buried among them.
  * North-east: mesa country with a big butte, a fin and the Needle's Eye arch.
  * The edges rise into layered sandstone cliffs.

Outputs (Unity ignores folders ending in "~"; the editor builder reads them):
  Assets/Terrain/Source~/desert_height.r16    1025^2 uint16 heights (row 0 = south)
  Assets/Terrain/Source~/desert_splat.png     physics surfaces: R sand, G gravel, B packed mud, A rock
  Assets/Terrain/Source~/desert_scatter.json  props to place
  Assets/Terrain/Source~/desert_info.json     size, spawn, road, landmarks, formations, markers
  Assets/Terrain/Masks/desert_mask.png        render mask: R sand, G mud, B pavement, A slickrock
"""
import json
import math
import os

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.spatial import cKDTree

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(REPO, "Assets", "Terrain", "Source~")
MASKS = os.path.join(REPO, "Assets", "Terrain", "Masks")
os.makedirs(SRC, exist_ok=True)
os.makedirs(MASKS, exist_ok=True)

N = 1025
SIZE = 1024.0
HEIGHT = 200.0
CELL = SIZE / (N - 1)
SEED = 11
rng = np.random.default_rng(SEED)
zs, xs = np.mgrid[0:N, 0:N].astype(np.float64) * CELL   # row = z, col = x


# ---------------------------------------------------------------------------- helpers

def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def value_noise(freq, seed):
    r = np.random.default_rng(seed)
    cells = int(freq) + 4
    big = ndimage.zoom(r.random((cells, cells)), (N - 1) / freq, order=3, mode="reflect")
    off = int((N - 1) / freq)
    return np.clip(big[off:off + N, off:off + N], 0, 1)


def fbm(freq, octaves, seed, gain=0.5):
    total, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        total = total + amp * value_noise(freq * 2 ** o, seed + o * 101)
        norm += amp
        amp *= gain
    return total / norm


def norm01(a):
    lo, hi = np.percentile(a, 1), np.percentile(a, 99)
    return np.clip((a - lo) / (hi - lo), 0, 1)


def catmull(points, samples):
    p = np.array(points, float)
    p = np.vstack([p[0] * 2 - p[1], p, p[-1] * 2 - p[-2]])
    out = []
    per = max(2, samples // (len(p) - 3))
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for t in np.linspace(0, 1, per, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(p[-2])
    return np.array(out)


def path_field(path):
    tree = cKDTree(path)
    d, i = tree.query(np.c_[xs.ravel(), zs.ravel()])
    return d.reshape(N, N), i.reshape(N, N), tree


def ellipse_r(cx, cz, rx, rz, yaw_deg=0.0, x=None, z=None):
    x = xs if x is None else x
    z = zs if z is None else z
    a = math.radians(yaw_deg)
    dx, dz = x - cx, z - cz
    u = dx * math.cos(a) - dz * math.sin(a)
    v = dx * math.sin(a) + dz * math.cos(a)
    return np.sqrt((u / rx) ** 2 + (v / rz) ** 2)


def idx(x, z):
    return int(np.clip(round(z / CELL), 0, N - 1)), int(np.clip(round(x / CELL), 0, N - 1))


def sample(arr, x, z):
    return arr[idx(x, z)]


def slope_map(hh):
    gz, gx = np.gradient(hh, CELL)
    return np.degrees(np.arctan(np.hypot(gx, gz)))


# ---------------------------------------------------------------------------- paths and zones

ROAD = [(566, -30), (574, 90), (556, 190), (528, 300), (532, 420), (508, 540), (474, 660), (480, 780),
        (458, 900), (452, 1060)]
WASH = [(-20, 330), (80, 352), (170, 322), (280, 372), (390, 352), (520, 392), (610, 440), (690, 500), (760, 560)]
def meander(path, amp, seed):
    """Wiggle a path sideways (dirt tracks wander around bumps and bushes)."""
    seg = np.diff(path, axis=0, prepend=path[:1])
    s = np.cumsum(np.hypot(seg[:, 0], seg[:, 1]))
    t = np.gradient(path, axis=0)
    t /= np.linalg.norm(t, axis=1, keepdims=True) + 1e-9
    nrm = np.stack([t[:, 1], -t[:, 0]], 1)
    r = np.random.default_rng(seed)
    p1, p2 = r.uniform(0, 6.3, 2)
    off = amp * (0.7 * np.sin(s / 41 + p1) + 0.3 * np.sin(s / 13.5 + p2))
    off *= np.minimum(1, np.minimum(s, s[-1] - s) / 25)       # pinned at both ends
    return path + nrm * off[:, None]


def path_length(points):
    p = np.array(points, float)
    return float(np.sum(np.hypot(*np.diff(p, axis=0).T)))


road = meander(catmull(ROAD, 4000), 3.0, SEED + 40)        # the main dirt track (the old wagon road)
wash = catmull(WASH, 4000)
d_road, i_road, road_tree = path_field(road)
d_wash, i_wash, _ = path_field(wash)


def snap_to_road(x, z):
    _, k = road_tree.query([x, z])
    return float(road[k][0]), float(road[k][1])


# Side tracks: narrower two-rut trails branching off the main track to the landmarks. Formations are
# pushed clear of them below, so the tracks squeeze through gaps in the rock.
SIDE_TRACKS = {
    "well":       [snap_to_road(532, 420), (566, 438), (600, 449), (628, 459)],
    "wave":       [snap_to_road(508, 540), (452, 553), (385, 572), (322, 582), (266, 578)],
    "chimneys":   [snap_to_road(538, 262), (482, 252), (410, 240), (332, 228), (262, 214), (238, 210)],
    "needle":     [snap_to_road(480, 780), (540, 793), (600, 812), (660, 836)],
    "rustbucket": [snap_to_road(570, 110), (628, 150), (690, 196), (752, 228), (806, 244)],
    "playa":      [(646, 482), (684, 512), (716, 545), (744, 575)],
}
side_paths = {k: meander(catmull(v, int(path_length(v) / 0.3)), 1.8, SEED + 50 + i)
              for i, (k, v) in enumerate(SIDE_TRACKS.items())}
side_trees = {k: cKDTree(v) for k, v in side_paths.items()}
d_side = np.full((N, N), 1e4)
for sp in side_paths.values():
    d_side = np.minimum(d_side, path_field(sp)[0])
d_track = np.minimum(d_road, d_side)       # distance to any track


# Hazards (cx, cz, rx, rz, yaw). Quicksand sits in the wash near the spring at Prospector's Well, just off
# the tracks, so shortcuts are risky; wet mud fills the wash crossing, the spring overflow and the playa edge.
QUICKSAND = [(596, 424, 11, 8, 30), (452, 371, 9, 7, -10), (705, 512, 8, 6, 45), (262, 356, 10, 7, 5)]
WET_MUD = [(531, 404, 15, 9, 25), (657, 474, 16, 9, -30), (757, 584, 34, 18, -40), (300, 368, 20, 8, 10),
           (150, 330, 18, 7, -5), (612, 441, 12, 7, 35)]
WASHBOARD_T = [(0.29, 0.40), (0.57, 0.68)]    # stretches of the main track with corrugations

WAVE = (215, 575, 125, 100)        # cx, cz, rx, rz
PLAYA = (785, 600, 150, 108)
DUNES = (815, 235, 185, 150)
CHIMNEYS = (205, 205)


def road_point(t, side=0.0):
    """Point at fraction t along the road, offset `side` metres to its right (east-ish)."""
    k = int(np.clip(t, 0, 1) * (len(road) - 1))
    k2 = min(k + 1, len(road) - 1)
    tx, tz = road[k2] - road[max(k - 1, 0)]
    ln = math.hypot(tx, tz) or 1
    rx, rz = tz / ln, -tx / ln
    return float(road[k][0] + rx * side), float(road[k][1] + rz * side), math.degrees(math.atan2(tx, tz))


# ---------------------------------------------------------------------------- formations (placed first, terrain adapts)
# name: (rx, rz) footprint half-extents in metres at scale 1, along the model's local x and z
FOOT = {"Mound_0": (23, 19), "Mound_1": (15, 13), "Mound_2": (28, 19), "Mound_3": (18, 13), "Mound_4": (31, 19),
        "Fin_0": (35, 8), "Fin_1": (23, 8), "Fin_2": (29, 10), "Spire_2": (8, 8),
        "Butte_0": (50, 40), "Spire_0": (7, 7), "Spire_1": (5, 5), "Ledge_0": (8, 6), "Ledge_1": (6, 4),
        "Ledge_2": (11, 5), "Arch_0": (21, 6)}

formations = []


def add_formation(model, x, z, yaw, scale, sink=2.5):
    formations.append({"model": model, "x": round(x, 2), "z": round(z, 2), "yaw": round(yaw % 360, 1),
                       "scale": round(scale, 2), "sink": sink})


def beside_road(model, t, side, yaw_off, scale, sink=2.5):
    x, z, heading = road_point(t, side)
    add_formation(model, x, z, heading + yaw_off, scale, sink)


def massif(t, side, length, count, scale_rng, seed,
           models=("Mound_0", "Mound_2", "Fin_0", "Mound_1", "Fin_1", "Mound_3", "Mound_4", "Fin_2")):
    """A long rock mass built from overlapping formations, running roughly parallel to the road."""
    r = np.random.default_rng(seed)
    cx, cz, heading = road_point(t, side)
    a = math.radians(heading + r.uniform(-25, 25))
    along = (math.sin(a), math.cos(a))
    for k in range(count):
        u = (k / max(count - 1, 1) - 0.5) * length + r.uniform(-8, 8)
        out = r.uniform(-14, 22) * (1 if side > 0 else -1)
        x = cx + along[0] * u + along[1] * out
        z = cz + along[1] * u - along[0] * out
        m = models[int(r.integers(len(models)))]
        add_formation(m, x, z, heading + r.uniform(-40, 40) + (90 if m.startswith("Fin") else r.uniform(0, 360)),
                      r.uniform(*scale_rng), 3.5)


# The valley: long rock masses on both sides of the highway with gaps between them, plus
# single giant "gateway" formations that pinch in close to the road (as in the reference photo).
massif(0.05, -118, 170, 4, (1.6, 2.3), 1)
massif(0.10, 120, 150, 4, (1.6, 2.4), 2)
massif(0.36, -125, 200, 5, (1.8, 2.6), 3)
massif(0.33, 128, 170, 4, (1.7, 2.5), 4)
massif(0.56, -122, 180, 5, (1.7, 2.6), 5)
massif(0.60, 130, 200, 5, (1.8, 2.8), 6)
massif(0.80, -118, 190, 4, (1.8, 2.6), 7)
massif(0.84, 125, 170, 4, (1.7, 2.5), 8)
beside_road("Mound_0", 0.255, 58, 30, 1.7, 3.0)          # gateway pair framing the first view
beside_road("Fin_1", 0.275, -62, 80, 2.0, 3.0)
beside_road("Mound_1", 0.15, 55, 200, 1.6, 3.0)
beside_road("Mound_2", 0.45, -66, 200, 1.7, 3.0)
beside_road("Spire_2", 0.49, 50, 0, 1.3, 2.5)
beside_road("Mound_1", 0.66, 62, 110, 2.1, 3.0)
beside_road("Fin_1", 0.71, -58, 95, 1.8, 3.0)
beside_road("Spire_1", 0.38, 46, 0, 1.3, 2.5)
beside_road("Ledge_2", 0.74, 34, 15, 1.4, 1.2)
beside_road("Ledge_0", 0.92, -40, 60, 1.5, 1.0)

# Base camp area: low ledges and a small mound make the rock garden.
for i, (t, side, m, s) in enumerate(((0.215, -62, "Ledge_0", 1.1), (0.205, -88, "Ledge_2", 1.0), (0.235, -78, "Ledge_1", 1.3),
                                     (0.19, -70, "Ledge_1", 0.9), (0.225, -110, "Mound_1", 0.7))):
    beside_road(m, t, side, i * 47, s, 1.0 if m.startswith("Ledge") else 2.5)

# The Wave: spires and fins around the rim of the slickrock basin.
for m, a, rad, s in (("Spire_0", 110, 1.05, 1.5), ("Spire_1", 70, 1.1, 1.4), ("Spire_1", 200, 1.08, 1.2),
                     ("Fin_1", 160, 1.25, 1.6), ("Ledge_2", 300, 0.95, 1.3), ("Ledge_0", 20, 1.0, 1.4),
                     ("Mound_1", 245, 1.22, 1.7), ("Mound_0", 135, 1.45, 1.8), ("Fin_0", 215, 1.5, 1.6)):
    ax = WAVE[0] + math.cos(math.radians(a)) * WAVE[2] * rad
    az = WAVE[1] + math.sin(math.radians(a)) * WAVE[3] * rad
    add_formation(m, ax, az, a + 90, s, 2.0 if m.startswith("Ledge") else 2.5)

# The Chimneys: spires and a mound among the hoodoos.
add_formation("Mound_1", 130, 140, 30, 1.8, 3.0)
add_formation("Mound_2", 90, 260, 70, 1.6, 3.0)
add_formation("Spire_2", 270, 260, 0, 1.0)
add_formation("Spire_1", 165, 290, 40, 1.2)
add_formation("Spire_1", 255, 150, 110, 1.0)

# Mesa country: a butte, a fin and the arch, its window turned toward the road.
add_formation("Butte_0", 850, 885, 15, 1.4, 4.0)
add_formation("Fin_0", 715, 735, 30, 1.5, 3.0)
add_formation("Mound_2", 610, 930, 80, 1.8, 3.0)
arch_x, arch_z = 690.0, 850.0
add_formation("Arch_0", arch_x, arch_z, math.degrees(math.atan2(arch_x - 480, arch_z - 780)) + 90, 1.4, 2.5)

# Playa shore and dunes: low ledges only, keeping the flats open.
add_formation("Ledge_1", 672, 650, 40, 1.2, 1.2)
add_formation("Ledge_0", 900, 520, 120, 1.1, 1.2)
add_formation("Mound_1", 930, 720, 80, 2.0, 3.0)
add_formation("Mound_0", 935, 420, 140, 1.8, 3.0)
add_formation("Ledge_2", 745, 335, 70, 1.0, 1.8)


def footprint_r(f, x=None, z=None):
    rx, rz = FOOT[f["model"]]
    return ellipse_r(f["x"], f["z"], rx * f["scale"], rz * f["scale"], -f["yaw"], x, z)


# Push formations clear of the main track (wide berth) and the side tracks (they may squeeze past).
for f in formations:
    for _ in range(60):
        moved = False
        reach = max(FOOT[f["model"]]) * f["scale"]
        d, k = road_tree.query([f["x"], f["z"]])
        if d < reach * 0.75 + 12:
            dx, dz = f["x"] - road[k][0], f["z"] - road[k][1]
            ln = math.hypot(dx, dz) or 1
            f["x"] += dx / ln * 3
            f["z"] += dz / ln * 3
            moved = True
        for kname, path in side_paths.items():
            near = side_trees[kname].query_ball_point([f["x"], f["z"]], reach * 1.6 + 8)
            if not near:
                continue
            pts = path[near]
            # Real footprint shape (elliptical), with ~4 m of track clearance.
            rx, rz = FOOT[f["model"]]
            fr = ellipse_r(f["x"], f["z"], rx * f["scale"] + 4, rz * f["scale"] + 4, -f["yaw"], pts[:, 0], pts[:, 1])
            j = int(np.argmin(fr))
            if fr[j] >= 1.0:
                continue
            dx, dz = f["x"] - pts[j][0], f["z"] - pts[j][1]
            ln = math.hypot(dx, dz) or 1
            f["x"] += dx / ln * 2.5
            f["z"] += dz / ln * 2.5
            moved = True
        if not moved:
            break

foot_r = np.full((N, N), 9.0)       # < 1 inside a formation footprint
for f in formations:
    foot_r = np.minimum(foot_r, footprint_r(f))


# ---------------------------------------------------------------------------- heightmap
print("Building heightmap...")
base = 24 + 4 * (fbm(3, 4, SEED) - 0.5) + 2 * (fbm(9, 3, SEED + 1) - 0.5)
valley = -7 * np.exp(-(d_road / 150) ** 2)
hills = 10 * (fbm(5, 4, SEED + 2) - 0.5) * smoothstep(45, 140, d_road)
h = base + valley + hills

rW = ellipse_r(*WAVE)
wW = smoothstep(1.18, 0.82, rW)
swirl = (4.5 * np.sin(xs / 19 + 1.4 * np.sin(zs / 35)) * np.cos(zs / 24 + 1.2 * np.sin(xs / 29))
         + 2.5 * (fbm(8, 3, SEED + 3) - 0.5))
h = h * (1 - wW) + (17 + swirl) * wW

rP = ellipse_r(*PLAYA, yaw_deg=-15)
wP = smoothstep(1.22, 0.92, rP)
h = h * (1 - wP) + (14.0 + 0.25 * (fbm(20, 2, SEED + 4) - 0.5)) * wP

rD = ellipse_r(*DUNES)
wD = smoothstep(1.1, 0.55, rD)
ph = (xs * 0.75 + zs * 0.66) / 26 + 3 * fbm(5, 2, SEED + 5)
saw = ph - np.floor(ph)
dune = np.where(saw < 0.75, saw / 0.75, (1 - saw) / 0.25)
h += wD * 8.0 * dune ** 1.4 * (0.5 + fbm(4, 2, SEED + 6))

ramp = (xs / SIZE + zs / SIZE - 1.25) * 1.5
mv = norm01(fbm(2.5, 3, SEED + 7)) * 0.6 + ramp
keep = smoothstep(70, 130, d_road) * (1 - wP)
plat = smoothstep(0.55, 0.58, mv) * keep
tier2 = smoothstep(0.82, 0.85, mv) * keep
h = np.maximum(h, h * (1 - plat) + (54 + 2 * fbm(6, 2, SEED + 8)) * plat)
h = h + 18 * tier2

edge = np.maximum(np.abs(xs - SIZE / 2), np.abs(zs - SIZE / 2)) / (SIZE / 2)
edge = edge + 0.07 * (fbm(5, 3, SEED + 9) - 0.5)
gap = smoothstep(30, 70, d_road)
skyline = 0.6 + 0.8 * fbm(7, 4, SEED + 10)
wall = (34 * smoothstep(0.84, 0.88, edge) + 40 * smoothstep(0.92, 0.96, edge) * skyline) * (0.6 + 0.7 * fbm(3, 3, SEED + 12))
h = h + wall * gap

h += 2.5 * smoothstep(1.6, 0.8, foot_r)          # each formation sits on a gentle apron

print("Eroding...")
talus = 1.3
for _ in range(25):
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nb = np.roll(np.roll(h, dx, axis=1), dz, axis=0)
        diff = h - nb
        move = np.where(diff > talus, (diff - talus) * 0.25, 0.0)
        h = h - move + np.roll(np.roll(move, -dx, axis=1), -dz, axis=0)
h = ndimage.gaussian_filter(h, 0.6)

carve = (1 - smoothstep(8, 26, d_wash)) * (1 - wP)
h -= 3.5 * carve

# Tracks are graded lightly: they follow the lie of the land instead of cutting a flat roadbed.
road_h = np.array([sample(h, x, z) for x, z in road])
road_h = ndimage.gaussian_filter1d(road_h, 28, mode="nearest")
road_w = (1 - smoothstep(3.5, 12, d_road)) * 0.85
h = h * (1 - road_w) + road_h[i_road] * road_w
for sp in side_paths.values():
    d_s, i_s, _ = path_field(sp)
    sh = ndimage.gaussian_filter1d(np.array([sample(h, x, z) for x, z in sp]), 22, mode="nearest")
    w_s = (1 - smoothstep(2.5, 9, d_s)) * 0.7
    h = h * (1 - w_s) + sh[i_s] * w_s

# Mud and quicksand lie in shallow, flat-bottomed hollows.
haz_mud = np.zeros((N, N))
haz_quick = np.zeros((N, N))
for cx, cz, rx, rz, yaw in WET_MUD:
    r = ellipse_r(cx, cz, rx, rz, yaw) * (1 + 0.18 * (fbm(9, 2, SEED + 60 + int(cx)) - 0.5))
    haz_mud = np.maximum(haz_mud, smoothstep(1.15, 0.85, r))
for cx, cz, rx, rz, yaw in QUICKSAND:
    r = ellipse_r(cx, cz, rx, rz, yaw) * (1 + 0.12 * (fbm(11, 2, SEED + 70 + int(cx)) - 0.5))
    haz_quick = np.maximum(haz_quick, smoothstep(1.1, 0.9, r))
soft = np.maximum(haz_mud, haz_quick)
if soft.max() > 0:
    lowered = ndimage.uniform_filter(h, 9)
    h = h * (1 - soft) + (lowered - 0.45) * soft


# ---------------------------------------------------------------------------- landmarks and spawn
print("Placing landmarks...")
landmarks = []


def piece(model, x, z, yaw, sink=0.0, align=0.0, local=None):
    if local:
        ox, oz, lx, lz, lyaw = local
        a = math.radians(lyaw)
        x = lx + ox * math.cos(a) + oz * math.sin(a)
        z = lz - ox * math.sin(a) + oz * math.cos(a)
        yaw = yaw + lyaw
    return {"model": model, "x": round(x, 2), "z": round(z, 2), "yaw": round(yaw % 360, 1), "sink": sink, "align": align}


def landmark(lid, name, x, z, radius, pieces, discover_radius=None):
    landmarks.append({"id": lid, "name": name, "x": round(x, 2), "z": round(z, 2), "radius": radius,
                      "discoverRadius": discover_radius or radius * 2.2, "pieces": pieces})


def flatten(x, z, radius, strength=1.0):
    global h
    d = np.hypot(xs - x, zs - z)
    target = h[d < radius * 0.5].mean()
    w = smoothstep(radius, radius * 0.55, d) * strength
    h = h * (1 - w) + target * w


spawn_x, spawn_z, spawn_heading = road_point(0.205, 0)
camp_x, camp_z, _ = road_point(0.205, 30)
flatten(camp_x, camp_z, 18)
cy = math.degrees(math.atan2(spawn_x - camp_x, spawn_z - camp_z))
landmark("basecamp", "Base Camp", camp_x, camp_z, 14, [
    piece("Tent", 0, 0, 0, 0.02, local=(0, -2, camp_x, camp_z, cy + 180)),
    piece("FireRing", 0, 0, 0, 0.05, local=(-3.5, 2.5, camp_x, camp_z, cy + 180)),
    piece("Crates", 0, 0, 30, 0.0, local=(3.2, 0.5, camp_x, camp_z, cy + 180)),
    piece("Signpost", 0, 0, 10, 0.1, local=(-1.0, -11.0, camp_x, camp_z, cy + 180)),
], discover_radius=1)

rg_x, rg_z, _ = road_point(0.215, -82)
landmark("rock_garden", "The Rock Garden", rg_x, rg_z, 34, [], discover_radius=42)
landmark("needles_eye", "The Needle's Eye", arch_x, arch_z, 24, [], discover_radius=55)

well_x, well_z = 642.0, 468.0
flatten(well_x, well_z, 26)
wy = math.degrees(math.atan2(spawn_x - well_x, spawn_z - well_z))
landmark("prospectors_well", "Prospector's Well", well_x, well_z, 22, [
    piece("Windmill", 0, 0, 0, 0.1, local=(0, 0, well_x, well_z, wy)),
    piece("WaterTank", 0, 0, 0, 0.05, local=(5.5, -1.5, well_x, well_z, wy)),
    piece("Shack", 0, 0, 90, 0.05, local=(-10, 5, well_x, well_z, wy)),
    piece("Crates", 0, 0, -20, 0.0, local=(-6.5, -2.0, well_x, well_z, wy)),
])
landmark("chimneys", "The Chimneys", CHIMNEYS[0], CHIMNEYS[1], 60,
         [piece("BalancedRock", CHIMNEYS[0], CHIMNEYS[1], 35, 0.3, 0.0)], discover_radius=80)
landmark("the_wave", "The Wave", WAVE[0], WAVE[1], 90, [], discover_radius=95)
rx_, rz_ = 830.0, 250.0
landmark("rustbucket", "Rustbucket", rx_, rz_, 8, [piece("Wreck", rx_, rz_, 137, 0.45, 0.7)])

h = np.clip(h, 1, HEIGHT - 1)
slope = slope_map(h)
np.round(h / HEIGHT * 65535).astype("<u2").tofile(os.path.join(SRC, "desert_height.r16"))
print(f"Height range {h.min():.1f}..{h.max():.1f} m")
for L in landmarks:
    print(f"  {L['name']:20s} ({L['x']:.0f}, {L['z']:.0f})  {math.hypot(L['x'] - spawn_x, L['z'] - spawn_z):.0f} m from spawn")


# ---------------------------------------------------------------------------- render mask + physics splat
print("Painting masks...")
curv = ndimage.laplace(ndimage.gaussian_filter(h, 2.5))
patch = fbm(10, 4, SEED + 20)
fine = fbm(28, 3, SEED + 21)
near_form = smoothstep(2.2, 1.0, foot_r)
apron = smoothstep(1.35, 1.0, foot_r)

mud = np.maximum(wP, (1 - smoothstep(5, 15, d_wash)) * 0.85 * (1 - wP))
mud = np.maximum(mud, smoothstep(0.15, 0.35, curv) * smoothstep(0.6, 0.75, patch) * (1 - wD))
pave = smoothstep(0.55, 0.72, patch) * 0.8 + near_form * 0.7 * smoothstep(0.35, 0.6, fine)
pave = np.maximum(pave, (smoothstep(2.6, 3.6, d_road) * (1 - smoothstep(5, 8, d_road))) * 0.45)   # graded berms
mud = np.maximum(mud, haz_mud * 0.9)
pave *= (1 - wD) * (1 - wP)
sand = np.clip(1.0 - mud - pave, 0.05, 1) + wD
rgb = np.stack([sand, mud, pave], -1)
rgb /= rgb.sum(-1, keepdims=True)

ridged = 1 - np.abs(fbm(9, 3, SEED + 22) * 2 - 1)
outcrop = smoothstep(0.86, 0.95, ridged) * smoothstep(80, 140, d_road) * (1 - wD) * (1 - wP)
slick = np.maximum.reduce([wW * smoothstep(0.25, 0.45, fine + 0.25), apron * 0.85,
                           plat * 0.5 * smoothstep(0.4, 0.6, fine), outcrop])
slick *= 1 - smoothstep(10, 4, d_track)

M = 1024
mask = np.concatenate([rgb, slick[..., None]], -1)
mask_img = ndimage.zoom(mask, (M / N, M / N, 1), order=1)
Image.fromarray((np.clip(mask_img[::-1], 0, 1) * 255).round().astype(np.uint8), "RGBA").save(os.path.join(MASKS, "desert_mask.png"))

rock_phys = np.maximum(slick, smoothstep(0.24, 0.42, 1 - np.cos(np.radians(slope))))
phys = np.stack([rgb[..., 0] * (1 - rock_phys), rgb[..., 2] * (1 - rock_phys), rgb[..., 1] * (1 - rock_phys), rock_phys], -1)
on_road = np.maximum(1 - smoothstep(2.4, 3.2, d_road), 1 - smoothstep(1.7, 2.4, d_side)) * (1 - rock_phys)
phys[..., 0] *= 1 - on_road                              # tracks are packed dirt
phys[..., 1] *= 1 - on_road
phys[..., 2] = np.maximum(phys[..., 2], on_road)
phys = phys / (phys.sum(-1, keepdims=True) + 1e-6)
S = 512
splat = ndimage.zoom(phys, (S / N, S / N, 1), order=1)
splat = splat / splat.sum(-1, keepdims=True)
Image.fromarray((splat[::-1] * 255).round().astype(np.uint8), "RGBA").save(os.path.join(SRC, "desert_splat.png"))


# ---------------------------------------------------------------------------- scatter
print("Scattering...")
props = []
pads = [(L["x"], L["z"], L["radius"]) for L in landmarks if L["id"] in ("basecamp", "prospectors_well")]


class Spacing:
    def __init__(self, cell=4.0):
        self.cell, self.grid = cell, {}

    def ok(self, x, z, r):
        cx, cz = int(x // self.cell), int(z // self.cell)
        reach = int(math.ceil(r / self.cell)) + 1
        for i in range(cx - reach, cx + reach + 1):
            for k in range(cz - reach, cz + reach + 1):
                for px, pz, pr in self.grid.get((i, k), ()):
                    if math.hypot(px - x, pz - z) < max(r, pr):
                        return False
        return True

    def add(self, x, z, r):
        self.grid.setdefault((int(x // self.cell), int(z // self.cell)), []).append((x, z, r))


solid = Spacing()


def blocked(x, z, road_clear=8.0, wash_clear=5.0):
    if not (12 < x < SIZE - 12 and 12 < z < SIZE - 12):
        return True
    if sample(d_road, x, z) < road_clear or sample(d_wash, x, z) < wash_clear or sample(d_side, x, z) < road_clear * 0.6:
        return True
    if sample(haz_quick, x, z) > 0.02 or (sample(haz_mud, x, z) > 0.05 and kind_hint[0] != "Grass"):
        return True
    if sample(foot_r, x, z) < 0.92:
        return True
    if math.hypot(x - spawn_x, z - spawn_z) < 14:
        return True
    return any(math.hypot(x - px, z - pz) < pr for px, pz, pr in pads)


kind_hint = [""]


def put(kind, variants, x, z, scale, sink, spacing=0.0, road_clear=8.0):
    kind_hint[0] = kind
    if blocked(x, z, road_clear):
        return False
    if sample(slope, x, z) > 34 and kind not in ("Boulder", "Rock"):
        return False
    if spacing and not solid.ok(x, z, spacing * scale):
        return False
    if spacing:
        solid.add(x, z, spacing * scale)
    props.append({"kind": kind, "variant": int(rng.integers(variants)), "x": round(float(x), 2), "z": round(float(z), 2),
                  "yaw": round(float(rng.uniform(0, 360)), 1), "scale": round(float(scale), 2), "sink": sink})
    return True


def ring_around(f, inner, outer, count, kind, variants, scale_rng, sink, spacing=0.0, decay=6.0):
    """Scatter in a band just outside a formation's footprint (talus, grass belts)."""
    rx, rz = FOOT[f["model"]]
    rx, rz = rx * f["scale"], rz * f["scale"]
    a0 = math.radians(f["yaw"])
    placed = tries = 0
    while placed < count and tries < count * 25:
        tries += 1
        ang = rng.uniform(0, 2 * math.pi)
        dist = inner + rng.exponential(decay)
        if dist > outer:
            continue
        ex, ez = math.cos(ang) * (rx + dist), math.sin(ang) * (rz + dist)
        x = f["x"] + ex * math.cos(a0) + ez * math.sin(a0)
        z = f["z"] - ex * math.sin(a0) + ez * math.cos(a0)
        sc = rng.uniform(*scale_rng) * (1.25 - 0.5 * min(dist / outer, 1))
        placed += put(kind, variants, x, z, sc, sink, spacing)


for f in formations:
    size = (FOOT[f["model"]][0] + FOOT[f["model"]][1]) * f["scale"]
    big = f["model"].split("_")[0] in ("Mound", "Fin", "Butte", "Arch")
    fs = min(f["scale"], 2.2)
    ring_around(f, -2, 10 + 6 * fs, int(size * (0.45 if big else 0.25)), "Boulder", 6,
                (0.9 * fs, 2.2 * fs) if big else (0.6, 1.4), 0.3, 1.2, 5 * fs)
    ring_around(f, -1, 22, int(size * 0.9), "Rock", 5, (0.6, 1.5), 0.1, 0, 8)
    ring_around(f, 0, 18, int(size * 1.6), "Grass", 2, (0.8, 1.4), 0.03, 0, 7)
    ring_around(f, 2, 22, int(size * 0.35), "Scrub", 3, (0.7, 1.3), 0.05, 0, 9)
    if f["model"].startswith(("Mound", "Fin")):
        ring_around(f, 3, 18, int(size * 0.12), "Yucca", 2, (0.8, 1.2), 0.02, 0, 8)

# Track verges: grass and the odd shrub, thinning out in places.
gaps = fbm(14, 2, SEED + 30)
for path, near, far, step in [(road, 4.0, 9.0, 3)] + [(sp, 3.0, 7.0, 4) for sp in side_paths.values()]:
    for k in range(0, len(path), step):
        x0, z0 = path[k]
        if not (20 < x0 < SIZE - 20 and 20 < z0 < SIZE - 20):
            continue
        tx, tz = path[min(k + 1, len(path) - 1)] - path[max(k - 1, 0)]
        ln = math.hypot(tx, tz) or 1
        for side in (-1, 1):
            if sample(gaps, x0, z0) < 0.42 and rng.random() < 0.7:
                continue
            off = side * rng.uniform(near, far)
            x, z = x0 + tz / ln * off, z0 - tx / ln * off
            put("Grass", 2, x, z, rng.uniform(0.8, 1.4), 0.03, road_clear=near * 0.8)
            if rng.random() < 0.14:
                put("Scrub", 3, x + side * abs(rng.normal(0, 2)), z, rng.uniform(0.7, 1.2), 0.05, road_clear=near)

# Wash banks: grass, shrubs and a few dead trees where water passes.
for k in range(0, len(wash), 4):
    x0, z0 = wash[k]
    if sample(wP, x0, z0) > 0.3:
        continue
    tx, tz = wash[min(k + 1, len(wash) - 1)] - wash[max(k - 1, 0)]
    ln = math.hypot(tx, tz) or 1
    for side in (-1, 1):
        off = side * rng.uniform(9, 22)
        x, z = x0 + tz / ln * off, z0 - tx / ln * off
        put("Grass", 2, x, z, rng.uniform(0.9, 1.5), 0.03)
        if rng.random() < 0.35:
            put("Scrub", 3, x, z, rng.uniform(0.8, 1.4), 0.05)
        if rng.random() < 0.025:
            put("DeadTree", 2, x, z, rng.uniform(0.9, 1.3), 0.1, 3.0)

# Open valley: loose clusters of grass and shrubs, denser in hollows.
weight = smoothstep(20, 6, slope) * (1 - wP) * (1 - wD * 0.85) * (1 - wW * 0.8) * (0.3 + np.clip(curv * 5, 0, 1))
flat_w = (weight / weight.sum()).ravel()
for c in rng.choice(N * N, size=70, replace=False, p=flat_w):
    zi, xi = divmod(int(c), N)
    cx, cz = xi * CELL, zi * CELL
    for _ in range(int(rng.integers(10, 40))):
        r = abs(rng.normal(0, 9))
        a = rng.uniform(0, 2 * math.pi)
        put("Grass", 2, cx + math.cos(a) * r, cz + math.sin(a) * r, rng.uniform(0.7, 1.3), 0.03)
    for _ in range(int(rng.integers(1, 7))):
        r = abs(rng.normal(0, 8))
        a = rng.uniform(0, 2 * math.pi)
        put("Scrub", 3, cx + math.cos(a) * r, cz + math.sin(a) * r, rng.uniform(0.7, 1.3), 0.05)

# The Wave: tufts in the low pockets of the slickrock.
low = h - ndimage.uniform_filter(h, 15)
for _ in range(500):
    x, z = WAVE[0] + rng.normal(0, WAVE[2] * 0.45), WAVE[1] + rng.normal(0, WAVE[3] * 0.45)
    if sample(low, x, z) < -0.6:
        put("Grass", 2, x, z, rng.uniform(0.6, 1.0), 0.03)

# The Chimneys: hoodoos with rubble between them.
placed = 0
for _ in range(400):
    if placed >= 22:
        break
    r = 12 + abs(rng.normal(0, 30))
    a = rng.uniform(0, 2 * math.pi)
    placed += put("Hoodoo", 3, CHIMNEYS[0] + math.cos(a) * r, CHIMNEYS[1] + math.sin(a) * r, rng.uniform(0.8, 1.6), 0.3, 4.5)
for _ in range(90):
    r = abs(rng.normal(0, 35))
    a = rng.uniform(0, 2 * math.pi)
    put("Rock", 5, CHIMNEYS[0] + math.cos(a) * r, CHIMNEYS[1] + math.sin(a) * r, rng.uniform(0.6, 1.4), 0.1)
    put("Grass", 2, CHIMNEYS[0] + math.cos(a + 1) * r, CHIMNEYS[1] + math.sin(a + 1) * r, rng.uniform(0.7, 1.2), 0.03)

# The Rock Garden: slabs and boulders with drivable gaps between the ledges.
for _ in range(220):
    r = abs(rng.normal(0, 18))
    a = rng.uniform(0, 2 * math.pi)
    x, z = rg_x + math.cos(a) * r, rg_z + math.sin(a) * r
    if rng.random() < 0.55:
        put("Slab", 3, x, z, rng.uniform(0.8, 1.5), 0.15, 1.6)
    else:
        put("Boulder", 6, x, z, rng.uniform(0.6, 1.2), 0.3, 1.4)

# Dead trees: a few lone sentinels on the valley floor.
for _ in range(10):
    x, z = rng.uniform(100, SIZE - 100, 2)
    if sample(wP, x, z) < 0.1 and sample(wD, x, z) < 0.2:
        put("DeadTree", 2, x, z, rng.uniform(0.9, 1.4), 0.1, 3.0)

# Cairns along the wash.
markers = []
acc = 0.0
for k in range(1, len(wash)):
    acc += math.hypot(*(wash[k] - wash[k - 1]))
    if acc > 85 and sample(wP, *wash[k]) < 0.3 and 40 < wash[k][0] < SIZE - 40:
        acc = 0.0
        tx, tz = wash[min(k + 1, len(wash) - 1)] - wash[k - 1]
        ln = math.hypot(tx, tz) or 1
        markers.append(piece("Cairn", wash[k][0] + tz / ln * 12, wash[k][1] - tx / ln * 12, float(rng.uniform(0, 360)), 0.05))
for a in (0, math.pi):
    markers.append(piece("Cairn", rg_x + math.cos(a) * 40, rg_z + math.sin(a) * 40, 0, 0.05))

with open(os.path.join(SRC, "desert_scatter.json"), "w") as f_:
    json.dump({"props": props}, f_, separators=(",", ":"))
counts = {}
for p in props:
    counts[p["kind"]] = counts.get(p["kind"], 0) + 1
print("Props:", counts, "formations:", len(formations), "markers:", len(markers))

road_x = [round(float(x), 2) for x, _ in road[::6]]
road_z = [round(float(z), 2) for _, z in road[::6]]


def track_record(name, path, width, step):
    pts = path[::step]
    n = len(pts)
    t = np.linspace(0, 1, n)
    wash_amt = np.zeros(n)
    if name == "main":
        for t0, t1 in WASHBOARD_T:
            wash_amt = np.maximum(wash_amt, smoothstep(t0, t0 + 0.02, t) * (1 - smoothstep(t1 - 0.02, t1, t)))
    # Tracks fade out where sand has drifted over them (dunes) and at the ends of side tracks.
    drift = np.array([sample(wD, x, z) for x, z in pts])
    fade = np.clip(1 - smoothstep(0.35, 0.8, drift), 0, 1)
    if name != "main":
        s = np.linspace(0, path_length(pts), n)
        fade *= np.clip((s[-1] - s) / 12, 0, 1)
    return {"name": name, "width": width,
            "x": [round(float(x), 2) for x, _ in pts], "z": [round(float(z), 2) for _, z in pts],
            "washboard": [round(float(v), 2) for v in wash_amt], "fade": [round(float(v), 2) for v in fade]}


for name, sp in side_paths.items():
    worst = min(sample(foot_r, x, z) for x, z in sp[::10])
    if worst < 1.0:
        print(f"  WARNING: track '{name}' crosses a formation footprint (foot_r {worst:.2f})")
tracks = [track_record("main", road, 4.6, 6)] + [track_record(k, sp, 3.4, 6) for k, sp in side_paths.items()]

# Hazard map (1024, bottom-up like the masks): R wet mud, G quicksand, B washboard, A standing water.
wb = np.zeros((N, N))
t_road = i_road / (len(road) - 1)
for t0, t1 in WASHBOARD_T:
    wb = np.maximum(wb, smoothstep(t0, t0 + 0.02, t_road) * (1 - smoothstep(t1 - 0.02, t1, t_road)))
wb *= 1 - smoothstep(2.0, 2.8, d_road)
puddle = haz_mud * smoothstep(0.55, 0.7, fbm(14, 3, SEED + 80)) * smoothstep(0.6, 0.9, haz_mud)
hz = np.stack([haz_mud, haz_quick, wb, puddle], -1)
HZ = 1024
hz_img = ndimage.zoom(hz, (HZ / N, HZ / N, 1), order=1)
Image.fromarray((np.clip(hz_img[::-1], 0, 1) * 255).round().astype(np.uint8), "RGBA").save(os.path.join(MASKS, "desert_hazard.png"))

# Warning signs beside the quicksand, and signposts where side tracks leave the main track.
for cx, cz, rx, rz, yaw in QUICKSAND:
    _, k = road_tree.query([cx, cz])
    best = None
    for sp in side_paths.values():
        d, kk = cKDTree(sp).query([cx, cz])
        if best is None or d < best[0]:
            best = (d, sp[kk])
    tx_, tz_ = best[1] if best and best[0] < sample(d_road, cx, cz) else road[k]
    ang = math.atan2(tx_ - cx, tz_ - cz)
    sx, sz = cx + math.sin(ang) * (max(rx, rz) + 3), cz + math.cos(ang) * (max(rx, rz) + 3)
    markers.append(piece("Signpost", sx, sz, math.degrees(ang), 0.1))
for name, sp in side_paths.items():
    if name == "playa":
        continue
    x0, z0 = sp[min(40, len(sp) - 1)]
    tx_, tz_ = sp[min(60, len(sp) - 1)] - sp[min(20, len(sp) - 1)]
    ln = math.hypot(tx_, tz_) or 1
    markers.append(piece("Signpost", x0 + tz_ / ln * 3.2, z0 - tx_ / ln * 3.2, math.degrees(math.atan2(tx_, tz_)) + 90, 0.1))
info = {"size": SIZE, "height": HEIGHT, "resolution": N, "splatResolution": S,
        "layers": ["Sand", "Gravel", "CrackedSoil", "RedRock"],
        "spawn": {"x": round(spawn_x, 2), "z": round(spawn_z, 2), "yaw": round(spawn_heading, 1)},
        "landmarks": landmarks, "markers": markers, "formations": formations, "roadX": road_x, "roadZ": road_z,
        "tracks": tracks}
with open(os.path.join(SRC, "desert_info.json"), "w") as f_:
    json.dump(info, f_, indent=1)
print("Done.")
