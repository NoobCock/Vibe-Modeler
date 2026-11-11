"""
templates/modeling.py
Vibe-Modeler 建模模板：导入免费 3D 模型、常用修改器、带细节的基础部件

用法：手写建模时不要用一个立方体或圆柱代表整个物体，先拆成部件，再用这里的修改器给部件加厚度、弯曲、倒角和细分。
树、岩石、家具、杂物这类形状复杂的东西，优先用 import_cc0_model 导入现成模型。
"""

MODELING_SNIPPETS = {
    # 1. 导入 Poly Haven 下载好的 .blend 模型
    "import_cc0_model": """
def import_cc0_model(blend_path, location=(0, 0, 0), rotation_z_deg=0.0, target_height=None, name=None):
    '''
    把 download_cc0_model() 下载的 .blend 模型追加进当前场景。
    所有导入的物体挂到一个空物体（Empty）下面，之后移动、旋转、缩放只操作这个空物体。
    target_height：传入数值（米）时把模型整体缩放到这个高度。
    模型底部会对齐到 location 的 Z 高度。返回空物体；失败返回 None。
    '''
    import os
    from mathutils import Vector
    if not blend_path or not os.path.exists(blend_path):
        print(f"[Modeling] 模型文件不存在: {blend_path}")
        return None

    with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
        data_to.objects = [n for n in data_from.objects]

    imported = [o for o in data_to.objects if o is not None]
    if not imported:
        return None

    root_name = name or os.path.splitext(os.path.basename(blend_path))[0]
    root = bpy.data.objects.new(root_name, None)
    root.empty_display_type = 'PLAIN_AXES'
    coll = bpy.context.collection
    coll.objects.link(root)
    for o in imported:
        coll.objects.link(o)
        if o.parent is None:
            o.parent = root
    bpy.context.view_layer.update()

    meshes = [o for o in imported if o.type == 'MESH']
    if meshes:
        pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
        min_v = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        max_v = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        height = max(max_v.z - min_v.z, 1e-6)
        scale = (target_height / height) if target_height else 1.0
        center_xy = Vector(((min_v.x + max_v.x) / 2, (min_v.y + max_v.y) / 2, min_v.z))
        # 先把子物体整体平移，让模型底部中心对齐空物体原点
        for o in imported:
            if o.parent == root:
                o.location -= center_xy
        root.scale = (scale, scale, scale)

    root.location = location
    root.rotation_euler = (0.0, 0.0, math.radians(rotation_z_deg))
    bpy.context.view_layer.update()
    return root
""",

    # 2. 常用修改器
    "add_bevel": """
def add_bevel(obj, width=0.02, segments=3, angle_deg=30.0):
    '''硬边倒角：让边缘接住高光，不再像纸片一样锋利。width 按物体实际尺寸设，桌子 0.005~0.01，建筑 0.02~0.05。'''
    mod = obj.modifiers.new("Bevel", 'BEVEL')
    mod.width = width
    mod.segments = segments
    mod.limit_method = 'ANGLE'
    mod.angle_limit = math.radians(angle_deg)
    if hasattr(mod, "harden_normals"):
        mod.harden_normals = True
    return mod
""",

    "add_solidify": """
def add_solidify(obj, thickness=0.05, offset=-1.0):
    '''给平面加厚度：墙板、屋顶、桌面、船壳、布料都应该有厚度，不要用单面片。'''
    mod = obj.modifiers.new("Solidify", 'SOLIDIFY')
    mod.thickness = thickness
    mod.offset = offset
    mod.use_even_offset = True
    return mod
""",

    "add_simple_deform": """
def add_simple_deform(obj, method='BEND', angle_deg=30.0, axis='Z', factor=None):
    '''
    整体变形：method 可选 BEND（弯曲，如拱形屋顶、弯曲路灯杆）/ TWIST（扭转）/
    TAPER（锥化，如上窄下宽的石柱、树干）/ STRETCH（拉伸）。
    注意：要变形得平滑，物体本身要有足够的分段（先细分或建模时多给几段）。
    '''
    mod = obj.modifiers.new("SimpleDeform", 'SIMPLE_DEFORM')
    mod.deform_method = method
    mod.deform_axis = axis
    if method in ('BEND', 'TWIST'):
        mod.angle = math.radians(angle_deg)
    else:
        mod.factor = factor if factor is not None else 0.5
    return mod
""",

    "add_subdivision": """
def add_subdivision(obj, levels=2, render_levels=None, simple=False):
    '''表面细分：让曲面圆润；simple=True 时只加分段不改形状（给后续变形和置换用）。'''
    mod = obj.modifiers.new("Subdivision", 'SUBSURF')
    mod.levels = levels
    mod.render_levels = render_levels if render_levels is not None else levels
    if simple:
        mod.subdivision_type = 'SIMPLE'
    return mod
""",

    "add_array": """
def add_array(obj, count=5, offset=(1.05, 0.0, 0.0), use_relative=True):
    '''阵列复制：栏杆、台阶、木板、窗格、柱廊。offset 是相邻两个之间的间距（相对尺寸或绝对米数）。'''
    mod = obj.modifiers.new("Array", 'ARRAY')
    mod.count = count
    mod.use_relative_offset = use_relative
    mod.use_constant_offset = not use_relative
    if use_relative:
        mod.relative_offset_displace = offset
    else:
        mod.constant_offset_displace = offset
    return mod
""",

    "add_noise_displace": """
def add_noise_displace(obj, strength=0.2, noise_scale=0.6, texture_type='CLOUDS'):
    '''用噪波打乱表面形状（只改形状，不当材质用）：岩石、土堆、旧墙的不平整。物体要先有足够分段。'''
    tex = bpy.data.textures.new(f"{obj.name}_DispTex", type=texture_type)
    if hasattr(tex, "noise_scale"):
        tex.noise_scale = noise_scale
    mod = obj.modifiers.new("Displace", 'DISPLACE')
    mod.texture = tex
    mod.strength = strength
    mod.texture_coords = 'LOCAL'
    return mod
""",

    # 3. 带细节的基础部件
    "make_rock": """
def make_rock(name="Rock", size=1.0, location=(0, 0, 0), seed=0, flatten=0.6):
    '''
    生成一块不规则岩石（找不到合适的 CC0 岩石模型时用）：
    细分球 → 噪波置换 → 压扁 → 平滑，形状每个 seed 都不一样。
    '''
    import random
    rnd = random.Random(seed)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=size * 0.5, location=location)
    rock = bpy.context.object
    rock.name = name
    rock.scale = (1.0 + rnd.uniform(-0.25, 0.35), 1.0 + rnd.uniform(-0.25, 0.25), flatten + rnd.uniform(-0.1, 0.15))
    rock.rotation_euler = (rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), rnd.uniform(0, 6.28))
    tex = bpy.data.textures.new(f"{name}_Tex", type='VORONOI')
    tex.noise_scale = 0.35 + rnd.uniform(0, 0.3)
    mod = rock.modifiers.new("Displace", 'DISPLACE')
    mod.texture = tex
    mod.strength = size * 0.16
    mod.texture_coords = 'LOCAL'
    tex2 = bpy.data.textures.new(f"{name}_Tex2", type='CLOUDS')
    tex2.noise_scale = 0.15
    mod2 = rock.modifiers.new("Displace2", 'DISPLACE')
    mod2.texture = tex2
    mod2.strength = size * 0.06
    mod2.texture_coords = 'LOCAL'
    bpy.ops.object.shade_smooth()
    return rock
""",

    "make_plank_floor": """
def make_plank_floor(name="PlankFloor", length=4.0, width=2.0, plank_width=0.18, gap=0.008, thickness=0.04, location=(0, 0, 0), seed=0):
    '''
    拼木板地面 / 栈道：每块木板单独一个物体，长度、高度、角度都有微小随机差异，比一整块贴木纹的平板真实得多。
    返回父级空物体。
    '''
    import random
    rnd = random.Random(seed)
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root.location = location
    count = max(1, int(width / (plank_width + gap)))
    for i in range(count):
        y = -width / 2 + i * (plank_width + gap) + plank_width / 2
        l = length * rnd.uniform(0.92, 1.0)
        bpy.ops.mesh.primitive_cube_add(size=1.0)
        p = bpy.context.object
        p.name = f"{name}_{i:02d}"
        p.scale = (l, plank_width, thickness)
        p.location = (rnd.uniform(-0.05, 0.05), y, thickness / 2 + rnd.uniform(-0.004, 0.004))
        p.rotation_euler = (rnd.uniform(-0.01, 0.01), rnd.uniform(-0.008, 0.008), rnd.uniform(-0.01, 0.01))
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        add_bevel(p, width=0.004, segments=2)
        p.parent = root
    return root
""",
}
