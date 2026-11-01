"""Shared helpers for the asset scripts.

Conventions (match Unity after FBX export):
  * Blender units are metres, Z is up.
  * Vehicles and props face Blender -Y, which becomes Unity +Z (forward).
  * Blender +X becomes Unity -X, so a vehicle's right-hand side is Blender -X.
  (Verified by Assets/Tests/EditMode/GeneratedAssetTests.cs after import.)
"""
import math
import os

import bpy  # must come first: makes bmesh/mathutils importable
import bmesh
from mathutils import Matrix, Vector

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def path_in_repo(*parts):
    p = os.path.join(REPO, *parts)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


# ---------------------------------------------------------------- scene / materials

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


_materials = {}


def material(name, color, metallic=0.0, roughness=0.5, emission=None, emission_strength=1.0):
    """Principled material. Names matter: Unity maps them to its own material library."""
    if name in _materials and _materials[name].name in bpy.data.materials:
        return _materials[name]
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    mat.diffuse_color = (*color, 1.0)
    bsdf = mat.node_tree.nodes.get("Principled BSDF") if mat.node_tree else None
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
        if emission:
            bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
            bsdf.inputs["Emission Strength"].default_value = emission_strength
    _materials[name] = mat
    return mat


# ---------------------------------------------------------------- mesh construction

def _link(name, mesh):
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def from_bmesh(name, bm, mat=None):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = _link(name, mesh)
    if mat:
        obj.data.materials.append(mat)
    return obj


def hull(name, bottom, top, mat=None, bevel=0.0, segments=2):
    """Eight-corner solid. bottom/top: 4 (x, y, z) points each, same winding."""
    bm = bmesh.new()
    vb = [bm.verts.new(p) for p in bottom]
    vt = [bm.verts.new(p) for p in top]
    bm.faces.new(vb[::-1])
    bm.faces.new(vt)
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((vb[i], vb[j], vt[j], vt[i]))
    obj = from_bmesh(name, bm, mat)
    if bevel > 0:
        add_bevel(obj, bevel, segments)
    return obj


def box(name, size, center, mat=None, bevel=0.0, segments=2):
    sx, sy, sz = (s / 2 for s in size)
    cx, cy, cz = center
    bottom = [(cx - sx, cy - sy, cz - sz), (cx + sx, cy - sy, cz - sz),
              (cx + sx, cy + sy, cz - sz), (cx - sx, cy + sy, cz - sz)]
    top = [(x, y, cz + sz) for x, y, _ in bottom]
    return hull(name, bottom, top, mat, bevel, segments)


def box_between(name, x0, x1, y0, y1, z0, z1, mat=None, bevel=0.0, segments=2):
    return box(name, (x1 - x0, y1 - y0, z1 - z0), ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2),
               mat, bevel, segments)


def cylinder(name, radius, depth, center, axis="X", verts=24, mat=None, bevel=0.0, segments=2, radius2=None):
    """Capped cylinder (or cone frustum with radius2) along the given axis."""
    bm = bmesh.new()
    r2 = radius if radius2 is None else radius2
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=verts,
                          radius1=radius, radius2=r2, depth=depth)
    rot = {"X": Matrix.Rotation(math.radians(90), 4, "Y"),
           "Y": Matrix.Rotation(math.radians(90), 4, "X"),
           "Z": Matrix.Identity(4)}[axis]
    bmesh.ops.transform(bm, matrix=Matrix.Translation(center) @ rot, verts=bm.verts)
    obj = from_bmesh(name, bm, mat)
    if bevel > 0:
        add_bevel(obj, bevel, segments)
    return obj


def tube(name, p0, p1, radius, mat=None, verts=12):
    """Cylinder between two points."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=verts,
                          radius1=radius, radius2=radius, depth=d.length)
    rot = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=Matrix.Translation((p0 + p1) / 2) @ rot, verts=bm.verts)
    return from_bmesh(name, bm, mat)


def tube_path(name, points, radius, mat=None, verts=12):
    parts = [tube(f"{name}_{i}", points[i], points[i + 1], radius, mat, verts) for i in range(len(points) - 1)]
    for p in points[1:-1]:
        parts.append(sphere(f"{name}_j", radius, p, mat, 1))
    return join(parts, name)


def sphere(name, radius, center, mat=None, subdiv=2):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=radius)
    bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts)
    return from_bmesh(name, bm, mat)


def face_panel(name, corners, u0, u1, v0, v1, offset, thickness, mat=None, bevel=0.0, inward=None):
    """Thin slab laid on a quad face.

    corners: (p00, p10, p11, p01) of the face, u along p00->p10, v along p00->p01.
    The slab sits `offset` outside the face and is `thickness` thick.
    inward: a point inside the solid, used to orient the face normal outwards.
    """
    p00, p10, p11, p01 = (Vector(c) for c in corners)

    def at(u, v):
        return p00.lerp(p10, u).lerp(p01.lerp(p11, u), v)

    n = (p10 - p00).cross(p01 - p00).normalized()
    if inward is not None and n.dot(Vector(inward) - p00) > 0:
        n = -n
    base = [at(u0, v0), at(u1, v0), at(u1, v1), at(u0, v1)]
    inner = [b + n * offset for b in base]
    outer = [b + n * (offset + thickness) for b in base]
    return hull(name, inner, outer, mat, bevel)


def add_bevel(obj, width, segments=2, angle=40):
    mod = obj.modifiers.new("Bevel", "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(angle)
    mod.use_clamp_overlap = True
    return mod


def boolean_cut(obj, cutters):
    for c in cutters:
        mod = obj.modifiers.new("Cut", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.object = c
        try:
            mod.solver = "EXACT"
        except Exception:
            pass
    apply_modifiers(obj)
    for c in cutters:
        bpy.data.objects.remove(c, do_unlink=True)


def apply_modifiers(obj):
    if not obj.modifiers:
        return obj
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    mesh = bpy.data.meshes.new_from_object(ev)
    old = obj.data
    obj.modifiers.clear()
    obj.data = mesh
    bpy.data.meshes.remove(old)
    return obj


def join(objs, name):
    objs = [o for o in objs if o is not None]
    for o in objs:
        apply_modifiers(o)
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    out = bpy.context.view_layer.objects.active
    out.name = name
    out.data.name = name
    return out


def smooth_by_angle(obj, angle_deg=35):
    """Smooth shading with hard edges above the angle (no modifiers, exports cleanly)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    limit = math.radians(angle_deg)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if not e.is_manifold or e.calc_face_angle(0.0) > limit:
            e.smooth = False
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def mirror_x(obj, name=None):
    """Duplicate an object mirrored across X (left <-> right)."""
    dup = obj.copy()
    dup.data = obj.data.copy()
    bpy.context.scene.collection.objects.link(dup)
    dup.name = name or obj.name + "_mx"
    bm = bmesh.new()
    bm.from_mesh(dup.data)
    bmesh.ops.scale(bm, vec=(-1, 1, 1), verts=bm.verts)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(dup.data)
    bm.free()
    return dup


def tri_count(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


# ---------------------------------------------------------------- export

def export_fbx(objs, path):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=True,
        object_types={"MESH", "EMPTY"},
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="Z",   # with Unity's FBX import this maps Blender -Y to Unity +Z
        axis_up="Y",
        bake_space_transform=True,
        use_mesh_modifiers=True,
        mesh_smooth_type="OFF",
        add_leaf_bones=False,
        bake_anim=False,
    )
    print("Exported", path)


def empty(name, location):
    obj = bpy.data.objects.new(name, None)
    obj.location = location
    bpy.context.scene.collection.objects.link(obj)
    return obj
