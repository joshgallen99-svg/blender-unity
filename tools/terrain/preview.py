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
Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).resize((768, 768)).save(sys.argv[1])
