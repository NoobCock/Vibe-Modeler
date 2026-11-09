"""
asset_loader.py
Vibe-Modeler 资产生成与加载调度器
提供：
1. 100% 离线自给的程序化着色器与几何体创建函数
2. 按需下载公共 CC0 (如 Poly Haven) HDRI 与 PBR 材质的轻量安全工具
"""

import os
import json
import urllib.request
import urllib.error

CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets_cache"))

def ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)
    return CACHE_DIR

def download_cc0_asset(asset_id, asset_type="hdris", resolution="1k"):
    """
    通过 Poly Haven 开放公共 API 检索并下载轻量 CC0 资产 (1k 极速预览)，
    若网络不可达或超时则返回 None 并平滑降级为程序化节点。
    """
    ensure_cache_dir()
    api_url = f"https://api.polyhaven.com/files/{asset_id}"
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "Vibe-Modeler/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        
        target_url = None
        target_ext = "exr" if asset_type == "hdris" else "jpg"
        
        if asset_type == "hdris" and "hdri" in data:
            hdri_entry = data["hdri"].get(resolution) or data["hdri"].get("1k")
            if hdri_entry:
                target_url = hdri_entry.get("exr", {}).get("url") or hdri_entry.get("hdr", {}).get("url")
                target_ext = "exr" if "exr" in hdri_entry else "hdr"
        
        if not target_url:
            return None

        local_filename = f"{asset_id}_{resolution}.{target_ext}"
        local_path = os.path.join(CACHE_DIR, local_filename)
        if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            return local_path

        # Download file
        req_file = urllib.request.Request(target_url, headers={"User-Agent": "Vibe-Modeler/1.0"})
        with urllib.request.urlopen(req_file, timeout=15) as resp_file, open(local_path, "wb") as out_f:
            out_f.write(resp_file.read())
        return local_path
    except Exception as e:
        print(f"[AssetLoader] CC0 资产加载降级为程序化: {e}")
        return None

# ==========================================
# Blender 内部程序化代码生成模板（供 Subagent 直接复用）
# ==========================================

PROCEDURAL_SKY_BPY = """
def setup_procedural_sky(world, sky_type="sunset", warm_tint=(1.0, 0.65, 0.4, 1.0), cool_tint=(0.15, 0.25, 0.55, 1.0)):
    world.use_nodes = True
    tree = world.node_tree
    tree.nodes.clear()
    
    node_out = tree.nodes.new(type="ShaderNodeOutputWorld")
    node_bg = tree.nodes.new(type="ShaderNodeBackground")
    node_ramp = tree.nodes.new(type="ShaderNodeValToRGB")
    node_coord = tree.nodes.new(type="ShaderNodeTexCoord")
    
    # Gradient background
    node_ramp.color_ramp.elements[0].color = cool_tint
    node_ramp.color_ramp.elements[1].color = warm_tint
    node_bg.inputs["Strength"].default_value = 1.2
    
    tree.links.new(node_coord.outputs["Generated"], node_ramp.inputs["Fac"])
    tree.links.new(node_ramp.outputs["Color"], node_bg.inputs["Color"])
    tree.links.new(node_bg.outputs["Background"], node_out.inputs["Surface"])
"""

PROCEDURAL_TOON_SHADER_BPY = """
def create_procedural_toon_material(mat_name, base_color=(0.9, 0.35, 0.35, 1.0), shadow_color=(0.2, 0.1, 0.25, 1.0), rim_color=(1.0, 0.95, 0.7, 1.0)):
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    
    node_out = nodes.new(type="ShaderNodeOutputMaterial")
    node_diff = nodes.new(type="ShaderNodeBsdfDiffuse")
    node_s2rgb = nodes.new(type="ShaderNodeShaderToRGB")
    node_ramp = nodes.new(type="ShaderNodeValToRGB")
    node_mix = nodes.new(type="ShaderNodeMix")
    node_mix.data_type = 'RGBA'
    
    # 2-step cel ramp
    node_ramp.color_ramp.interpolation = 'CONSTANT'
    node_ramp.color_ramp.elements[0].position = 0.45
    node_ramp.color_ramp.elements[0].color = shadow_color
    node_ramp.color_ramp.elements[1].position = 0.5
    node_ramp.color_ramp.elements[1].color = base_color
    
    # Rim light with fresnel
    node_layer = nodes.new(type="ShaderNodeLayerWeight")
    node_layer.inputs["Blend"].default_value = 0.3
    node_rim_ramp = nodes.new(type="ShaderNodeValToRGB")
    node_rim_ramp.color_ramp.interpolation = 'CONSTANT'
    node_rim_ramp.color_ramp.elements[0].position = 0.6
    node_rim_ramp.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    node_rim_ramp.color_ramp.elements[1].color = rim_color
    
    node_add = nodes.new(type="ShaderNodeMix")
    node_add.data_type = 'RGBA'
    node_add.blend_type = 'ADD'
    node_add.inputs["Factor"].default_value = 0.8
    
    mat.node_tree.links.new(node_diff.outputs["BSDF"], node_s2rgb.inputs["Shader"])
    mat.node_tree.links.new(node_s2rgb.outputs["Color"], node_ramp.inputs["Fac"])
    mat.node_tree.links.new(node_layer.outputs["Facing"], node_rim_ramp.inputs["Fac"])
    mat.node_tree.links.new(node_ramp.outputs["Color"], node_add.inputs[6])
    mat.node_tree.links.new(node_rim_ramp.outputs["Color"], node_add.inputs[7])
    
    node_emit = nodes.new(type="ShaderNodeEmission")
    mat.node_tree.links.new(node_add.outputs[2], node_emit.inputs["Color"])
    mat.node_tree.links.new(node_emit.outputs["Emission"], node_out.inputs["Surface"])
    return mat
"""

PROCEDURAL_VOLUMETRIC_FOG_BPY = """
def create_volumetric_fog(density=0.03, color=(0.8, 0.85, 0.95, 1.0)):
    world = bpy.context.scene.world
    if not world or not world.node_tree: return
    nodes = world.node_tree.nodes
    node_out = nodes.get("World Output") or nodes.new(type="ShaderNodeOutputWorld")
    node_vol = nodes.new(type="ShaderNodeVolumeScatter")
    node_vol.inputs["Density"].default_value = density
    node_vol.inputs["Color"].default_value = color
    node_vol.inputs["Anisotropy"].default_value = 0.4
    world.node_tree.links.new(node_vol.outputs["Volume"], node_out.inputs["Volume"])
"""
