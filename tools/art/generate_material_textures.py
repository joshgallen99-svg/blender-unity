"""Tileable textures for man-made landmark materials (albedo + normal), 512 px.

Run:  python tools/art/generate_material_textures.py
Writes: Assets/Art/Textures/Materials/{Wood,Rust,Galvanized,Canvas}_{albedo,normal}.png
"""
import math
import os

import numpy as np
from PIL import Image

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(REPO, "Assets", "Art", "Textures", "Materials")
os.makedirs(OUT, exist_ok=True)
T = 512
yy, xx = np.mgrid[0:T, 0:T] / T


def tile_noise(beta, seed, shape=(T, T), aniso=(1.0, 1.0)):
    """Tileable 1/f^beta noise in [0,1]; aniso stretches features along x or y."""
    r = np.random.default_rng(seed)
    fy = np.fft.fftfreq(shape[0])[:, None] * aniso[1]
    fx = np.fft.fftfreq(shape[1])[None, :] * aniso[0]
    k = np.hypot(fx, fy)
    k[0, 0] = 1
    spec = np.fft.fft2(r.standard_normal(shape)) / k ** (beta / 2)
    spec[0, 0] = 0
    n = np.real(np.fft.ifft2(spec))
    return (n - n.min()) / (n.max() - n.min())


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def mix(c0, c1, t):
    t = np.asarray(t)[..., None]
    return np.array(c0) * (1 - t) + np.array(c1) * t


def save(name, albedo, height, strength):
    Image.fromarray((np.clip(albedo, 0, 1) * 255).astype(np.uint8), "RGB").save(os.path.join(OUT, f"{name}_albedo.png"))
    gx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) * strength
    gy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) * strength
    n = np.stack([-gx, gy, np.ones_like(gx)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    Image.fromarray(((n * 0.5 + 0.5) * 255).astype(np.uint8), "RGB").save(os.path.join(OUT, f"{name}_normal.png"))
    print("wrote", name)


# Weathered wood: 4 planks per tile (tile = 1 m), sun-bleached grey-brown with grain and gaps.
planks = 4
plank_id = np.floor(yy * planks).astype(int)
within = (yy * planks) % 1.0
r = np.random.default_rng(1)
tone = r.uniform(0.75, 1.1, planks)[plank_id]
grain = tile_noise(2.2, 2, aniso=(0.08, 1.0))                          # long streaks along x
knots = smoothstep(0.82, 0.95, tile_noise(3.0, 3))
gap = smoothstep(0.0, 0.04, within) * smoothstep(1.0, 0.96, within)
wood = mix((0.36, 0.30, 0.24), (0.62, 0.56, 0.48), grain * 0.7 + 0.3 * tile_noise(1.0, 4)) * tone[..., None]
wood *= (0.55 + 0.45 * gap)[..., None] * (1 - 0.35 * knots)[..., None]
save("Wood", wood, grain * 0.5 + gap * 0.8 - knots * 0.3, 4.0)

# Rust: orange-brown blotches over dark metal with pitting.
blot = tile_noise(2.4, 5)
pits = smoothstep(0.75, 0.9, tile_noise(0.8, 6))
streak = tile_noise(2.0, 7, aniso=(1.0, 0.15))                         # vertical run-off streaks
rust = mix((0.18, 0.12, 0.09), (0.58, 0.28, 0.12), smoothstep(0.35, 0.65, blot * 0.7 + streak * 0.3))
rust *= (0.85 + 0.3 * tile_noise(0.6, 8))[..., None] * (1 - 0.4 * pits)[..., None]
save("Rust", rust, blot * 0.4 - pits * 0.6, 5.0)

# Galvanised / corrugated steel: mottled grey with spangle, faint rust spots.
spangle = tile_noise(1.2, 9)
spots = smoothstep(0.8, 0.92, tile_noise(2.5, 10))
corr = 0.5 + 0.5 * np.sin(2 * math.pi * xx * 16)                        # 16 ridges per metre
galv = mix((0.48, 0.50, 0.52), (0.70, 0.72, 0.73), spangle) * (0.9 + 0.1 * corr)[..., None]
galv = galv * (1 - spots[..., None]) + np.array([0.45, 0.25, 0.13]) * spots[..., None]
save("Galvanized", galv, corr * 0.8 + spangle * 0.1, 6.0)

# Canvas: woven, sun-faded orange.
weave = (0.5 + 0.25 * np.sin(2 * math.pi * xx * 128) + 0.25 * np.sin(2 * math.pi * yy * 128))
fade = tile_noise(2.0, 11)
canvas = mix((0.70, 0.32, 0.12), (0.86, 0.52, 0.26), fade) * (0.9 + 0.1 * weave)[..., None]
save("Canvas", canvas, weave * 0.3 + fade * 0.2, 2.0)
