"""High-quality tileable ground and rock textures (1024 px) for the desert biome.

Run:  python tools/art/generate_terrain_textures.py
Writes Assets/Terrain/Textures/<Name>_albedo.png (RGB + height in alpha) and <Name>_normal.png:
  Sand        wind-blown pinkish-orange sand with faint ripples and the odd pebble
  Mud         cracked playa mud: curled plates, deep dark cracks, secondary crazing
  Pavement    desert pavement: packed varnished pebbles in a sandy matrix
  Sandstone   neutral cross-bedded sandstone detail (tinted by the strata palette in the shaders)
  TrackDirt   packed track dirt with pebbles and hairline cracks (dirt track decals)
plus Macro.png (large-scale variation, RGBA).
"""
import math
import os

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.spatial import cKDTree

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(REPO, "Assets", "Terrain", "Textures")
os.makedirs(OUT, exist_ok=True)
T = 1024


def tile_noise(beta, seed, size=T, aniso=(1.0, 1.0), warp=None):
    """Tileable 1/f^beta noise in [0, 1]."""
    r = np.random.default_rng(seed)
    fy = np.fft.fftfreq(size)[:, None] * aniso[1]
    fx = np.fft.fftfreq(size)[None, :] * aniso[0]
    k = np.hypot(fx, fy)
    k[0, 0] = 1
    spec = np.fft.fft2(r.standard_normal((size, size))) / k ** (beta / 2)
    spec[0, 0] = 0
    n = np.real(np.fft.ifft2(spec))
    return (n - n.min()) / (n.max() - n.min())


def band_noise(lo, hi, seed, size=T):
    """Tileable noise containing only wavelengths between size/hi and size/lo pixels."""
    r = np.random.default_rng(seed)
    f = np.fft.fftfreq(size) * size
    k = np.hypot(f[None, :], f[:, None])
    mask = ((k >= lo) & (k <= hi)).astype(float)
    n = np.real(np.fft.ifft2(np.fft.fft2(r.standard_normal((size, size))) * mask))
    return (n - n.min()) / (n.max() - n.min())


def voronoi(cells, seed, size=T, jitter=1.0, warp=0.0):
    """Tileable Voronoi: F1, F2-F1 (edge distance) in pixels, and the cell index.
    warp > 0 bends cell borders with tileable noise (pixels), so shapes look natural."""
    r = np.random.default_rng(seed)
    g = int(math.ceil(math.sqrt(cells)))
    base = (np.stack(np.meshgrid(np.arange(g), np.arange(g)), -1).reshape(-1, 2) + 0.5) / g
    pts = (base + (r.random(base.shape) - 0.5) * jitter / g) % 1.0 * size
    tiled = np.concatenate([pts + (dx * size, dy * size) for dx in (-1, 0, 1) for dy in (-1, 0, 1)])
    ids = np.tile(np.arange(len(pts)), 9)
    yy, xx = np.mgrid[0:size, 0:size].astype(float)
    if warp:
        xx = xx + (band_noise(2, 10, seed + 500, size) - 0.5) * 2 * warp
        yy = yy + (band_noise(2, 10, seed + 501, size) - 0.5) * 2 * warp
    d, i = cKDTree(tiled).query(np.c_[(xx.ravel() + 0.5) % size, (yy.ravel() + 0.5) % size], k=2)
    return d[:, 0].reshape(size, size), (d[:, 1] - d[:, 0]).reshape(size, size), ids[i[:, 0]].reshape(size, size)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def mix(c0, c1, t):
    t = np.asarray(t)[..., None]
    return np.array(c0) * (1 - t) + np.array(c1) * t


def save(name, albedo, height, strength):
    h = (height - height.min()) / (np.ptp(height) + 1e-9)
    rgba = np.concatenate([np.clip(albedo, 0, 1), h[..., None]], -1)
    Image.fromarray((rgba * 255).round().astype(np.uint8), "RGBA").save(os.path.join(OUT, f"{name}_albedo.png"))
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * strength
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * strength
    n = np.stack([-gx, gy, np.ones_like(gx)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    Image.fromarray(((n * 0.5 + 0.5) * 255).round().astype(np.uint8), "RGB").save(os.path.join(OUT, f"{name}_normal.png"))
    print("wrote", name)


yy, xx = np.mgrid[0:T, 0:T] / T

# ---------------------------------------------------------------- Sand (tile = 3.5 m)
# Photo-scanned sand (ambientCG Ground054, CC0) used for its grain and surface relief only: the
# luminance detail is high-passed (so no large blotches repeat) and re-coloured to our palette.
# Wind ripples are not baked in: the terrain shader draws them in world space so they never tile.
SRC = os.path.join(REPO, "tools", "art", "sources", "ambientcg", "Ground054")


def load(name, mode="RGB"):
    im = Image.open(os.path.join(SRC, name)).convert(mode)
    return np.asarray(im.resize((T, T), Image.LANCZOS)).astype(np.float64) / 255


def wrap_blur(a, sigma):
    return ndimage.gaussian_filter(a, sigma, mode="wrap")


photo = load("Ground054_1K_Color.jpg")
lum = photo @ np.array([0.2126, 0.7152, 0.0722])
detail = lum / np.maximum(wrap_blur(lum, 48), 1e-3)                    # ~1.0 on average, grain detail only
detail = 1 + (detail - 1) * 1.35
chroma = photo / np.maximum(lum[..., None], 1e-3)                      # keep the hue of individual grains a little
chroma = chroma / chroma.reshape(-1, 3).mean(0)
tone = band_noise(2, 8, 7)                                             # gentle in-tile variation only
alb = mix((0.76, 0.50, 0.35), (0.84, 0.58, 0.41), tone)
alb = alb * detail[..., None] * (1 + (chroma - 1) * 0.35)
disp = load("Ground054_1K_Displacement.jpg", "L")
disp = disp - wrap_blur(disp, 96) * 0.6                                # flatten the largest lumps (trampled look)
h = (disp - disp.min()) / np.ptp(disp)
rgba = np.concatenate([np.clip(alb, 0, 1), h[..., None]], -1)
Image.fromarray((rgba * 255).round().astype(np.uint8), "RGBA").save(os.path.join(OUT, "Sand_albedo.png"))
nrm = load("Ground054_1K_NormalGL.jpg") * 2 - 1                        # OpenGL convention = Unity's
nrm[..., :2] *= 0.75
nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
Image.fromarray(((nrm * 0.5 + 0.5) * 255).round().astype(np.uint8), "RGB").save(os.path.join(OUT, "Sand_normal.png"))
print("wrote Sand (photo detail)")

# ---------------------------------------------------------------- Track dirt (tile = 3 m)
# Packed, darker dirt for the tracks: the same scanned grain, tighter, with small embedded pebbles,
# hairline cracks and a little loose sand.
f1, edge, cid = voronoi(900, 91, jitter=1.0, warp=3.0)
rr = np.random.default_rng(92)
peb = smoothstep(3.2, 0.8, f1) * (rr.random(cid.max() + 1)[cid] > 0.82)
peb_col = mix((0.30, 0.20, 0.15), (0.62, 0.46, 0.34), rr.random(cid.max() + 1)[cid])
f1c, edgec, _ = voronoi(60, 93, warp=10.0)
cracks = smoothstep(1.4, 0.0, edgec) * smoothstep(0.45, 0.65, band_noise(2, 8, 94))
loose = smoothstep(0.55, 0.8, band_noise(3, 16, 95))
base = mix((0.60, 0.40, 0.28), (0.70, 0.49, 0.35), band_noise(2, 10, 96))
alb = base * (1 + (detail[..., None] - 1) * 0.8)
alb = alb * (1 - loose[..., None] * 0.5) + np.array([0.80, 0.56, 0.40]) * loose[..., None] * 0.5
alb = alb * (1 - cracks[..., None] * 0.35)
alb = alb * (1 - peb[..., None]) + peb_col * peb[..., None]
save("TrackDirt", alb, 0.35 * h + 0.6 * peb - 0.4 * cracks + 0.15 * loose, 6.0)

# ---------------------------------------------------------------- Cracked mud (tile = 4 m)
f1, edge, cid = voronoi(70, 11, jitter=0.9)
f1b, edge2, _ = voronoi(420, 12, jitter=1.0)
crack_w = 2.5 + 3.5 * band_noise(2, 8, 13)
crack = smoothstep(crack_w, 0.0, edge)                                # main cracks
craze = smoothstep(1.4, 0.0, edge2) * (band_noise(2, 6, 14) > 0.55)  # fine crazing inside plates
plate_r = edge / (edge + f1 + 1e-6)                                   # 0 at the crack, ~0.5 in the middle
curl = smoothstep(0.0, 0.12, plate_r) * (1 - 0.6 * smoothstep(0.05, 0.3, plate_r))  # edges curl up
cell_tone = np.random.default_rng(15).random(cid.max() + 1)[cid]
dust = band_noise(4, 40, 16)
alb = mix((0.66, 0.52, 0.40), (0.84, 0.71, 0.57), 0.5 * cell_tone + 0.5 * dust)
alb = alb * (1 - craze[..., None] * 0.25)
alb = alb * (1 - crack[..., None]) + np.array([0.27, 0.17, 0.12]) * crack[..., None]
height = 0.65 + 0.25 * curl - 0.9 * crack - 0.08 * craze + 0.05 * dust
save("Mud", alb, height, 9.0)

# ---------------------------------------------------------------- Desert pavement (tile = 3 m)
# Tightly packed, angular varnished stones with thin sandy gaps.
f1, edge, cid = voronoi(520, 21, jitter=1.0, warp=9.0)
f1s, edges, cids = voronoi(2600, 26, jitter=1.0, warp=4.0)             # small grit between the stones
rr = np.random.default_rng(22)
gap = rr.uniform(1.5, 7.0, cid.max() + 1)[cid]
stone = smoothstep(gap, gap + 4.0, edge) * (rr.random(cid.max() + 1)[cid] > 0.12)
grit = smoothstep(1.0, 3.0, edges) * (np.random.default_rng(27).random(cids.max() + 1)[cids] > 0.55) * (1 - stone)
dome = np.clip(edge / 16.0, 0, 1) ** 0.5                               # rounded tops
varn = rr.random(cid.max() + 1)[cid]
pebble_col = mix((0.27, 0.16, 0.11), (0.66, 0.47, 0.33), varn ** 1.3)  # desert varnish: dark red-brown to tan
pebble_col *= (0.82 + 0.3 * dome)[..., None] * (0.92 + 0.16 * tile_noise(0.5, 25))[..., None]
sand = mix((0.66, 0.45, 0.32), (0.80, 0.58, 0.42), band_noise(3, 30, 23))
alb = sand * (1 - stone[..., None]) + pebble_col * stone[..., None]
alb = alb * (1 - grit[..., None] * 0.35)
save("Pavement", alb, stone * (0.5 + 0.5 * dome) + 0.25 * grit + 0.08 * band_noise(20, 200, 24), 7.0)

# ---------------------------------------------------------------- Sandstone detail (tile = 8 m, neutral)
# Cross-bedded sets of laminations with irregular spacing, joints and granular weathering.
set_id = np.floor(yy * 4 + 0.8 * band_noise(1, 3, 31)).astype(int)
dip = np.random.default_rng(32).uniform(-0.7, 0.7, 64)[set_id % 64]
phase = yy * 34 + xx * dip * 10 + band_noise(2, 6, 33) * 3 + band_noise(6, 20, 38) * 0.6
lam = 0.5 + 0.5 * np.sin(2 * math.pi * phase)
lam = lam ** 3 * band_noise(2, 8, 39)                                  # laminations fade in and out
grain = tile_noise(0.35, 34)
weather = band_noise(2, 12, 35)
blotch = band_noise(1, 5, 40)
f1, edge, cid = voronoi(22, 36, warp=22.0)
jw = 1.0 + 3.0 * band_noise(3, 12, 43)
joints = smoothstep(jw, 0.0, edge) * smoothstep(0.35, 0.6, band_noise(2, 5, 41))   # weathered fractures
holes = band_noise(10, 40, 37)
pits = smoothstep(0.80, 0.9, holes) * smoothstep(0.4, 0.7, band_noise(2, 6, 44))   # irregular tafoni pits
lum = 0.66 + 0.10 * lam + 0.10 * weather + 0.08 * grain + 0.08 * blotch - 0.25 * pits - 0.30 * joints
alb = np.stack([lum * 1.04, lum, lum * 0.95], -1)                      # nearly neutral; shaders apply colour
save("Sandstone", alb, 0.30 * lam + 0.35 * weather + 0.15 * grain - 0.6 * pits - 0.8 * joints, 7.0)

# ---------------------------------------------------------------- Macro variation (512, tile = 256 m)
M = 512
macro = np.stack([band_noise(1, 4, 61, M), band_noise(3, 12, 62, M), band_noise(8, 40, 63, M), band_noise(20, 90, 64, M)], -1)
Image.fromarray((macro * 255).astype(np.uint8), "RGBA").save(os.path.join(OUT, "Macro.png"))
print("wrote Macro")
