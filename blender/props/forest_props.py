"""Forest river valley scenery: conifers, aspens, logs, granite boulders and understorey.

Run:  python blender/props/forest_props.py
Writes: Assets/Models/Props/ForestProps.fbx and the fir impostor atlas
        Assets/Art/Textures/Foliage/FirImpostors.png (side renders used by the far LOD).
Objects (origin at the base centre, Z up in Blender):
  Fir_0..2        conifers 16-24 m: tapered bark trunk + whorls of V-shaped needle-spray cards.
                  _LOD1 (sparser, bigger cards) and _LOD2 (two crossed impostor cards).
  Snag_0          dead conifer with broken branch stubs
  Aspen_0..1      white-barked aspens with leaf-cluster cards (+ _LOD1)
  Log_0..1        fallen trunks with stubs; Stump_0
  GBoulder_0..3   rounded, jointed granite boulders (+ _LOD1)
  Fern_0..1, MeadowGrass_0..1, Flowers_0, Bush_0   understorey cards
Material names map to Unity materials (Assets/Editor/MaterialLibrary.cs).
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

import tempfile  # noqa: E402

TMP = tempfile.mkdtemp(prefix="impostors_")
FOLIAGE_DIR = C.path_in_repo("Assets", "Art", "Textures", "Foliage", "x")[:-2]
MATS_DIR = C.path_in_repo("Assets", "Art", "Textures", "Materials", "x")[:-2]


def palette():
    m = C.material
    return {
        "BarkFir": m("BarkFir", (0.30, 0.22, 0.17), 0.0, 0.9),
        "FirNeedles": m("FirNeedles", (0.14, 0.24, 0.13), 0.0, 0.8),
        "FirImpostor": m("FirImpostor", (0.14, 0.24, 0.13), 0.0, 0.8),
        "BarkDead": m("BarkDead", (0.45, 0.42, 0.38), 0.0, 0.9),
        "BarkAspen": m("BarkAspen", (0.78, 0.76, 0.70), 0.0, 0.7),
        "AspenLeaves": m("AspenLeaves", (0.45, 0.55, 0.20), 0.0, 0.7),
        "WoodEnd": m("WoodEnd", (0.62, 0.48, 0.33), 0.0, 0.8),
        "Granite": m("Granite", (0.45, 0.45, 0.45), 0.0, 0.85),
        "Fern": m("Fern", (0.25, 0.40, 0.15), 0.0, 0.8),
        "MeadowGrass": m("MeadowGrass", (0.30, 0.42, 0.16), 0.0, 0.85),
        "Wildflowers": m("Wildflowers", (0.40, 0.45, 0.25), 0.0, 0.85),
        "BushLeaves": m("BushLeaves", (0.22, 0.32, 0.14), 0.0, 0.8),
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
    zmin = min(v.co.z for v in obj.data.vertices)
    for v in obj.data.vertices:
        v.co.z -= zmin + sink


def new_obj(name, bm, mats):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    for m in mats:
        obj.data.materials.append(m)
    for p in mesh.polygons:
        p.use_smooth = True
    return obj


def trunk(bm, uv, base, height, r0, r1, sides, mat_index, bend=None, rnd=None, uv_tile=1.6):
    """Tapered trunk with cylindrical UVs in metres (u around, v up), optional gentle bend."""
    rings = max(3, int(height / 2.0) + 2)
    rows = []
    for i in range(rings):
        t = i / (rings - 1)
        z = height * t
        r = r0 + (r1 - r0) * t ** 0.9
        off = bend(t) if bend else Vector((0, 0, 0))
        ring = []
        for k in range(sides):
            a = 2 * math.pi * k / sides
            ring.append(bm.verts.new(base + off + Vector((math.cos(a) * r, math.sin(a) * r, z))))
        rows.append((ring, r, z))
    circ = 2 * math.pi * r0
    for i in range(rings - 1):
        (ra, _, za), (rb, _, zb) = rows[i], rows[i + 1]
        for k in range(sides):
            k2 = (k + 1) % sides
            f = bm.faces.new((ra[k], ra[k2], rb[k2], rb[k]))
            f.material_index = mat_index
            u0, u1 = k / sides * circ / uv_tile, (k + 1) / sides * circ / uv_tile
            for loop, (u, v) in zip(f.loops, ((u0, za), (u1, za), (u1, zb), (u0, zb))):
                loop[uv].uv = (u, v / uv_tile)
    return rows


def branch_tube(bm, uv, p0, p1, r0, r1, sides, mat_index):
    """Tapered tube from p0 to p1 along any direction (branch stubs, roots)."""
    axis = (p1 - p0)
    length = axis.length
    axis.normalize()
    ref = Vector((0, 0, 1)) if abs(axis.z) < 0.9 else Vector((1, 0, 0))
    u = axis.cross(ref).normalized()
    v = axis.cross(u)
    rings = []
    for t, r in ((0.0, r0), (1.0, r1)):
        c = p0 + axis * length * t
        rings.append([bm.verts.new(c + (u * math.cos(2 * math.pi * k / sides) + v * math.sin(2 * math.pi * k / sides)) * r)
                      for k in range(sides)])
    for k in range(sides):
        k2 = (k + 1) % sides
        f = bm.faces.new((rings[0][k], rings[0][k2], rings[1][k2], rings[1][k]))
        f.material_index = mat_index
        for loop, t in zip(f.loops, ((k / sides, 0), ((k + 1) / sides, 0), ((k + 1) / sides, length), (k / sides, length))):
            loop[uv].uv = t


def quad(bm, uv, corners, uvs, mat_index):
    vs = [bm.verts.new(c) for c in corners]
    f = bm.faces.new(vs)
    f.material_index = mat_index
    for loop, t in zip(f.loops, uvs):
        loop[uv].uv = t
    return f


def bent_normals(obj, axis_bias=0.55, up_bias=0.45, centre_z=None, mat_index=None):
    """Foliage normals point away from the tree axis (soft, volumetric lighting on cards)."""
    me = obj.data
    # Per polygon: only foliage polygons get bent normals; trunk keeps its geometric normal.
    me_normals = [None] * len(me.loops)
    for poly in me.polygons:
        for li in poly.loop_indices:
            p = me.vertices[me.loops[li].vertex_index].co
            if mat_index is not None and poly.material_index != mat_index:
                me_normals[li] = tuple(poly.normal)
                continue
            out = Vector((p.x, p.y, 0))
            out = out.normalized() if out.length > 1e-4 else Vector((0, 0, 1))
            n = (out * axis_bias + Vector((0, 0, up_bias))).normalized()
            me_normals[li] = tuple(n)
    me.normals_split_custom_set(me_normals)


# ---------------------------------------------------------------------------- conifers

def fir(name, seed, height, M, crown_base=2.5, width=0.24, whorl_gap=0.55, per_whorl=6, droop=0.35,
        lod=0, sparse_low=0.0):
    rnd = random.Random(seed)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    r_base = 0.32 * height / 18
    lean = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)) * 0.012 * height

    def bend(t):
        return lean * t * t

    trunk(bm, uv, Vector((0, 0, -0.3)), height + 0.3, r_base, 0.04, 10 if lod == 0 else 6, 0, bend)
    R = width * height
    gap = whorl_gap * (2.0 if lod == 1 else 1.0)
    n_per = per_whorl if lod == 0 else max(4, per_whorl - 2)
    z = crown_base
    whorl = 0
    while z < height - 0.6:
        t = (z - crown_base) / (height - crown_base)
        L = R * (1 - t) ** 0.85 * rnd.uniform(0.85, 1.1) + 0.35
        if t < 0.25 and rnd.random() < sparse_low:
            z += gap
            continue
        phase = rnd.uniform(0, 2 * math.pi)
        for b in range(n_per):
            a = phase + 2 * math.pi * b / n_per + rnd.uniform(-0.25, 0.25)
            d = Vector((math.cos(a), math.sin(a), 0))
            dz = -droop * (0.5 + 0.5 * (1 - t)) + rnd.uniform(-0.08, 0.08)
            axis = (d + Vector((0, 0, dz))).normalized()
            root = Vector((0, 0, z)) + bend(z / height) + d * r_base * (1 - t) * 0.8
            tip = root + axis * L * (1.25 if lod == 1 else 1.0)
            w = L * (0.62 if lod == 0 else 0.85)
            side = axis.cross(Vector((0, 0, 1))).normalized()
            tilts = (0.5, -0.5) if lod == 0 else (0.0,)
            for tilt in tilts:
                # V-shaped spray: two cards tilted up/down about the branch axis.
                s = (side * math.cos(tilt) + Vector((0, 0, 1)) * math.sin(tilt)).normalized() * (w / 2)
                drop = Vector((0, 0, -0.12 * L))
                quad(bm, uv, [root - s * 0.35, root + s * 0.35, tip + s + drop, tip - s + drop],
                     [(0.3, 0), (0.7, 0), (1, 1), (0, 1)], 1)
        # Filler: short upswept sprays hugging the trunk, so it hides inside the crown as in real firs.
        if lod == 0 and t > 0.08:
            for b in range(3):
                a = phase + 2 * math.pi * (b + 0.5) / 3
                d = Vector((math.cos(a), math.sin(a), 0))
                root = Vector((0, 0, z + gap * 0.5)) + bend(z / height)
                Lf = max(0.6, L * 0.45)
                tip = root + (d * 0.8 + Vector((0, 0, 0.6))).normalized() * Lf
                s = d.cross(Vector((0, 0, 1))).normalized() * (Lf * 0.35)
                quad(bm, uv, [root - s * 0.4, root + s * 0.4, tip + s, tip - s], [(0.3, 0), (0.7, 0), (1, 1), (0, 1)], 1)
        z += gap * rnd.uniform(0.85, 1.15)
        whorl += 1
    # Leader: two crossed cards at the top.
    top = Vector((0, 0, height - 1.2)) + bend(1.0)
    for a in (0, math.pi / 2):
        s = Vector((math.cos(a), math.sin(a), 0)) * 0.45
        quad(bm, uv, [top - s, top + s, top + s * 0.2 + Vector((0, 0, 1.6)), top - s * 0.2 + Vector((0, 0, 1.6))],
             [(0, 0), (1, 0), (0.6, 1), (0.4, 1)], 1)
    obj = new_obj(name, bm, [M["BarkFir"], M["FirNeedles"]])
    bent_normals(obj, 0.6, 0.4, mat_index=1)
    return obj


def impostor_cards(name, index, count, height, width, M):
    """Far LOD: two crossed vertical cards showing the rendered fir (atlas column `index`)."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    u0, u1 = index / count, (index + 1) / count
    for a in (0, math.pi / 2):
        s = Vector((math.cos(a), math.sin(a), 0)) * (width / 2)
        quad(bm, uv, [Vector((0, 0, 0)) - s, s, s + Vector((0, 0, height)), -s + Vector((0, 0, height))],
             [(u0, 0), (u1, 0), (u1, 1), (u0, 1)], 0)
    obj = new_obj(name, bm, [M["FirImpostor"]])
    bent_normals(obj, 0.5, 0.5)
    return obj


def snag(name, seed, height, M):
    rnd = random.Random(seed)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    lean = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)) * 0.03 * height
    trunk(bm, uv, Vector((0, 0, -0.3)), height, 0.3, 0.06, 8, 0, lambda t: lean * t * t)
    for i in range(16):
        z = rnd.uniform(2.5, height - 1.5)
        a = rnd.uniform(0, 2 * math.pi)
        d = Vector((math.cos(a), math.sin(a), rnd.uniform(-0.45, 0.05))).normalized()
        L = rnd.uniform(0.4, 1.6) * (1 - z / height * 0.6)
        p0 = Vector((0, 0, z)) + lean * (z / height) ** 2
        branch_tube(bm, uv, p0, p0 + d * L, 0.06, 0.015, 4, 0)
    obj = new_obj(name, bm, [M["BarkDead"]])
    return obj


def aspen(name, seed, height, M, lod=0):
    rnd = random.Random(seed)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    lean = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)) * 0.02 * height
    trunk(bm, uv, Vector((0, 0, -0.2)), height * 0.85, 0.16, 0.04, 8 if lod == 0 else 5, 0, lambda t: lean * t * t, uv_tile=1.0)
    # Leaf clusters: crossed cards in an oval crown on the upper half.
    count = 46 if lod == 0 else 14
    for i in range(count):
        t = rnd.random()
        z = height * (0.45 + 0.5 * t)
        rad = height * 0.16 * math.sin(math.pi * min(1.0, 0.15 + t)) * rnd.uniform(0.4, 1.0)
        a = rnd.uniform(0, 2 * math.pi)
        c = Vector((math.cos(a) * rad, math.sin(a) * rad, z)) + lean * (z / height) ** 2
        s = (1.6 if lod == 0 else 2.6) * rnd.uniform(0.8, 1.2)
        fa = rnd.uniform(0, math.pi)
        for k in (0, 1):
            ang = fa + k * math.pi / 2
            sv = Vector((math.cos(ang), math.sin(ang), 0)) * (s / 2)
            quad(bm, uv, [c - sv - Vector((0, 0, s / 2)), c + sv - Vector((0, 0, s / 2)), c + sv + Vector((0, 0, s / 2)), c - sv + Vector((0, 0, s / 2))],
                 [(0, 0), (1, 0), (1, 1), (0, 1)], 1)
    obj = new_obj(name, bm, [M["BarkAspen"], M["AspenLeaves"]])
    bent_normals(obj, 0.6, 0.4, mat_index=1)
    return obj


def log(name, seed, length, radius, M):
    rnd = random.Random(seed)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    rows = trunk(bm, uv, Vector((0, 0, 0)), length, radius, radius * 0.7, 10, 0)
    # caps (cut ends)
    for ring, r, z in (rows[0], rows[-1]):
        f = bm.faces.new(ring if z > 0 else list(reversed(ring)))
        f.material_index = 1
        for loop in f.loops:
            co = loop.vert.co
            loop[uv].uv = (co.x / (2 * r) + 0.5, co.y / (2 * r) + 0.5)
    for i in range(7):
        z = rnd.uniform(0.8, length - 0.8)
        a = rnd.uniform(0, 2 * math.pi)
        rr = radius * (1 - 0.3 * z / length)
        d = Vector((math.cos(a), math.sin(a), rnd.uniform(-0.2, 0.3))).normalized()
        p0 = Vector((math.cos(a) * rr * 0.7, math.sin(a) * rr * 0.7, z))
        branch_tube(bm, uv, p0, p0 + d * rnd.uniform(0.3, 0.9), 0.07, 0.02, 4, 0)
    obj = new_obj(name, bm, [M["BarkFir"], M["WoodEnd"]])
    # lay it down along +Y (Blender), resting on the ground
    for v in obj.data.vertices:
        x, y, z = v.co
        v.co = Vector((x, z - length / 2, y + radius * 0.85))
        v.co.z += 0.03 * math.sin(v.co.y * 0.7)
    return obj


def stump(name, seed, M):
    rnd = random.Random(seed)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    rows = trunk(bm, uv, Vector((0, 0, -0.2)), 1.0, 0.45, 0.4, 10, 0)
    ring, r, z = rows[-1]
    f = bm.faces.new(ring)
    f.material_index = 1
    for loop in f.loops:
        co = loop.vert.co
        loop[uv].uv = (co.x / (2 * r) + 0.5, co.y / (2 * r) + 0.5)
    for i in range(5):
        a = i * 2 * math.pi / 5 + rnd.uniform(-0.3, 0.3)
        d = Vector((math.cos(a), math.sin(a), -0.35)).normalized()
        p0 = Vector((math.cos(a) * 0.3, math.sin(a) * 0.3, 0.3))
        branch_tube(bm, uv, p0, p0 + d * rnd.uniform(0.7, 1.1), 0.16, 0.04, 5, 0)
    return new_obj(name, bm, [M["BarkFir"], M["WoodEnd"]])


def granite(name, seed, size, mat, subdiv=5, ratio=0.16):
    """Rounded granite boulder with a few flat joint faces (exfoliated, not layered)."""
    rnd = random.Random(seed)
    off = Vector((rnd.uniform(-90, 90), rnd.uniform(-90, 90), rnd.uniform(-90, 90)))
    planes = []
    for _ in range(rnd.randint(2, 4)):
        n = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.3, 0.6))).normalized()
        planes.append((n, rnd.uniform(0.55, 0.85)))
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    for v in bm.verts:
        p = v.co.copy()
        p *= 1 + 0.22 * fbm(p * 0.8 + off, 3) + 0.04 * fbm(p * 4.0 + off, 2)
        for n, dist in planes:          # joint faces: clip to planes, softly
            d = p.dot(n) - dist
            if d > 0:
                p -= n * d * 0.9
        p.z = max(p.z, -0.45)
        v.co = Vector((p.x * size[0], p.y * size[1], p.z * size[2]))
    obj = C.from_bmesh(name, bm, mat)
    decimate(obj, ratio)
    ground(obj, 0.1 * size[2])
    C.smooth_by_angle(obj, 45)
    return obj


def card(bm, uv, center, normal, up, w, h, mat_index=0):
    right = up.cross(normal).normalized() * (w / 2)
    upv = up.normalized() * h
    return quad(bm, uv, [center - right, center + right, center + right + upv, center - right + upv],
                [(0, 0), (1, 0), (1, 1), (0, 1)], mat_index)


def cards_plant(name, seed, mat, count, radius, height, card_size, flat=0.4, radial=False):
    rnd = random.Random(seed)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    for i in range(count):
        a = (2 * math.pi * i / count + rnd.uniform(-0.3, 0.3)) if radial else rnd.uniform(0, 2 * math.pi)
        r = radius * (0.15 if radial else math.sqrt(rnd.random()) * 0.6)
        base = Vector((math.cos(a) * r, math.sin(a) * r, 0))
        if radial:      # fern fronds: tilted outward from the centre
            out = Vector((math.cos(a), math.sin(a), 0))
            upv = (out * 0.75 + Vector((0, 0, 0.65))).normalized()
            normal = (Vector((0, 0, 1)) - out * 0.5).normalized()
            f = card(bm, uv, base, normal, upv, card_size * 0.9, height * rnd.uniform(0.85, 1.15))
        else:
            fa = a + rnd.uniform(-1.2, 1.2)
            facing = Vector((math.cos(fa), math.sin(fa), 0))
            upv = Vector((rnd.uniform(-flat, flat), rnd.uniform(-flat, flat), 1)).normalized()
            s = card_size * rnd.uniform(0.75, 1.15)
            card(bm, uv, base, facing, upv, s, s * (height / card_size) * rnd.uniform(0.8, 1.1))
    obj = new_obj(name, bm, [mat])
    bent_normals(obj, 0.5, 0.5)
    return obj


def lod_copy(obj, ratio):
    c = obj.copy()
    c.data = obj.data.copy()
    c.name = obj.name + "_LOD1"
    bpy.context.collection.objects.link(c)
    decimate(c, ratio)
    return c


# ---------------------------------------------------------------------------- impostor rendering

def image_material(mat, path, alpha=True):
    """Give a Blender material an image texture (for the impostor render only; Unity remaps by name)."""
    img = bpy.data.images.load(path, check_existing=True)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if alpha:
        nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    try:
        mat.blend_method = "CLIP"
    except Exception:
        pass


IMPOSTOR_TILE = (600, 1024)
IMPOSTOR_ASPECT = IMPOSTOR_TILE[0] / IMPOSTOR_TILE[1]


def render_impostors(trees, out_path, tile=IMPOSTOR_TILE):
    """Orthographic side renders of each tree under soft, even light -> one atlas, transparent background."""
    from PIL import Image
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 24
    sc.cycles.use_denoising = False
    sc.render.film_transparent = True
    sc.render.resolution_x, sc.render.resolution_y = tile
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    world = bpy.data.worlds.new("ImpostorWorld")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 1.0
    sc.world = world
    cam_data = bpy.data.cameras.new("ImpCam")
    cam_data.type = "ORTHO"
    cam = bpy.data.objects.new("ImpCam", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    tiles = []
    for t in trees:
        for o in sc.objects:
            if o.type == "MESH":
                o.hide_render = o is not t
        h = max(v.co.z for v in t.data.vertices) + 0.3
        cam_data.ortho_scale = h          # the frame's long side (height) spans the tree exactly
        cam.location = (0, -60, h / 2 - 0.3)
        cam.rotation_euler = (math.pi / 2, 0, 0)
        path = os.path.join(TMP, f"imp_{t.name}.png")
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        tiles.append(Image.open(path).convert("RGBA"))
    for o in sc.objects:
        o.hide_render = False
    atlas = Image.new("RGBA", (tile[0] * len(tiles), tile[1]), (0, 0, 0, 0))
    for i, im in enumerate(tiles):
        atlas.paste(im, (i * tile[0], 0))
    # Bleed colour into transparent texels (no dark halos when mip-mapped).
    import numpy as np
    from PIL import ImageFilter
    a = np.asarray(atlas).astype(np.float32)
    alpha = a[..., 3:4] / 255.0
    blur = np.asarray(Image.fromarray(a.astype(np.uint8)).filter(ImageFilter.GaussianBlur(8))).astype(np.float32)
    fill = np.where(blur[..., 3:4] > 4, blur[..., :3] / np.maximum(blur[..., 3:4] / 255.0, 1e-3), np.array([40, 60, 38]))
    rgb = a[..., :3] * alpha + np.clip(fill, 0, 255) * (1 - alpha)
    Image.fromarray(np.concatenate([rgb, a[..., 3:4]], -1).clip(0, 255).astype(np.uint8), "RGBA").save(out_path)
    bpy.data.objects.remove(cam)
    print("wrote", out_path)


def build():
    C.reset_scene()
    M = palette()
    objs = []
    fir_specs = [(16.0, dict(width=0.21, droop=0.32), 11), (20.0, dict(width=0.25, droop=0.38, sparse_low=0.3), 12),
                 (24.0, dict(width=0.19, droop=0.42, crown_base=4.0, sparse_low=0.5), 13)]
    firs = []
    for i, (h, kw, seed) in enumerate(fir_specs):
        f0 = fir(f"Fir_{i}", seed, h, M, **kw)
        f1 = fir(f"Fir_{i}_LOD1", seed, h, M, lod=1, **kw)
        firs.append((f0, h, kw.get("width", 0.22)))
        objs += [f0, f1]
    objs.append(snag("Snag_0", 21, 15.0, M))
    for i, h in enumerate((11.0, 14.0)):
        objs.append(aspen(f"Aspen_{i}", 31 + i, h, M))
        objs.append(aspen(f"Aspen_{i}_LOD1", 31 + i, h, M, lod=1))
    objs.append(log("Log_0", 41, 9.0, 0.42, M))
    objs.append(log("Log_1", 42, 6.0, 0.32, M))
    objs.append(stump("Stump_0", 43, M))
    for i, size in enumerate([(1.4, 1.1, 0.9), (2.2, 1.8, 1.4), (3.2, 2.6, 2.0), (1.0, 0.9, 0.6)]):
        b = granite(f"GBoulder_{i}", 50 + i, size, M["Granite"])
        objs += [b, lod_copy(b, 0.3)]
    objs.append(cards_plant("Fern_0", 61, M["Fern"], 9, 0.9, 0.9, 0.6, radial=True))
    objs.append(cards_plant("Fern_1", 62, M["Fern"], 7, 0.7, 0.7, 0.5, radial=True))
    objs.append(cards_plant("MeadowGrass_0", 71, M["MeadowGrass"], 7, 0.4, 0.6, 0.6, flat=0.15))
    objs.append(cards_plant("MeadowGrass_1", 72, M["MeadowGrass"], 10, 0.55, 0.75, 0.75, flat=0.2))
    objs.append(cards_plant("Flowers_0", 73, M["Wildflowers"], 8, 0.5, 0.6, 0.6, flat=0.2))
    objs.append(cards_plant("Bush_0", 74, M["BushLeaves"], 18, 1.4, 1.2, 1.1))

    # Impostors: render the LOD0 firs with their real textures, then build the crossed cards.
    image_material(M["FirNeedles"], os.path.join(FOLIAGE_DIR, "FirBranch.png"))
    image_material(M["BarkFir"], os.path.join(MATS_DIR, "BarkFir_albedo.png"), alpha=False)
    render_impostors([f for f, _, _ in firs], os.path.join(FOLIAGE_DIR, "FirImpostors.png"))
    for i, (f, h, w) in enumerate(firs):
        objs.append(impostor_cards(f"Fir_{i}_LOD2", i, len(firs), h + 0.3, (h + 0.3) * IMPOSTOR_ASPECT, M))
    return objs


if __name__ == "__main__":
    objs = build()
    for o in objs:
        print(f"{o.name:16s} tris={C.tri_count(o):5d}  size={tuple(round(d, 1) for d in o.dimensions)}")
    C.export_fbx(objs, C.path_in_repo("Assets", "Models", "Props", "ForestProps.fbx"))
