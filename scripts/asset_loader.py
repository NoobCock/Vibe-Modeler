"""
asset_loader.py
Vibe-Modeler 资产与材质调度器
提供：
1. 免费高质量 CC0 PBR 贴图集下载与缓存（基于 Poly Haven 开放 API，涵盖混凝土、木材、锈铁、岩石等）
2. 免费 CC0 3D 模型搜索与下载（树、岩石、家具、杂物等，.blend 格式连同贴图）
3. 天空环境光（HDRI）下载
4. 将生图生成的单张纹理自动转换为完整 PBR 贴图（粗糙度图 Roughness、凹凸图 Bump、法线图 Normal）
5. 离线兜底天空、二次元赛璐珞着色器与体积雾
"""

import os
import json
import urllib.request
import urllib.error

try:
    from PIL import Image, ImageOps, ImageFilter
    import numpy as np
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets_cache"))

def ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)
    return CACHE_DIR

# ==========================================
# 常见常用 CC0 写实材质预设（仅作快捷参考，不作为唯一样本）
# ==========================================
COMMON_PBR_PRESETS = {
    "concrete": "brushed_concrete_03",
    "concrete_rough": "concrete_layers_02",
    "wood": "weathered_planks",
    "wood_dark": "dark_wood",
    "metal_rust": "green_metal_rust",
    "metal_plate": "metal_plate",
    "rock": "aerial_rocks_01",
    "rock_grass": "aerial_grass_rock",
    "sand": "aerial_sand",
    "plaster": "clay_plaster",
    "brick": "brick_floor_003"
}

# 常见天空环境光（HDRI）预设（仅作快捷参考，可用 search_cc0_assets("hdris", ...) 搜更多）
COMMON_HDRI_PRESETS = {
    "midday_clouds": "kloofendal_48d_partly_cloudy_puresky",
    "dusk": "qwantani_dusk_2_puresky",
    "sunset": "industrial_sunset_02_puresky",
    "night_moon": "moonlit_golf",
    "studio": "studio_small_09",
}

_API_HEADERS = {"User-Agent": "Vibe-Modeler/1.0"}
_CATALOG_MEMO = {}

def _get_json(url, timeout=8):
    req = urllib.request.Request(url, headers=_API_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def _download_file(url, out_path, timeout=20):
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return out_path
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    req = urllib.request.Request(url, headers=_API_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as rf, open(out_path, "wb") as wf:
        wf.write(rf.read())
    return out_path

def search_cc0_assets(asset_type="models", keywords=None, categories=None, limit=15):
    """
    在 Poly Haven 资产库里按关键词搜索，返回 [(asset_id, 名称, 分类列表), ...]。
    asset_type: "models"（3D 模型）/ "textures"（贴图）/ "hdris"（天空环境光）
    keywords:   英文关键词列表，匹配资产 id、名称、标签，任一命中即可，如 ["boat", "ship"]
    categories: 分类过滤，如 ["trees"]、["rocks"]、["furniture"]、["sunrise-sunset"]
    预设表只是常用快捷方式，场景需要别的东西时应当先用这个函数搜，不要只在预设里挑。
    """
    try:
        if asset_type not in _CATALOG_MEMO:
            _CATALOG_MEMO[asset_type] = _get_json(f"https://api.polyhaven.com/assets?type={asset_type}")
        catalog = _CATALOG_MEMO[asset_type]
    except Exception as e:
        print(f"[AssetLoader] 资产目录获取失败: {e}")
        return []

    kws = [k.lower() for k in (keywords or [])]
    cats = [c.lower() for c in (categories or [])]
    results = []
    for asset_id, info in catalog.items():
        name = str(info.get("name", asset_id))
        tags = [t.lower() for t in info.get("tags", [])]
        acats = [c.lower() for c in info.get("categories", [])]
        haystack = " ".join([asset_id.lower(), name.lower()] + tags)
        if kws and not any(k in haystack for k in kws):
            continue
        if cats and not any(c in acats for c in cats):
            continue
        results.append((asset_id, name, info.get("categories", []), info.get("download_count", 0)))
    results.sort(key=lambda r: -r[3])
    return [(r[0], r[1], r[2]) for r in results[:limit]]

def download_cc0_model(asset_id, resolution="1k"):
    """
    下载 Poly Haven 的免费 3D 模型（.blend 格式，连同贴图一起），返回本地 .blend 绝对路径。
    贴图按 .blend 里记录的相对路径（textures/...）放好，导入后材质能直接找到图。
    失败返回 None，调用方应退回手写建模。
    """
    ensure_cache_dir()
    model_dir = os.path.join(CACHE_DIR, "models", asset_id)
    try:
        data = _get_json(f"https://api.polyhaven.com/files/{asset_id}")
        blend_res = data.get("blend", {})
        entry = blend_res.get(resolution) or blend_res.get("1k") or (next(iter(blend_res.values())) if blend_res else None)
        if not entry or "blend" not in entry:
            print(f"[AssetLoader] {asset_id} 没有 .blend 版本")
            return None
        info = entry["blend"]
        blend_path = os.path.join(model_dir, os.path.basename(info["url"]))
        _download_file(info["url"], blend_path)
        for rel_path, inc in info.get("include", {}).items():
            _download_file(inc["url"], os.path.join(model_dir, *rel_path.split("/")))
        return blend_path
    except Exception as e:
        print(f"[AssetLoader] 模型 {asset_id} 下载失败: {e}")
        return None

def download_pbr_texture_set(asset_id, resolution="1k", maps=None):
    """
    通过 Poly Haven 开放公共 API 检索并下载轻量真实扫描 CC0 PBR 贴图（1k 快速预览）。
    下载并缓存：Diffuse（颜色）、Roughness（表面微反光粗糙度）、nor_gl（物理凹凸法线）、Displacement（置换凹凸）。
    返回各贴图在本地磁盘的绝对路径字典：{'diffuse': ..., 'roughness': ..., 'normal': ...}
    若网络不可达或超时则返回已有缓存或已下载的贴图，调用方可平滑降级。
    """
    ensure_cache_dir()
    if maps is None:
        maps = ["diffuse", "roughness", "normal", "displacement"]

    # 若输入的是预设别名，自动映射为 asset_id
    real_asset_id = COMMON_PBR_PRESETS.get(asset_id, asset_id)
    asset_dir = os.path.join(CACHE_DIR, real_asset_id)
    os.makedirs(asset_dir, exist_ok=True)

    cached_paths = {}
    missing_maps = []
    for m in maps:
        candidate_jpg = os.path.join(asset_dir, f"{m}_{resolution}.jpg")
        candidate_png = os.path.join(asset_dir, f"{m}_{resolution}.png")
        if os.path.exists(candidate_jpg) and os.path.getsize(candidate_jpg) > 0:
            cached_paths[m] = candidate_jpg
        elif os.path.exists(candidate_png) and os.path.getsize(candidate_png) > 0:
            cached_paths[m] = candidate_png
        else:
            missing_maps.append(m)

    if not missing_maps:
        return cached_paths

    api_url = f"https://api.polyhaven.com/files/{real_asset_id}"
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "Vibe-Modeler/1.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        map_candidates = {
            "diffuse": ["Diffuse", "diff", "diffuse"],
            "roughness": ["Rough", "rough", "roughness"],
            "normal": ["nor_gl", "nor_dx", "normal", "nor"],
            "displacement": ["Displacement", "disp", "displacement"],
            "metallic": ["metal", "metallic", "Metal"]
        }

        for m in missing_maps:
            keys = map_candidates.get(m, [m])
            target_dict = None
            for k in keys:
                if k in data:
                    target_dict = data[k]
                    break
            if not target_dict:
                continue

            res_entry = target_dict.get(resolution) or target_dict.get("1k") or (list(target_dict.values())[0] if target_dict else None)
            if not res_entry or not isinstance(res_entry, dict):
                continue

            file_info = res_entry.get("jpg") or res_entry.get("png") or res_entry.get("exr")
            if not file_info:
                continue

            url = file_info.get("url")
            ext = "jpg" if "jpg" in res_entry else ("png" if "png" in res_entry else "exr")
            out_path = os.path.join(asset_dir, f"{m}_{resolution}.{ext}")

            req_f = urllib.request.Request(url, headers={"User-Agent": "Vibe-Modeler/1.0"})
            with urllib.request.urlopen(req_f, timeout=12) as rf, open(out_path, "wb") as wf:
                wf.write(rf.read())
            cached_paths[m] = out_path

        return cached_paths
    except Exception as e:
        print(f"[AssetLoader] 获取 CC0 PBR 贴图集 {real_asset_id} 异常: {e}")
        return cached_paths

def convert_image_to_pbr_maps(input_image_path, output_dir=None, strength=2.0):
    """
    将单张图片（例如自带生图能力生成的彩色纹理）就地转换为完整的 PBR 贴图集：
    1. diffuse: 原图
    2. roughness: 基于明暗对比提取的粗糙度灰度图（亮部偏哑光，暗部偏微反光）
    3. bump: 高频边缘凹凸图
    4. normal: 切线空间标准法线图（RGB 格式，R=Nx, G=Ny, B=Nz）
    返回绝对路径字典：{'diffuse': ..., 'roughness': ..., 'bump': ..., 'normal': ...}
    若当前 Python 环境缺少 PIL/numpy，则返回原图路径字典，Blender 节点树可直接处理。
    """
    if not os.path.exists(input_image_path):
        return None
    if not output_dir:
        output_dir = os.path.dirname(input_image_path)
    os.makedirs(output_dir, exist_ok=True)

    diffuse_path = input_image_path
    if not PIL_AVAILABLE:
        print("[AssetLoader] 当前环境无 PIL/numpy，跳过离线生图贴图转换，由 Blender 内部节点衍生 PBR。")
        return {"diffuse": diffuse_path}

    # 2. 粗糙度灰度贴图
    gray = ImageOps.grayscale(img)
    roughness_img = ImageOps.autocontrast(gray, cutoff=2)
    roughness_path = os.path.join(output_dir, f"{base_name}_roughness.png")
    roughness_img.save(roughness_path)

    # 3. 凹凸贴图
    bump_img = gray.filter(ImageFilter.EDGE_ENHANCE_MORE)
    bump_path = os.path.join(output_dir, f"{base_name}_bump.png")
    bump_img.save(bump_path)

    # 4. 切线空间标准法线图 (RGB: (Nx*0.5+0.5, Ny*0.5+0.5, Nz*0.5+0.5))
    arr = np.asarray(gray, dtype=np.float32) / 255.0
    dy, dx = np.gradient(arr)
    dx = dx * strength * 4.0
    dy = dy * strength * 4.0
    dz = np.ones_like(arr)
    norm = np.sqrt(dx**2 + dy**2 + dz**2)
    nx = -dx / norm
    ny = -dy / norm
    nz = dz / norm

    r = ((nx * 0.5 + 0.5) * 255).astype(np.uint8)
    g = ((ny * 0.5 + 0.5) * 255).astype(np.uint8)
    b = ((nz * 0.5 + 0.5) * 255).astype(np.uint8)
    normal_img = Image.fromarray(np.stack([r, g, b], axis=-1))
    normal_path = os.path.join(output_dir, f"{base_name}_normal.png")
    normal_img.save(normal_path)

    return {
        "diffuse": diffuse_path,
        "roughness": roughness_path,
        "bump": bump_path,
        "normal": normal_path
    }

def download_cc0_asset(asset_id, asset_type="hdris", resolution="1k"):
    """
    通过 Poly Haven API 下载轻量 HDRI 环境天空图（1k 极速预览），失败则平滑降级。
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

        req_file = urllib.request.Request(target_url, headers={"User-Agent": "Vibe-Modeler/1.0"})
        with urllib.request.urlopen(req_file, timeout=15) as resp_file, open(local_path, "wb") as out_f:
            out_f.write(resp_file.read())
        return local_path
    except Exception as e:
        print(f"[AssetLoader] CC0 环境光加载降级: {e}")
        return None

# ==========================================
# Blender 内部着色器复用模板
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
    
    node_ramp.color_ramp.interpolation = 'CONSTANT'
    node_ramp.color_ramp.elements[0].position = 0.45
    node_ramp.color_ramp.elements[0].color = shadow_color
    node_ramp.color_ramp.elements[1].position = 0.5
    node_ramp.color_ramp.elements[1].color = base_color
    
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
