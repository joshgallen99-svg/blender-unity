"""Desert scenery, sculpted for the triplanar rock shader and leaf-card foliage.

Run:  python blender/props/desert_props.py
Writes: Assets/Models/Props/DesertProps.fbx
Objects (origin at the base centre):
  Boulder_0..5   weathered sandstone boulders with layered ledges      (~0.7k tris)
  Slab_0..2      stacked flat rock shelves, for rock gardens and ledges
  Hoodoo_0..2    tall eroded spires with cap rocks (4-7 m)
  Rock_0..4      small rocks for scatter
  Scrub_0..2     leafy desert shrubs (alpha cards, bent normals)
  Grass_0..1     dry grass tufts
  Yucca_0..1     spiky rosettes (1 with a flower stalk)
  DeadTree_0..1  bleached dead trees

Material names map to Unity materials (Assets/Editor/MaterialLibrary.cs):
  RockSandstone / RockPale -> Offroad/RockTriplanar, Leaves / LeavesFlowering / GrassCards -> Offroad/Foliage
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import bpy  # noqa: E402,F401
import bmesh  # noqa: E402
from mathutils import Vector, noise  # noqa: E402

from lib import common as C  # noqa: E402


def palette():
    m = C.material
    return {
        "RockSandstone": m("RockSandstone", (0.42, 0.19, 0.11), 0.0, 0.88),
        "RockPale": m("RockPale", (0.62, 0.42, 0.29), 0.0, 0.9),
        "Leaves": m("Leaves", (0.30, 0.35, 0.22), 0.0, 0.8),
        "LeavesFlowering": m("LeavesFlowering", (0.40, 0.40, 0.20), 0.0, 0.8),
        "GrassCards": m("GrassCards", (0.55, 0.47, 0.30), 0.0, 0.85),
        "Yucca": m("Yucca", (0.25, 0.36, 0.27), 0.0, 0.6),
        "Bark": m("Bark", (0.33, 0.28, 0.23), 0.0, 0.9),
        "BarkBleached": m("BarkBleached", (0.55, 0.50, 0.44), 0.0, 0.85),
    }


def fbm(p, octaves=4):
    total, amp, freq, norm = 0.0, 1.0, 1.0, 0.0
    for _ in range(octaves):
        total += amp * noise.noise(p * freq)
        norm += amp
        amp *= 0.5
        freq *= 2.03
    return total / norm


def decimate(obj, ratio):
    mod = obj.modifiers.new("Dec", "DECIMATE")
    mod.ratio = ratio
    C.apply_modifiers(obj)


def ground(obj, sink=0.0):
    """Move the mesh so its lowest point is at z = -sink."""
    zmin = min(v.co.z for v in obj.data.vertices)
    for v in obj.data.vertices:
        v.co.z -= zmin + sink


# ---------------------------------------------------------------------------- rocks

def sandstone(name, seed, size, mat, subdiv=5, ratio=0.15, lumpy=0.38, ledges=0.6, layers=5.0):
    """Rounded, wind-worn block with horizontal ledges (sandstone bedding)."""
    rnd = random.Random(seed)
    off = Vector((rnd.uniform(-90, 90), rnd.uniform(-90, 90), rnd.uniform(-90, 90)))
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    for v in bm.verts:
        p = v.co.copy()
        d = 1 + lumpy * fbm(p * 0.9 + off, 3) + 0.07 * fbm(p * 3.2 + off, 2)
        p *= d
        # Bedding ledges: pull heights toward layer planes, more on the sides than the top.
        side = 1 - abs(p.normalized().z)
        q = round(p.z * layers) / layers
        p.z += (q - p.z) * ledges * side
        # Undercut near the base, like real wind-eroded rocks.
        if p.z < -0.2:
            p.x *= 0.88
            p.y *= 0.88
        p.z = max(p.z, -0.55)
        v.co = Vector((p.x * size[0], p.y * size[1], p.z * size[2]))
    obj = C.from_bmesh(name, bm, mat)
    decimate(obj, ratio)
    ground(obj, 0.05 * size[2])
    C.smooth_by_angle(obj, 38)
    return obj


def slab(name, seed, M):
    """Two to four stacked, offset rock plates."""
    rnd = random.Random(seed)
    parts = []
    z = 0.0
    for k in range(rnd.randint(2, 4)):
        r = rnd.uniform(1.0, 1.8) * (1 - 0.18 * k)
        t = rnd.uniform(0.22, 0.42)
        n = 14
        cx, cy = rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3)
        bm = bmesh.new()
        ring_b, ring_t = [], []
        for i in range(n):
            a = 2 * math.pi * i / n
            rr = r * (0.75 + 0.35 * noise.noise(Vector((math.cos(a), math.sin(a), seed + k)) * 1.7))
            x, y = cx + math.cos(a) * rr * 1.25, cy + math.sin(a) * rr
            ring_b.append(bm.verts.new((x, y, z)))
            ring_t.append(bm.verts.new((x * 0.96, y * 0.96, z + t)))
        bm.faces.new(ring_b[::-1])
        bm.faces.new(ring_t)
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((ring_b[i], ring_b[j], ring_t[j], ring_t[i]))
        plate = C.from_bmesh(f"{name}_{k}", bm, M["RockSandstone"])
        C.add_bevel(plate, 0.06, 2, 30)
        C.apply_modifiers(plate)
        sub = plate.modifiers.new("Sub", "SUBSURF")
        sub.levels = 1
        C.apply_modifiers(plate)
        for v in plate.data.vertices:
            v.co += Vector((0, 0, 0.05 * noise.noise(v.co * 2.1 + Vector((seed, k, 0)))))
        parts.append(plate)
        z += t * rnd.uniform(0.7, 0.95)
    obj = C.join(parts, name)
    decimate(obj, 0.3)
    ground(obj, 0.08)
    C.smooth_by_angle(obj, 40)
    return obj


def hoodoo(name, seed, height, M):
    """Eroded spire: a leaning, fluted column of soft layered rock under a harder cap rock."""
    rnd = random.Random(seed)
    off = Vector((rnd.uniform(-50, 50), rnd.uniform(-50, 50), rnd.uniform(-50, 50)))
    lean = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)).normalized() * height * 0.05
    rings, seg = 36, 18
    base_r = height * 0.17
    bm = bmesh.new()
    rows = []
    for k in range(rings):
        t = k / (rings - 1)
        z = t * height
        r = base_r * (1.05 - 0.35 * t + 0.22 * fbm(Vector((0, 0, z * 0.45)) + off, 2))
        r *= 1 + 0.6 * (1 - min(t / 0.14, 1)) ** 2               # talus flare at the base
        r *= 1 - 0.38 * math.exp(-((t - 0.92) / 0.05) ** 2)      # neck under the cap
        band = (z * 1.35 + 0.3 * fbm(off + Vector((z, 0, 0)), 1)) % 1.0
        r *= 1 + 0.11 * max(0.0, (band - 0.72) / 0.28) ** 2      # hard layers stick out as lips
        centre = lean * t * t
        row = []
        for i in range(seg):
            a = 2 * math.pi * i / seg
            dirv = Vector((math.cos(a), math.sin(a), 0))
            rr = r * (1 + 0.3 * fbm(dirv * 1.6 + Vector((0, 0, z * 0.9)) + off, 3)
                      + 0.06 * math.sin(a * 5 + z * 0.7))            # vertical flutes
            row.append(bm.verts.new((centre.x + dirv.x * rr, centre.y + dirv.y * rr, z)))
        rows.append(row)
    for k in range(rings - 1):
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((rows[k][i], rows[k][j], rows[k + 1][j], rows[k + 1][i]))
    bm.faces.new(rows[0][::-1])
    bm.faces.new(rows[-1])
    column = C.from_bmesh(name + "_col", bm, M["RockSandstone"])
    decimate(column, 0.7)
    cap = sandstone(name + "_cap", seed + 100, (base_r * 1.7, base_r * 1.4, base_r * 0.6), M["RockPale"],
                    subdiv=4, ratio=0.3, lumpy=0.35, ledges=0.5, layers=3)
    for v in cap.data.vertices:
        v.co += Vector((lean.x, lean.y, height - base_r * 0.15))
    obj = C.join([column, cap], name)
    ground(obj, 0.2)
    C.smooth_by_angle(obj, 38)
    return obj


def small_rock(name, seed, size, mat):
    return sandstone(name, seed, size, mat, subdiv=3, ratio=0.5, lumpy=0.4, ledges=0.2, layers=3)


# ---------------------------------------------------------------------------- foliage

def card(bm, center, normal, up, w, h):
    """Quad facing `normal`, bottom edge centred on `center`."""
    right = up.cross(normal).normalized() * (w / 2)
    upv = up.normalized() * h
    vs = [bm.verts.new(center - right), bm.verts.new(center + right),
          bm.verts.new(center + right + upv), bm.verts.new(center - right + upv)]
    return bm.faces.new(vs)


def foliage_cards(name, seed, mat, count, radius, height, card_size, flat=0.4):
    """Dome of leaf cards with normals bent outward from the plant centre (soft lighting)."""
    rnd = random.Random(seed)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    for _ in range(count):
        a = rnd.uniform(0, 2 * math.pi)
        r = radius * math.sqrt(rnd.random()) * 0.6
        base = Vector((math.cos(a) * r, math.sin(a) * r, rnd.uniform(0, height * 0.25)))
        fa = a + rnd.uniform(-1.2, 1.2)
        facing = Vector((math.cos(fa), math.sin(fa), 0))
        upv = Vector((rnd.uniform(-flat, flat), rnd.uniform(-flat, flat), 1)).normalized()
        s = card_size * rnd.uniform(0.75, 1.15)
        f = card(bm, base, facing.normalized(), upv, s, s * (height / card_size) * rnd.uniform(0.8, 1.1))
        for loop, (u, v) in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
            loop[uv].uv = (u, v)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(mat)
    for p in mesh.polygons:
        p.use_smooth = True
    # Bent normals: point away from a centre below the plant, mostly upward.
    centre = Vector((0, 0, -height * 0.3))
    normals = []
    for loop in mesh.loops:
        p = mesh.vertices[loop.vertex_index].co
        normals.append(tuple(((p - centre).normalized() * 0.6 + Vector((0, 0, 0.4))).normalized()))
    mesh.normals_split_custom_set(normals)
    return obj


def yucca(name, seed, M, stalk=False):
    rnd = random.Random(seed)
    bm = bmesh.new()
    trunk_h = rnd.uniform(0.25, 0.5)
    for i in range(54):
        a = i * 2.399963 + rnd.uniform(-0.1, 0.1)
        tilt = 0.12 + 1.3 * (i / 54) ** 0.8
        d = Vector((math.cos(a) * math.sin(tilt), math.sin(a) * math.sin(tilt), math.cos(tilt)))
        length = rnd.uniform(0.55, 0.85)
        side = d.cross(Vector((0, 0, 1)))
        side = (side if side.length > 1e-3 else Vector((1, 0, 0))).normalized()
        base = Vector((0, 0, trunk_h))
        mid = base + d * length * 0.5 + Vector((0, 0, -0.05 * (i / 54)))
        tip = base + d * length + Vector((0, 0, -0.12 * (i / 54) ** 2))
        w = 0.035
        v = [bm.verts.new(base + side * w * 0.6), bm.verts.new(base - side * w * 0.6),
             bm.verts.new(mid + side * w), bm.verts.new(mid - side * w), bm.verts.new(tip)]
        bm.faces.new((v[0], v[1], v[3], v[2]))
        bm.faces.new((v[2], v[3], v[4]))
    leaves = C.from_bmesh(name + "_leaves", bm, M["Yucca"])
    parts = [leaves, C.cylinder(name + "_trunk", 0.1, trunk_h + 0.05, (0, 0, (trunk_h + 0.05) / 2), "Z", 8, M["Bark"],
                                radius2=0.075)]
    if stalk:
        parts.append(C.tube(name + "_stalk", (0, 0, trunk_h), (0.05, 0.02, trunk_h + 1.7), 0.018, M["Bark"], 5))
        for k in range(9):
            z = trunk_h + 1.05 + k * 0.08
            parts.append(C.sphere(f"{name}_fl{k}", 0.05, (0.03 + 0.06 * math.sin(k * 2.1), 0.06 * math.cos(k * 2.1), z),
                                  M["BarkBleached"], 1))
    obj = C.join(parts, name)
    ground(obj)
    C.smooth_by_angle(obj, 35)
    return obj


def dead_tree(name, seed, M):
    rnd = random.Random(seed)
    parts = []

    def branch(p, d, length, radius, depth):
        end = p + d.normalized() * length
        end += Vector((rnd.uniform(-0.15, 0.15), rnd.uniform(-0.15, 0.15), 0)) * length
        parts.append(C.tube(f"{name}_{len(parts)}", p, end, radius, M["BarkBleached"], 7 if depth < 2 else 5))
        parts.append(C.sphere(f"{name}_k{len(parts)}", radius * 1.02, end, M["BarkBleached"], 1))
        if depth >= 3 or radius < 0.025:
            return
        for _ in range(rnd.randint(2, 3)):
            nd = d.normalized() + Vector((rnd.uniform(-0.9, 0.9), rnd.uniform(-0.9, 0.9), rnd.uniform(0.0, 0.6)))
            branch(end, nd, length * rnd.uniform(0.55, 0.75), radius * 0.62, depth + 1)

    branch(Vector((0, 0, -0.1)), Vector((rnd.uniform(-0.2, 0.2), rnd.uniform(-0.2, 0.2), 1)), rnd.uniform(1.8, 2.4),
           0.17, 0)
    for i in range(4):   # root flare
        a = i * math.pi / 2 + rnd.uniform(-0.4, 0.4)
        parts.append(C.tube(f"{name}_root{i}", (0, 0, 0.25), (math.cos(a) * 0.55, math.sin(a) * 0.55, -0.05), 0.07,
                            M["BarkBleached"], 6))
    obj = C.join(parts, name)
    ground(obj, 0.05)
    C.smooth_by_angle(obj, 45)
    return obj


def build():
    C.reset_scene()
    M = palette()
    objs = []
    boulder_sizes = [(1.3, 1.0, 0.85), (1.1, 1.0, 1.0), (1.6, 1.1, 0.7), (1.0, 0.9, 1.2), (1.4, 1.3, 0.9),
                     (1.2, 0.8, 0.65)]
    for i, size in enumerate(boulder_sizes):
        objs.append(sandstone(f"Boulder_{i}", 10 + i, size, M["RockPale"] if i in (2, 5) else M["RockSandstone"]))
    for i in range(3):
        objs.append(slab(f"Slab_{i}", 40 + i, M))
    for i, h in enumerate((4.5, 6.0, 7.2)):
        objs.append(hoodoo(f"Hoodoo_{i}", 50 + i, h, M))
    for i in range(5):
        objs.append(small_rock(f"Rock_{i}", 30 + i, (0.45, 0.38, 0.28 + 0.05 * i),
                               M["RockPale"] if i % 2 else M["RockSandstone"]))
    objs.append(foliage_cards("Scrub_0", 60, M["Leaves"], 16, 1.1, 0.9, 1.0))
    objs.append(foliage_cards("Scrub_1", 61, M["Leaves"], 22, 1.5, 1.1, 1.2))
    objs.append(foliage_cards("Scrub_2", 62, M["LeavesFlowering"], 16, 1.2, 0.95, 1.05))
    objs.append(foliage_cards("Grass_0", 70, M["GrassCards"], 7, 0.35, 0.55, 0.6, flat=0.15))
    objs.append(foliage_cards("Grass_1", 71, M["GrassCards"], 10, 0.5, 0.7, 0.75, flat=0.2))
    objs.append(yucca("Yucca_0", 80, M))
    objs.append(yucca("Yucca_1", 81, M, stalk=True))
    objs.append(dead_tree("DeadTree_0", 90, M))
    objs.append(dead_tree("DeadTree_1", 91, M))
    return objs


if __name__ == "__main__":
    objs = build()
    for o in objs:
        print(f"{o.name:12s} tris={C.tri_count(o):5d}  size={tuple(round(d, 1) for d in o.dimensions)}")
    C.export_fbx(objs, C.path_in_repo("Assets", "Models", "Props", "DesertProps.fbx"))
