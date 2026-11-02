"""Download the CC0 Poly Haven assets the game uses into tools/art/sources/polyhaven/<asset>/.

Run:  python tools/art/fetch_polyhaven.py
Poly Haven assets are CC0 (public domain); see docs/art-direction.md for the list and links.
Already-downloaded files are skipped.
"""
import json
import os
import urllib.request

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(REPO, "tools", "art", "sources", "polyhaven")

# Scanned granite boulders (Namaqualand, South Africa): the rock-crawling obstacles.
MODELS = ["namaqualand_boulder_02", "namaqualand_boulder_03", "namaqualand_boulder_04",
          "namaqualand_boulder_05", "namaqualand_boulder_06"]
# Ground and rock surfaces: lichen-covered and mossy rock.
TEXTURES = ["lichen_rock", "rock_pitted_mossy"]
RES = "1k"


def get(url, path):
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "offroad-expedition-asset-fetch"})
    with urllib.request.urlopen(req, timeout=60) as r, open(path + ".part", "wb") as f:
        f.write(r.read())
    os.replace(path + ".part", path)
    print("  ", os.path.relpath(path, REPO))


def files(asset):
    req = urllib.request.Request(f"https://api.polyhaven.com/files/{asset}",
                                 headers={"User-Agent": "offroad-expedition-asset-fetch"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


for asset in MODELS:
    print(asset)
    g = files(asset)["gltf"][RES]["gltf"]
    get(g["url"], os.path.join(OUT, asset, os.path.basename(g["url"])))
    for rel, inc in g["include"].items():
        get(inc["url"], os.path.join(OUT, asset, rel))

for asset in TEXTURES:
    print(asset)
    f = files(asset)
    for key in ("Diffuse", "nor_gl", "arm"):
        e = f[key][RES]
        e = e.get("jpg") or e.get("png")
        get(e["url"], os.path.join(OUT, asset, os.path.basename(e["url"])))
print("Done.")
