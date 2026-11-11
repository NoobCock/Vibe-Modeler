"""
templates/materials.py
Vibe-Modeler 物理级 PBR 材质与风格着色器生成库

包含：
1. 真实物理扫描 PBR 贴图着色器（首选，支持三向投影 Box Mapping 免展 UV，自动配置 Non-Color）
2. 生图贴图一体化着色器（接收自带生图生成的图片，在节点树内自动提取 Roughness 粗糙度与 Bump 凹凸）
3. 纯程序化着色器（玻璃、哑光石膏、双层油漆剥落、低多边形纯平色块，仅供极简风格或离线保底）
"""

MATERIAL_SNIPPETS = {
    # 1. 【写实首选】真实物理扫描 PBR 贴图材质（支持 Box Mapping 三向免展 UV 投影）
    "setup_pbr_texture_material": """
def setup_pbr_texture_material(
    name="Mat_PBR_Textured",
    diffuse_path=None,
    roughness_path=None,
    normal_path=None,
    displacement_path=None,
    base_color=(0.8, 0.8, 0.8, 1.0),
    roughness_default=0.5,
    metallic=0.0,
    mapping_scale=(1.0, 1.0, 1.0),
    use_box_mapping=True,
    blend_factor=0.2
):
    \"\"\"
    构建真实扫描 PBR 材质。
    粗糙度与法线贴图自动设为 Non-Color 色彩空间。
    默认开启 Box Mapping（三向盒式投影），物体无需展开 UV 即可均匀平铺。
    \"\"\"
    import bpy, os
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    
    out_node = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness_default
    bsdf.inputs["Base Color"].default_value = base_color
    links.new(bsdf.outputs["BSDF"], out_node.inputs["Surface"])
    
    tex_coord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = mapping_scale
    
    coord_output = tex_coord.outputs["Object"] if use_box_mapping else tex_coord.outputs["UV"]
    links.new(coord_output, mapping.inputs["Vector"])
    
    # 颜色贴图 (sRGB)
    if diffuse_path and os.path.exists(diffuse_path):
        img_diff = bpy.data.images.load(diffuse_path)
        node_diff = nodes.new("ShaderNodeTexImage")
        node_diff.image = img_diff
        if use_box_mapping:
            node_diff.projection = 'BOX'
            node_diff.projection_blend = blend_factor
        links.new(mapping.outputs["Vector"], node_diff.inputs["Vector"])
        links.new(node_diff.outputs["Color"], bsdf.inputs["Base Color"])
        
    # 表面微反光粗糙度贴图 (必须为 Non-Color)
    if roughness_path and os.path.exists(roughness_path):
        img_rough = bpy.data.images.load(roughness_path)
        img_rough.colorspace_settings.name = 'Non-Color'
        node_rough = nodes.new("ShaderNodeTexImage")
        node_rough.image = img_rough
        if use_box_mapping:
            node_rough.projection = 'BOX'
            node_rough.projection_blend = blend_factor
        links.new(mapping.outputs["Vector"], node_rough.inputs["Vector"])
        links.new(node_rough.outputs["Color"], bsdf.inputs["Roughness"])
        
    # 物理凹凸法线贴图 (必须为 Non-Color)
    if normal_path and os.path.exists(normal_path):
        img_norm = bpy.data.images.load(normal_path)
        img_norm.colorspace_settings.name = 'Non-Color'
        node_norm = nodes.new("ShaderNodeTexImage")
        node_norm.image = img_norm
        if use_box_mapping:
            node_norm.projection = 'BOX'
            node_norm.projection_blend = blend_factor
        node_norm_map = nodes.new("ShaderNodeNormalMap")
        node_norm_map.inputs["Strength"].default_value = 1.0
        links.new(mapping.outputs["Vector"], node_norm.inputs["Vector"])
        links.new(node_norm.outputs["Color"], node_norm_map.inputs["Color"])
        links.new(node_norm_map.outputs["Normal"], bsdf.inputs["Normal"])
    elif displacement_path and os.path.exists(displacement_path):
        # 凹凸高度贴图 (Non-Color)
        img_disp = bpy.data.images.load(displacement_path)
        img_disp.colorspace_settings.name = 'Non-Color'
        node_disp = nodes.new("ShaderNodeTexImage")
        node_disp.image = img_disp
        if use_box_mapping:
            node_disp.projection = 'BOX'
            node_disp.projection_blend = blend_factor
        node_bump = nodes.new("ShaderNodeBump")
        node_bump.inputs["Strength"].default_value = 0.2
        links.new(mapping.outputs["Vector"], node_disp.inputs["Vector"])
        links.new(node_disp.outputs["Color"], node_bump.inputs["Height"])
        links.new(node_bump.outputs["Normal"], bsdf.inputs["Normal"])
        
    return mat
""",

    # 2. 【特化写实首选】生图贴图一体化接入材质（将 AI 生成图片自动转化为带凹凸与粗糙度的 PBR）
    "setup_generated_texture_material": """
def setup_generated_texture_material(
    name="Mat_AIGenerated_PBR",
    image_path=None,
    bump_strength=0.15,
    roughness_min=0.2,
    roughness_max=0.85,
    mapping_scale=(1.0, 1.0, 1.0),
    use_box_mapping=True,
    blend_factor=0.2
):
    \"\"\"
    将单张生图生成的纹理载入 Blender，并在着色器内部自动衍生为 PBR：
    通过 RGBToBW 分离明暗，同时驱动表面微观凹凸（Bump）与不同区域的反光差异（Roughness）。
    \"\"\"
    import bpy, os
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    
    out_node = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out_node.inputs["Surface"])
    
    if not image_path or not os.path.exists(image_path):
        bsdf.inputs["Base Color"].default_value = (0.7, 0.7, 0.7, 1.0)
        return mat
        
    tex_coord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = mapping_scale
    
    coord_output = tex_coord.outputs["Object"] if use_box_mapping else tex_coord.outputs["UV"]
    links.new(coord_output, mapping.inputs["Vector"])
    
    # 加载主图
    img = bpy.data.images.load(image_path)
    tex_node = nodes.new("ShaderNodeTexImage")
    tex_node.image = img
    if use_box_mapping:
        tex_node.projection = 'BOX'
        tex_node.projection_blend = blend_factor
    links.new(mapping.outputs["Vector"], tex_node.inputs["Vector"])
    links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])
    
    # 提取黑白信号驱动物理质感
    rgb2bw = nodes.new("ShaderNodeRGBToBW")
    links.new(tex_node.outputs["Color"], rgb2bw.inputs["Color"])
    
    # 粗糙度阶梯映射（亮部微光暗部哑光）
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.1
    ramp.color_ramp.elements[0].color = (roughness_min, roughness_min, roughness_min, 1.0)
    ramp.color_ramp.elements[1].position = 0.9
    ramp.color_ramp.elements[1].color = (roughness_max, roughness_max, roughness_max, 1.0)
    links.new(rgb2bw.outputs["Val"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Roughness"])
    
    # 微观表面凹凸
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = bump_strength
    bump.inputs["Distance"].default_value = 0.05
    links.new(rgb2bw.outputs["Val"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    
    return mat
""",

    # 3. 物理级 PBR：磨砂玻璃与高透色散
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
    
    if "Transmission Weight" in bsdf.inputs:
        bsdf.inputs["Transmission Weight"].default_value = 1.0
    elif "Transmission" in bsdf.inputs:
        bsdf.inputs["Transmission"].default_value = 1.0
        
    # EEVEE 透明与折射设置（兼容 4.2+ 与 5.x；5.0 起 shadow_method 已删除）
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = 'DITHERED'
        if hasattr(mat, "use_raytrace_refraction"):
            mat.use_raytrace_refraction = True
        if hasattr(mat, "use_transparent_shadow"):
            mat.use_transparent_shadow = True
    elif hasattr(mat, "blend_method"):
        mat.blend_method = 'BLEND'
    if hasattr(mat, "shadow_method"):
        mat.shadow_method = 'NONE'
    return mat
""",

    # 4. 物理级 PBR：极简哑光石膏与黏土（适用于超现实极简空间）
    "pbr_matte_plaster_clay": """
def create_pbr_matte_plaster_material(name="Mat_PBR_Plaster", color=(0.94, 0.82, 0.80, 1.0)):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if not bsdf: return mat
    
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = 0.92
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.2
        
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 120.0
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.02
    
    mat.node_tree.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    mat.node_tree.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat
""",

    # 5. 纯平低多边形着色（Low-Poly Flat Shading）
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
