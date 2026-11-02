"""High alpine pass textures: snow, scree, tundra grass, dark mountain rock and a gravel track.

Run:  python tools/art/generate_alpine_textures.py
Writes Assets/Terrain/Textures/<Name>_albedo.png (RGB + height in alpha) and <Name>_normal.png:
  Snow          wind-packed snow: soft lumps, sastrugi ripples, faint grain (procedural)
  Scree         angular, lichen-flecked rock fragments with grit between them (procedural + Rock030 detail)
  AlpineGrass   short tundra turf, straw and olive with stones showing through (Ground037 + scree)
  AlpineRock    dark, cool gneiss with rusty staining in the cracks (Rock030)
  AlpineTrack   grey gravelly dirt for the pass track (Ground048 + Gravel021)
Photo sources are CC0 1.0 (https://ambientcg.com); see docs/art-direction.md.
"""
import os

import numpy as np
from PIL import Image
from scipy import ndimage

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(REPO, "tools", "art", "sources", "ambientcg")
TERRAIN = os.path.join(REPO, "Assets", "Terrain", "Textures")
os.makedirs(TERRAIN, exist_ok=True)
T = 1024


def load(name, mode="RGB", size=T):
    folder = name.split("_")[0]
    im = Image.open(os.path.join(SRC, folder, name)).convert(mode)
    return np.asarray(im.resize((size, size), Image.LANCZOS)).astype(np.float64) / 255


def blur(a, sigma):
    return ndimage.gaussian_filter(a, sigma if a.ndim == 2 else (sigma, sigma, 0), mode="wrap")


def lum(rgb):
    return rgb @ np.array([0.2126, 0.7152, 0.0722])


def norm01(a):
    return (a - a.min()) / (np.ptp(a) + 1e-9)


def flatten_lowfreq(rgb, sigma=96, amount=0.6):
    low = blur(rgb, sigma)
    return rgb / np.maximum(low, 1e-3) * (low * (1 - amount) + low.reshape(-1, 3).mean(0) * amount)


def normal_from_height(h, strength):
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * strength
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * strength
    n = np.stack([-gx, gy, np.ones_like(gx)], -1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


def gl_normal(name, flat=1.0, size=T):
    n = load(name, size=size) * 2 - 1
    n[..., :2] *= flat
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


# Target mean brightness (sRGB) per texture, so the region sits in the same exposure range as the
# others: snow a little under paper-white, rock and turf mid-dark, like the forest's granite and meadow.
TARGET = {"Snow": 0.81, "Scree": 0.45, "AlpineGrass": 0.42, "AlpineRock": 0.44, "AlpineTrack": 0.45}


def save(name, albedo, height, normal):
    if name in TARGET:
        albedo = albedo * (TARGET[name] / max(float(np.clip(albedo, 0, 1).mean()), 1e-3))
    h = norm01(height)
    rgba = np.concatenate([np.clip(albedo, 0, 1), h[..., None]], -1)
    Image.fromarray((rgba * 255).round().astype(np.uint8), "RGBA").save(os.path.join(TERRAIN, f"{name}_albedo.png"))
    Image.fromarray(((normal * 0.5 + 0.5) * 255).round().astype(np.uint8), "RGB").save(os.path.join(TERRAIN, f"{name}_normal.png"))
    print("wrote", name)


def tile_noise(size, beta, seed, stretch=(1.0, 1.0)):
    """Tileable 1/f^beta noise; `stretch` squashes frequencies along x/y (anisotropic ripples)."""
    r = np.random.default_rng(seed)
    f = np.fft.fftfreq(size)
    k = np.hypot(f[None, :] * stretch[0], f[:, None] * stretch[1])
    k[0, 0] = 1
    spec = np.fft.fft2(r.standard_normal((size, size))) / k ** (beta / 2)
    spec[0, 0] = 0
    return norm01(np.real(np.fft.ifft2(spec)))


def voronoi(size, cells, seed, jitter=0.9):
    """Tileable Voronoi: (d1, d2, cell id, points) per pixel, distances in pixels."""
    from scipy.spatial import cKDTree
    r = np.random.default_rng(seed)
    g = size / cells
    pts = (np.stack(np.meshgrid(np.arange(cells), np.arange(cells), indexing="ij"), -1).reshape(-1, 2) + 0.5
           + r.uniform(-jitter / 2, jitter / 2, (cells * cells, 2))) * g
    pts = np.mod(pts, size)
    ys, xs = np.mgrid[0:size, 0:size].astype(np.float64)
    tree = cKDTree(pts, boxsize=size)
    d, i = tree.query(np.c_[ys.ravel(), xs.ravel()], k=2)
    return d[:, 0].reshape(size, size), d[:, 1].reshape(size, size), i[:, 0].reshape(size, size), pts


rock_detail = lum(flatten_lowfreq(load("Rock030_1K_Color.jpg"), 128, 0.6))
rock_detail = rock_detail / rock_detail.mean()

# ---------------------------------------------------------------- snow (tile 5 m)
lumps = tile_noise(T, 3.6, 301)
ripples = tile_noise(T, 3.0, 302, stretch=(0.45, 1.3))              # sastrugi: soft ridges across the wind
grain = tile_noise(T, 1.2, 303)
sh = lumps * 0.7 + ripples * 0.24 + grain * 0.06
low = 1 - norm01(blur(sh, 6))
snow = np.array([0.90, 0.93, 0.97]) * (0.94 + 0.06 * sh[..., None])
snow = snow * (1 - 0.06 * low[..., None]) + np.array([-0.03, -0.01, 0.02]) * low[..., None]   # bluer hollows
specks = (tile_noise(T, 0.8, 304) > 0.83) * (tile_noise(T, 2.5, 305) > 0.6)                    # old snow: faint grit
snow = snow * (1 - 0.06 * blur(specks.astype(float), 0.7)[..., None])
save("Snow", snow, sh, normal_from_height(blur(sh, 1.5), 7.0))

# ---------------------------------------------------------------- scree (tile 3 m)
ys, xs = np.mgrid[0:T, 0:T].astype(np.float64)


def rubble(cells, seed, keep, gap_px, height):
    """Loose angular stones: Voronoi cells shrunk apart, pyramid-faceted and tilted at random."""
    d1, d2, cid, pts = voronoi(T, cells, seed, 1.0)
    r = np.random.default_rng(seed + 1)
    n = len(pts)
    g = T / cells
    alive = (r.random(n) < keep)[cid]
    cy, cx = pts[cid, 0], pts[cid, 1]
    dy = (ys - cy + T / 2) % T - T / 2
    dx = (xs - cx + T / 2) % T - T / 2
    tilt = r.normal(0, 0.45, (n, 2))[cid]
    bd = (d2 - d1) / 2                                         # distance to the cell boundary
    body = np.clip((bd - gap_px) / (g * 0.35), 0, 1)
    h = (body ** 0.55 + (tilt[..., 0] * dx + tilt[..., 1] * dy) / g * body) * alive * (bd > gap_px)
    tone = r.uniform(0.72, 1.12, n)[cid]
    hue = r.uniform(-0.04, 0.04, n)[cid]
    return np.clip(h, 0, 1.4) * height, tone, hue, alive & (bd > gap_px)


big_h, big_t, big_c, big_m = rubble(9, 311, 0.8, 4.0, 1.0)
sm_h, sm_t, sm_c, sm_m = rubble(26, 313, 0.9, 2.5, 0.42)
use_big = big_h > sm_h
sh = np.where(use_big, big_h, sm_h)
tone = np.where(use_big, big_t, sm_t)
hue = np.where(use_big, big_c, sm_c)
solid = big_m | sm_m
sh = sh + 0.04 * rock_detail
base = np.array([0.44, 0.43, 0.42])
sc = base * (tone[..., None] + hue[..., None] * np.array([1, 0.2, -1]))
sc = sc * (0.72 + 0.28 * rock_detail[..., None])
sc = sc * (0.78 + 0.22 * np.clip(sh / 0.6, 0, 1))[..., None]                                    # darker low edges
grit = np.array([0.24, 0.23, 0.21]) * (0.75 + 0.5 * tile_noise(T, 1.4, 315))[..., None]
sc = np.where(solid[..., None], sc, grit)
lichen = (tile_noise(T, 2.2, 316) > 0.74) & solid & (sh > 0.3)                                 # pale green-grey lichen
lichen2 = (tile_noise(T, 2.0, 317) > 0.82) & solid & (sh > 0.4)                                # orange crust lichen
sc = np.where(lichen[..., None], sc * 0.55 + np.array([0.55, 0.57, 0.47]) * 0.45, sc)
sc = np.where(lichen2[..., None], sc * 0.6 + np.array([0.62, 0.40, 0.16]) * 0.4, sc)
scree_albedo, scree_h = sc, sh
save("Scree", sc, sh, normal_from_height(blur(sh, 0.7), 9.0))

# ---------------------------------------------------------------- alpine grass / tundra (tile 4 m)
fl = flatten_lowfreq(load("Ground037_1K_Color.jpg"), 96, 0.5)
fh = load("Ground037_1K_Displacement.jpg", "L")
L = norm01(blur(lum(fl), 0.6))
dark, mid, light = np.array([0.14, 0.12, 0.07]), np.array([0.36, 0.33, 0.18]), np.array([0.62, 0.55, 0.36])
gr = np.where((L < 0.5)[..., None], dark + (mid - dark) * (L / 0.5)[..., None], mid + (light - mid) * ((L - 0.5) / 0.5)[..., None])
greenish = tile_noise(T, 2.8, 321)
gr = gr * (1 + np.array([-0.12, 0.08, -0.14]) * (greenish[..., None] - 0.5) * 2)
straw = np.clip((tile_noise(T, 3.0, 323) - 0.45) * 3, 0, 1)[..., None]
gr = gr * (1 - 0.5 * straw) + lum(gr)[..., None] * np.array([1.25, 1.1, 0.7]) * 0.5 * straw
stones = np.clip((tile_noise(T, 2.6, 322) - 0.66) * 6, 0, 1) * np.clip(scree_h * 3, 0, 1)
gr = gr * (1 - stones[..., None]) + scree_albedo * stones[..., None]
gh = fh * 0.6 + scree_h * stones * 0.6
save("AlpineGrass", gr, gh, normal_from_height(blur(gh, 0.7), 6.0) * 0.5 + gl_normal("Ground037_1K_NormalGL.jpg", 0.6) * 0.5)

# ---------------------------------------------------------------- alpine rock (tile 8 m)
ar = flatten_lowfreq(load("Rock030_1K_Color.jpg"), 128, 0.55)
al = lum(ar)[..., None]
ar = al * np.array([0.92, 0.93, 0.97]) * 0.75 + ar * 0.25 * 0.8
ah = load("Rock030_1K_Displacement.jpg", "L")
crack = np.clip((0.35 - ah) * 4, 0, 1)[..., None]
ar = ar * (1 - 0.35 * crack) + np.array([0.30, 0.16, 0.08]) * 0.35 * crack * (tile_noise(T, 2.0, 331) > 0.45)[..., None]
save("AlpineRock", ar, ah, gl_normal("Rock030_1K_NormalGL.jpg"))

# ---------------------------------------------------------------- pass track: grey gravelly dirt (tile 3 m)
so = flatten_lowfreq(load("Ground048_1K_Color.jpg"), 96, 0.6)
sl = lum(so)[..., None]
so = sl * np.array([1.0, 0.97, 0.92]) * 1.35
gv = load("Gravel021_1K_Color.jpg", size=T // 2)
gv = np.tile(gv, (2, 2, 1))
gvh = np.tile(load("Gravel021_1K_Displacement.jpg", "L", size=T // 2), (2, 2))
gvl = lum(gv)[..., None] * np.array([0.96, 0.96, 0.95]) * 1.5
mix = np.clip((gvh - 0.35) * 3, 0, 1)[..., None] * (0.55 + 0.45 * tile_noise(T, 2.5, 341))[..., None]
tr = so * (1 - mix) + gvl * mix
th = blur(lum(so), 1.0) * 0.4 + gvh * 0.6
save("AlpineTrack", tr, th, normal_from_height(blur(th, 0.7), 6.0))
