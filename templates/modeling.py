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

    "build_curved_open_book": """
def build_curved_open_book(
    name="CurvedOpenBook",
    location=(0.0, 0.0, 0.0),
    rotation=(0.0, 0.0, 0.0),
    width=1.25,
    depth=0.86,
    page_arch=0.14,
    flutter_count=3,
    mat_cover=None,
    mat_page=None,
    allow_float=False,
):
    '''
    用 BMesh 程序化生成带有自然 S 型拱曲书页、圆弧书脊与翻飞卷曲单页的精装摊开大书
    （彻底避免把翻开的书做成两块死板直方块的积木感）。返回父级 Empty。
    '''
    import bmesh
    import random
    rnd = random.Random(hash(name) & 0xFFFFFFFF)
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root.location = location
    root.rotation_euler = rotation
    if allow_float:
        root["vm_allow_float"] = True

    def _assign(obj, mat):
        if mat:
            if obj.data.materials:
                obj.data.materials[0] = mat
            else:
                obj.data.materials.append(mat)

    half_w = width * 0.5
    # 1. 左右微倾硬壳封皮 + 弧形书脊
    for side in (-1, 1):
        bpy.ops.mesh.primitive_cube_add(size=1.0)
        cov = bpy.context.object
        cov.name = f"{name}_Cover_{'L' if side < 0 else 'R'}"
        cov.scale = (half_w * 0.98, depth * 1.02, 0.024)
        cov.location = (side * half_w * 0.49, 0.0, 0.02)
        cov.rotation_euler = (0.0, -side * math.radians(8.5), 0.0)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        add_bevel(cov, width=0.005, segments=2)
        _assign(cov, mat_cover)
        if allow_float:
            cov["vm_allow_float"] = True
        cov.parent = root

    bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.055, depth=depth * 1.03,
                                        location=(0.0, 0.0, 0.0), rotation=(math.radians(90), 0.0, 0.0))
    spine = bpy.context.object
    spine.name = f"{name}_Spine"
    spine.scale = (1.15, 0.55, 1.0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    _assign(spine, mat_cover)
    if allow_float:
        spine["vm_allow_float"] = True
    spine.parent = root

    # 2. 左右拱曲厚书页块（BMesh 沿 X 采样正弦拱起曲线并挤出厚度）
    segs_x = 24
    segs_y = 8
    for side in (-1, 1):
        mesh = bpy.data.meshes.new(f"{name}_PageBlock_{'L' if side < 0 else 'R'}")
        bm = bmesh.new()
        grid_top = []
        grid_bot = []
        for iy in range(segs_y + 1):
            vy = -depth * 0.47 + (iy / float(segs_y)) * (depth * 0.94)
            row_t = []
            row_b = []
            for ix in range(segs_x + 1):
                t = ix / float(segs_x)
                vx = side * (0.015 + t * (half_w * 0.92))
                # 自然书页拱曲：近书脊深凹爬升，中段饱满拱起，外缘微翘
                arch_z = math.sin(t * math.pi * 0.88) * page_arch - math.sin(t * math.pi * 1.85) * (page_arch * 0.18)
                thick = 0.055 * (1.0 - 0.22 * t)
                base_z = 0.025 + t * 0.035
                row_t.append(bm.verts.new((vx, vy, base_z + arch_z + thick)))
                row_b.append(bm.verts.new((vx, vy, base_z + arch_z * 0.35)))
            grid_top.append(row_t)
            grid_bot.append(row_b)
        for iy in range(segs_y):
            for ix in range(segs_x):
                v1, v2, v3, v4 = grid_top[iy][ix], grid_top[iy][ix + 1], grid_top[iy + 1][ix + 1], grid_top[iy + 1][ix]
                bm.faces.new((v1, v2, v3, v4) if side > 0 else (v4, v3, v2, v1))
                b1, b2, b3, b4 = grid_bot[iy][ix], grid_bot[iy][ix + 1], grid_bot[iy + 1][ix + 1], grid_bot[iy + 1][ix]
                bm.faces.new((b4, b3, b2, b1) if side > 0 else (b1, b2, b3, b4))
        # 封边
        for ix in range(segs_x):
            bm.faces.new((grid_bot[0][ix], grid_bot[0][ix + 1], grid_top[0][ix + 1], grid_top[0][ix]))
            bm.faces.new((grid_top[-1][ix], grid_top[-1][ix + 1], grid_bot[-1][ix + 1], grid_bot[-1][ix]))
        for iy in range(segs_y):
            bm.faces.new((grid_bot[iy][0], grid_top[iy][0], grid_top[iy + 1][0], grid_bot[iy + 1][0]))
            bm.faces.new((grid_top[iy][-1], grid_bot[iy][-1], grid_bot[iy + 1][-1], grid_top[iy + 1][-1]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(mesh)
        bm.free()
        for poly in mesh.polygons:
            poly.use_smooth = True
        pobj = bpy.data.objects.new(mesh.name, mesh)
        bpy.context.collection.objects.link(pobj)
        add_bevel(pobj, width=0.003, segments=2)
        _assign(pobj, mat_page)
        if allow_float:
            pobj["vm_allow_float"] = True
        pobj.parent = root

    # 3. 正在翻起 / 悬浮卷曲的散页
    for fi in range(max(0, int(flutter_count))):
        mesh = bpy.data.meshes.new(f"{name}_FlutterPage_{fi}")
        bm = bmesh.new()
        pw = half_w * 0.86
        pd = depth * 0.88
        s_u, s_v = 16, 6
        verts = []
        curl_dir = -1 if fi % 2 == 0 else 1
        lift_h = 0.16 + fi * 0.14
        for iv in range(s_v + 1):
            vv = (iv / float(s_v) - 0.5) * pd
            row = []
            for iu in range(s_u + 1):
                u = iu / float(s_u)
                ux = curl_dir * (u * pw)
                uz = math.sin(u * math.pi) * (page_arch * 1.35) + (u ** 1.7) * 0.11 + math.cos(vv * 3.0 + fi) * 0.018
                row.append(bm.verts.new((ux, vv, uz)))
            verts.append(row)
        for iv in range(s_v):
            for iu in range(s_u):
                bm.faces.new((verts[iv][iu], verts[iv][iu + 1], verts[iv + 1][iu + 1], verts[iv + 1][iu]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(mesh)
        bm.free()
        for poly in mesh.polygons:
            poly.use_smooth = True
        fobj = bpy.data.objects.new(mesh.name, mesh)
        bpy.context.collection.objects.link(fobj)
        fobj.location = (rnd.uniform(-0.08, 0.08), rnd.uniform(-0.06, 0.06), lift_h)
        fobj.rotation_euler = (rnd.uniform(-0.18, 0.18), curl_dir * rnd.uniform(0.15, 0.42), rnd.uniform(-0.22, 0.22))
        add_solidify(fobj, thickness=0.004)
        _assign(fobj, mat_page)
        fobj["vm_allow_float"] = True
        fobj.parent = root

    bpy.context.view_layer.update()
    return root
""",

    "build_hanging_cables": """
def build_hanging_cables(
    name="HangingCables",
    start_pt=(-4.0, 0.0, 8.0),
    end_pt=(4.0, 0.0, 8.0),
    sag=1.4,
    count=3,
    spread=0.35,
    radius=0.025,
    mat_cable=None,
    seed=42,
):
    '''
    在两点之间生成多根自然垂坠的悬链线电缆 / 软管束（自动标记 vm_allow_float=True），
    用于打破巨构峡谷、工业内景或超现实空间的僵硬直线。返回父级 Empty。
    '''
    import random
    from mathutils import Vector
    rnd = random.Random(seed)
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root["vm_allow_float"] = True
    p0 = Vector(start_pt)
    p1 = Vector(end_pt)
    span_vec = p1 - p0
    perp = Vector((-span_vec.y, span_vec.x, 0.0))
    if perp.length > 1e-4:
        perp.normalize()
    else:
        perp = Vector((1.0, 0.0, 0.0))

    for i in range(max(1, int(count))):
        off_t = (i - (count - 1) * 0.5) * spread if count > 1 else 0.0
        cur_sag = sag * rnd.uniform(0.82, 1.22)
        cdata = bpy.data.curves.new(f"{name}_Curve_{i}", type='CURVE')
        cdata.dimensions = '3D'
        cdata.bevel_depth = radius * rnd.uniform(0.85, 1.15)
        cdata.bevel_resolution = 3
        spline = cdata.splines.new('POLY')
        steps = 20
        spline.points.add(steps)
        for s in range(steps + 1):
            t = s / float(steps)
            pt = p0.lerp(p1, t) + perp * off_t
            pt.z -= 4.0 * cur_sag * t * (1.0 - t)
            spline.points[s].co = (pt.x, pt.y, pt.z, 1.0)
        cobj = bpy.data.objects.new(f"{name}_{i}", cdata)
        bpy.context.collection.objects.link(cobj)
        cobj["vm_allow_float"] = True
        if mat_cable:
            cobj.data.materials.append(mat_cable)
        cobj.parent = root
    return root
""",

    "build_human_scale_railing": """
def build_human_scale_railing(
    name="HumanScaleRailing",
    start_pt=(-4.0, 0.0, 0.0),
    end_pt=(4.0, 0.0, 0.0),
    height=1.05,
    post_spacing=1.5,
    rail_count=2,
    mat_rail=None,
    allow_float=False,
):
    '''
    沿 start_pt 到 end_pt 生成标准人体尺度（默认高 1.05 米）的金属/混凝土护栏（立柱 + 顶扶手 + 横档），
    专用于给 30~60 米高的巨构峡谷、观测连桥、台阶边缘注入明确的“人体尺度参照物”。返回父级 Empty。
    '''
    from mathutils import Vector
    p0 = Vector(start_pt)
    p1 = Vector(end_pt)
    diff = p1 - p0
    length = diff.length
    if length < 0.1:
        return None
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root.location = p0
    angle_z = math.atan2(diff.y, diff.x)
    root.rotation_euler = (0.0, 0.0, angle_z)
    if allow_float:
        root["vm_allow_float"] = True

    def _assign(obj):
        if mat_rail:
            if obj.data.materials:
                obj.data.materials[0] = mat_rail
            else:
                obj.data.materials.append(mat_rail)
        if allow_float:
            obj["vm_allow_float"] = True
        obj.parent = root

    n_posts = max(2, int(round(length / max(0.4, post_spacing))) + 1)
    for i in range(n_posts):
        x = (i / float(n_posts - 1)) * length
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, 0.0, height * 0.5))
        post = bpy.context.object
        post.name = f"{name}_Post_{i}"
        post.scale = (0.04, 0.04, height)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        add_bevel(post, width=0.004, segments=2)
        _assign(post)

    for r in range(max(1, int(rail_count))):
        rz = height if r == 0 else height * (1.0 - (r / float(rail_count + 0.5)))
        thick = 0.048 if r == 0 else 0.024
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(length * 0.5, 0.0, rz))
        bar = bpy.context.object
        bar.name = f"{name}_Rail_{r}"
        bar.scale = (length + 0.04, thick, thick)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        add_bevel(bar, width=0.004, segments=2)
        _assign(bar)

    bpy.context.view_layer.update()
    return root
""",
}
