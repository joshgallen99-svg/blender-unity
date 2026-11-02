"""Game-ready versions of the CC0 Poly Haven Namaqualand granite boulder scans.

Run:  python tools/art/fetch_polyhaven.py && python blender/props/granite_scans.py
Reads:  tools/art/sources/polyhaven/namaqualand_boulder_0N/*.gltf (+ textures)
Writes: Assets/Models/Props/GraniteScans.fbx  objects Scan_0..Scan_4 (~2.5k tris) and Scan_N_LOD1 (~500 tris),
        origin at the centre of the base, normalised to ~2 m across (scaled per instance in game);
        Assets/Art/Textures/Scans/scan_N_{diff,nor,arm}.jpg  the scans' own 1k texture maps.
"""
import glob
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from lib import common as C  # noqa: E402

SRC = C.path_in_repo("tools", "art", "sources", "polyhaven")
TEX_OUT = C.path_in_repo("Assets", "Art", "Textures", "Scans")
IDS = ["namaqualand_boulder_02", "namaqualand_boulder_03", "namaqualand_boulder_04",
       "namaqualand_boulder_05", "namaqualand_boulder_06"]
LOD0_TRIS, LOD1_TRIS = 2500, 500
SIZE = 2.0


def decimated(src, name, tris):
    o = src.copy()
    o.data = src.data.copy()
    o.name = name
    bpy.context.scene.collection.objects.link(o)
    ratio = min(1.0, tris / max(1, C.tri_count(src)))
    m = o.modifiers.new("dec", "DECIMATE")
    m.ratio = ratio
    m.use_collapse_triangulate = True
    C.apply_modifiers(o)
    return o


def build():
    C.reset_scene()
    os.makedirs(TEX_OUT, exist_ok=True)
    out = []
    for i, asset in enumerate(IDS):
        gltf = glob.glob(os.path.join(SRC, asset, "*.gltf"))
        if not gltf:
            raise SystemExit(f"Missing {asset}: run tools/art/fetch_polyhaven.py first")
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=gltf[0])
        meshes = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
        src = C.join(meshes, f"src{i}") if len(meshes) > 1 else meshes[0]
        bpy.context.view_layer.objects.active = src
        src.select_set(True)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        # Normalise: base centre at the origin, largest horizontal extent SIZE.
        vs = [v.co for v in src.data.vertices]
        lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
        hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
        k = SIZE / max(hi.x - lo.x, hi.y - lo.y)
        shift = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
        for v in src.data.vertices:
            v.co = (v.co - shift) * k
        src.data.update()
        lod0 = decimated(src, f"Scan_{i}", LOD0_TRIS)
        lod1 = decimated(src, f"Scan_{i}_LOD1", LOD1_TRIS)
        mat = bpy.data.materials.new(f"Scan_{i}")
        for o in (lod0, lod1):
            o.data.materials.clear()
            o.data.materials.append(mat)
            C.smooth_by_angle(o, 60)
        bpy.data.objects.remove(src)
        for f in glob.glob(os.path.join(SRC, asset, "textures", "*.jpg")):
            kind = "diff" if "_diff_" in f else "nor" if "_nor_" in f else "arm" if "_arm_" in f else None
            if kind:
                shutil.copyfile(f, os.path.join(TEX_OUT, f"scan_{i}_{kind}.jpg"))
        print(f"Scan_{i}: {C.tri_count(lod0)} / {C.tri_count(lod1)} tris, height {(hi.z - lo.z) * k:.2f} m")
        out += [lod0, lod1]
    return out


if __name__ == "__main__":
    objs = build()
    C.export_fbx(objs, C.path_in_repo("Assets", "Models", "Props", "GraniteScans.fbx"))
