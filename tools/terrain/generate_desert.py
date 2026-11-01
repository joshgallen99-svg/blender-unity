"""Generate the desert test region: heightmap, splat map, ground textures and prop scatter.

Run:  python tools/terrain/generate_desert.py
Needs numpy, scipy, pillow.

Outputs (Unity ignores folders ending in "~", the editor setup reads them directly):
  Assets/Terrain/Source~/desert_height.r16   1025x1025 uint16 little-endian, row 0 = south (z=0)
  Assets/Terrain/Source~/desert_splat.png    RGBA weights: R sand, G gravel, B cracked soil, A rock
  Assets/Terrain/Source~/desert_scatter.json props to place (x, z in metres; Unity samples the height)
  Assets/Terrain/Source~/desert_info.json    size, height, spawn point
  Assets/Terrain/Textures/*.png              tileable albedo + normal maps
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
TEX = os.path.join(REPO, "Assets", "Terrain", "Textures")
os.makedirs(SRC, exist_ok=True)
os.makedirs(TEX, exist_ok=True)

N = 1025            # heightmap samples per side
SIZE = 1024.0       # metres
HEIGHT = 160.0      # metres represented by uint16 max
SEED = 7
rng = np.random.default_rng(SEED)

ys, xs = np.mgrid[0:N, 0:N].astype(np.float64) * (SIZE / (N - 1))   # metres; row = z, col = x
cx = cz = SIZE / 2


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def value_noise(freq, seed):
    """Smooth noise in [0,1] with `freq` cells across the map (bicubic upsampled lattice)."""
    r = np.random.default_rng(seed)
    cells = int(freq) + 4
    grid = r.random((cells, cells))
    zoom = (N - 1) / freq
    big = ndimage.zoom(grid, zoom, order=3, mode="reflect")
    off = int(zoom)
    return np.clip(big[off:off + N, off:off + N], 0, 1)


def fbm(freq, octaves, seed, gain=0.5):
    total, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        total = total + amp * value_noise(freq * 2 ** o, seed + o * 101)
        norm += amp
        amp *= gain
    return total / norm


def ridged(freq, octaves, seed):
    return 1.0 - np.abs(fbm(freq, octaves, seed) * 2 - 1)


# ------------------------------------------------------------------------- heightmap
print("Building heightmap...")
dist_spawn = np.hypot(xs - cx, ys - cz)
spawn_mask = smoothstep(70, 170, dist_spawn)                 # 0 near spawn, 1 away

base = 18.0 + 10.0 * fbm(3, 5, SEED)                         # gentle basin floor
hills = 14.0 * (fbm(5, 4, SEED + 1) - 0.5) * spawn_mask       # rolling hills

# Winding dry wash (the main trail) crossing the map and passing near spawn.
t = np.linspace(0, 1, 4000)
path_x = SIZE * (0.5 + 0.18 * np.sin(2 * math.pi * t * 1.15 + 0.4) + 0.06 * np.sin(2 * math.pi * t * 3.3))
path_z = SIZE * (0.06 + 0.88 * t)
tree = cKDTree(np.c_[path_x, path_z])
d_wash, _ = tree.query(np.c_[xs.ravel(), ys.ravel()])
d_wash = d_wash.reshape(N, N)
wash = -6.0 * (1.0 - smoothstep(9.0, 38.0, d_wash)) - 2.5 * np.exp(-(d_wash / 70.0) ** 2)   # flat floor, soft banks
keep_clear = smoothstep(18, 55, d_wash) * spawn_mask           # mesas stay off the trail and spawn


def norm01(a):
    lo, hi = np.percentile(a, 1), np.percentile(a, 99)
    return np.clip((a - lo) / (hi - lo), 0, 1)


# Mesas / buttes: flat tops, two tiers, steep terraced sides.
m = norm01(fbm(3.0, 4, SEED + 4) + 0.25 * fbm(9, 2, SEED + 11))
plateau = smoothstep(0.70, 0.74, m) * keep_clear
tier2 = smoothstep(0.84, 0.865, m) * keep_clear
mesas = 32.0 * plateau + 20.0 * tier2

# Dune field in the south-east quarter.
dmask = smoothstep(0.35, 0.0, np.hypot(xs / SIZE - 0.78, ys / SIZE - 0.25)) * spawn_mask
dunes = (1.5 + 7.0 * dmask) * (0.5 + 0.5 * np.sin((xs * 0.8 + ys * 0.6) / (10.0 + 14 * dmask)
                                                  + 5.0 * fbm(6, 3, SEED + 2))) * fbm(4, 2, SEED + 3) * keep_clear

# Sparse crawling outcrops (ridged fins) in a rocky band west of the trail.
rmask = smoothstep(0.30, 0.05, np.abs(xs / SIZE - 0.22)) * keep_clear
fins = 6.0 * smoothstep(0.86, 0.97, ridged(7, 3, SEED + 5)) * rmask

# Boundary: rising ridges keep the player inside without invisible walls.
edge = np.maximum(np.abs(xs - cx), np.abs(ys - cz)) / (SIZE / 2)
border = 90.0 * smoothstep(0.82, 0.985, edge + 0.08 * (fbm(5, 3, SEED + 6) - 0.5)) * (0.7 + 0.6 * fbm(4, 3, SEED + 7))

h = base + hills + dunes + mesas + fins + wash + border

# Thermal erosion: soften slopes steeper than the talus angle, keep cliffs sharp-ish.
print("Eroding...")
talus = 1.25  # metres per metre (~51 degrees)
for _ in range(40):
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nb = np.roll(np.roll(h, dx, axis=1), dz, axis=0)
        diff = h - nb
        move = np.where(diff > talus, (diff - talus) * 0.25, 0.0)
        h = h - move + np.roll(np.roll(move, -dx, axis=1), -dz, axis=0)
h = ndimage.gaussian_filter(h, 0.7)
h = np.clip(h, 0.5, HEIGHT - 1)

# ------------------------------------------------------------------------- landmarks
print("Placing landmarks...")
CELL = SIZE / (N - 1)


def idx(x, z):
    return (int(np.clip(round(z / CELL), 0, N - 1)), int(np.clip(round(x / CELL), 0, N - 1)))


def sample(arr, x, z):
    return arr[idx(x, z)]


def slope_map(hh):
    gz_, gx_ = np.gradient(hh, CELL)
    return np.degrees(np.arctan(np.hypot(gx_, gz_)))


slope = slope_map(h)

# Spawn on the wash near the centre, facing along it.
i0 = int(np.argmin(np.hypot(path_x - cx, path_z - cz)))
spawn_x, spawn_z = float(path_x[i0]), float(path_z[i0])
j = min(i0 + 25, len(t) - 1)
heading = math.degrees(math.atan2(path_x[j] - spawn_x, path_z[j] - spawn_z))
fwd = np.array([math.sin(math.radians(heading)), math.cos(math.radians(heading))])
right = np.array([fwd[1], -fwd[0]])

landmarks = []


def flatten(x, z, radius, strength=1.0):
    """Blend the ground toward its average height inside a radius (building pads, camp)."""
    global h
    d = np.hypot(xs - x, ys - z)
    inner = d < radius * 0.5
    target = h[inner].mean()
    w = smoothstep(radius, radius * 0.55, d) * strength
    h = h * (1 - w) + target * w


def find_site(dist, bearing, spread=50, max_slope=9, min_wash=45, min_sep=150, radius=20):
    best, best_score = None, 1e9
    for r_ in np.arange(dist - 70, dist + 71, 10):
        for b in np.arange(bearing - spread, bearing + spread + 1, 5):
            x = spawn_x + math.sin(math.radians(b)) * r_
            z = spawn_z + math.cos(math.radians(b)) * r_
            if not (110 < x < SIZE - 110 and 110 < z < SIZE - 110):
                continue
            if sample(d_wash, x, z) < min_wash:
                continue
            if any(math.hypot(x - L["x"], z - L["z"]) < min_sep for L in landmarks):
                continue
            ring = [sample(slope, x + math.cos(a) * radius * f, z + math.sin(a) * radius * f)
                    for a in np.linspace(0, 2 * math.pi, 8, endpoint=False) for f in (0.4, 1.0)]
            ms = float(np.mean(ring))
            if ms > max_slope:
                continue
            score = ms + abs(r_ - dist) * 0.03 + abs(b - bearing) * 0.02
            if score < best_score:
                best, best_score = (float(x), float(z)), score
    if best is None:
        raise SystemExit(f"No site found near {dist} m / {bearing} deg")
    return best


def facing(x, z, tx, tz):
    return math.degrees(math.atan2(tx - x, tz - z))


def piece(model, x, z, yaw, sink=0.0, align=0.0, local=None):
    """local=(ox, oz, landmark_x, landmark_z, landmark_yaw) places relative to a landmark."""
    if local:
        ox, oz, lx, lz, lyaw = local
        a = math.radians(lyaw)
        x = lx + ox * math.cos(a) + oz * math.sin(a)
        z = lz - ox * math.sin(a) + oz * math.cos(a)
        yaw = yaw + lyaw
    return {"model": model, "x": round(x, 2), "z": round(z, 2), "yaw": round(yaw % 360, 1),
            "sink": sink, "align": align}


def landmark(lid, name, x, z, radius, pieces, discover_radius=None):
    landmarks.append({"id": lid, "name": name, "x": round(x, 2), "z": round(z, 2), "radius": radius,
                      "discoverRadius": discover_radius or radius * 2.2, "pieces": pieces})


# Base camp on the bank beside the spawn point.
camp_x, camp_z = (np.array([spawn_x, spawn_z]) + right * 24).tolist()
flatten(camp_x, camp_z, 18)
cy = facing(camp_x, camp_z, spawn_x, spawn_z)
landmark("basecamp", "Base Camp", camp_x, camp_z, 14, [
    piece("Tent", 0, 0, 0, 0.02, local=(0, -2, camp_x, camp_z, cy + 180)),
    piece("FireRing", 0, 0, 0, 0.05, local=(-3.5, 2.5, camp_x, camp_z, cy + 180)),
    piece("Crates", 0, 0, 30, 0.0, local=(3.2, 0.5, camp_x, camp_z, cy + 180)),
    piece("Signpost", 0, 0, 10, 0.1, local=(-1.0, -9.0, camp_x, camp_z, cy + 180)),
], discover_radius=1)

# The Needle's Eye: a big natural arch you can drive through, framed from the trail.
ax, az = find_site(300, (heading + 50) % 360, radius=26, max_slope=10)
flatten(ax, az, 30, 0.6)
landmark("needles_eye", "The Needle's Eye", ax, az, 24, [
    piece("NeedlesEye", ax, az, facing(ax, az, spawn_x, spawn_z) + 90, 0.6, 0.0)])

# Prospector's Well: windmill, tank and shack beside the wash, with an oasis.
wx, wz = find_site(330, (heading + 190) % 360, min_wash=28, radius=24, max_slope=8)
flatten(wx, wz, 26)
wy = facing(wx, wz, spawn_x, spawn_z)
landmark("prospectors_well", "Prospector's Well", wx, wz, 22, [
    piece("Windmill", 0, 0, 0, 0.1, local=(0, 0, wx, wz, wy)),
    piece("WaterTank", 0, 0, 0, 0.05, local=(5.5, -1.5, wx, wz, wy)),
    piece("Shack", 0, 0, 90, 0.05, local=(-10, 5, wx, wz, wy)),
    piece("Crates", 0, 0, -20, 0.0, local=(-6.5, -2.0, wx, wz, wy)),
])

# The Chimneys: a hoodoo field around Balanced Rock.
hx, hz = find_site(380, (heading + 290) % 360, radius=30, max_slope=12, min_wash=60)
landmark("chimneys", "The Chimneys", hx, hz, 70, [piece("BalancedRock", hx, hz, 35, 0.3, 0.0)],
         discover_radius=90)

# Rustbucket: an old pickup half-buried in the dunes.
best = None
for _ in range(400):
    x, z = rng.uniform(0.62, 0.9) * SIZE, rng.uniform(0.12, 0.38) * SIZE
    if sample(slope, x, z) < 7 and sample(d_wash, x, z) > 60 and all(math.hypot(x - L["x"], z - L["z"]) > 150 for L in landmarks):
        best = (float(x), float(z))
        break
rx, rz = best or (SIZE * 0.75, SIZE * 0.25)
landmark("rustbucket", "Rustbucket", rx, rz, 8, [piece("Wreck", rx, rz, float(rng.uniform(0, 360)), 0.4, 0.7)])

# Rock garden: a crawling playground near camp.
gx_, gz_ = find_site(150, (heading + 300) % 360, radius=30, max_slope=11, min_wash=35, min_sep=110)
landmark("rock_garden", "The Rock Garden", gx_, gz_, 32, [], discover_radius=40)

# Re-smooth after pads, then write the heightmap.
h = np.clip(h, 0.5, HEIGHT - 1)
spawn_h = float(sample(h, spawn_x, spawn_z))
np.round(h / HEIGHT * 65535).astype("<u2").tofile(os.path.join(SRC, "desert_height.r16"))
print(f"Height range {h.min():.1f}..{h.max():.1f} m, spawn at {spawn_h:.1f} m")
for L in landmarks:
    print(f"  {L['name']:22s} at ({L['x']:.0f}, {L['z']:.0f}), {math.hypot(L['x'] - spawn_x, L['z'] - spawn_z):.0f} m from spawn")

# ------------------------------------------------------------------------- splat map
print("Painting splat...")
slope = slope_map(h)
curv = ndimage.laplace(ndimage.gaussian_filter(h, 2))
nz = fbm(20, 3, SEED + 8)

rock = smoothstep(30, 42, slope + 8 * (nz - 0.5))
gravel = smoothstep(10, 22, slope) * (1 - rock) + smoothstep(0.55, 0.75, fbm(14, 3, SEED + 9)) * 0.6
soil = smoothstep(0.5, 0.7, fbm(9, 4, SEED + 10)) * (1 - rock) * smoothstep(5, 0, slope)
soil = np.maximum(soil, np.exp(-(d_wash / 14.0) ** 2) * (1 - rock))      # cracked mud in the wash
for L in landmarks:                                                          # packed dirt around camps and the well
    if L["id"] in ("basecamp", "prospectors_well"):
        soil = np.maximum(soil, smoothstep(L["radius"] * 1.3, L["radius"] * 0.5, np.hypot(xs - L["x"], ys - L["z"])))
sand = np.clip(1.0 - rock - gravel - soil, 0, 1) + np.clip(curv * 2, 0, 0.5) * (1 - rock)  # sand pools in hollows
w = np.stack([sand, gravel, soil, rock], axis=-1).clip(0, None) + 1e-4
w = w / w.sum(-1, keepdims=True)
SPLAT = 512
splat = ndimage.zoom(w, (SPLAT / N, SPLAT / N, 1), order=1)
splat = splat / splat.sum(-1, keepdims=True)
# PNG row 0 is the top of the image; store north at top so row index = N-1-z.
Image.fromarray((splat[::-1] * 255).round().astype(np.uint8), "RGBA").save(os.path.join(SRC, "desert_splat.png"))

# ------------------------------------------------------------------------- scatter (clustered)
print("Scattering props in clusters...")
props = []


class Spacing:
    """Grid hash enforcing a minimum distance between solid props."""
    def __init__(self, cell=4.0):
        self.cell, self.grid = cell, {}

    def ok(self, x, z, r):
        cx_, cz_ = int(x // self.cell), int(z // self.cell)
        reach = int(math.ceil(r / self.cell)) + 1
        for i in range(cx_ - reach, cx_ + reach + 1):
            for k in range(cz_ - reach, cz_ + reach + 1):
                for (px, pz, pr) in self.grid.get((i, k), ()):
                    if math.hypot(px - x, pz - z) < max(r, pr):
                        return False
        return True

    def add(self, x, z, r):
        self.grid.setdefault((int(x // self.cell), int(z // self.cell)), []).append((x, z, r))


solid = Spacing()


def blocked(x, z, trail=10.0, margin=1.0):
    if not (15 < x < SIZE - 15 and 15 < z < SIZE - 15):
        return True
    if sample(d_wash, x, z) < trail:
        return True
    if math.hypot(x - spawn_x, z - spawn_z) < 28:
        return True
    return any(math.hypot(x - L["x"], z - L["z"]) < L["radius"] * margin for L in landmarks
               if L["id"] not in ("chimneys", "rock_garden"))


def put(kind, variants, x, z, scale, sink, spacing=0.0, trail=10.0):
    if blocked(x, z, trail):
        return False
    if spacing and not solid.ok(x, z, spacing * scale):
        return False
    if spacing:
        solid.add(x, z, spacing * scale)
    props.append({"kind": kind, "variant": int(rng.integers(variants)), "x": round(float(x), 2),
                  "z": round(float(z), 2), "yaw": round(float(rng.uniform(0, 360)), 1),
                  "scale": round(float(scale), 2), "sink": sink})
    return True


def cluster(cx_, cz_, radius, items, falloff=0.5):
    """items: (kind, variants, count, (smin, smax), sink, spacing)"""
    for kind, variants, count, (s0, s1), sink, spacing in items:
        placed = tries = 0
        while placed < count and tries < count * 30:
            tries += 1
            r = radius * abs(rng.normal(0, falloff))
            if r > radius:
                continue
            a = rng.uniform(0, 2 * math.pi)
            x, z = cx_ + math.cos(a) * r, cz_ + math.sin(a) * r
            if put(kind, variants, x, z, rng.uniform(s0, s1) * (1.15 - 0.3 * r / radius), sink, spacing):
                placed += 1


L = {l["id"]: l for l in landmarks}

# 1. The Chimneys: hoodoo field with rubble.
cluster(L["chimneys"]["x"], L["chimneys"]["z"], 75, [
    ("Hoodoo", 3, 16, (0.8, 1.4), 0.3, 4.5),
    ("Boulder", 6, 45, (0.6, 1.5), 0.25, 1.4),
    ("Rock", 5, 90, (0.6, 1.3), 0.1, 0),
    ("Scrub", 3, 14, (0.7, 1.1), 0.05, 0),
    ("Grass", 2, 40, (0.8, 1.3), 0.02, 0),
], falloff=0.55)

# 2. Rock garden: dense slabs and boulders with drivable gaps.
cluster(L["rock_garden"]["x"], L["rock_garden"]["z"], 34, [
    ("Slab", 3, 30, (0.8, 1.6), 0.15, 1.7),
    ("Boulder", 6, 26, (0.6, 1.3), 0.3, 1.5),
    ("Rock", 5, 50, (0.7, 1.4), 0.1, 0),
], falloff=0.6)

# 3. Talus fans: boulders spilling from the base of cliffs.
steep = slope > 38
dist_cliff = ndimage.distance_transform_edt(~steep) * CELL
cand = np.argwhere((dist_cliff > 2) & (dist_cliff < 20) & (slope < 26))
rng.shuffle(cand)
n_b = n_r = 0
for zi, xi in cand:
    if n_b >= 650 and n_r >= 700:
        break
    dcl = dist_cliff[zi, xi]
    if rng.random() > math.exp(-dcl / 6.0):
        continue
    x, z = xi * CELL + rng.uniform(-0.5, 0.5), zi * CELL + rng.uniform(-0.5, 0.5)
    if n_b < 650 and rng.random() < 0.5:
        n_b += put("Boulder", 6, x, z, rng.uniform(0.9, 2.2) * (1.2 - dcl / 30), 0.3, 1.3)
    elif n_r < 700:
        n_r += put("Rock", 5, x, z, rng.uniform(0.6, 1.5), 0.1)

# 4. Scrub patches where water collects (near the wash, in hollows), plus the oasis at the well.
weight = np.exp(-(d_wash / 90.0) ** 2) * smoothstep(18, 4, slope) * (0.4 + np.clip(curv * 4, 0, 1))
flat_w = (weight / weight.sum()).ravel()
centres = rng.choice(N * N, size=30, replace=False, p=flat_w)
for c in centres:
    zi, xi = divmod(int(c), N)
    cluster(xi * CELL, zi * CELL, rng.uniform(10, 24), [
        ("Scrub", 3, int(rng.integers(6, 22)), (0.7, 1.4), 0.05, 0),
        ("Grass", 2, int(rng.integers(15, 45)), (0.7, 1.3), 0.02, 0),
        ("Yucca", 2, int(rng.integers(0, 4)), (0.8, 1.2), 0.02, 0),
        ("Rock", 5, int(rng.integers(0, 5)), (0.5, 1.0), 0.1, 0),
    ])
well = L["prospectors_well"]
for k in range(10):   # ring of greenery around the well, outside the buildings
    a = rng.uniform(0, 2 * math.pi)
    cluster(well["x"] + math.cos(a) * 30, well["z"] + math.sin(a) * 30, 12, [
        ("Scrub", 3, 8, (0.9, 1.5), 0.05, 0), ("Grass", 2, 20, (0.9, 1.4), 0.02, 0)])

# 5. Yucca stands on gentle slopes away from the wash.
for _ in range(14):
    for _try in range(50):
        x, z = rng.uniform(80, SIZE - 80, 2)
        if 4 < sample(slope, x, z) < 16 and sample(d_wash, x, z) > 50:
            cluster(x, z, rng.uniform(10, 18), [("Yucca", 2, int(rng.integers(5, 12)), (0.8, 1.3), 0.02, 0),
                                                ("Grass", 2, int(rng.integers(5, 15)), (0.8, 1.2), 0.02, 0)])
            break

# 6. Dead trees: small groves on the wash banks, plus lone sentinels.
for _ in range(6):
    k = int(rng.integers(0, len(t)))
    side_ = 1 if rng.random() < 0.5 else -1
    nx_, nz_ = path_z[min(k + 1, len(t) - 1)] - path_z[k], -(path_x[min(k + 1, len(t) - 1)] - path_x[k])
    nl = math.hypot(nx_, nz_) or 1
    cluster(path_x[k] + side_ * nx_ / nl * 22, path_z[k] + side_ * nz_ / nl * 22, 9,
            [("DeadTree", 2, int(rng.integers(2, 5)), (0.8, 1.3), 0.1, 3.0),
             ("Grass", 2, 12, (0.8, 1.2), 0.02, 0)])
for _ in range(8):
    x, z = rng.uniform(80, SIZE - 80, 2)
    put("DeadTree", 2, x, z, rng.uniform(0.9, 1.4), 0.1, 3.0)

# 7. A light sprinkle of small rocks so open ground isn't empty.
for _ in range(500):
    x, z = rng.uniform(20, SIZE - 20, 2)
    if rng.random() < 0.6:
        put("Rock", 5, x, z, rng.uniform(0.4, 0.9), 0.08)

# Cairns marking the trail every ~90 m, plus a pair at each end of the rock garden.
markers = []
dist_acc, last = 0.0, (path_x[0], path_z[0])
for k in range(1, len(t)):
    dist_acc += math.hypot(path_x[k] - last[0], path_z[k] - last[1])
    last = (path_x[k], path_z[k])
    if dist_acc > 90 and 60 < path_x[k] < SIZE - 60 and 60 < path_z[k] < SIZE - 60:
        dist_acc = 0.0
        nx_, nz_ = path_z[min(k + 1, len(t) - 1)] - path_z[k], -(path_x[min(k + 1, len(t) - 1)] - path_x[k])
        nl = math.hypot(nx_, nz_) or 1
        markers.append(piece("Cairn", path_x[k] + nx_ / nl * 11, path_z[k] + nz_ / nl * 11, float(rng.uniform(0, 360)), 0.05))
rg = L["rock_garden"]
for a in (0, math.pi):
    markers.append(piece("Cairn", rg["x"] + math.cos(a) * 38, rg["z"] + math.sin(a) * 38, 0, 0.05))

with open(os.path.join(SRC, "desert_scatter.json"), "w") as f:
    json.dump({"props": props}, f, separators=(",", ":"))
counts = {}
for p in props:
    counts[p["kind"]] = counts.get(p["kind"], 0) + 1
print("Props:", counts, "markers:", len(markers))

info = {"size": SIZE, "height": HEIGHT, "resolution": N, "splatResolution": SPLAT,
        "layers": ["Sand", "Gravel", "CrackedSoil", "RedRock"],
        "spawn": {"x": round(spawn_x, 2), "z": round(spawn_z, 2), "yaw": round(heading, 1)},
        "landmarks": landmarks, "markers": markers}
with open(os.path.join(SRC, "desert_info.json"), "w") as f:
    json.dump(info, f, indent=2)


# ------------------------------------------------------------------------- textures
print("Generating ground textures...")
T = 512


def tile_noise(beta, seed, size=T):
    """Perfectly tileable 1/f^beta noise in [0,1] via FFT filtering."""
    r = np.random.default_rng(seed)
    f = np.fft.fftfreq(size)
    fx, fy = np.meshgrid(f, f)
    k = np.hypot(fx, fy)
    k[0, 0] = 1
    spec = np.fft.fft2(r.standard_normal((size, size))) / k ** (beta / 2)
    spec[0, 0] = 0
    n = np.real(np.fft.ifft2(spec))
    return (n - n.min()) / (n.max() - n.min())


def voronoi(cells, seed, size=T):
    """Tileable Voronoi: (F1 distance, F2-F1 edge distance) in pixels."""
    r = np.random.default_rng(seed)
    pts = r.random((cells, 2)) * size
    tiled = np.concatenate([pts + (dx * size, dy * size) for dx in (-1, 0, 1) for dy in (-1, 0, 1)])
    yy, xx = np.mgrid[0:size, 0:size]
    d, _ = cKDTree(tiled).query(np.c_[xx.ravel(), yy.ravel()], k=2)
    return d[:, 0].reshape(size, size), (d[:, 1] - d[:, 0]).reshape(size, size)


def colorize(t, c0, c1):
    t = t[..., None]
    return np.array(c0) * (1 - t) + np.array(c1) * t


def save_maps(name, albedo, height, strength):
    a = np.clip(albedo, 0, 1)
    Image.fromarray((a * 255).astype(np.uint8), "RGB").save(os.path.join(TEX, f"{name}_albedo.png"))
    gx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) * strength
    gy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) * strength
    n = np.stack([-gx, gy, np.ones_like(gx)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    Image.fromarray(((n * 0.5 + 0.5) * 255).astype(np.uint8), "RGB").save(os.path.join(TEX, f"{name}_normal.png"))


# Sand: warm orange with wind ripples.
yy, xx = np.mgrid[0:T, 0:T] / T
warp = tile_noise(2.5, 1)
ripples = 0.5 + 0.5 * np.sin(2 * math.pi * (yy * 9 + xx * 2 + warp * 3.0))
grain = tile_noise(0.6, 2)
save_maps("Sand", colorize(0.62 * tile_noise(2.0, 3) + 0.10 * ripples + 0.28 * grain,
                           (0.62, 0.45, 0.33), (0.80, 0.63, 0.47)), ripples * 0.35 + grain * 0.65, 2.5)

# Gravel: pebbles in a dusty matrix.
f1, edge = voronoi(260, 4)
peb = smoothstep(9, 2, f1)
tone = tile_noise(1.0, 5)
alb = colorize(tone, (0.42, 0.31, 0.24), (0.62, 0.48, 0.38)) * (0.75 + 0.35 * peb[..., None])
save_maps("Gravel", alb, peb * 0.8 + tile_noise(0.8, 6) * 0.2, 5.0)

# Cracked soil: dried mud plates.
f1, edge = voronoi(70, 7)
crack = smoothstep(0, 3.5, edge)
plate = tile_noise(1.5, 8)
alb = colorize(plate, (0.62, 0.44, 0.31), (0.78, 0.60, 0.45)) * (0.45 + 0.55 * crack[..., None])
save_maps("CrackedSoil", alb, crack * 0.9 + plate * 0.1, 7.0)

# Red rock: sandstone strata and fractures.
warp = tile_noise(3.0, 9)
strata = 0.5 + 0.5 * np.sin(2 * math.pi * (yy * 9 + warp * 1.5))
frac = smoothstep(0, 2.5, voronoi(40, 10)[1])
detail = tile_noise(0.9, 11)
alb = colorize(0.5 * strata + 0.3 * detail + 0.2 * tile_noise(2.0, 12), (0.42, 0.18, 0.11), (0.70, 0.38, 0.24))
alb *= (0.6 + 0.4 * frac[..., None])
save_maps("RedRock", alb, strata * 0.4 + detail * 0.3 + frac * 0.3, 8.0)
print("Done.")
