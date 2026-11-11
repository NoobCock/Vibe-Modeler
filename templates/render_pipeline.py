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
    scene = bpy.context.scene

    def _set_glare(gl):
        if "Type" in gl.inputs:  # 5.x：参数都在输入插槽上
            try:
                gl.inputs["Type"].default_value = glare_type
            except Exception:
                gl.inputs["Type"].default_value = "Bloom"
            gl.inputs["Threshold"].default_value = threshold
            if "Strength" in gl.inputs:
                gl.inputs["Strength"].default_value = strength
            if "Size" in gl.inputs:
                gl.inputs["Size"].default_value = size
        else:  # 4.x：参数是节点属性
            try:
                gl.glare_type = glare_type.upper().replace(" ", "_")
            except Exception:
                gl.glare_type = "FOG_GLOW"
            gl.threshold = threshold
            if hasattr(gl, "mix"):
                gl.mix = strength - 1.0
            if hasattr(gl, "size"):
                gl.size = max(1, min(9, int(round(size * 9))))

    if hasattr(scene, "compositing_node_group"):  # Blender 5.x
        ng = bpy.data.node_groups.new("VM_Compositor", "CompositorNodeTree")
        ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        rl = ng.nodes.new("CompositorNodeRLayers")
        gl = ng.nodes.new("CompositorNodeGlare")
        out = ng.nodes.new("NodeGroupOutput")
        _set_glare(gl)
        ng.links.new(rl.outputs["Image"], gl.inputs["Image"])
        ng.links.new(gl.outputs["Image"], out.inputs[0])
        scene.compositing_node_group = ng
        return ng
    else:  # Blender 4.x
        scene.use_nodes = True
        tree = scene.node_tree
        tree.nodes.clear()
        rl = tree.nodes.new("CompositorNodeRLayers")
        gl = tree.nodes.new("CompositorNodeGlare")
        comp = tree.nodes.new("CompositorNodeComposite")
        _set_glare(gl)
        tree.links.new(rl.outputs["Image"], gl.inputs["Image"])
        tree.links.new(gl.outputs["Image"], comp.inputs["Image"])
        return tree
""",

    # 6. 一键配置：预览（EEVEE 快速）/ 正式出图（Cycles GPU）
    "configure_render": """
def configure_render(mode="preview", width=1920, height=1080, samples=None,
                     view="AgX", look="AgX - Base Contrast", exposure=0.0,
                     bloom=None, transparent=False):
    '''
    mode="preview"：EEVEE，800 宽预览，几秒出图，给自审用
    mode="final"：Cycles + GPU + 降噪，最终分辨率，玻璃折射、水面反射、暗部细节都更真实
    bloom：None 不加泛光；传 dict（如 {"glare_type": "Bloom", "threshold": 0.9, "strength": 0.4}）加泛光
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
    if bloom:
        setup_bloom_glow(**bloom)
    return scene.render.engine
""",
}
