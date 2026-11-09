"""
templates/materials.py
Vibe-Modeler 物理级程序化 PBR 材质与风格到着色器生成库
内置无需外部贴图的物理微质感着色器（微水泥做旧、磨砂玻璃色散、金属拉丝、极简石膏、双层剥落铁锈、水面）
以及经典二次元赛璐珞与纯平低多边形着色器
"""

MATERIAL_SNIPPETS = {
    # 1. 物理级 PBR：微水泥/风化混凝土
    "pbr_concrete_weathered": """
def create_pbr_concrete_material(name="Mat_PBR_Concrete", base_color=(0.75, 0.74, 0.72, 1.0), roughness_base=0.85):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if not bsdf: return mat
    
    # 细微噪波驱动粗糙度微起伏与微表面凹凸
    tex_noise = nodes.new("ShaderNodeTexNoise")
    tex_noise.inputs["Scale"].default_value = 45.0
    tex_noise.inputs["Detail"].default_value = 4.0
    tex_noise.inputs["Roughness"].default_value = 0.6
    
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.3
    ramp.color_ramp.elements[0].color = (roughness_base - 0.15, roughness_base - 0.15, roughness_base - 0.15, 1.0)
    ramp.color_ramp.elements[1].position = 0.8
    ramp.color_ramp.elements[1].color = (roughness_base + 0.1, roughness_base + 0.1, roughness_base + 0.1, 1.0)
    
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    bump.inputs["Distance"].default_value = 0.05
    
    mat.node_tree.links.new(tex_noise.outputs["Fac"], ramp.inputs["Fac"])
    mat.node_tree.links.new(ramp.outputs["Color"], bsdf.inputs["Roughness"])
    mat.node_tree.links.new(tex_noise.outputs["Fac"], bump.inputs["Height"])
    mat.node_tree.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    
    bsdf.inputs["Base Color"].default_value = base_color
    return mat
""",

    # 2. 物理级 PBR：磨砂玻璃与高透色散
    "pbr_frosted_dispersion_glass": """
def create_pbr_frosted_glass_material(name="Mat_PBR_FrostedGlass", tint_color=(0.95, 0.98, 1.0, 1.0), roughness=0.12, ior=1.52):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if not bsdf: return mat
    
    bsdf.inputs["Base Color"].default_value = tint_color
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["IOR"].default_value = ior
    
    # 兼容 Blender 4.x / 5.x Transmission 命名
    if "Transmission Weight" in bsdf.inputs:
        bsdf.inputs["Transmission Weight"].default_value = 1.0
    elif "Transmission" in bsdf.inputs:
        bsdf.inputs["Transmission"].default_value = 1.0
        
    mat.blend_method = 'BLEND'
    mat.shadow_method = 'NONE'
    return mat
""",

    # 3. 物理级 PBR：阳极氧化拉丝金属
    "pbr_brushed_metal": """
def create_pbr_brushed_metal_material(name="Mat_PBR_Metal", color=(0.88, 0.89, 0.90, 1.0), roughness=0.22):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if not bsdf: return mat
    
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = roughness
    
    # 细微拉丝 Bump
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 80.0
    noise.inputs["Detail"].default_value = 6.0
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.04
    
    mat.node_tree.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    mat.node_tree.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat
""",

    # 4. 物理级 PBR：极简哑光石膏与黏土（适用于超现实主义建筑）
    "pbr_matte_plaster_clay": """
def create_pbr_matte_plaster_material(name="Mat_PBR_Plaster", color=(0.94, 0.82, 0.80, 1.0)):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if not bsdf: return mat
    
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = 0.92  # 几乎完全哑光漫射
    bsdf.inputs["Specular IOR Level"].default_value = 0.2 if "Specular IOR Level" in bsdf.inputs else 0.2
    
    # 极微弱粉墙质感
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 120.0
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.02
    
    mat.node_tree.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    mat.node_tree.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat
""",

    # 5. 物理级 PBR：双层油漆剥落与底层锈蚀（适用于日系动漫写实风）
    "pbr_peeling_paint_rust": """
def create_pbr_paint_rust_material(name="Mat_PaintRust", paint_color=(0.92, 0.92, 0.94, 1.0), rust_color=(0.35, 0.12, 0.05, 1.0)):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf_paint = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf_paint.inputs["Base Color"].default_value = paint_color
    bsdf_paint.inputs["Roughness"].default_value = 0.4
    
    bsdf_rust = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf_rust.inputs["Base Color"].default_value = rust_color
    bsdf_rust.inputs["Roughness"].default_value = 0.88
    bsdf_rust.inputs["Metallic"].default_value = 0.65
    
    # 噪波斑驳遮罩
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 15.0
    noise.inputs["Detail"].default_value = 8.0
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.52
    ramp.color_ramp.elements[1].position = 0.58
    
    mix = nodes.new("ShaderNodeMixShader")
    
    mat.node_tree.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    mat.node_tree.links.new(ramp.outputs["Color"], mix.inputs["Fac"])
    mat.node_tree.links.new(bsdf_paint.outputs["BSDF"], mix.inputs[1])
    mat.node_tree.links.new(bsdf_rust.outputs["BSDF"], mix.inputs[2])
    mat.node_tree.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat
""",

    # 6. 纯平低多边形着色（Low-Poly Flat Shading）
    "flat_shaded_lowpoly": """
def create_flat_lowpoly_material(name="Mat_LowPoly", color=(0.9, 0.45, 0.35, 1.0), roughness=0.7):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = roughness
    return mat
"""
}
