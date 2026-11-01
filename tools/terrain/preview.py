"""Shaded top-down preview of a generated region (north up). Usage: python tools/terrain/preview.py out.png"""
import json
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

SRC = os.path.join(os.path.dirname(__file__), "..", "..", "Assets", "Terrain", "Source~")
info = json.load(open(os.path.join(SRC, "desert_info.json")))
N, H = info["resolution"], info["height"]
h = np.fromfile(os.path.join(SRC, "desert_height.r16"), "<u2").reshape(N, N) / 65535 * H
gz, gx = np.gradient(h, info["size"] / (N - 1))
L = np.array([-0.55, 0.45, 0.45]); L /= np.linalg.norm(L)
n = np.stack([-gx, -gz, np.ones_like(gx)], -1); n /= np.linalg.norm(n, axis=-1, keepdims=True)
shade = np.clip((n * L).sum(-1), 0, 1)
sp = np.asarray(Image.open(os.path.join(SRC, "desert_splat.png"))).astype(float)[::-1] / 255
sp = ndimage.zoom(sp, (N / sp.shape[0], N / sp.shape[1], 1), order=1)[:N, :N]
cols = np.array([[0.80, 0.55, 0.36], [0.55, 0.43, 0.34], [0.70, 0.52, 0.38], [0.55, 0.26, 0.16]])
img = (sp[..., :, None] * cols[None, None]).sum(2) * (0.25 + 0.95 * shade[..., None])
img = img[::-1].copy()
s = info["spawn"]; px, pz = int(s["x"] / info["size"] * (N - 1)), N - 1 - int(s["z"] / info["size"] * (N - 1))
img[pz - 6:pz + 6, px - 6:px + 6] = [0.1, 0.9, 1.0]


def dot(x, z, r, col):
    px_, pz_ = int(x / info["size"] * (N - 1)), N - 1 - int(z / info["size"] * (N - 1))
    img[max(pz_ - r, 0):pz_ + r + 1, max(px_ - r, 0):px_ + r + 1] = col


import json as _json  # noqa: E402
colours = {"Hoodoo": [0.9, 0.2, 0.9], "Boulder": [0.25, 0.1, 0.05], "Slab": [0.9, 0.9, 0.2], "Scrub": [0.2, 0.55, 0.15],
           "Grass": [0.75, 0.7, 0.4], "Yucca": [0.1, 0.4, 0.3], "DeadTree": [1, 1, 1], "Rock": [0.45, 0.3, 0.2]}
for p_ in _json.load(open(os.path.join(SRC, "desert_scatter.json")))["props"]:
    dot(p_["x"], p_["z"], 2 if p_["kind"] in ("Hoodoo", "Boulder", "DeadTree", "Slab") else 1, colours.get(p_["kind"], [0, 0, 0]))
for m in info.get("markers", []):
    dot(m["x"], m["z"], 3, [1, 1, 0.6])
for L_ in info.get("landmarks", []):
    dot(L_["x"], L_["z"], 7, [1, 0.25, 0.1])
Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).resize((900, 900)).save(sys.argv[1])
