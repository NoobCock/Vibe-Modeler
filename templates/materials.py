"""
templates/materials.py
Vibe-Modeler 唯美程序化材质生成器集合
包含赛璐珞卡通、次表面玉石、发光水晶、磨砂玻璃与微噪波金属等
"""

MATERIAL_SNIPPETS = {
    "toon_cel": """
def create_toon_cel_material(name="Mat_Toon", base_rgb=(0.95, 0.45, 0.35), shadow_rgb=(0.25, 0.15, 0.3), rim_rgb=(1.0, 0.9, 0.6)):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    
    out = nodes.new('ShaderNodeOutputMaterial')
    diffuse = nodes.new('ShaderNodeBsdfDiffuse')
    s2rgb = nodes.new('ShaderNodeShaderToRGB')
    ramp = nodes.new('ShaderNodeValToRGB')
    
    # 2-step color ramp
    ramp.color_ramp.interpolation = 'CONSTANT'
    ramp.color_ramp.elements[0].position = 0.42
    ramp.color_ramp.elements[0].color = (*shadow_rgb, 1.0)
    ramp.color_ramp.elements[1].position = 0.44
    ramp.color_ramp.elements[1].color = (*base_rgb, 1.0)
    
    # Rim light
    fresnel = nodes.new('ShaderNodeLayerWeight')
    fresnel.inputs['Blend'].default_value = 0.25
    rim_ramp = nodes.new('ShaderNodeValToRGB')
    rim_ramp.color_ramp.interpolation = 'CONSTANT'
    rim_ramp.color_ramp.elements[0].position = 0.65
    rim_ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
    rim_ramp.color_ramp.elements[1].position = 0.68
    rim_ramp.color_ramp.elements[1].color = (*rim_rgb, 1.0)
    
    add = nodes.new('ShaderNodeMix')
    add.data_type = 'RGBA'
    add.blend_type = 'ADD'
    add.inputs['Factor'].default_value = 1.0
    
    mat.node_tree.links.new(diffuse.outputs['BSDF'], s2rgb.inputs['Shader'])
    mat.node_tree.links.new(s2rgb.outputs['Color'], ramp.inputs['Fac'])
    mat.node_tree.links.new(fresnel.outputs['Facing'], rim_ramp.inputs['Fac'])
    mat.node_tree.links.new(ramp.outputs['Color'], add.inputs[6])
    mat.node_tree.links.new(rim_ramp.outputs['Color'], add.inputs[7])
    
    emit = nodes.new('ShaderNodeEmission')
    mat.node_tree.links.new(add.outputs[2], emit.inputs['Color'])
    mat.node_tree.links.new(emit.outputs['Emission'], out.inputs['Surface'])
    return mat
""",

    "glowing_crystal": """
def create_glowing_crystal_material(name="Mat_Crystal", color=(0.2, 0.8, 1.0), strength=3.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    
    out = nodes.new('ShaderNodeOutputMaterial')
    glass = nodes.new('ShaderNodeBsdfGlass')
    glass.inputs['Color'].default_value = (*color, 1.0)
    glass.inputs['Roughness'].default_value = 0.08
    glass.inputs['IOR'].default_value = 1.54
    
    emit = nodes.new('ShaderNodeEmission')
    emit.inputs['Color'].default_value = (*color, 1.0)
    emit.inputs['Strength'].default_value = strength
    
    mix = nodes.new('ShaderNodeMixShader')
    mix.inputs['Fac'].default_value = 0.25
    
    mat.node_tree.links.new(glass.outputs['BSDF'], mix.inputs[1])
    mat.node_tree.links.new(emit.outputs['Emission'], mix.inputs[2])
    mat.node_tree.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    return mat
""",

    "frosted_water": """
def create_water_surface_material(name="Mat_Water", deep_color=(0.05, 0.2, 0.4, 1.0)):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = deep_color
        bsdf.inputs['Roughness'].default_value = 0.05
        if 'Transmission Weight' in bsdf.inputs:
            bsdf.inputs['Transmission Weight'].default_value = 0.95
        elif 'Transmission' in bsdf.inputs:
            bsdf.inputs['Transmission'].default_value = 0.95
        bsdf.inputs['IOR'].default_value = 1.333
    return mat
"""
}
