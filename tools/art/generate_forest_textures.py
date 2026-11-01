"""Forest river valley textures: ground layers from CC0 photo scans (ambientCG) plus painted foliage.

Run:  python tools/art/generate_forest_textures.py
Writes Assets/Terrain/Textures/<Name>_albedo.png (RGB + height in alpha) and <Name>_normal.png:
  ForestFloor   moss, needles, twigs and leaf litter (Ground037)
  ForestSoil    dark humus / forest track soil (Ground048)
  ForestMud     the same soil, wet and smeared
  Granite       grey granite with pale veins (Rock030), slightly cooled
  RiverGravel   rounded river stones (Gravel021), lightened and warmed
  Meadow        greener, fuller moss-and-grass ground for clearings
plus Assets/Art/Textures/Materials/BarkFir_{albedo,normal}.png (Bark001, recoloured)
and Assets/Art/Textures/Foliage/{FirBranch,Fern,MeadowGrass,Wildflowers}.png (painted, alpha-cut).
All photo sources are CC0 1.0 (https://ambientcg.com); see docs/art-direction.md.
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(REPO, "tools", "art", "sources", "ambientcg")
TERRAIN = os.path.join(REPO, "Assets", "Terrain", "Textures")
MATS = os.path.join(REPO, "Assets", "Art", "Textures", "Materials")
FOLIAGE = os.path.join(REPO, "Assets", "Art", "Textures", "Foliage")
for d in (TERRAIN, MATS, FOLIAGE):
    os.makedirs(d, exist_ok=True)
T = 1024


def load(name, mode="RGB"):
    folder = name.split("_")[0]
    im = Image.open(os.path.join(SRC, folder, name)).convert(mode)
    return np.asarray(im.resize((T, T), Image.LANCZOS)).astype(np.float64) / 255


def blur(a, sigma):
    return ndimage.gaussian_filter(a, sigma if a.ndim == 2 else (sigma, sigma, 0), mode="wrap")


def lum(rgb):
    return rgb @ np.array([0.2126, 0.7152, 0.0722])


def flatten_lowfreq(rgb, sigma=96, amount=0.6):
    """Remove part of the large-scale blotchiness so tiles don't show (macro variation is in the shader)."""
    low = blur(rgb, sigma)
    return rgb / np.maximum(low, 1e-3) * (low * (1 - amount) + low.reshape(-1, 3).mean(0) * amount)


def normal_from_height(h, strength):
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * strength
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * strength
    n = np.stack([-gx, gy, np.ones_like(gx)], -1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


def save(name, albedo, height, normal, folder=TERRAIN):
    h = (height - height.min()) / (np.ptp(height) + 1e-9)
    rgba = np.concatenate([np.clip(albedo, 0, 1), h[..., None]], -1)
    Image.fromarray((rgba * 255).round().astype(np.uint8), "RGBA").save(os.path.join(folder, f"{name}_albedo.png"))
    Image.fromarray(((normal * 0.5 + 0.5) * 255).round().astype(np.uint8), "RGB").save(os.path.join(folder, f"{name}_normal.png"))
    print("wrote", name)


def gl_normal(name, flat=1.0):
    n = load(name) * 2 - 1
    n[..., :2] *= flat
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


# ---------------------------------------------------------------- forest floor (tile 4 m)
floor = flatten_lowfreq(load("Ground037_1K_Color.jpg"), 96, 0.5)
floor_h = load("Ground037_1K_Displacement.jpg", "L")
save("ForestFloor", floor * np.array([0.97, 1.0, 0.95]), floor_h, gl_normal("Ground037_1K_NormalGL.jpg"))

# ---------------------------------------------------------------- meadow: greener and fuller
mg = floor.copy()
moss = np.clip((mg[..., 1] - mg[..., 0]) * 6, 0, 1)             # where the scan is mossy
green = np.array([0.36, 0.45, 0.17])
mg = mg * (1 - 0.45 * (1 - moss[..., None])) + green * 0.45 * (1 - moss[..., None])
mg = mg * np.array([0.97, 1.0, 0.88])
mg = lum(mg)[..., None] * 0.22 + mg * 0.78                           # a little less saturated
save("Meadow", mg, floor_h * 0.6 + 0.4 * blur(floor_h, 3), gl_normal("Ground037_1K_NormalGL.jpg", 0.7))

# ---------------------------------------------------------------- soil (tile 3 m) and wet mud
soil = flatten_lowfreq(load("Ground048_1K_Color.jpg"), 96, 0.5)
soil_h = blur(lum(soil), 1.0)
soil_n = gl_normal("Ground048_1K_NormalGL.jpg")
save("ForestSoil", soil * np.array([1.02, 1.0, 0.97]), soil_h, soil_n)
mud = blur(soil, 2.5) * 0.55 + soil * 0.15                            # smeared and dark
mud = mud * np.array([0.92, 0.9, 0.86])
mud_h = blur(soil_h, 4)
save("ForestMud", mud, mud_h, normal_from_height(mud_h, 4.0))

# ---------------------------------------------------------------- granite (tile 6 m)
gr = flatten_lowfreq(load("Rock030_1K_Color.jpg"), 128, 0.5)
gl = lum(gr)[..., None]
gr = gl * np.array([0.98, 1.0, 1.03]) * 0.55 + gr * 0.45             # cooler, less brown
gr = gr * 1.25
save("Granite", gr, load("Rock030_1K_Displacement.jpg", "L"), gl_normal("Rock030_1K_NormalGL.jpg"))

# ---------------------------------------------------------------- river gravel (tile 2.5 m)
gv = load("Gravel021_1K_Color.jpg")
gv_l = lum(gv)[..., None]
gv = (gv_l * np.array([1.08, 1.0, 0.9]) * 0.7 + gv * 0.3) * 1.6      # pale, warm river stones
gv_h = load("Gravel021_1K_Displacement.jpg", "L")
silt = np.array([0.42, 0.39, 0.33]) * (0.9 + 0.2 * blur(gv_h, 6)[..., None])
gap = np.clip(1 - (gv_h - 0.08) / 0.18, 0, 1)[..., None] ** 1.5      # sandy silt between the stones
gv = gv * (1 - gap * 0.7) + silt * gap * 0.7
save("RiverGravel", np.clip(gv, 0, 1), gv_h, normal_from_height(gv_h, 6.0))

# ---------------------------------------------------------------- fir bark (material texture)
bk = load("Bark001_1K_Color.jpg")
bl = lum(bk)[..., None]
bk = bl * np.array([0.98, 0.76, 0.62]) * 0.95                          # grey-brown fir bark, red in the furrows
bk = bk * (1 + 0.25 * (1 - np.clip(bl / bl.mean(), 0, 1.5)) * np.array([0.25, 0.0, -0.1]))
bk_n = gl_normal("Bark001_1K_NormalGL.jpg")
save("BarkFir", bk, lum(bk), bk_n, MATS)


# ---------------------------------------------------------------- foliage sprites (512, alpha-cut)
S = 512
SS = 2


def finish(img, name):
    img = img.resize((S, S), Image.LANCZOS)
    a = np.asarray(img).astype(np.float32)
    rgb, alpha = a[..., :3], a[..., 3:4] / 255.0
    mean = (rgb * alpha).sum((0, 1)) / max(alpha.sum(), 1)
    blurred = np.asarray(Image.fromarray(a.astype(np.uint8)).filter(ImageFilter.GaussianBlur(6))).astype(np.float32)
    fill = np.where(blurred[..., 3:4] > 5, blurred[..., :3] / np.maximum(blurred[..., 3:4] / 255.0, 1e-3), mean)
    rgb = rgb * alpha + np.clip(fill, 0, 255) * (1 - alpha)
    out = np.concatenate([rgb, alpha * 255], -1).clip(0, 255).astype(np.uint8)
    Image.fromarray(out, "RGBA").save(os.path.join(FOLIAGE, name))
    print("wrote", name)


def fir_branch(name, seed):
    """A flat spray of fir needles: a central twig with side twigs, needles all along them."""
    r = np.random.default_rng(seed)
    W = S * SS
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    base = np.array([0.16, 0.27, 0.15])

    def twig(x0, y0, ang, length, width, depth):
        x1, y1 = x0 + math.cos(ang) * length, y0 + math.sin(ang) * length
        d.line([(x0, y0), (x1, y1)], fill=(70, 52, 36, 255), width=max(1, int(width)))
        steps = int(length / (5 * SS))
        for k in range(steps):
            t = k / max(steps - 1, 1)
            px, py = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            nl = (16 + 10 * (1 - t)) * SS * r.uniform(0.8, 1.15)
            for side in (-1, 1):
                a2 = ang + side * r.uniform(0.9, 1.25) - 0.25 * side
                ex, ey = px + math.cos(a2) * nl, py + math.sin(a2) * nl
                shade = 0.7 + 0.55 * (1 - py / W) + r.normal(0, 0.08)
                col = np.clip(base * shade * r.uniform(0.85, 1.15) + np.array([0, 0.02, 0]) * t, 0, 1) * 255
                d.line([(px, py), (ex, ey)], fill=tuple(int(c) for c in col) + (255,), width=int(2.2 * SS))
        if depth > 0:
            for k in range(1, 6):
                t = k / 6
                px, py = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
                for side in (-1, 1):
                    if r.random() < 0.85:
                        twig(px, py, ang + side * r.uniform(0.6, 0.9), length * (0.42 - 0.2 * t) * r.uniform(0.8, 1.1), width * 0.6, depth - 1)

    twig(W * 0.5, W * 0.98, -math.pi / 2 + r.normal(0, 0.05), W * 0.88, 4 * SS, 2)
    finish(img, name)


def fern(name, seed):
    r = np.random.default_rng(seed)
    W = S * SS
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for f in range(7):                                       # fronds fanning out from the bottom centre
        ang = -math.pi / 2 + (f - 3) * 0.32 + r.normal(0, 0.06)
        L = W * r.uniform(0.62, 0.9)
        pts = []
        for k in range(40):
            t = k / 39
            bend = 0.45 * t * t * (1 if ang > -math.pi / 2 else -1)
            a = ang + bend
            pts.append((W * 0.5 + math.cos(ang) * L * t + math.cos(a) * 0, W * 0.98 + math.sin(a) * L * t))
        d.line(pts, fill=(80, 96, 44, 255), width=int(3 * SS))
        for k in range(2, 38):
            t = k / 39
            px, py = pts[k]
            nx, ny = pts[k + 1][0] - px, pts[k + 1][1] - py
            ln = math.hypot(nx, ny) or 1
            nx, ny = nx / ln, ny / ln
            leaf = W * 0.11 * math.sin(math.pi * min(1, t * 1.1)) ** 0.8
            for side in (-1, 1):
                ex, ey = px - ny * side * leaf + nx * leaf * 0.35, py + nx * side * leaf + ny * leaf * 0.35
                g = np.clip(np.array([0.28, 0.46, 0.16]) * (0.8 + 0.4 * (1 - t)) * r.uniform(0.9, 1.1), 0, 1) * 255
                d.polygon([(px, py), (ex, ey), (px + nx * 6 * SS, py + ny * 6 * SS)], fill=tuple(int(c) for c in g) + (255,))
    finish(img, name)


def meadow_grass(name, seed, flowers=False):
    r = np.random.default_rng(seed)
    W = S * SS
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for _ in range(150):
        x0 = W / 2 + r.normal(0, 85 * SS)
        h = r.uniform(0.4, 0.95) * W
        bend = r.normal(0, 0.3) * h * 0.5
        w = r.uniform(3, 6) * SS
        tone = r.uniform(0.75, 1.1)
        base = np.array([88, 120, 46]) if r.random() < 0.75 else np.array([150, 150, 80])
        col = tuple(int(c) for c in np.clip(base * tone, 0, 255)) + (255,)
        pts = [(x0 + bend * (k / 8) ** 2 - w * (1 - k / 8), W - (k / 8) * h) for k in range(9)]
        pts += [(x0 + bend * (k / 8) ** 2 + w * (1 - k / 8), W - (k / 8) * h) for k in range(8, -1, -1)]
        d.polygon(pts, fill=col)
    if flowers:
        for _ in range(60):
            cx, cy = W / 2 + r.normal(0, 90 * SS), W * r.uniform(0.15, 0.55)
            rad = r.uniform(6, 10) * SS
            c = [(240, 236, 220), (236, 196, 60), (170, 120, 210), (230, 120, 150)][r.integers(4)]
            d.line([(cx, cy), (cx + r.normal(0, 8), W)], fill=(90, 120, 50, 255), width=int(2 * SS))
            d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=c + (255,))
            d.ellipse([cx - rad * 0.35, cy - rad * 0.35, cx + rad * 0.35, cy + rad * 0.35], fill=(220, 170, 40, 255))
    finish(img, name)


fir_branch("FirBranch.png", 101)
fern("Fern.png", 102)
meadow_grass("MeadowGrass.png", 103)
meadow_grass("Wildflowers.png", 104, flowers=True)


# ---------------------------------------------------------------- water (512, tileable)
def tile_noise(size, beta, seed):
    r = np.random.default_rng(seed)
    f = np.fft.fftfreq(size)
    k = np.hypot(f[None, :], f[:, None])
    k[0, 0] = 1
    spec = np.fft.fft2(r.standard_normal((size, size))) / k ** (beta / 2)
    spec[0, 0] = 0
    n = np.real(np.fft.ifft2(spec))
    return (n - n.min()) / (n.max() - n.min())


W = 512
wave = tile_noise(W, 3.2, 201) * 0.7 + tile_noise(W, 2.2, 202) * 0.3      # soft swell + small chop
wn = normal_from_height(wave, 9.0)
Image.fromarray(((wn * 0.5 + 0.5) * 255).round().astype(np.uint8), "RGB").save(os.path.join(TERRAIN, "Water_normal.png"))
foam = tile_noise(W, 1.6, 203)
streak = tile_noise(W, 2.8, 204)
foam = np.clip((foam - 0.45) * 3.5, 0, 1) * np.clip((streak - 0.3) * 2.5, 0, 1)
foam = ndimage.gaussian_filter(foam, 0.8, mode="wrap")
Image.fromarray((np.clip(foam, 0, 1) * 255).astype(np.uint8), "L").convert("RGB").save(os.path.join(TERRAIN, "Foam_albedo.png"))
print("wrote Water_normal, Foam")
