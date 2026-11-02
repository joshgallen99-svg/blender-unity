"""Paint leaf/grass sprite textures for the foliage cards (RGBA, alpha-cut).

Run:  python tools/art/generate_foliage_textures.py
Writes: Assets/Art/Textures/Foliage/{ScrubLeaves,ScrubFlowering,AutumnLeaves,AutumnShrub,DryGrass}.png
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(REPO, "Assets", "Art", "Textures", "Foliage")
os.makedirs(OUT, exist_ok=True)
S = 512           # output size
SS = 2            # supersampling


def leaf_poly(cx, cy, length, width, angle):
    pts = []
    for k in range(12):
        t = k / 11
        # pointed ellipse: wide in the middle, sharp at both ends
        r = width * math.sin(math.pi * t) ** 0.8
        x, y = (t - 0.5) * length, r
        pts.append((x, y))
    pts += [(x, -y) for x, y in reversed(pts)]
    ca, sa = math.cos(angle), math.sin(angle)
    return [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts]


def finish(img, name):
    img = img.resize((S, S), Image.LANCZOS)
    a = np.asarray(img).astype(np.float32)
    rgb, alpha = a[..., :3], a[..., 3:4] / 255.0
    # Bleed colour into transparent pixels so mipmaps don't get dark fringes.
    mean = (rgb * alpha).sum((0, 1)) / max(alpha.sum(), 1)
    blurred = np.asarray(Image.fromarray(a.astype(np.uint8)).filter(ImageFilter.GaussianBlur(6))).astype(np.float32)
    fill = np.where(blurred[..., 3:4] > 5, blurred[..., :3] / np.maximum(blurred[..., 3:4] / 255.0, 1e-3), mean)
    rgb = rgb * alpha + np.clip(fill, 0, 255) * (1 - alpha)
    out = np.concatenate([rgb, alpha * 255], -1).clip(0, 255).astype(np.uint8)
    Image.fromarray(out, "RGBA").save(os.path.join(OUT, name))
    print("wrote", name)


# Autumn palettes (colour, weight): aspen/larch gold with amber; shrubs from rust to crimson.
AUTUMN_GOLD = [((0.86, 0.66, 0.16), 5), ((0.93, 0.78, 0.24), 4), ((0.80, 0.48, 0.10), 2), ((0.62, 0.62, 0.20), 1),
               ((0.72, 0.22, 0.08), 0.4)]
AUTUMN_SHRUB = [((0.66, 0.20, 0.08), 4), ((0.80, 0.34, 0.08), 3), ((0.50, 0.12, 0.10), 2), ((0.86, 0.60, 0.16), 1)]


def scrub(name, seed, flowers, palette=None):
    rng = np.random.default_rng(seed)
    W = S * SS
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    base = np.array([0.42, 0.47, 0.33])          # dusty sage
    # Twigs radiating up from the bottom centre.
    twigs = []
    for i in range(14):
        a = math.radians(rng.uniform(-70, 70)) - math.pi / 2
        L = rng.uniform(0.55, 0.9) * W * 0.5
        x0, y0 = W / 2 + rng.uniform(-30, 30) * SS, W * 0.98
        x1, y1 = x0 + math.cos(a) * L, y0 + math.sin(a) * L
        twigs.append((x0, y0, x1, y1))
        d.line([(x0, y0), (x1, y1)], fill=(92, 72, 55, 255), width=int(3 * SS))
    # Leaves clustered toward twig ends, lighter at the top.
    for _ in range(900):
        x0, y0, x1, y1 = twigs[rng.integers(len(twigs))]
        t = rng.uniform(0.3, 1.0) ** 0.6
        cx = x0 + (x1 - x0) * t + rng.normal(0, 14 * SS)
        cy = y0 + (y1 - y0) * t + rng.normal(0, 14 * SS)
        shade = 0.75 + 0.45 * (1 - cy / W) + rng.normal(0, 0.06)
        if palette:
            w = np.array([p[1] for p in palette], float)
            leaf = np.array(palette[rng.choice(len(palette), p=w / w.sum())][0])
        else:
            leaf = base
        col = np.clip(leaf * shade + rng.normal(0, 0.03, 3), 0, 1) * 255
        d.polygon(leaf_poly(cx, cy, rng.uniform(18, 30) * SS, rng.uniform(4, 7) * SS, rng.uniform(0, math.pi)),
                  fill=tuple(int(c) for c in col) + (255,))
    if flowers:
        for _ in range(70):
            x0, y0, x1, y1 = twigs[rng.integers(len(twigs))]
            cx = x1 + rng.normal(0, 22 * SS)
            cy = y1 + rng.normal(0, 22 * SS) - 10 * SS
            r = rng.uniform(5, 8) * SS
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(232, 186, 48, 255))
            d.ellipse([cx - r * 0.35, cy - r * 0.35, cx + r * 0.35, cy + r * 0.35], fill=(150, 90, 30, 255))
    finish(img, name)


def grass(name, seed):
    rng = np.random.default_rng(seed)
    W = S * SS
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for _ in range(110):
        x0 = W / 2 + rng.normal(0, 70 * SS)
        h = rng.uniform(0.45, 0.95) * W
        bend = rng.normal(0, 0.35) * h * 0.5
        w = rng.uniform(4, 8) * SS
        tone = rng.uniform(0.7, 1.05)
        base = np.array([196, 168, 112]) if rng.random() < 0.6 else np.array([168, 162, 96])   # straw or sage-green
        col = tuple(int(c) for c in np.clip(base * tone, 0, 255)) + (255,)
        pts = []
        for k in range(9):
            t = k / 8
            x = x0 + bend * t * t
            y = W - t * h
            pts.append((x - w * (1 - t), y))
        pts += [(x0 + bend * (k / 8) ** 2 + w * (1 - k / 8), W - (k / 8) * h) for k in range(8, -1, -1)]
        d.polygon(pts, fill=col)
        if rng.random() < 0.25:   # seed heads
            tx, ty = x0 + bend, W - h
            d.ellipse([tx - 5 * SS, ty - 12 * SS, tx + 5 * SS, ty + 12 * SS], fill=(214, 190, 140, 255))
    finish(img, name)


scrub("ScrubLeaves.png", 1, flowers=False)
scrub("ScrubFlowering.png", 2, flowers=True)
scrub("AutumnLeaves.png", 4, flowers=False, palette=AUTUMN_GOLD)
scrub("AutumnShrub.png", 5, flowers=False, palette=AUTUMN_SHRUB)
grass("DryGrass.png", 3)
