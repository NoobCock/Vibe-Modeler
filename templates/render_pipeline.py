"""
templates/render_pipeline.py
Vibe-Modeler 渲染管线模板：渲染引擎、GPU 光线追踪、色彩管理、真实天空环境光（HDRI）、泛光后期

兼容 Blender 4.2 ~ 5.x：
- 4.2~4.x 的 EEVEE 引擎名是 BLENDER_EEVEE_NEXT，5.0 起改回 BLENDER_EEVEE，这里两个都试
- 5.0 起合成器去掉了 scene.node_tree 和 Composite 节点，改成 scene.compositing_node_group + 节点组输出
- 5.0 起 Glare 节点参数从属性变成了输入插槽（Type / Threshold / Strength / Size）
- 5.0 起材质去掉了 shadow_method
"""

RENDER_PIPELINE_SNIPPETS = {
    # 1. EEVEE 预览引擎（兼容新旧引擎名）
    "set_eevee_engine": """
def set_eevee_engine(samples=64, use_raytracing=True):
    scene = bpy.context.scene
    for engine_id in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            scene.render.engine = engine_id
            break
        except Exception:
            continue
    eevee = scene.eevee
    if hasattr(eevee, "taa_render_samples"):
        eevee.taa_render_samples = samples
    if hasattr(eevee, "use_raytracing"):
        eevee.use_raytracing = use_raytracing
    if hasattr(eevee, "use_shadows"):
        eevee.use_shadows = True
    return scene.render.engine
""",

    # 2. Cycles 光线追踪 + 自动选 GPU + 降噪（正式出图用）
    "setup_cycles_gpu": """
def setup_cycles_gpu(samples=256, adaptive_threshold=0.02, use_denoise=True):
    '''
    依次尝试 OPTIX / CUDA / HIP / ONEAPI / METAL，找到能用的显卡就开 GPU 渲染，否则退回 CPU。
    返回实际使用的设备类型字符串。
    '''
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    chosen = None
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for compute_type in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
            try:
                prefs.compute_device_type = compute_type
            except Exception:
                continue
            if hasattr(prefs, "refresh_devices"):
                prefs.refresh_devices()
            else:
                prefs.get_devices()
            matched = [d for d in prefs.devices if d.type == compute_type]
            if matched:
                for d in prefs.devices:
                    d.use = (d.type == compute_type)
                chosen = compute_type
                break
    except Exception as e:
        print(f"[RenderPipeline] GPU 探测失败，退回 CPU: {e}")

    cyc = scene.cycles
    cyc.device = "GPU" if chosen else "CPU"
    cyc.samples = samples
    if hasattr(cyc, "use_adaptive_sampling"):
        cyc.use_adaptive_sampling = True
        cyc.adaptive_threshold = adaptive_threshold
    if hasattr(cyc, "use_denoising"):
        cyc.use_denoising = use_denoise
        try:
            cyc.denoiser = "OPTIX" if chosen == "OPTIX" else "OPENIMAGEDENOISE"
        except Exception:
            pass
        if hasattr(cyc, "denoising_use_gpu"):
            cyc.denoising_use_gpu = bool(chosen)
    # 防止水面、玻璃反射里出现白色噪点
    if hasattr(cyc, "sample_clamp_indirect"):
        cyc.sample_clamp_indirect = 10.0
    print(f"[RenderPipeline] Cycles 设备: {chosen or 'CPU'}")
    return chosen or "CPU"
""",

    # 3. 色彩管理：AgX 防止亮部死白
    "setup_color_management": """
def setup_color_management(view="AgX", look="AgX - Base Contrast", exposure=0.0, gamma=1.0):
    '''
    view 可选：AgX（默认，亮部过渡自然）/ Khronos PBR Neutral（颜色更忠实）/ Filmic / Standard（二次元纯色块推荐）
    look 示例：AgX - Base Contrast / AgX - Medium High Contrast / AgX - Punchy
    '''
    vs = bpy.context.scene.view_settings
    for v in (view, "AgX", "Filmic", "Standard"):
        try:
            vs.view_transform = v
            break
        except Exception:
            continue
    for lk in (look, "AgX - Base Contrast", "Medium Contrast", "None"):
        try:
            vs.look = lk
            break
        except Exception:
            continue
    vs.exposure = exposure
    vs.gamma = gamma
    return vs.view_transform, vs.look
""",

    # 4. 真实天空环境光（HDRI）
    "setup_hdri_world": """
def setup_hdri_world(hdri_path, strength=1.0, rotation_deg=0.0, camera_background=None, camera_background_strength=1.0):
    '''
    用 HDRI 照亮场景，金属、玻璃、水面能反射出真实天空。
    camera_background：传入 RGBA 时，镜头直接看到的背景换成这个颜色，但照明和反射仍来自 HDRI
                       （适合想要纯色或深色背景、又想保留真实反射的画面）。
    hdri_path 不存在时返回 None，调用方应改用程序化天空。
    '''
    import os
    if not hdri_path or not os.path.exists(hdri_path):
        return None
    scene = bpy.context.scene
    world = scene.world or bpy.data.worlds.new("VM_World")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputWorld")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(rotation_deg))
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(hdri_path, check_existing=True)
    bg_hdri = nt.nodes.new("ShaderNodeBackground")
    bg_hdri.inputs["Strength"].default_value = strength

    nt.links.new(coord.outputs["Generated"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], env.inputs["Vector"])
    nt.links.new(env.outputs["Color"], bg_hdri.inputs["Color"])

    if camera_background is None:
        nt.links.new(bg_hdri.outputs["Background"], out.inputs["Surface"])
    else:
        bg_cam = nt.nodes.new("ShaderNodeBackground")
        bg_cam.inputs["Color"].default_value = camera_background
        bg_cam.inputs["Strength"].default_value = camera_background_strength
        light_path = nt.nodes.new("ShaderNodeLightPath")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(light_path.outputs["Is Camera Ray"], mix.inputs["Fac"])
        nt.links.new(bg_hdri.outputs["Background"], mix.inputs[1])
        nt.links.new(bg_cam.outputs["Background"], mix.inputs[2])
        nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return world
""",

    # 5. 泛光后期（Glare 节点，兼容 4.x / 5.x 合成器）
    "setup_bloom_glow": """
def setup_bloom_glow(glare_type="Bloom", threshold=1.0, strength=0.5, size=0.5):
    '''
    给逆光、发光体、高光加柔和光晕。glare_type 可选 Bloom / Fog Glow / Streaks / Ghosts。
    threshold 越低越多东西发光；strength 控制光晕亮度；size 控制光晕扩散范围（0~1）。
    '''
    return setup_compositor_post_process({
        "glare": {"glare_type": glare_type, "threshold": threshold, "strength": strength, "size": size}
    })
""",

    # 6. 全管线电影级合成器后期处理（7 大模块 + 风格预设 + MultiLayer EXR 缓存）
    "setup_compositor_post_process": """
POST_PROCESS_PRESETS = {
    "cinematic_warm": {
        "mist": {"start": 6.0, "depth": 55.0, "falloff": "QUADRATIC", "color": (0.86, 0.76, 0.66, 1.0), "strength": 0.22},
        "ao_boost": {"strength": 0.25},
        "glare": {"glare_type": "Bloom", "threshold": 0.85, "strength": 0.35, "size": 0.55},
        "color_balance": {"lift": (0.98, 0.99, 1.03, 1.0), "gamma": (1.02, 1.00, 0.97, 1.0), "gain": (1.05, 1.01, 0.95, 1.0), "factor": 0.65},
        "vignette": {"strength": 0.28, "scale": 0.82, "feather": 0.22},
        "lens_distortion": {"dispersion": 0.008, "distortion": -0.006},
        "sharpen": {"strength": 0.12},
    },
    "sterile_cold_brutalist": {
        "mist": {"start": 8.0, "depth": 68.0, "falloff": "QUADRATIC", "color": (0.78, 0.85, 0.92, 1.0), "strength": 0.32},
        "ao_boost": {"strength": 0.38},
        "glare": {"glare_type": "Fog Glow", "threshold": 0.92, "strength": 0.28, "size": 0.45},
        "color_balance": {"lift": (0.95, 0.98, 1.04, 1.0), "gamma": (0.98, 1.00, 1.03, 1.0), "gain": (0.98, 1.01, 1.05, 1.0), "factor": 0.70},
        "contrast_saturation": {"brightness": 0.0, "contrast": 8.0, "saturation": 0.88},
        "vignette": {"strength": 0.34, "scale": 0.80, "feather": 0.24},
        "lens_distortion": {"dispersion": 0.010, "distortion": -0.008},
        "sharpen": {"strength": 0.16},
    },
    "liminal_dream": {
        "mist": {"start": 4.0, "depth": 38.0, "falloff": "LINEAR", "color": (0.88, 0.86, 0.78, 1.0), "strength": 0.35},
        "ao_boost": {"strength": 0.22},
        "glare": {"glare_type": "Bloom", "threshold": 0.72, "strength": 0.48, "size": 0.68},
        "color_balance": {"lift": (1.02, 1.01, 0.96, 1.0), "gamma": (1.02, 1.01, 0.97, 1.0), "gain": (1.03, 1.00, 0.93, 1.0), "factor": 0.60},
        "vignette": {"strength": 0.36, "scale": 0.76, "feather": 0.26},
        "lens_distortion": {"dispersion": 0.015, "distortion": -0.012},
    },
    "surreal_ethereal_glow": {
        "mist": {"start": 6.0, "depth": 50.0, "falloff": "QUADRATIC", "color": (0.14, 0.22, 0.38, 1.0), "strength": 0.24},
        "ao_boost": {"strength": 0.18},
        "glare": {"glare_type": "Bloom", "threshold": 0.78, "strength": 0.46, "size": 0.62},
        "streaks": {"glare_type": "Streaks", "threshold": 1.15, "strength": 0.24, "size": 0.50, "streaks": 6},
        "color_balance": {"lift": (0.96, 0.98, 1.05, 1.0), "gamma": (1.00, 1.02, 1.05, 1.0), "gain": (1.02, 1.01, 1.06, 1.0), "factor": 0.65},
        "vignette": {"strength": 0.30, "scale": 0.80, "feather": 0.25},
        "lens_distortion": {"dispersion": 0.012, "distortion": -0.008},
    },
    "high_contrast_chiaroscuro": {
        "ao_boost": {"strength": 0.42},
        "glare": {"glare_type": "Fog Glow", "threshold": 0.95, "strength": 0.30, "size": 0.50},
        "contrast_saturation": {"brightness": -2.0, "contrast": 14.0, "saturation": 0.92},
        "vignette": {"strength": 0.42, "scale": 0.75, "feather": 0.25},
        "sharpen": {"strength": 0.15},
    },
    "clean_anime": {
        "glare": {"glare_type": "Bloom", "threshold": 0.82, "strength": 0.38, "size": 0.58},
        "contrast_saturation": {"brightness": 1.5, "contrast": 6.0, "saturation": 1.12},
        "vignette": {"strength": 0.16, "scale": 0.88, "feather": 0.22},
    },
    "bright_luminous_daylight": {
        "mist": {"start": 32.0, "depth": 190.0, "falloff": "QUADRATIC", "color": (0.78, 0.91, 0.99, 1.0), "strength": 0.14},
        "ao_boost": {"strength": 0.12},
        "glare": {"glare_type": "Bloom", "threshold": 0.88, "strength": 0.30, "size": 0.62},
        "color_balance": {"lift": (1.00, 1.01, 1.02, 1.0), "gamma": (1.01, 1.02, 1.02, 1.0), "gain": (1.02, 1.03, 1.02, 1.0), "factor": 0.45},
        "contrast_saturation": {"brightness": 1.0, "contrast": 4.0, "saturation": 1.08},
        "vignette": {"strength": 0.08, "scale": 0.92, "feather": 0.28},
    },
    "vibrant_futuristic_gloss": {
        "mist": {"start": 24.0, "depth": 170.0, "falloff": "QUADRATIC", "color": (0.72, 0.89, 1.0, 1.0), "strength": 0.16},
        "ao_boost": {"strength": 0.16},
        "glare": {"glare_type": "Bloom", "threshold": 0.84, "strength": 0.36, "size": 0.58},
        "color_balance": {"lift": (0.98, 1.01, 1.03, 1.0), "gamma": (1.01, 1.02, 1.03, 1.0), "gain": (1.03, 1.04, 1.03, 1.0), "factor": 0.50},
        "contrast_saturation": {"brightness": 0.5, "contrast": 6.0, "saturation": 1.10},
        "vignette": {"strength": 0.12, "scale": 0.90, "feather": 0.25},
        "lens_distortion": {"dispersion": 0.005, "distortion": -0.003},
    },
}

def _resolve_post_process_config(post_process):
    if not post_process:
        return {}
    if isinstance(post_process, str):
        return dict(POST_PROCESS_PRESETS.get(post_process, {}))
    if isinstance(post_process, dict):
        preset_name = post_process.get("preset")
        merged = dict(POST_PROCESS_PRESETS.get(preset_name, {})) if preset_name else {}
        for k, v in post_process.items():
            if k == "preset":
                continue
            if isinstance(v, dict) and isinstance(merged.get(k), dict):
                sub = dict(merged[k])
                sub.update(v)
                merged[k] = sub
            else:
                merged[k] = v
        return merged
    return {}

def setup_compositor_post_process(post_process=None, raw_cache_dir=None, source_image_path=None):
    '''
    构建 Blender Compositor 电影级后处理节点管线（兼容 Blender 4.x 与 5.x）。
    - post_process: 可传预设名（如 "sterile_cold_brutalist", "cinematic_warm", "liminal_dream", "surreal_ethereal_glow"）
      或自定义 dict（支持含 "preset" 键再叠加局部覆盖）。
    - raw_cache_dir: 若传入目录路径且处于实时 3D 渲染阶段，自动挂载 MultiLayer OpenEXR 输出节点保存 raw_cache.exr
      （包含 Image / Mist / AO 三通道，供后续 br.run_post_process 秒级反复调色与加后期）。
    - source_image_path: 若传入已渲染好的 raw_cache.exr 或 render.png 路径，则直接以 CompositorNodeImage 作为输入源，
      无需重新跑 3D 光追，约 1 秒即可输出全新后期成片。
    '''
    import os
    scene = bpy.context.scene
    cfg = _resolve_post_process_config(post_process)
    if not cfg and not raw_cache_dir and not source_image_path:
        return None

    use_5x = hasattr(scene, "compositing_node_group")
    if use_5x:
        tree = bpy.data.node_groups.new("VM_Compositor", "CompositorNodeTree")
        tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        scene.compositing_node_group = tree
    else:
        scene.use_nodes = True
        tree = scene.node_tree
        tree.nodes.clear()

    def _mix_rgba(sock_a, sock_b, blend_type="MIX", factor=0.5):
        if use_5x:
            mx = tree.nodes.new("ShaderNodeMix")
            mx.data_type = 'RGBA'
            mx.blend_type = blend_type
            if isinstance(factor, (int, float)):
                mx.inputs[0].default_value = float(factor)
            else:
                tree.links.new(factor, mx.inputs[0])
            if isinstance(sock_a, (tuple, list)):
                mx.inputs[6].default_value = tuple(sock_a)
            else:
                tree.links.new(sock_a, mx.inputs[6])
            if isinstance(sock_b, (tuple, list)):
                mx.inputs[7].default_value = tuple(sock_b)
            else:
                tree.links.new(sock_b, mx.inputs[7])
            return mx.outputs[2]
        else:
            mx = tree.nodes.new("CompositorNodeMixRGB")
            mx.blend_type = blend_type
            if isinstance(factor, (int, float)):
                mx.inputs[0].default_value = float(factor)
            else:
                tree.links.new(factor, mx.inputs[0])
            if isinstance(sock_a, (tuple, list)):
                mx.inputs[1].default_value = tuple(sock_a)
            else:
                tree.links.new(sock_a, mx.inputs[1])
            if isinstance(sock_b, (tuple, list)):
                mx.inputs[2].default_value = tuple(sock_b)
            else:
                tree.links.new(sock_b, mx.inputs[2])
            return mx.outputs["Image"]

    def _configure_glare(gl, gcfg):
        gtype = gcfg.get("glare_type", "Bloom")
        thresh = float(gcfg.get("threshold", 0.9))
        strength = float(gcfg.get("strength", 0.4))
        size = float(gcfg.get("size", 0.5))
        if "Type" in gl.inputs:  # Blender 5.x
            try:
                gl.inputs["Type"].default_value = gtype
            except Exception:
                gl.inputs["Type"].default_value = "Bloom"
            gl.inputs["Threshold"].default_value = thresh
            if "Strength" in gl.inputs:
                gl.inputs["Strength"].default_value = strength
            if "Size" in gl.inputs:
                gl.inputs["Size"].default_value = size
            if "Tint" in gl.inputs and "tint" in gcfg:
                gl.inputs["Tint"].default_value = tuple(gcfg["tint"])
            if "Saturation" in gl.inputs and "saturation" in gcfg:
                gl.inputs["Saturation"].default_value = float(gcfg["saturation"])
            if "Streaks" in gl.inputs and "streaks" in gcfg:
                gl.inputs["Streaks"].default_value = int(gcfg["streaks"])
        else:  # Blender 4.x
            try:
                gl.glare_type = gtype.upper().replace(" ", "_")
            except Exception:
                gl.glare_type = "FOG_GLOW"
            gl.threshold = thresh
            if hasattr(gl, "mix"):
                gl.mix = strength - 1.0
            if hasattr(gl, "size"):
                gl.size = max(1, min(9, int(round(size * 9))))

    # 1. 输入源：离线 EXR/PNG 图像 或 实时 Render Layers
    if source_image_path and os.path.exists(source_image_path):
        src = tree.nodes.new("CompositorNodeImage")
        src.image = bpy.data.images.load(source_image_path, check_existing=False)
        img_sock = src.outputs.get("Image") or src.outputs.get("Combined") or src.outputs[0]
        mist_sock = src.outputs.get("Mist")
        ao_sock = src.outputs.get("AO") or src.outputs.get("Ambient Occlusion")
    else:
        vl = bpy.context.view_layer
        need_mist = bool(raw_cache_dir or cfg.get("mist"))
        need_ao = bool(raw_cache_dir or cfg.get("ao_boost"))
        if need_mist and hasattr(vl, "use_pass_mist"):
            vl.use_pass_mist = True
            mcfg = cfg.get("mist") if isinstance(cfg.get("mist"), dict) else {}
            if scene.world and hasattr(scene.world, "mist_settings"):
                ms = scene.world.mist_settings
                ms.start = float(mcfg.get("start", 6.0))
                ms.depth = float(mcfg.get("depth", 55.0))
                falloff = str(mcfg.get("falloff", "QUADRATIC")).upper()
                if falloff in ("QUADRATIC", "LINEAR", "INVERSE_QUADRATIC"):
                    ms.falloff = falloff
        if need_ao and hasattr(vl, "use_pass_ambient_occlusion"):
            vl.use_pass_ambient_occlusion = True

        src = tree.nodes.new("CompositorNodeRLayers")
        img_sock = src.outputs["Image"]
        mist_sock = src.outputs.get("Mist")
        ao_sock = src.outputs.get("Ambient Occlusion") or src.outputs.get("AO")

        if raw_cache_dir:
            try:
                os.makedirs(raw_cache_dir, exist_ok=True)
                of = tree.nodes.new("CompositorNodeOutputFile")
                of.format.file_format = 'OPEN_EXR_MULTILAYER'
                of.format.color_depth = '16'
                if hasattr(of, "directory"):  # Blender 5.x
                    of.directory = raw_cache_dir
                    of.file_name = "raw_cache"
                    of.file_output_items.clear()
                    of.file_output_items.new('RGBA', 'Image')
                    tree.links.new(img_sock, of.inputs['Image'])
                    if mist_sock is not None:
                        of.file_output_items.new('FLOAT', 'Mist')
                        tree.links.new(mist_sock, of.inputs['Mist'])
                    if ao_sock is not None:
                        of.file_output_items.new('RGBA', 'AO')
                        tree.links.new(ao_sock, of.inputs['AO'])
                else:  # Blender 4.x
                    of.base_path = os.path.join(raw_cache_dir, "raw_cache")
                    of.file_slots.clear()
                    s_img = of.file_slots.new("Image")
                    tree.links.new(img_sock, s_img)
                    if mist_sock is not None:
                        s_mist = of.file_slots.new("Mist")
                        tree.links.new(mist_sock, s_mist)
                    if ao_sock is not None:
                        s_ao = of.file_slots.new("AO")
                        tree.links.new(ao_sock, s_ao)
            except Exception as _e:
                print(f"[RenderPipeline] EXR 缓存节点配置警告: {_e}")

    cur = img_sock

    # 2. AO 接触阴影强化 (Ambient Occlusion Boost)
    ao_cfg = cfg.get("ao_boost")
    if isinstance(ao_cfg, dict) and ao_sock is not None and float(ao_cfg.get("strength", 0.0)) > 0:
        cur = _mix_rgba(cur, ao_sock, blend_type="MULTIPLY", factor=min(1.0, float(ao_cfg.get("strength", 0.25))))

    # 3. 景深雾气 / 空气透视混色 (Mist Depth Atmospheric Fog)
    mist_cfg = cfg.get("mist")
    if isinstance(mist_cfg, dict) and mist_sock is not None and float(mist_cfg.get("strength", 0.0)) > 0:
        fog_color = tuple(mist_cfg.get("color", (0.80, 0.85, 0.92, 1.0)))
        if len(fog_color) == 3:
            fog_color = (fog_color[0], fog_color[1], fog_color[2], 1.0)
        strength = min(1.0, max(0.0, float(mist_cfg.get("strength", 0.25))))
        math_m = tree.nodes.new("ShaderNodeMath" if use_5x else "CompositorNodeMath")
        math_m.operation = 'MULTIPLY'
        tree.links.new(mist_sock, math_m.inputs[0])
        math_m.inputs[1].default_value = strength
        cur = _mix_rgba(cur, fog_color, blend_type="MIX", factor=math_m.outputs[0])

    # 4. 多模式高光泛光与星芒 (Glare / Bloom / Fog Glow / Streaks)
    for glare_key in ("bloom", "glare", "streaks"):
        gcfg = cfg.get(glare_key)
        if isinstance(gcfg, dict) and float(gcfg.get("strength", 0.4)) > 0:
            gl = tree.nodes.new("CompositorNodeGlare")
            _configure_glare(gl, gcfg)
            tree.links.new(cur, gl.inputs["Image"])
            cur = gl.outputs["Image"]

    # 5. 电影级调色 (Color Balance: Lift / Gamma / Gain + Temperature / Tint)
    cb_cfg = cfg.get("color_balance")
    if isinstance(cb_cfg, dict):
        cb = tree.nodes.new("CompositorNodeColorBalance")
        factor = float(cb_cfg.get("factor", 0.65))
        if "Factor" in cb.inputs:
            cb.inputs["Factor"].default_value = factor
        elif "Fac" in cb.inputs:
            cb.inputs["Fac"].default_value = factor
        if use_5x:
            rgba_sockets = {s.name: s for s in cb.inputs if s.type == 'RGBA'}
            for k in ("lift", "gamma", "gain"):
                if k in cb_cfg and k.capitalize() in rgba_sockets:
                    val = tuple(cb_cfg[k])
                    rgba_sockets[k.capitalize()].default_value = val if len(val) == 4 else (val[0], val[1], val[2], 1.0)
        else:
            for k in ("lift", "gamma", "gain"):
                if k in cb_cfg and hasattr(cb, k):
                    setattr(cb, k, tuple(cb_cfg[k])[:3])
        tree.links.new(cur, cb.inputs["Image"])
        cur = cb.outputs["Image"]

    # 6. 曝光、对比度与饱和度微调 (Exposure / Brightness-Contrast / Hue-Saturation)
    cs_cfg = cfg.get("contrast_saturation")
    if isinstance(cs_cfg, dict):
        if "exposure" in cs_cfg and float(cs_cfg["exposure"]) != 0.0:
            exp_node = tree.nodes.new("CompositorNodeExposure")
            exp_node.inputs["Exposure"].default_value = float(cs_cfg["exposure"])
            tree.links.new(cur, exp_node.inputs["Image"])
            cur = exp_node.outputs["Image"]
        if ("brightness" in cs_cfg or "contrast" in cs_cfg):
            bc = tree.nodes.new("CompositorNodeBrightContrast")
            bc.inputs["Brightness"].default_value = float(cs_cfg.get("brightness", 0.0))
            bc.inputs["Contrast"].default_value = float(cs_cfg.get("contrast", 0.0))
            tree.links.new(cur, bc.inputs["Image"])
            cur = bc.outputs["Image"]
        if "saturation" in cs_cfg and float(cs_cfg["saturation"]) != 1.0:
            hs = tree.nodes.new("CompositorNodeHueSat")
            hs.inputs["Saturation"].default_value = float(cs_cfg["saturation"])
            tree.links.new(cur, hs.inputs["Image"])
            cur = hs.outputs["Image"]

    # 7. 清晰度微锐化 (Filter Sharpen)
    sh_cfg = cfg.get("sharpen")
    if isinstance(sh_cfg, dict) and float(sh_cfg.get("strength", 0.0)) > 0:
        flt = tree.nodes.new("CompositorNodeFilter")
        stype = sh_cfg.get("type", "Box Sharpen")
        if "Type" in flt.inputs:
            try:
                flt.inputs["Type"].default_value = stype
            except Exception:
                flt.inputs["Type"].default_value = "Box Sharpen"
        elif hasattr(flt, "filter_type"):
            flt.filter_type = "SHARPEN"
        fac_sock = flt.inputs.get("Factor") or flt.inputs.get("Fac")
        if fac_sock is not None:
            fac_sock.default_value = min(0.5, float(sh_cfg.get("strength", 0.12)))
        tree.links.new(cur, flt.inputs["Image"])
        cur = flt.outputs["Image"]

    # 8. 镜头暗角压边 (Vignette: EllipseMask + Gaussian Blur)
    vig_cfg = cfg.get("vignette")
    if isinstance(vig_cfg, dict) and float(vig_cfg.get("strength", 0.0)) > 0:
        v_strength = min(0.85, max(0.0, float(vig_cfg.get("strength", 0.28))))
        v_scale = float(vig_cfg.get("scale", 0.80))
        v_feather = float(vig_cfg.get("feather", 0.22))
        # 用图像乘 0 生成同画幅尺寸的 0 底板传给 EllipseMask，保证暗角永远居中且匹配当前分辨率
        zero_math = tree.nodes.new("ShaderNodeMath" if use_5x else "CompositorNodeMath")
        zero_math.operation = 'MULTIPLY'
        tree.links.new(cur, zero_math.inputs[0])
        zero_math.inputs[1].default_value = 0.0

        em = tree.nodes.new("CompositorNodeEllipseMask")
        if "Size" in em.inputs:
            em.inputs["Size"].default_value = (v_scale, v_scale)
        else:
            em.width = v_scale
            em.height = v_scale
        tree.links.new(zero_math.outputs[0], em.inputs["Mask"])

        bl = tree.nodes.new("CompositorNodeBlur")
        px_blur = max(24.0, scene.render.resolution_x * v_feather)
        if "Size" in bl.inputs:
            bl.inputs["Size"].default_value = (px_blur, px_blur)
        else:
            bl.size_x = int(px_blur)
            bl.size_y = int(px_blur)
        tree.links.new(em.outputs["Mask"], bl.inputs["Image"])
        cur = _mix_rgba(cur, bl.outputs["Image"], blend_type="MULTIPLY", factor=v_strength)

    # 9. 边缘色散与镜头畸变 (Lens Distortion & Chromatic Aberration)
    ld_cfg = cfg.get("lens_distortion")
    if isinstance(ld_cfg, dict) and (float(ld_cfg.get("dispersion", 0.0)) > 0 or float(ld_cfg.get("distortion", 0.0)) != 0.0):
        ld = tree.nodes.new("CompositorNodeLensdist")
        disp = float(ld_cfg.get("dispersion", 0.008))
        dist = float(ld_cfg.get("distortion", -0.005))
        if "Dispersion" in ld.inputs:
            ld.inputs["Dispersion"].default_value = disp
        if "Distortion" in ld.inputs:
            ld.inputs["Distortion"].default_value = dist
        if "Fit" in ld.inputs:
            ld.inputs["Fit"].default_value = True
        elif hasattr(ld, "use_fit"):
            ld.use_fit = True
        tree.links.new(cur, ld.inputs["Image"])
        cur = ld.outputs["Image"]

    if use_5x:
        out = tree.nodes.new("NodeGroupOutput")
        tree.links.new(cur, out.inputs[0])
    else:
        comp = tree.nodes.new("CompositorNodeComposite")
        tree.links.new(cur, comp.inputs["Image"])
    return tree
""",

    # 7. 一键配置：预览（EEVEE 快速）/ 正式出图（Cycles GPU + 合成器后处理 + EXR 缓存）
    "configure_render": """
def configure_render(mode="preview", width=1920, height=1080, samples=None,
                     view="AgX", look="AgX - Base Contrast", exposure=0.0,
                     bloom=None, post_process=None, raw_cache_dir=None, transparent=False):
    '''
    mode="preview"：EEVEE，800 宽预览，几秒出图，给自审用
    mode="final"：Cycles + GPU + 降噪，最终分辨率，玻璃折射、水面反射、暗部细节都更真实
    bloom：兼容旧接口，传 dict（如 {"glare_type": "Bloom", "threshold": 0.9, "strength": 0.4}）加泛光
    post_process：传预设名（如 "sterile_cold_brutalist", "cinematic_warm", "liminal_dream", "surreal_ethereal_glow"）
                  或完整后处理配置 dict（支持 mist, ao_boost, glare, color_balance, contrast_saturation, vignette, lens_distortion, sharpen）
    raw_cache_dir：正式出图时传入输出文件夹路径，会自动保存 MultiLayer EXR (raw_cache.exr)，供渲染后秒级重调后期
    '''
    scene = bpy.context.scene
    if mode == "preview":
        ratio = height / float(width)
        scene.render.resolution_x = 800
        scene.render.resolution_y = max(1, int(round(800 * ratio)))
        set_eevee_engine(samples=samples or 32)
    else:
        scene.render.resolution_x = width
        scene.render.resolution_y = height
        setup_cycles_gpu(samples=samples or 256)
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = transparent
    scene.render.image_settings.file_format = "PNG"
    setup_color_management(view=view, look=look, exposure=exposure)
    merged_pp = _resolve_post_process_config(post_process)
    if bloom and "glare" not in merged_pp and "bloom" not in merged_pp:
        merged_pp["glare"] = dict(bloom)
    if merged_pp or (mode == "final" and raw_cache_dir):
        setup_compositor_post_process(
            post_process=merged_pp,
            raw_cache_dir=raw_cache_dir if mode == "final" else None,
        )
    return scene.render.engine
""",
}
