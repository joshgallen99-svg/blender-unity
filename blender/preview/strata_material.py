"""Blender approximation of the in-game sandstone look (world-space strata bands) for previews."""
import bpy


def strata_material(name="StrataPreview"):
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = nodes.get("Principled BSDF")
    geo = nodes.new("ShaderNodeNewGeometry")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(geo.outputs["Position"], sep.inputs[0])
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.02
    links.new(geo.outputs["Position"], noise.inputs["Vector"])
    mul = nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY_ADD"
    mul.inputs[1].default_value = 0.33
    links.new(sep.outputs["Z"], mul.inputs[0])
    links.new(noise.outputs["Fac"], mul.inputs[2])
    frac = nodes.new("ShaderNodeMath")
    frac.operation = "FRACT"
    links.new(mul.outputs[0], frac.inputs[0])
    ramp = nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.interpolation = "EASE"
    cols = [(0.0, (0.42, 0.10, 0.035)), (0.3, (0.55, 0.19, 0.07)), (0.5, (0.36, 0.08, 0.03)),
            (0.7, (0.62, 0.28, 0.12)), (0.86, (0.70, 0.45, 0.26)), (1.0, (0.42, 0.10, 0.035))]
    cr.elements[0].position, cr.elements[0].color = cols[0][0], (*cols[0][1], 1)
    cr.elements[1].position, cr.elements[1].color = cols[-1][0], (*cols[-1][1], 1)
    for pos, c in cols[1:-1]:
        e = cr.elements.new(pos)
        e.color = (*c, 1)
    links.new(frac.outputs[0], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.85
    return mat
