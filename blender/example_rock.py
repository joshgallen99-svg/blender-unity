"""Example asset script: builds a low-poly rock and exports it for Unity.

Run:  python blender/example_rock.py   (needs the `bpy` package)
Output: Assets/Models/Rock.fbx
"""
import os, random
import bpy

OUT = os.path.join(os.path.dirname(__file__), "..", "Assets", "Models", "Rock.fbx")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1)
rock = bpy.context.active_object
rock.name = "Rock"
random.seed(4)
for v in rock.data.vertices:
    v.co *= random.uniform(0.8, 1.15)
rock.scale = (1.2, 0.8, 1.0)
bpy.ops.object.transform_apply(scale=True)

mat = bpy.data.materials.new("RockMat")
mat.diffuse_color = (0.42, 0.40, 0.38, 1)
rock.data.materials.append(mat)

# Unity is Y-up; these settings give correct orientation and 1 unit = 1 metre.
bpy.ops.export_scene.fbx(filepath=os.path.abspath(OUT), use_selection=False,
                         apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Z', axis_up='Y',
                         bake_space_transform=True, mesh_smooth_type='FACE')
print("Exported", os.path.abspath(OUT))
