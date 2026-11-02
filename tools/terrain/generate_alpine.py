"""Highline Pass: the high alpine region.

Run:  python tools/terrain/generate_alpine.py
Needs numpy, scipy, pillow.

Layout (x east, z north, metres):
  * A U-shaped glacial valley climbs from the south (sparse firs and krummholz at the treeline, tundra
    turf, a braided meltwater stream) to a cirque holding a turquoise tarn below a glacier.
  * Peaks rise all round: Grey Tooth (west), the Sentinels (east) and the cirque headwall (north),
    with scree fans at the foot of every cliff and snow lingering above ~250 m and in north-facing hollows.
  * The pass track climbs the valley, fords the stream, passes the Stone Hut on the tarn shore, then
    switchbacks up the eastern cirque wall, across late-lying snowfields, to the saddle of Highline Pass.
    Side tracks lead to an old silver mine on the western scree slopes and a weather station on a knoll.
  * Hazards: deep snowdrifts across the upper track, sheet ice where meltwater refroze, slushy
    meltwater puddles, the stream ford and the frozen tarn by the pass.

Outputs:
  Assets/Terrain/Source~/alpine_height.r16, alpine_splat.png (R tundra, G scree, B snow, A rock),
  alpine_scatter.json, alpine_info.json (incl. stream and tarn for the water meshes)
  Assets/Terrain/Masks/alpine_mask.png    render mask: R tundra, G scree, B snow, A track/soil
  Assets/Terrain/Masks/alpine_hazard.png  R deep snow, G water depth (/2.5 m), B ice, A meltwater/slush
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
HEIGHT = 520.0
CELL = SIZE / (N - 1)
SEED = 41
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


def ridged(freq, octaves, seed):
    total, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        total = total + amp * (1 - np.abs(value_noise(freq * 2 ** o, seed + o * 37) * 2 - 1)) ** 2
        norm += amp
        amp *= 0.5
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


def gauss(cx, cz, r):
    return np.exp(-((xs - cx) ** 2 + (zs - cz) ** 2) / (2 * r * r))


# ---------------------------------------------------------------------------- valley, tarn, stream

TARN = (420, 600, 58, 40, 15)                  # glacial lake in the cirque
TARN_LEVEL = 164.0
SADDLE = (712, 905)                            # Highline Pass
FROZEN = (775, 868, 22, 15, -20)               # small frozen tarn just below the saddle
STREAM = [(398, 562), (420, 520), (470, 470), (500, 400), (486, 330), (520, 250), (548, 180), (530, 100), (560, 30), (575, -30)]
stream = resample(catmull(STREAM, 5000), 1.0)
n_s = len(stream)
t_s = np.linspace(0, 1, n_s)
stream_w = 3.0 + 2.5 * t_s + 1.5 * np.sin(t_s * 17) ** 2
FORD_T = 0.56
stream_w += 6.0 * np.exp(-((t_s - FORD_T) / 0.015) ** 2)
stream_level = TARN_LEVEL - 0.3 - 102.0 * t_s ** 0.9      # tumbling down the valley
stream_depth = 0.7 + 0.4 * np.sin(t_s * 31) ** 2
stream_depth *= 1 - 0.6 * np.exp(-((t_s - FORD_T) / 0.016) ** 2)
d_stream, i_stream, _ = path_field(stream)
s_hw = stream_w[i_stream]
s_level = stream_level[i_stream]
s_depth = stream_depth[i_stream]

print("Building heightmap...")
# Valley axis (the glacier's old path) from the cirque south to the map edge.
VALLEY = [(420, 640), (440, 520), (490, 420), (500, 300), (530, 180), (560, 40), (575, -60)]
valley = resample(catmull(VALLEY, 4000), 1.0)
d_valley, i_valley, _ = path_field(valley)
t_v = np.linspace(0, 1, len(valley))
floor_v = TARN_LEVEL + 4.0 - 108.0 * t_v ** 0.9
floor = ndimage.gaussian_filter(floor_v[i_valley], 18)

# Mountain mass: domain-warped ridged noise, so crests run as long arêtes and spurs, not blobs.
def warped_ridges(freq, octaves, seed, warp):
    wx = (fbm(2.0, 3, seed + 11) - 0.5) * warp / CELL
    wz = (fbm(2.0, 3, seed + 12) - 0.5) * warp / CELL
    out, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        base = value_noise(freq * 2 ** o, seed + o * 37)
        r = 1 - np.abs(base * 2 - 1)
        r = ndimage.map_coordinates(r, [np.clip(np.mgrid[0:N, 0:N][0] + wz, 0, N - 1),
                                         np.clip(np.mgrid[0:N, 0:N][1] + wx, 0, N - 1)], order=1)
        out = out + amp * r ** 1.6
        norm += amp
        amp *= 0.45
    return out / norm


rid = warped_ridges(2.6, 4, SEED + 1, 180.0)
mass = 0.55 * rid + 0.45 * fbm(2.2, 4, SEED + 6)
wall = smoothstep(55, 280, d_valley) ** 1.25
crags = warped_ridges(7.0, 4, SEED + 13, 90.0)            # spurs, arêtes and the gullies between them
fines = warped_ridges(20.0, 3, SEED + 14, 35.0)           # rock ribs and couloirs
mountain = wall * (105 + 150 * mass) + wall ** 1.5 * 70 * (crags - 0.42) + wall * 22 * (fines - 0.45)
# Cliff bands: the mountain part is partly terraced into steps, which erode into rock bands.
step_h = 16.0
t_ = mountain / step_h + 2.0 * fbm(6, 2, SEED + 15)
terr = (np.floor(t_) + smoothstep(0.35, 0.75, t_ - np.floor(t_))) * step_h - 2.0 * fbm(6, 2, SEED + 15) * step_h
mountain = mountain * 0.6 + terr * 0.4 * smoothstep(0.15, 0.5, wall) + mountain * 0.4 * (1 - smoothstep(0.15, 0.5, wall))
h = floor + mountain + 8 * (fbm(7, 4, SEED + 2) - 0.5) * smoothstep(30, 140, d_valley)
h += 1.6 * (fbm(18, 3, SEED + 3) - 0.5)
# Moraine ridges along the valley sides and a terminal moraine below the tarn.
h += 4.0 * np.exp(-((d_valley - 85) / 14) ** 2) * (1 - smoothstep(540, 620, zs))
rm = ellipse_r(445, 520, 80, 22, 25)
h += 5.0 * np.exp(-(rm - 1) ** 2 / 0.06) * (rm < 1.5)
# Peaks.
h += 150 * gauss(230, 850, 80) * (0.85 + 0.3 * rid)      # Grey Tooth
h += 120 * gauss(935, 760, 85) * (0.85 + 0.3 * rid)      # the Sentinels
h += 90 * gauss(540, 1010, 110)                          # north rim
# Cirque headwall behind the tarn, a steep amphitheatre.
cr = np.hypot((xs - 420) / 1.15, zs - 640)
h += smoothstep(90, 230, cr) * 80 * smoothstep(560, 720, zs) * (1 - smoothstep(540, 680, xs))
# Pass slope: the eastern cirque wall is a broad, even ramp from the tarn up to the saddle.
ramp_axis = np.array([[455, 640], [560, 720], [640, 800], [SADDLE[0], SADDLE[1]]], float)
ramp = resample(catmull(ramp_axis, 600), 1.0)
d_ramp, i_ramp, _ = path_field(ramp)
t_r = np.linspace(0, 1, len(ramp))
ramp_h = TARN_LEVEL + 6 + (292 - TARN_LEVEL - 6) * t_r
rw = (1 - smoothstep(105, 200, d_ramp + 25 * (fbm(5, 2, SEED + 9) - 0.5))) ** 1.5
h = h * (1 - rw) + (ramp_h[i_ramp] + 9 * (fbm(6, 3, SEED + 8) - 0.5) + 5 * (crags - 0.45)) * rw
# The saddle itself, between the shoulders, and the far side dropping away to the north.
sw = gauss(*SADDLE, 60)
h = h * (1 - sw) + (292 + 0.002 * (xs - SADDLE[0]) ** 2) * sw
h += 50 * smoothstep(950, 1024, zs) * (1 - sw)
# Edge mountains (except where the valley leaves to the south).
edge = (0.5 * np.maximum(np.abs(xs - SIZE / 2), np.abs(zs - SIZE / 2)) + 0.5 * np.hypot(xs - SIZE / 2, zs - SIZE / 2) * 0.85) / (SIZE / 2)
exitgap = smoothstep(70, 170, np.hypot(xs - 570, zs + 20))
h += 50 * smoothstep(0.84, 0.99, edge + 0.08 * (fbm(5, 3, SEED + 5) - 0.5)) * exitgap
# Weather station knoll: a rounded shoulder on the east side of the valley.
h += 18 * gauss(690, 430, 28)
# Soft cap: summits compress instead of clipping.
h = np.where(h > 430, 430 + (h - 430) * 0.55, h)

# Tarn basin.
rT = ellipse_r(*TARN)
tarn_bed = TARN_LEVEL - 5.0 * (1 - smoothstep(0.0, 1.0, rT))
wl = 1 - smoothstep(0.95, 1.45, rT)
h = h * (1 - wl) + np.minimum(h * (1 - wl) + tarn_bed * wl, np.maximum(tarn_bed, TARN_LEVEL - 5.0)) * wl
h = np.where(rT < 1.0, np.minimum(h, tarn_bed), h)
# Frozen tarn: a flat iced hollow below the saddle.
rF = ellipse_r(*FROZEN)
frozen_level = float(np.mean(h[rF < 0.6])) - 1.5
h = np.where(rF < 1.0, frozen_level, h * smoothstep(0.9, 1.6, rF) + frozen_level * (1 - smoothstep(0.9, 1.6, rF)))

# Stream channel.
bank = 1 - smoothstep(s_hw * 0.8, s_hw + 6.0, d_stream)
bed = s_level - s_depth * (1 - smoothstep(s_hw * 0.3, s_hw, d_stream)) - 0.2
h = h * (1 - bank) + np.minimum(h, np.maximum(bed, s_level - s_depth)) * bank
h = np.where(d_stream < s_hw, np.minimum(h, bed), h)

print("Eroding...")
talus = 2.2
for _ in range(14):
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nb = np.roll(np.roll(h, dx, axis=1), dz, axis=0)
        diff = h - nb
        move = np.where(diff > talus, (diff - talus) * 0.25, 0.0)
        h = h - move + np.roll(np.roll(move, -dx, axis=1), -dz, axis=0)
h = ndimage.gaussian_filter(h, 0.7)
h = np.where(d_stream < s_hw, np.minimum(h, s_level - 0.2), h)
h = np.where(rT < 1.0, np.minimum(h, TARN_LEVEL - 0.25), h)

water_depth = np.maximum(0, np.where(rT < 1.2, TARN_LEVEL, -1e3) - h)
water_depth = np.maximum(water_depth, np.where(d_stream < s_hw + 5, s_level - h, 0))
water_depth = np.clip(water_depth, 0, 6)


# ---------------------------------------------------------------------------- formations

FOOT = {"Spire_0": (9, 8), "Spire_1": (7, 6), "Ridge_0": (30, 9), "Ridge_1": (22, 8), "Ridge_2": (40, 11),
        "Erratic_0": (5, 4), "Erratic_1": (3.5, 3)}
formations = []


def add_formation(model, x, z, yaw, scale, sink=2.0):
    formations.append({"model": model, "x": round(float(x), 2), "z": round(float(z), 2), "yaw": round(float(yaw), 1),
                       "scale": round(float(scale), 2), "sink": sink})


add_formation("Spire_0", 236, 812, 20, 1.3, 6.0)              # Grey Tooth's summit tower
add_formation("Spire_1", 905, 735, 140, 1.2, 5.0)             # the Sentinels
add_formation("Spire_1", 958, 790, 60, 1.0, 5.0)
slope0 = slope_map(h)
gz0, gx0 = np.gradient(h, CELL)
cand = np.argwhere((slope0 > 26) & (slope0 < 48) & (d_valley > 110) & (d_ramp > 90))
rng.shuffle(cand)
placed = 0
for zi, xi in cand:
    if placed >= 20:
        break
    x, z = xi * CELL, zi * CELL
    if not (60 < x < SIZE - 60 and 60 < z < SIZE - 60):
        continue
    if any(math.hypot(x - f["x"], z - f["z"]) < 80 for f in formations):
        continue
    yaw = math.degrees(math.atan2(gx0[zi, xi], gz0[zi, xi]))     # long axis across the slope
    add_formation(["Ridge_0", "Ridge_1", "Ridge_2"][placed % 3], x, z, yaw + 90, rng.uniform(0.85, 1.35), 5.0)
    placed += 1
for k in range(16):                                              # glacial erratics on the valley floor
    for _ in range(100):
        x, z = rng.uniform(80, SIZE - 80, 2)
        if (sample(d_valley, x, z) < 140 and sample(slope0, x, z) < 14 and sample(water_depth, x, z) <= 0
                and sample(d_ramp, x, z) > 30 and all(math.hypot(x - f["x"], z - f["z"]) > 50 for f in formations)):
            add_formation(["Erratic_0", "Erratic_1"][k % 2], x, z, rng.uniform(0, 360), rng.uniform(0.8, 1.4), 0.8)
            break


def footprint_r(f, x=None, z=None):
    rx, rz = FOOT[f["model"]]
    return ellipse_r(f["x"], f["z"], rx * f["scale"], rz * f["scale"], -f["yaw"], x, z)


foot_r = np.full((N, N), 9.0)
for f in formations:
    foot_r = np.minimum(foot_r, footprint_r(f))


# ---------------------------------------------------------------------------- tracks

def stream_point(t, side):
    k = int(np.clip(t, 0, 1) * (n_s - 1))
    a, b = stream[max(k - 3, 0)], stream[min(k + 3, n_s - 1)]
    tx, tz = b - a
    ln = math.hypot(tx, tz) or 1
    return float(stream[k][0] + tz / ln * side), float(stream[k][1] - tx / ln * side)


def side_of(x, z, t):
    k = int(np.clip(t, 0, 1) * (n_s - 1))
    a, b = stream[max(k - 3, 0)], stream[min(k + 3, n_s - 1)]
    tx, tz = b - a
    return 1 if ((x - stream[k][0]) * tz - (z - stream[k][1]) * tx) > 0 else -1


start = (600, 18)
MAIN = [start, (598, 90), (590, 170)]
fs = side_of(590, 170, FORD_T)
MAIN += [stream_point(FORD_T, fs * 30), stream_point(FORD_T, 0), stream_point(FORD_T, -fs * 30)]
MAIN += [(455, 330), (440, 410), (478, 470), (515, 545), (492, 610)]       # up the valley to the hut
# Switchbacks up the eastern cirque wall to the saddle.
MAIN += [(540, 640), (640, 668), (590, 712), (548, 752), (650, 760), (720, 790), (668, 832), (640, 860), (700, 885), SADDLE,
         (720, 960)]
main = resample(meander(catmull(MAIN, 9000), 1.4, SEED + 30), 0.3)
spawn_x, spawn_z = float(main[60][0]), float(main[60][1])
spawn_heading = math.degrees(math.atan2(*(main[90] - main[40])))

HUT = (520, 600)
MINE = (318, 404)
STATION = (690, 430)
SIDE = {
    "mine": [(455, 330), (400, 352), (350, 380), (330, 398)],
    "station": [(478, 470), (560, 505), (640, 480), (672, 446)],
    "frozen": [(700, 885), (740, 870), (760, 862)],
}
side_paths = {k: resample(meander(catmull(v, int(path_length(v) / 0.3)), 1.2, SEED + 40 + i), 0.3)
              for i, (k, v) in enumerate(SIDE.items())}
d_main, i_main, main_tree = path_field(main)
d_side = np.full((N, N), 1e4)
for sp in side_paths.values():
    d_side = np.minimum(d_side, path_field(sp)[0])
d_track = np.minimum(d_main, d_side)

# Grade the tracks: the profile is smoothed and its gradient capped (cut into rises, built up over
# dips), then the terrain is benched to it, with banks that widen with the depth of the cut or fill.
def grade_limited(profile, step, max_deg):
    g = math.tan(math.radians(max_deg)) * step
    p = profile.copy()
    for _ in range(3):
        for i in range(1, len(p)):
            p[i] = np.clip(p[i], p[i - 1] - g, p[i - 1] + g)
        for i in range(len(p) - 2, -1, -1):
            p[i] = np.clip(p[i], p[i + 1] - g, p[i + 1] + g)
    return p


for path, width, strength, max_deg in [(main, 3.3, 0.95, 12.5)] + [(sp, 2.7, 0.9, 14.0) for sp in side_paths.values()]:
    d_p, i_p, _ = path_field(path)
    raw = np.array([sample(h, x, z) for x, z in path])
    ph = grade_limited(ndimage.gaussian_filter1d(raw, 20, mode="nearest"), 0.3, max_deg)
    ph = ndimage.gaussian_filter1d(ph, 10, mode="nearest")
    delta = np.abs(ph - raw)[i_p]
    w_p = (1 - smoothstep(width, width + 5 + 1.6 * delta, d_p)) * strength * (d_stream > s_hw + 2)
    h = h * (1 - w_p) + ph[i_p] * w_p


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
camp_x, camp_z = float(main[130][0] - 20), float(main[130][1] + 4)
flatten(camp_x, camp_z, 16)
cy = math.degrees(math.atan2(spawn_x - camp_x, spawn_z - camp_z))
landmark("trailhead", "Trailhead Camp", camp_x, camp_z, 12, [
    piece("Tent", 0, 0, 0, 0.02, local=(0, -2, camp_x, camp_z, cy + 180)),
    piece("FireRing", 0, 0, 0, 0.05, local=(-3.5, 2.5, camp_x, camp_z, cy + 180)),
    piece("Crates", 0, 0, 30, 0.0, local=(3.2, 0.5, camp_x, camp_z, cy + 180)),
], discover_radius=1)
flatten(*HUT, 20)
landmark("stone_hut", "Stone Hut", *HUT, 16, [
    piece("StoneHut", HUT[0], HUT[1], 250, 0.15),
    piece("WoodPile", HUT[0] - 6, HUT[1] + 5, 160, 0.05),
    piece("Cairn", HUT[0] - 12, HUT[1] - 8, 0, 0.1),
])
landmark("glacier_tarn", "Glacier Tarn", TARN[0], TARN[1], 50, [], discover_radius=75)
flatten(*SADDLE, 18, 0.7)
landmark("highline_pass", "Highline Pass", *SADDLE, 14, [
    piece("Cairn", SADDLE[0] + 5, SADDLE[1] + 3, 0, 0.1),
    piece("Cairn", SADDLE[0] - 7, SADDLE[1] + 6, 70, 0.1),
    piece("SummitSign", SADDLE[0] + 3, SADDLE[1] - 5, 200, 0.2),
], discover_radius=26)
flatten(*MINE, 24, 0.85)
landmark("silver_mine", "Old Silver Mine", *MINE, 20, [
    piece("MineAdit", MINE[0] - 13, MINE[1] + 2, 270, 0.5, 0.0),
    piece("OreCart", MINE[0] + 2, MINE[1] - 3, 95, 0.05, 0.6),
    piece("Rails", MINE[0] - 2, MINE[1] + 0.5, 95, 0.12, 0.6),
    piece("LogPile", MINE[0] + 8, MINE[1] + 8, 20, 0.05),
])
flatten(*STATION, 16)
landmark("weather_station", "Weather Station", *STATION, 12, [piece("WeatherStation", STATION[0], STATION[1], 40, 0.1)])
landmark("frozen_tarn", "Frozen Tarn", FROZEN[0], FROZEN[1], 22, [], discover_radius=40)
landmark("grey_tooth", "Grey Tooth", 236, 812, 50, [], discover_radius=150)

# Hazards: drifts across the upper track, sheet ice on it, slushy meltwater puddles lower down.
DRIFTS, ICE, SLUSH = [], [], []
for k in range(160, len(main) - 60, 90):
    x, z = main[k]
    hh = sample(h, x, z)
    a = math.degrees(math.atan2(*(main[min(k + 5, len(main) - 1)] - main[k - 5])))
    if hh > 238 and rng.random() < 0.42 and all(math.hypot(x - dx_, z - dz_) > 45 for dx_, dz_, *_ in DRIFTS):
        DRIFTS.append((float(x), float(z), rng.uniform(9, 15), rng.uniform(5, 8), -a + 90))
    elif hh > 205 and rng.random() < 0.18 and all(math.hypot(x - ix, z - iz) > 60 for ix, iz, *_ in ICE):
        ICE.append((float(x), float(z), rng.uniform(5, 8), rng.uniform(3.5, 5), -a))
    elif (90 < hh < 200 and sample(slope0, x, z) < 11 and rng.random() < 0.4 and sample(d_stream, x, z) > 20
          and all(math.hypot(x - ix, z - iz) > 50 for ix, iz, *_ in SLUSH)):
        SLUSH.append((float(x), float(z), rng.uniform(4, 7), rng.uniform(3, 4.5), -a))


# ---------------------------------------------------------------------------- output heights

h = np.clip(h, 1, HEIGHT - 1)
slope = slope_map(h)
np.round(h / HEIGHT * 65535).astype("<u2").tofile(os.path.join(SRC, "alpine_height.r16"))
print(f"Height range {h.min():.1f}..{h.max():.1f} m; saddle {sample(h, *SADDLE):.0f} m, tarn {TARN_LEVEL} m")
track_slopes = np.array([sample(slope, x, z) for x, z in main[::10]])
print(f"Main track slope: mean {track_slopes.mean():.1f}, 95% {np.percentile(track_slopes, 95):.1f}, max {track_slopes.max():.1f} deg")
for L in landmarks:
    print(f"  {L['name']:20s} ({L['x']:.0f}, {L['z']:.0f})  {math.hypot(L['x'] - spawn_x, L['z'] - spawn_z):.0f} m from spawn")


# ---------------------------------------------------------------------------- masks

print("Painting masks...")
gz, gx = np.gradient(h, CELL)
nrm_len = np.sqrt(gx * gx + gz * gz + 1)
north = -gz / nrm_len                                   # normal's +z (north-facing) component
patch = fbm(9, 4, SEED + 20)
fine = fbm(28, 3, SEED + 21)
concave = ndimage.gaussian_filter(h, 6) - h              # hollows hold snow
snowline = 250 + 40 * (patch - 0.5) - 60 * np.clip(north, 0, 1)
snow = smoothstep(snowline - 12, snowline + 12, h) * smoothstep(44, 30, slope)
snow = np.maximum(snow, smoothstep(0.6, 2.2, concave) * smoothstep(175, 230, h) * smoothstep(0.1, 0.4, north + 0.1 * (fine - 0.5)))
# Talus: scree fans below the steep ground, and bare scree high up.
steep_above = ndimage.maximum_filter(smoothstep(30, 42, slope), size=9)
scree = np.clip(steep_above * smoothstep(42, 24, slope) + smoothstep(230, 290, h) * 0.4 * (1 - snow), 0, 1)
scree *= smoothstep(0.3, 0.55, fbm(12, 3, SEED + 22) + 0.25)
scree = np.maximum(scree, (1 - smoothstep(s_hw + 1, s_hw + 5 + 4 * fine, d_stream)) * (d_stream > 0) * 0.85)   # stream cobbles
scree = np.maximum(scree, (1 - smoothstep(0.95, 1.2, rT)) * 0.9)                                            # tarn shore
trackm = 1 - smoothstep(1.8, 3.6, d_track)
snow_on_track = snow * (1 - trackm * 0.85)            # tracks are mostly cleared, drifts come from the hazard map
tundra = np.clip(1 - snow_on_track - scree - trackm, 0.03, 1)
mask = np.stack([tundra, scree * (1 - trackm), snow_on_track, trackm], -1)
mask /= mask.sum(-1, keepdims=True)
M = 1024
mask_img = ndimage.zoom(mask, (M / N, M / N, 1), order=1)
Image.fromarray((np.clip(mask_img[::-1], 0, 1) * 255).round().astype(np.uint8), "RGBA").save(os.path.join(MASKS, "alpine_mask.png"))

# Hazards.
haz_snow = np.zeros((N, N))
for cx, cz, rx, rz, yaw in DRIFTS:
    r = ellipse_r(cx, cz, rx, rz, yaw) * (1 + 0.25 * (fbm(9, 2, SEED + 60 + int(cx)) - 0.5))
    haz_snow = np.maximum(haz_snow, smoothstep(1.15, 0.7, r))
haz_snow = np.maximum(haz_snow, snow * smoothstep(0.5, 0.9, snow) * smoothstep(22, 12, slope) * 0.85 * (1 - trackm))
haz_ice = np.zeros((N, N))
for cx, cz, rx, rz, yaw in ICE:
    r = ellipse_r(cx, cz, rx, rz, yaw) * (1 + 0.3 * (fbm(11, 2, SEED + 70 + int(cz)) - 0.5))
    haz_ice = np.maximum(haz_ice, smoothstep(1.1, 0.8, r))
haz_ice = np.maximum(haz_ice, smoothstep(1.02, 0.9, rF))
haz_slush = np.zeros((N, N))
for cx, cz, rx, rz, yaw in SLUSH:
    r = ellipse_r(cx, cz, rx, rz, yaw) * (1 + 0.25 * (fbm(13, 2, SEED + 80 + int(cx)) - 0.5))
    haz_slush = np.maximum(haz_slush, smoothstep(1.1, 0.75, r))
haz_snow *= 1 - haz_ice
hz = np.stack([haz_snow, np.clip(water_depth / 2.5, 0, 1), haz_ice, haz_slush], -1)
hz_img = ndimage.zoom(hz, (1024 / N, 1024 / N, 1), order=1)
Image.fromarray((np.clip(hz_img[::-1], 0, 1) * 255).round().astype(np.uint8), "RGBA").save(os.path.join(MASKS, "alpine_hazard.png"))

# Physics layers: tundra (soil tyres), scree (gravel), snow (soft, like sand), rock.
rock_phys = smoothstep(0.32, 0.5, 1 - np.cos(np.radians(slope)))
phys = np.stack([(tundra + trackm) * (1 - rock_phys), scree * (1 - rock_phys), snow_on_track * (1 - rock_phys), rock_phys], -1)
phys = phys / (phys.sum(-1, keepdims=True) + 1e-6)
S = 512
splat = ndimage.zoom(phys, (S / N, S / N, 1), order=1)
splat = splat / splat.sum(-1, keepdims=True)
Image.fromarray((splat[::-1] * 255).round().astype(np.uint8), "RGBA").save(os.path.join(SRC, "alpine_splat.png"))


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


def blocked(x, z, track_clear):
    if not (10 < x < SIZE - 10 and 10 < z < SIZE - 10):
        return True
    if sample(d_track, x, z) < track_clear or sample(water_depth, x, z) > 0.05:
        return True
    if sample(foot_r, x, z) < 0.95 or sample(haz_ice, x, z) > 0.1:
        return True
    if math.hypot(x - spawn_x, z - spawn_z) < 12:
        return True
    return any(math.hypot(x - px, z - pz) < pr for px, pz, pr in pads)


def put(kind, variants, x, z, scale, sink, spacing=0.0, track_clear=6.0, max_slope=36, snow_ok=False):
    if blocked(x, z, track_clear) or sample(slope, x, z) > max_slope:
        return False
    if not snow_ok and sample(snow, x, z) > 0.35:
        return False
    if spacing and not solid.ok(x, z, spacing * scale):
        return False
    if spacing:
        solid.add(x, z, spacing * scale)
    props.append({"kind": kind, "variant": int(rng.integers(variants)), "x": round(float(x), 2), "z": round(float(z), 2),
                  "yaw": round(float(rng.uniform(0, 360)), 1), "scale": round(float(scale), 2), "sink": sink})
    return True


# Treeline: scattered firs in the lower valley, thinning and shrinking with height, krummholz above.
trees_w = smoothstep(150, 95, h) * smoothstep(34, 14, slope) * smoothstep(8, 20, d_track) * (water_depth <= 0)
trees_w *= 0.35 + 0.65 * smoothstep(0.35, 0.65, fbm(8, 3, SEED + 90))
fw = (trees_w / trees_w.sum()).ravel()
for c in rng.choice(N * N, size=2600, replace=True, p=fw):
    zi, xi = divmod(int(c), N)
    x, z = xi * CELL + rng.uniform(-1, 1), zi * CELL + rng.uniform(-1, 1)
    hh = sample(h, x, z)
    sc = rng.uniform(0.45, 0.8) * (1.0 - 0.35 * smoothstep(100, 150, hh))
    put("Fir", 3, x, z, sc, 0.3, 4.0, 8.0)
krum_w = smoothstep(110, 150, h) * smoothstep(215, 175, h) * smoothstep(32, 12, slope) * (water_depth <= 0)
kw = (krum_w / krum_w.sum()).ravel()
for c in rng.choice(N * N, size=1800, replace=True, p=kw):
    zi, xi = divmod(int(c), N)
    x, z = xi * CELL + rng.uniform(-2, 2), zi * CELL + rng.uniform(-2, 2)
    put("Krummholz", 2, x, z, rng.uniform(0.7, 1.3), 0.1, 2.2, 4.0, 30)
# Tundra: tussocks everywhere it is green, cushion flowers in drifts.
tw = (tundra * smoothstep(30, 15, slope) * (water_depth < 0.01) * smoothstep(260, 200, h)).ravel()
tw /= tw.sum()
flowers = fbm(16, 2, SEED + 95)
for c in rng.choice(N * N, size=24000, replace=True, p=tw):
    zi, xi = divmod(int(c), N)
    x, z = xi * CELL + rng.uniform(-1, 1), zi * CELL + rng.uniform(-1, 1)
    if sample(flowers, x, z) > 0.6 and rng.random() < 0.45:
        put("Cushion", 1, x, z, rng.uniform(0.7, 1.2), 0.02, track_clear=2.4)
    else:
        put("Tussock", 2, x, z, rng.uniform(0.7, 1.3), 0.03, track_clear=2.4)
# Scree: loose rocks on the talus fans, boulders at their feet and along the stream.
sw_ = (scree * (water_depth <= 0)).ravel()
sw_ /= sw_.sum()
for c in rng.choice(N * N, size=9000, replace=True, p=sw_):
    zi, xi = divmod(int(c), N)
    x, z = xi * CELL + rng.uniform(-1, 1), zi * CELL + rng.uniform(-1, 1)
    if rng.random() < 0.88:
        put("ScreeRock", 3, x, z, rng.uniform(0.5, 1.4), 0.08, track_clear=2.6, max_slope=44, snow_ok=True)
    else:
        put("SBoulder", 4, x, z, rng.uniform(0.5, 1.3), 0.3, 1.4, 4.5, 44, snow_ok=True)
for k in range(0, n_s, 11):
    if rng.random() < 0.5:
        continue
    side = rng.choice([-1, 1]) * (stream_w[k] + rng.uniform(1, 7))
    x, z = stream_point(k / (n_s - 1), side)
    put("SBoulder", 4, x, z, rng.uniform(0.5, 1.2), 0.3, 1.2, 4.0, 40)
for f in formations:
    rx, rz = FOOT[f["model"]]
    for _ in range(int((rx + rz) * f["scale"] * 0.4)):
        a = rng.uniform(0, 2 * math.pi)
        dist = rng.uniform(1.0, 1.7)
        put("SBoulder", 4, f["x"] + math.cos(a) * rx * f["scale"] * dist, f["z"] + math.sin(a) * rz * f["scale"] * dist,
            rng.uniform(0.5, 1.5), 0.4, 1.4, 4.0, 45, snow_ok=True)
# Snow poles marking the pass track above the hut (every ~25 m, alternating sides).
poles = 0
s_acc = 0.0
for k in range(1, len(main)):
    s_acc += 0.3
    x, z = main[k]
    if s_acc < 25 or sample(h, x, z) < 185:
        continue
    s_acc = 0.0
    tx, tz = main[min(k + 3, len(main) - 1)] - main[max(k - 3, 0)]
    ln = math.hypot(tx, tz) or 1
    side = 1 if poles % 2 == 0 else -1
    px, pz = x + tz / ln * 3.6 * side, z - tx / ln * 3.6 * side
    props.append({"kind": "SnowPole", "variant": 0, "x": round(float(px), 2), "z": round(float(pz), 2),
                  "yaw": round(float(rng.uniform(0, 360)), 1), "scale": round(float(rng.uniform(0.95, 1.05)), 2), "sink": 0.25})
    poles += 1

markers = []
for name, sp in side_paths.items():           # signposts where side tracks leave the main track
    if name == "frozen":
        continue
    x0, z0 = sp[min(40, len(sp) - 1)]
    tx_, tz_ = sp[min(60, len(sp) - 1)] - sp[min(20, len(sp) - 1)]
    ln = math.hypot(tx_, tz_) or 1
    markers.append(piece("Signpost", x0 + tz_ / ln * 3.0, z0 - tx_ / ln * 3.0, math.degrees(math.atan2(tx_, tz_)) + 90, 0.1))

with open(os.path.join(SRC, "alpine_scatter.json"), "w") as f_:
    json.dump({"props": props}, f_, separators=(",", ":"))
counts = {}
for p in props:
    counts[p["kind"]] = counts.get(p["kind"], 0) + 1
print("Props:", counts, "formations:", len(formations), "drifts:", len(DRIFTS), "ice:", len(ICE), "slush:", len(SLUSH))


# ---------------------------------------------------------------------------- info

def track_record(name, path, width, step=6):
    pts = path[::step]
    n = len(pts)
    fade = np.ones(n)
    if name != "main":
        s = np.linspace(0, path_length(pts), n)
        fade *= np.clip((s[-1] - s) / 10, 0, 1)
    wet = np.array([sample(water_depth, x, z) for x, z in pts])
    fade *= np.clip(1 - wet / 0.08, 0, 1)
    if name == "frozen":
        fade *= np.clip(1 - np.array([sample(haz_ice, x, z) for x, z in pts]) * 1.5, 0, 1)
    return {"name": name, "width": width, "x": [round(float(x), 2) for x, _ in pts], "z": [round(float(z), 2) for _, z in pts],
            "washboard": [0.0] * n, "fade": [round(float(v), 2) for v in fade]}


sv = stream[::4]
info = {"size": SIZE, "height": HEIGHT, "resolution": N, "splatResolution": S,
        "layers": ["Tundra", "Scree", "Snow", "Rock"],
        "spawn": {"x": round(spawn_x, 2), "z": round(spawn_z, 2), "yaw": round(spawn_heading, 1)},
        "landmarks": landmarks, "markers": markers, "formations": formations,
        "roadX": [round(float(x), 2) for x, _ in main[::6]], "roadZ": [round(float(z), 2) for _, z in main[::6]],
        "tracks": [track_record("main", main, 4.0)] + [track_record(k, sp, 3.2) for k, sp in side_paths.items()],
        "river": {"x": [round(float(x), 2) for x, _ in sv], "z": [round(float(z), 2) for _, z in sv],
                  "halfWidth": [round(float(v), 2) for v in stream_w[::4]],
                  "level": [round(float(v), 3) for v in stream_level[::4]]},
        "lake": {"x": TARN[0], "z": TARN[1], "rx": TARN[2], "rz": TARN[3], "yaw": TARN[4], "level": round(TARN_LEVEL, 3)}}
with open(os.path.join(SRC, "alpine_info.json"), "w") as f_:
    json.dump(info, f_, indent=1)
print("Done.")
