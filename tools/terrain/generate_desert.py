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

spawn_h = float(h[int(cz), int(cx)])
np.round(h / HEIGHT * 65535).astype("<u2").tofile(os.path.join(SRC, "desert_height.r16"))
print(f"Height range {h.min():.1f}..{h.max():.1f} m, spawn at {spawn_h:.1f} m")

# ------------------------------------------------------------------------- splat map
print("Painting splat...")
gz, gx = np.gradient(h, SIZE / (N - 1))
slope = np.degrees(np.arctan(np.hypot(gx, gz)))
curv = ndimage.laplace(ndimage.gaussian_filter(h, 2))
nz = fbm(20, 3, SEED + 8)

rock = smoothstep(30, 42, slope + 8 * (nz - 0.5))
gravel = smoothstep(10, 22, slope) * (1 - rock) + smoothstep(0.55, 0.75, fbm(14, 3, SEED + 9)) * 0.6
soil = smoothstep(0.5, 0.7, fbm(9, 4, SEED + 10)) * (1 - rock) * smoothstep(5, 0, slope)
soil = np.maximum(soil, np.exp(-(d_wash / 14.0) ** 2) * (1 - rock))      # cracked mud in the wash
sand = np.clip(1.0 - rock - gravel - soil, 0, 1) + np.clip(curv * 2, 0, 0.5) * (1 - rock)  # sand pools in hollows
w = np.stack([sand, gravel, soil, rock], axis=-1).clip(0, None) + 1e-4
w = w / w.sum(-1, keepdims=True)
SPLAT = 512
splat = ndimage.zoom(w, (SPLAT / N, SPLAT / N, 1), order=1)
splat = splat / splat.sum(-1, keepdims=True)
# PNG row 0 is the top of the image; store north at top so row index = N-1-z.
Image.fromarray((splat[::-1] * 255).round().astype(np.uint8), "RGBA").save(os.path.join(SRC, "desert_splat.png"))

# ------------------------------------------------------------------------- scatter
print("Scattering props...")
props = []


def sample(arr, x, z):
    return arr[int(round(z / SIZE * (N - 1))), int(round(x / SIZE * (N - 1)))]


def scatter(kind, variants, count, accept, scale=(0.8, 1.4), sink=0.15, min_spacing=0.0):
    placed = []
    tries = 0
    while len(placed) < count and tries < count * 40:
        tries += 1
        x, z = rng.uniform(20, SIZE - 20, 2)
        p = accept(x, z)
        if rng.random() > p:
            continue
        if min_spacing and placed and np.min(np.hypot(*(np.array(placed) - (x, z)).T)) < min_spacing:
            continue
        placed.append((x, z))
        props.append({"kind": kind, "variant": int(rng.integers(variants)), "x": round(float(x), 2),
                      "z": round(float(z), 2), "yaw": round(float(rng.uniform(0, 360)), 1),
                      "scale": round(float(rng.uniform(*scale)), 2), "sink": sink})


def not_on_route(x, z):
    return smoothstep(6, 16, sample(d_wash, x, z)) * smoothstep(25, 45, math.hypot(x - cx, z - cz))


scatter("Boulder", 5, 900, lambda x, z: (0.15 + 0.85 * smoothstep(22, 40, sample(slope, x, z))) * not_on_route(x, z),
        (0.8, 2.6), 0.35, 4)
scatter("Rock", 5, 1400, lambda x, z: 0.5 * not_on_route(x, z) + 0.2, (0.5, 1.3), 0.12)
scatter("Scrub", 3, 1800, lambda x, z: smoothstep(25, 5, sample(slope, x, z)) *
        (0.3 + 0.7 * np.exp(-(sample(d_wash, x, z) / 70) ** 2)) * not_on_route(x, z), (0.7, 1.4), 0.05)
scatter("Yucca", 2, 350, lambda x, z: smoothstep(20, 5, sample(slope, x, z)) * 0.6 * not_on_route(x, z), (0.8, 1.3), 0.02)
scatter("DeadTree", 2, 120, lambda x, z: smoothstep(15, 3, sample(slope, x, z)) *
        np.exp(-(sample(d_wash, x, z) / 40) ** 2) * not_on_route(x, z), (0.8, 1.3), 0.1, 12)

with open(os.path.join(SRC, "desert_scatter.json"), "w") as f:
    json.dump({"props": props}, f, separators=(",", ":"))
counts = {}
for p in props:
    counts[p["kind"]] = counts.get(p["kind"], 0) + 1
print("Props:", counts)

# Spawn: just off the wash near the centre, facing north along it.
i = int(np.argmin(np.hypot(path_x - cx, path_z - cz)))
sx_, sz_ = float(path_x[i]), float(path_z[i])
heading = math.degrees(math.atan2(path_x[min(i + 20, len(t) - 1)] - sx_, path_z[min(i + 20, len(t) - 1)] - sz_))
info = {"size": SIZE, "height": HEIGHT, "resolution": N, "splatResolution": SPLAT,
        "layers": ["Sand", "Gravel", "CrackedSoil", "RedRock"],
        "spawn": {"x": round(sx_, 2), "z": round(sz_, 2), "yaw": round(heading, 1)}}
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
