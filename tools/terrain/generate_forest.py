"""Cedar Hollow: the forest river valley region.

Run:  python tools/terrain/generate_forest.py
Needs numpy, scipy, pillow.

Layout (x east, z north, metres):
  * A river pours over a granite cliff in the north (Twin Falls) into a plunge lake, then meanders
    south-east down a broad valley floor of meadows, gravel bars and aspen groves.
  * Forested slopes (firs, with ferns and fallen logs) rise to granite crags and two domes.
  * An old logging track runs up the valley from the south, fording the river twice and crossing it
    once on an old timber bridge; side tracks climb in switchbacks to a fire lookout, and lead to the
    ranger's cabin, the logging camp and a marshy beaver pond.
  * Low spots on the tracks hold mud holes; the soft forest soil takes deep ruts.

Outputs:
  Assets/Terrain/Source~/forest_height.r16, forest_splat.png (R forest floor, G meadow, B soil, A rock),
  forest_scatter.json, forest_info.json (incl. river and lake for the water meshes)
  Assets/Terrain/Masks/forest_mask.png    render mask: R forest floor, G meadow, B soil, A gravel
  Assets/Terrain/Masks/forest_hazard.png  R mud, G water depth (/2.5 m), B unused, A puddles
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
HEIGHT = 300.0
CELL = SIZE / (N - 1)
SEED = 23
rng = np.random.default_rng(SEED)
zs, xs = np.mgrid[0:N, 0:N].astype(np.float64) * CELL


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


def path_length(points):
    p = np.array(points, float)
    return float(np.sum(np.hypot(*np.diff(p, axis=0).T)))


def resample(path, step):
    seg = np.hypot(*np.diff(path, axis=0).T)
    s = np.concatenate([[0], np.cumsum(seg)])
    t = np.arange(0, s[-1], step)
    return np.stack([np.interp(t, s, path[:, 0]), np.interp(t, s, path[:, 1])], 1)


def meander(path, amp, seed):
    seg = np.diff(path, axis=0, prepend=path[:1])
    s = np.cumsum(np.hypot(seg[:, 0], seg[:, 1]))
    t = np.gradient(path, axis=0)
    t /= np.linalg.norm(t, axis=1, keepdims=True) + 1e-9
    nrm = np.stack([t[:, 1], -t[:, 0]], 1)
    r = np.random.default_rng(seed)
    p1, p2 = r.uniform(0, 6.3, 2)
    off = amp * (0.7 * np.sin(s / 37 + p1) + 0.3 * np.sin(s / 12 + p2))
    off *= np.minimum(1, np.minimum(s, s[-1] - s) / 20)
    return path + nrm * off[:, None]


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


# ---------------------------------------------------------------------------- river, lake, valley

RIVER = [(338, 880), (342, 846), (370, 812), (402, 790), (446, 730), (432, 660), (468, 590), (540, 540),
         (590, 470), (570, 390), (612, 316), (684, 256), (744, 190), (800, 120), (850, 40), (880, -30)]
river = resample(catmull(RIVER, 6000), 1.0)
n_r = len(river)
t_r = np.linspace(0, 1, n_r)
LAKE = (338, 872, 46, 34, 0)                            # plunge pool below the falls
FALLS = (338, 906)                                      # the cliff band on the lake's north shore

d_river, i_river, river_tree = path_field(river)
river_w = 7.0 + 5.0 * np.sin(t_r * 9.0 + 1.0) ** 2 + 4.0 * t_r      # half width grows downstream
river_level = 66.0 - 30.0 * t_r                                      # water surface, falling downstream
FORDS = [0.47, 0.70]                                   # where the main track wades across (fraction along)
BRIDGE_T = 0.315
for ft in FORDS:                                       # fords: wide and shallow
    river_w += 7.0 * np.exp(-((t_r - ft) / 0.012) ** 2)
river_depth = 1.6 + 0.6 * np.sin(t_r * 23.0) ** 2
for ft in FORDS:
    river_depth = river_depth * (1 - 0.8 * np.exp(-((t_r - ft) / 0.014) ** 2))

hw = river_w[i_river]
level = river_level[i_river]
depth = river_depth[i_river]

print("Building heightmap...")
# Valley floor follows the river; slopes rise to ridges and mountains at the edges.
# (Smoothed: the nearest river point jumps between distant bends along straight seams, and a raw
# lookup would leave steps there.)
floor = ndimage.gaussian_filter(level, 24) + 1.2
rise = smoothstep(30, 420, d_river) ** 1.25 * 95.0
ridges = 1 - np.abs(fbm(3.0, 4, SEED + 1) * 2 - 1)
mount = rise * (0.65 + 0.55 * ridges) + 18 * (fbm(6, 4, SEED + 2) - 0.5) * smoothstep(40, 200, d_river)
h = floor + mount + 2.2 * (fbm(14, 3, SEED + 3) - 0.5)
# Terraces near the river (old flood benches) and meadow flats.
bench = smoothstep(25, 60, d_river) * (1 - smoothstep(90, 150, d_river))
h -= bench * 3.0 * fbm(5, 2, SEED + 4)
# Northern headwall: the plateau the falls pour from, rising into mountains behind.
zw = zs + 40 * (fbm(4, 3, SEED + 7) - 0.5) * smoothstep(60, 160, np.abs(xs - FALLS[0]))   # wavy, straight only at the falls
head = smoothstep(898, 922, zw) * 22.0 + smoothstep(922, 1024, zw) * 30.0
h = h + head
# Edges rise into mountains everywhere except where the river leaves (south-east).
edge = (0.5 * np.maximum(np.abs(xs - SIZE / 2), np.abs(zs - SIZE / 2)) + 0.5 * np.hypot(xs - SIZE / 2, zs - SIZE / 2) * 0.85) / (SIZE / 2)
exitgap = smoothstep(60, 140, np.hypot(xs - 860, zs - 0))
h += 45 * smoothstep(0.82, 0.98, edge + 0.08 * (fbm(5, 3, SEED + 5) - 0.5)) * exitgap

# River channel: flat-bottomed, with sloping banks; the water surface sits at `level`.
bank = 1 - smoothstep(hw * 0.75, hw + 9.0, d_river)
bed = level - depth * (1 - smoothstep(hw * 0.3, hw, d_river)) - 0.3
h = h * (1 - bank) + np.minimum(h, np.maximum(bed, level - depth)) * bank
h = np.where(d_river < hw, np.minimum(h, bed), h)

# Plunge lake.
rL = ellipse_r(*LAKE)
lake_level = float(river_level[0] - 0.2)
lake_bed = lake_level - 3.2 * (1 - smoothstep(0.0, 1.0, rL))
wl = 1 - smoothstep(0.95, 1.35, rL)
h = h * (1 - wl) + np.minimum(h * (1 - wl) + lake_bed * wl, np.maximum(lake_bed, lake_level - 3.2)) * wl
h = np.where(rL < 1.0, np.minimum(h, lake_bed), h)

print("Eroding...")
talus = 1.6
for _ in range(16):
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nb = np.roll(np.roll(h, dx, axis=1), dz, axis=0)
        diff = h - nb
        move = np.where(diff > talus, (diff - talus) * 0.25, 0.0)
        h = h - move + np.roll(np.roll(move, -dx, axis=1), -dz, axis=0)
h = ndimage.gaussian_filter(h, 0.7)
# Re-carve the water so erosion can't fill it.
h = np.where(d_river < hw, np.minimum(h, level - 0.25), h)
h = np.where(rL < 1.0, np.minimum(h, lake_level - 0.25), h)

water_depth = np.maximum(0, np.where(rL < 1.15, lake_level, -1e3) - h)
water_depth = np.maximum(water_depth, np.where(d_river < hw + 6, level - h, 0))
water_depth = np.clip(water_depth, 0, 6)


# ---------------------------------------------------------------------------- formations

FOOT = {"Dome_0": (37, 35), "Dome_1": (27, 25), "Crag_0": (17, 9), "Crag_1": (12, 7), "Crag_2": (23, 9),
        "Tor_0": (4.5, 3.7), "Tor_1": (3.0, 2.8), "Falls_0": (32, 11)}
formations = []


def add_formation(model, x, z, yaw, scale, sink=2.0):
    formations.append({"model": model, "x": round(float(x), 2), "z": round(float(z), 2), "yaw": round(float(yaw), 1),
                       "scale": round(float(scale), 2), "sink": sink})


# The falls cliff on the lake's north shore, its face (and the notch the water pours through) to the south.
add_formation("Falls_0", FALLS[0], FALLS[1], 180, 1.0, 3.0)
add_formation("Dome_0", 170, 560, 120, 1.0, 6.0)
add_formation("Dome_1", 838, 650, 300, 1.05, 5.0)
slope0 = slope_map(h)
cand = np.argwhere((slope0 > 24) & (slope0 < 45) & (d_river > 120))
rng.shuffle(cand)
placed = 0
for zi, xi in cand:
    if placed >= 16:
        break
    x, z = xi * CELL, zi * CELL
    if not (60 < x < SIZE - 60 and 60 < z < SIZE - 60):
        continue
    if any(math.hypot(x - f["x"], z - f["z"]) < 90 for f in formations):
        continue
    model = ["Crag_0", "Crag_1", "Crag_2"][placed % 3]
    gz, gx = np.gradient(h, CELL)
    yaw = math.degrees(math.atan2(gx[zi, xi], gz[zi, xi]))     # long axis across the slope
    add_formation(model, x, z, yaw + 90, rng.uniform(0.8, 1.3), 4.0)
    placed += 1
for k in range(22):
    for _ in range(80):
        x, z = rng.uniform(80, SIZE - 80, 2)
        if sample(d_river, x, z) > 90 and sample(slope0, x, z) < 22 and all(math.hypot(x - f["x"], z - f["z"]) > 45 for f in formations):
            add_formation(["Tor_0", "Tor_1"][k % 2], x, z, rng.uniform(0, 360), rng.uniform(0.8, 1.4), 1.0)
            break


def footprint_r(f, x=None, z=None):
    rx, rz = FOOT[f["model"]]
    return ellipse_r(f["x"], f["z"], rx * f["scale"], rz * f["scale"], -f["yaw"], x, z)


foot_r = np.full((N, N), 9.0)
for f in formations:
    foot_r = np.minimum(foot_r, footprint_r(f))
h += 2.0 * smoothstep(1.5, 0.8, foot_r) * (d_river > 30)


# ---------------------------------------------------------------------------- tracks

def river_point(t, side):
    k = int(np.clip(t, 0, 1) * (n_r - 1))
    a, b = river[max(k - 3, 0)], river[min(k + 3, n_r - 1)]
    tx, tz = b - a
    ln = math.hypot(tx, tz) or 1
    return float(river[k][0] + tz / ln * side), float(river[k][1] - tx / ln * side)


# Main track: from the south up the west bank, fording to the east bank, back to the west at the
# second ford, then over the Old Bridge to the east bank and on to the lake below the falls.
def crossing(t, from_side, reach=38.0):
    """Approach, centre and exit points of a river crossing (sides: +1 / -1 of the river's normal)."""
    return [river_point(t, from_side * reach), river_point(t, 0), river_point(t, -from_side * reach)]


def side_of(x, z, t):
    k = int(np.clip(t, 0, 1) * (n_r - 1))
    a, b = river[max(k - 3, 0)], river[min(k + 3, n_r - 1)]
    tx, tz = b - a
    return 1 if ((x - river[k][0]) * tz - (z - river[k][1]) * tx) > 0 else -1


start = (690, 15)
MAIN = [start, (680, 100), (660, 170)]
MAIN += crossing(FORDS[1], side_of(660, 170, FORDS[1]))
MAIN += [(700, 330), (652, 405), (640, 468)]
MAIN += crossing(FORDS[0], side_of(640, 468, FORDS[0]))
MAIN += [(520, 520)]
MAIN += crossing(BRIDGE_T, side_of(520, 520, BRIDGE_T), 34.0)
MAIN += [(500, 660), (490, 740), (440, 800), (402, 858), (392, 884)]
main = resample(meander(catmull(MAIN, 8000), 2.0, SEED + 30), 0.3)
spawn_x, spawn_z = float(main[60][0]), float(main[60][1])
spawn_heading = math.degrees(math.atan2(*(main[90] - main[40])))

LOOKOUT = (872, 430)
CABIN = (238, 380)
CAMP = (230, 140)
POND = (770, 790)
SIDE = {
    "lookout": [(700, 330), (760, 340), (805, 378), (772, 410), (830, 420), (858, 432)],
    "cabin": [(520, 520), (430, 470), (330, 410), (262, 386)],
    "camp": [(680, 100), (560, 120), (420, 110), (300, 130), (252, 140)],
    "pond": [(490, 740), (580, 760), (680, 790), (752, 795)],
}
side_paths = {k: resample(meander(catmull(v, int(path_length(v) / 0.3)), 1.6, SEED + 40 + i), 0.3)
              for i, (k, v) in enumerate(SIDE.items())}
d_main, i_main, main_tree = path_field(main)
d_side = np.full((N, N), 1e4)
for sp in side_paths.values():
    d_side = np.minimum(d_side, path_field(sp)[0])
d_track = np.minimum(d_main, d_side)

# Grade tracks lightly (they follow the land); keep the fords at the river bed.
for path, width, strength in [(main, 3.2, 0.8)] + [(sp, 2.6, 0.75) for sp in side_paths.values()]:
    d_p, i_p, _ = path_field(path)
    ph = ndimage.gaussian_filter1d(np.array([sample(h, x, z) for x, z in path]), 18, mode="nearest")
    w_p = (1 - smoothstep(width, width + 7, d_p)) * strength * (d_river > hw + 2)
    h = h * (1 - w_p) + ph[i_p] * w_p


# ---------------------------------------------------------------------------- hazards

MUD_HOLES = []
for path in [main] + list(side_paths.values()):
    for k in range(200, len(path) - 200, 260):
        x, z = path[k]
        if sample(d_river, x, z) < 30 or sample(slope0, x, z) > 7 or rng.random() < 0.45:
            continue
        a = math.degrees(math.atan2(*(path[k + 5] - path[k - 5])))
        MUD_HOLES.append((float(x), float(z), rng.uniform(5, 9), rng.uniform(3.5, 6), -a))
POND_MARSH = (POND[0] + 30, POND[1] + 10, 38, 26, 20)
haz_mud = np.zeros((N, N))
for cx, cz, rx, rz, yaw in MUD_HOLES + [POND_MARSH]:
    r = ellipse_r(cx, cz, rx, rz, yaw) * (1 + 0.2 * (fbm(9, 2, SEED + 60 + int(cx)) - 0.5))
    haz_mud = np.maximum(haz_mud, smoothstep(1.15, 0.8, r))
lowered = ndimage.uniform_filter(h, 7)
h = h * (1 - haz_mud) + (lowered - 0.35) * haz_mud
puddle = haz_mud * smoothstep(0.5, 0.68, fbm(16, 3, SEED + 80)) * smoothstep(0.55, 0.9, haz_mud)
puddle = np.maximum(puddle, smoothstep(0.9, 0.5, ellipse_r(*POND_MARSH)) * 0.9)   # the pond itself


# ---------------------------------------------------------------------------- landmarks

landmarks = []


def piece(model, x, z, yaw, sink=0.0, align=0.0, local=None):
    if local:
        ox, oz, lx, lz, lyaw = local
        a = math.radians(lyaw)
        x = lx + ox * math.cos(a) + oz * math.sin(a)
        z = lz - ox * math.sin(a) + oz * math.cos(a)
        yaw = yaw + lyaw
    return {"model": model, "x": round(float(x), 2), "z": round(float(z), 2), "yaw": round(yaw % 360, 1), "sink": sink, "align": align}


def landmark(lid, name, x, z, radius, pieces, discover_radius=None):
    landmarks.append({"id": lid, "name": name, "x": round(float(x), 2), "z": round(float(z), 2), "radius": radius,
                      "discoverRadius": discover_radius or radius * 2.2, "pieces": pieces})


def flatten(x, z, radius, strength=1.0):
    global h
    d = np.hypot(xs - x, zs - z)
    target = h[d < radius * 0.5].mean()
    w = smoothstep(radius, radius * 0.55, d) * strength
    h = h * (1 - w) + target * w


print("Placing landmarks...")
camp_x, camp_z = float(main[130][0] + 22), float(main[130][1] + 6)
flatten(camp_x, camp_z, 16)
cy = math.degrees(math.atan2(spawn_x - camp_x, spawn_z - camp_z))
landmark("trailhead", "Trailhead Camp", camp_x, camp_z, 12, [
    piece("Tent", 0, 0, 0, 0.02, local=(0, -2, camp_x, camp_z, cy + 180)),
    piece("FireRing", 0, 0, 0, 0.05, local=(-3.5, 2.5, camp_x, camp_z, cy + 180)),
    piece("Crates", 0, 0, 30, 0.0, local=(3.2, 0.5, camp_x, camp_z, cy + 180)),
], discover_radius=1)
flatten(*CABIN, 22)
landmark("ranger_cabin", "Ranger's Cabin", *CABIN, 18, [
    piece("LogCabin", CABIN[0], CABIN[1], 75, 0.1),
    piece("WoodPile", CABIN[0] + 8, CABIN[1] - 4, 75, 0.05),
])
flatten(*LOOKOUT, 18)
landmark("lookout", "Fire Lookout", *LOOKOUT, 14, [piece("FireLookout", LOOKOUT[0], LOOKOUT[1], 30, 0.2)])
flatten(*CAMP, 30, 0.8)
landmark("logging_camp", "Logging Camp", *CAMP, 26, [
    piece("LogPile", CAMP[0] + 6, CAMP[1] + 4, 20, 0.05),
    piece("LogPile", CAMP[0] - 8, CAMP[1] + 10, 110, 0.05),
    piece("Wreck", CAMP[0] + 14, CAMP[1] - 8, 60, 0.3, 0.7),
    piece("Shack", CAMP[0] - 14, CAMP[1] - 10, 200, 0.05),
])
bx, bz = river_point(BRIDGE_T, 0)
ta, tb = river_point(BRIDGE_T, -10), river_point(BRIDGE_T, 10)
bridge_yaw = math.degrees(math.atan2(tb[0] - ta[0], tb[1] - ta[1]))
landmark("old_bridge", "The Old Bridge", bx, bz, 16, [piece("WoodBridge", bx, bz, bridge_yaw, 0.0)], discover_radius=30)
landmark("twin_falls", "Twin Falls", LAKE[0], LAKE[1] + 30, 40, [], discover_radius=70)
landmark("beaver_pond", "Beaver Pond", POND_MARSH[0], POND_MARSH[1], 30, [], discover_radius=55)
landmark("granite_dome", "Sentinel Dome", 170, 560, 40, [], discover_radius=80)

# Bridge deck just above the water; the track ramps up to it on both banks.
bridge_deck = float(river_level[int(BRIDGE_T * (n_r - 1))] + 2.2)
hw_b = float(river_w[int(BRIDGE_T * (n_r - 1))])
d_b = np.hypot(xs - bx, zs - bz)
ramp = (1 - smoothstep(3.5, 7.0, d_main)) * (1 - smoothstep(hw_b + 6, hw_b + 22, d_b)) * (d_river > hw_b + 0.5)
h = h * (1 - ramp) + np.maximum(h, bridge_deck - 0.12) * ramp
landmarks[-4]["pieces"][0]["absY"] = round(bridge_deck, 3)


# ---------------------------------------------------------------------------- output heights

h = np.clip(h, 1, HEIGHT - 1)
slope = slope_map(h)
np.round(h / HEIGHT * 65535).astype("<u2").tofile(os.path.join(SRC, "forest_height.r16"))
print(f"Height range {h.min():.1f}..{h.max():.1f} m")
for L in landmarks:
    print(f"  {L['name']:20s} ({L['x']:.0f}, {L['z']:.0f})  {math.hypot(L['x'] - spawn_x, L['z'] - spawn_z):.0f} m from spawn")


# ---------------------------------------------------------------------------- masks

print("Painting masks...")
patch = fbm(10, 4, SEED + 20)
fine = fbm(26, 3, SEED + 21)
meadow = smoothstep(95, 40, d_river) * smoothstep(14, 6, slope) * smoothstep(0.35, 0.55, patch + 0.15)
meadow = np.maximum(meadow, smoothstep(40, 18, np.hypot(xs - CABIN[0], zs - CABIN[1])))
gravel = (1 - smoothstep(hw + 1, hw + 7 + 6 * fine, d_river)) * (d_river > 0)
gravel = np.maximum(gravel, (1 - smoothstep(0.95, 1.25, rL)) * 0.9)
soil = np.maximum(1 - smoothstep(1.8, 3.6, d_track), haz_mud * 0.9)
soil = np.maximum(soil, smoothstep(0.6, 0.8, fine) * 0.5 * (1 - meadow))
floor_ = np.clip(1 - meadow - gravel - soil, 0.05, 1)
mask = np.stack([floor_, meadow * (1 - gravel), soil * (1 - gravel), gravel], -1)
mask /= mask.sum(-1, keepdims=True)
M = 1024
mask_img = ndimage.zoom(mask, (M / N, M / N, 1), order=1)
Image.fromarray((np.clip(mask_img[::-1], 0, 1) * 255).round().astype(np.uint8), "RGBA").save(os.path.join(MASKS, "forest_mask.png"))

rock_phys = np.maximum(smoothstep(0.3, 0.5, 1 - np.cos(np.radians(slope))), gravel * 0.8)
phys = np.stack([floor_ * (1 - rock_phys), meadow * (1 - rock_phys), soil * (1 - rock_phys), rock_phys], -1)
phys = phys / (phys.sum(-1, keepdims=True) + 1e-6)
S = 512
splat = ndimage.zoom(phys, (S / N, S / N, 1), order=1)
splat = splat / splat.sum(-1, keepdims=True)
Image.fromarray((splat[::-1] * 255).round().astype(np.uint8), "RGBA").save(os.path.join(SRC, "forest_splat.png"))

hz = np.stack([haz_mud, np.clip(water_depth / 2.5, 0, 1), np.zeros((N, N)), puddle], -1)
hz_img = ndimage.zoom(hz, (1024 / N, 1024 / N, 1), order=1)
Image.fromarray((np.clip(hz_img[::-1], 0, 1) * 255).round().astype(np.uint8), "RGBA").save(os.path.join(MASKS, "forest_hazard.png"))


# ---------------------------------------------------------------------------- scatter

print("Scattering...")
props = []
pads = [(L["x"], L["z"], L["radius"]) for L in landmarks if L["pieces"]]


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


solid = Spacing(6.0)


def blocked(x, z, kind, track_clear):
    if not (10 < x < SIZE - 10 and 10 < z < SIZE - 10):
        return True
    if sample(d_track, x, z) < track_clear or sample(water_depth, x, z) > 0.05:
        return True
    if sample(foot_r, x, z) < 0.95:
        return True
    if sample(haz_mud, x, z) > 0.1 and kind not in ("MeadowGrass",):
        return True
    if math.hypot(x - spawn_x, z - spawn_z) < 12:
        return True
    return any(math.hypot(x - px, z - pz) < pr for px, pz, pr in pads)


def put(kind, variants, x, z, scale, sink, spacing=0.0, track_clear=6.0, max_slope=36):
    if blocked(x, z, kind, track_clear) or sample(slope, x, z) > max_slope:
        return False
    if spacing and not solid.ok(x, z, spacing * scale):
        return False
    if spacing:
        solid.add(x, z, spacing * scale)
    props.append({"kind": kind, "variant": int(rng.integers(variants)), "x": round(float(x), 2), "z": round(float(z), 2),
                  "yaw": round(float(rng.uniform(0, 360)), 1), "scale": round(float(scale), 2), "sink": sink})
    return True


# Forest density: thick on the slopes, thinning toward meadows, rock and the high ridges.
forest = (1 - meadow) * smoothstep(40, 12, slope) * smoothstep(22, 45, d_river) * (1 - smoothstep(170, 215, h))
forest *= 0.55 + 0.45 * smoothstep(0.3, 0.6, fbm(7, 3, SEED + 90))
forest *= smoothstep(1.4, 2.2, foot_r)
forest *= 0.25 + 0.75 * smoothstep(9, 24, d_track)          # logging roads run through cleared corridors
fw = (forest / forest.sum()).ravel()
cells = rng.choice(N * N, size=16000, replace=True, p=fw)
trees = 0
for c in cells:
    zi, xi = divmod(int(c), N)
    x, z = xi * CELL + rng.uniform(-1, 1), zi * CELL + rng.uniform(-1, 1)
    hh = sample(h, x, z)
    kind = "Snag" if rng.random() < 0.03 else "Fir"
    sc = rng.uniform(0.75, 1.25) * (1.1 - 0.3 * smoothstep(120, 200, hh))
    if put(kind, 3 if kind == "Fir" else 1, x, z, sc, 0.3, 4.2, 8.5):
        trees += 1
# Aspen groves at meadow edges and along the river.
grove = smoothstep(0.2, 0.5, meadow) * (1 - smoothstep(0.6, 0.95, meadow)) + smoothstep(70, 30, d_river) * 0.4
grove *= smoothstep(14, 6, slope) * (d_river > hw + 8)
gw = (grove / grove.sum()).ravel()
for c in rng.choice(N * N, size=60, replace=False, p=gw):
    zi, xi = divmod(int(c), N)
    cx, cz = xi * CELL, zi * CELL
    for _ in range(int(rng.integers(5, 14))):
        r = abs(rng.normal(0, 9))
        a = rng.uniform(0, 2 * math.pi)
        put("Aspen", 2, cx + math.cos(a) * r, cz + math.sin(a) * r, rng.uniform(0.8, 1.2), 0.2, 3.0, 7.0)
# Understorey: ferns and bushes under the trees, logs and stumps on the forest floor.
for c in rng.choice(N * N, size=14000, replace=True, p=fw):
    zi, xi = divmod(int(c), N)
    x, z = xi * CELL + rng.uniform(-2, 2), zi * CELL + rng.uniform(-2, 2)
    r = rng.random()
    if r < 0.6:
        put("Fern", 2, x, z, rng.uniform(0.7, 1.4), 0.02, track_clear=3.0)
    elif r < 0.85:
        put("Bush", 1, x, z, rng.uniform(0.6, 1.2), 0.05, track_clear=3.5)
    elif r < 0.93:
        put("Log", 2, x, z, rng.uniform(0.8, 1.3), 0.25, 3.0, 4.0, 22)
    else:
        put("Stump", 1, x, z, rng.uniform(0.7, 1.2), 0.15, 2.0, 3.0)
# Meadows: grass everywhere, flowers in drifts.
mw = (meadow * (water_depth < 0.01)).ravel()
mw /= mw.sum()
flowers = fbm(18, 2, SEED + 95)
for c in rng.choice(N * N, size=26000, replace=True, p=mw):
    zi, xi = divmod(int(c), N)
    x, z = xi * CELL + rng.uniform(-1, 1), zi * CELL + rng.uniform(-1, 1)
    if sample(flowers, x, z) > 0.62 and rng.random() < 0.5:
        put("Flowers", 1, x, z, rng.uniform(0.8, 1.3), 0.03, track_clear=2.4)
    else:
        put("MeadowGrass", 2, x, z, rng.uniform(0.8, 1.5), 0.03, track_clear=2.4)
# River boulders and granite talus below the crags and domes.
for k in range(0, n_r, 9):
    if rng.random() < 0.55:
        continue
    side = rng.choice([-1, 1]) * (river_w[k] + rng.uniform(1, 9))
    x, z = river_point(k / (n_r - 1), side)
    put("GBoulder", 4, x, z, rng.uniform(0.5, 1.4), 0.3, 1.2, 4.0, 40)
for f in formations:
    rx, rz = FOOT[f["model"]]
    for _ in range(int((rx + rz) * f["scale"] * 0.5)):
        a = rng.uniform(0, 2 * math.pi)
        dist = rng.uniform(1.0, 1.6)
        x = f["x"] + math.cos(a) * rx * f["scale"] * dist
        z = f["z"] + math.sin(a) * rz * f["scale"] * dist
        put("GBoulder", 4, x, z, rng.uniform(0.5, 1.6), 0.4, 1.4, 4.0, 45)

markers = []
for name, sp in side_paths.items():           # signposts where side tracks leave the main track
    x0, z0 = sp[min(40, len(sp) - 1)]
    tx_, tz_ = sp[min(60, len(sp) - 1)] - sp[min(20, len(sp) - 1)]
    ln = math.hypot(tx_, tz_) or 1
    markers.append(piece("Signpost", x0 + tz_ / ln * 3.0, z0 - tx_ / ln * 3.0, math.degrees(math.atan2(tx_, tz_)) + 90, 0.1))

with open(os.path.join(SRC, "forest_scatter.json"), "w") as f_:
    json.dump({"props": props}, f_, separators=(",", ":"))
counts = {}
for p in props:
    counts[p["kind"]] = counts.get(p["kind"], 0) + 1
print("Props:", counts, "formations:", len(formations), "mud holes:", len(MUD_HOLES))


# ---------------------------------------------------------------------------- info

def track_record(name, path, width, step=6):
    pts = path[::step]
    n = len(pts)
    fade = np.ones(n)
    if name != "main":
        s = np.linspace(0, path_length(pts), n)
        fade *= np.clip((s[-1] - s) / 10, 0, 1)
    # No track decal in the water (fords) or on the bridge deck.
    wet = np.array([sample(water_depth, x, z) for x, z in pts])
    fade *= np.clip(1 - wet / 0.08, 0, 1)
    return {"name": name, "width": width, "x": [round(float(x), 2) for x, _ in pts], "z": [round(float(z), 2) for _, z in pts],
            "washboard": [0.0] * n, "fade": [round(float(v), 2) for v in fade]}


rv = river[::4]
info = {"size": SIZE, "height": HEIGHT, "resolution": N, "splatResolution": S,
        "layers": ["ForestFloor", "Meadow", "Soil", "Granite"],
        "spawn": {"x": round(spawn_x, 2), "z": round(spawn_z, 2), "yaw": round(spawn_heading, 1)},
        "landmarks": landmarks, "markers": markers, "formations": formations,
        "roadX": [round(float(x), 2) for x, _ in main[::6]], "roadZ": [round(float(z), 2) for _, z in main[::6]],
        "tracks": [track_record("main", main, 4.2)] + [track_record(k, sp, 3.2) for k, sp in side_paths.items()],
        "river": {"x": [round(float(x), 2) for x, _ in rv], "z": [round(float(z), 2) for _, z in rv],
                  "halfWidth": [round(float(v), 2) for v in river_w[::4]],
                  "level": [round(float(v), 3) for v in river_level[::4]]},
        "lake": {"x": LAKE[0], "z": LAKE[1], "rx": LAKE[2], "rz": LAKE[3], "yaw": LAKE[4], "level": round(lake_level, 3)},
        "falls": {"x": FALLS[0], "z": FALLS[1], "top": round(float(river_level[0] + 22), 2), "bottom": round(lake_level, 2)},
        "bridge": {"x": round(bx, 2), "z": round(bz, 2), "yaw": round(bridge_yaw, 1), "deck": round(bridge_deck, 2)}}
with open(os.path.join(SRC, "forest_info.json"), "w") as f_:
    json.dump(info, f_, indent=1)
print("Done.")
