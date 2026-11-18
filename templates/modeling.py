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

    "build_bmesh_fractured_slab": """
def build_bmesh_fractured_slab(
    name="FracturedSlab",
    location=(0.0, 0.0, 0.0),
    dims=(2.8, 1.8, 0.36),
    rotation=(0.0, 0.0, 0.0),
    crack_irregularity=0.24,
    rebar_count=5,
    mat_shell=None,
    mat_core=None,
    mat_rebar=None,
    allow_float=False,
    seed=0,
):
    '''
    用 BMesh 程序化生成带有真实锯齿状断裂截面、粗糙混凝土内芯与外露扭曲钢筋束的崩裂板体/残骸横梁/碎裂台阶。
    彻底取代“把完整长方体歪转几个角度冒充破碎”的假破碎做法！返回父级 Empty。
    '''
    import bmesh
    import random as _r
    rnd = _r.Random(seed)
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root.location = location
    root.rotation_euler = rotation
    if allow_float:
        root["vm_allow_float"] = True

    def _assign(ob, mat):
        if mat:
            if ob.data.materials:
                ob.data.materials[0] = mat
            else:
                ob.data.materials.append(mat)
        if allow_float:
            ob["vm_allow_float"] = True
        ob.parent = root

    w, d, h = float(dims[0]), float(dims[1]), float(dims[2])
    core_mat = mat_core or mat_shell
    reb_mat = mat_rebar or core_mat

    # 生成左、右两半沿不规则锯齿裂缝撕开的 BMesh 块体，并在断口散落小碎石与外露钢筋
    nx, ny, nz = 10, 6, 4
    gap = w * 0.06
    for side in (-1, 1):
        me = bpy.data.meshes.new(f"{name}_Half_{'L' if side < 0 else 'R'}")
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=4, use_grid_fill=True)
        for v in bm.verts:
            vx, vy, vz = v.co.x, v.co.y, v.co.z
            # 靠近内侧断口 (vx * side < 0) 的顶点施加剧烈锯齿凹凸扰动
            dist_to_fracture = abs(vx - (-0.5 * side))
            if dist_to_fracture < 0.38:
                jag = (1.0 - dist_to_fracture / 0.38) * crack_irregularity
                vx += rnd.uniform(-jag, jag) * 0.85
                vy += rnd.uniform(-jag, jag) * 0.35
                vz += rnd.uniform(-jag, jag) * 0.45
            else:
                vx += rnd.uniform(-0.015, 0.015)
                vy += rnd.uniform(-0.015, 0.015)
            v.co.x = vx * (w * 0.46)
            v.co.y = vy * d
            v.co.z = vz * h
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(me.name, me)
        bpy.context.collection.objects.link(ob)
        ob.location = (side * (w * 0.25 + gap * 0.5), rnd.uniform(-0.04, 0.04) * d, rnd.uniform(-0.03, 0.03) * h)
        ob.rotation_euler = (
            math.radians(rnd.uniform(-4.5, 4.5)),
            math.radians(side * rnd.uniform(2.5, 9.5)),
            math.radians(rnd.uniform(-4.0, 4.0)),
        )
        add_bevel(ob, width=min(0.012, min(w, d, h) * 0.04), segments=1)
        _assign(ob, mat_shell)

    # 裂缝断面粗糙混凝土内芯块
    for ci in range(3):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=min(d, h) * rnd.uniform(0.32, 0.48))
        chunk = bpy.context.object
        chunk.name = f"{name}_FractureCore_{ci}"
        chunk.scale = (rnd.uniform(0.6, 1.3), rnd.uniform(0.8, 1.5), rnd.uniform(0.6, 1.1))
        chunk.location = (rnd.uniform(-gap, gap), (ci - 1) * d * 0.26, rnd.uniform(-h * 0.15, h * 0.15))
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        add_noise_displace(chunk, strength=min(d, h) * 0.14, noise_scale=0.35)
        _assign(chunk, core_mat)

    # 断裂缝隙间扭曲外露的钢筋束
    for ri in range(max(0, int(rebar_count))):
        ry = (ri / max(1.0, float(rebar_count - 1)) - 0.5) * d * 0.76 + rnd.uniform(-0.04, 0.04)
        rz = rnd.uniform(-h * 0.28, h * 0.28)
        rlen = gap * rnd.uniform(2.2, 4.2)
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=10,
            radius=max(0.010, min(h, d) * 0.032),
            depth=rlen,
            location=(rnd.uniform(-gap * 0.3, gap * 0.3), ry, rz),
            rotation=(math.radians(rnd.uniform(-16, 16)), math.radians(90 + rnd.uniform(-22, 22)), math.radians(rnd.uniform(-18, 18))),
        )
        reb = bpy.context.object
        reb.name = f"{name}_Rebar_{ri}"
        _assign(reb, reb_mat)

    bpy.context.view_layer.update()
    return root
""",

    "build_shattered_shard_vortex": """
def build_shattered_shard_vortex(
    name="ShardVortex",
    count=120,
    center=(0.0, 12.0, 5.0),
    radius_range=(1.2, 8.5),
    height_span=9.0,
    scale_range=(0.07, 0.52),
    spiral_turns=1.6,
    mat_primary=None,
    mat_accent=None,
    accent_ratio=0.18,
    seed=42,
):
    '''
    用 BMesh 程序化生成大、中、小三级尺度的立体多面体尖锐碎晶/残片漩涡场（仅适用于崩塌废墟、能量结晶漩涡等对应题材）。
    每个碎片均为真实封闭凸多面体棱晶或楔形石块，自动标记 vm_allow_float=True。返回父级 Empty。
    '''
    import bmesh
    import random as _r
    rnd = _r.Random(seed)
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root.location = center
    root["vm_allow_float"] = True

    # 预先生成 6 种不同拓扑形态的 BMesh 尖锐多面体网格模板以复用并保持极高运行速度
    archetype_meshes = []
    for a_i in range(6):
        me = bpy.data.meshes.new(f"{name}_ProtoMesh_{a_i}")
        bm = bmesh.new()
        n_ring = rnd.randint(5, 8)
        top_v = bm.verts.new((rnd.uniform(-0.12, 0.12), rnd.uniform(-0.12, 0.12), rnd.uniform(0.95, 1.45)))
        bot_v = bm.verts.new((rnd.uniform(-0.12, 0.12), rnd.uniform(-0.12, 0.12), -rnd.uniform(0.75, 1.25)))
        ring_verts = []
        for k in range(n_ring):
            ang = (k / float(n_ring)) * math.tau + rnd.uniform(-0.22, 0.22)
            rad = rnd.uniform(0.22, 0.58)
            vz = rnd.uniform(-0.28, 0.32)
            ring_verts.append(bm.verts.new((rad * math.cos(ang), rad * math.sin(ang), vz)))
        for k in range(n_ring):
            v_cur = ring_verts[k]
            v_nxt = ring_verts[(k + 1) % n_ring]
            bm.faces.new((top_v, v_cur, v_nxt))
            bm.faces.new((bot_v, v_nxt, v_cur))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        archetype_meshes.append(me)

    r_min, r_max = float(radius_range[0]), float(radius_range[1])
    s_min, s_max = float(scale_range[0]), float(scale_range[1])
    total = max(8, int(count))

    for i in range(total):
        t = i / float(total)
        # 螺旋上升流线 + 随机径向散射
        base_ang = t * spiral_turns * math.tau + rnd.uniform(-0.65, 0.65)
        rad = r_min + (r_max - r_min) * (t ** 0.75) * rnd.uniform(0.65, 1.25)
        px = rad * math.cos(base_ang)
        py = rad * math.sin(base_ang)
        pz = (t - 0.5) * height_span + rnd.uniform(-0.85, 0.85)

        # 三级尺度分布：12% 巨型残块，33% 中型锋利棱片，55% 高频细碎微晶
        roll = rnd.random()
        if roll < 0.12:
            sc = rnd.uniform(s_max * 0.72, s_max * 1.35)
        elif roll < 0.45:
            sc = rnd.uniform((s_min + s_max) * 0.35, s_max * 0.72)
        else:
            sc = rnd.uniform(s_min, (s_min + s_max) * 0.35)

        proto = archetype_meshes[i % len(archetype_meshes)]
        ob = bpy.data.objects.new(f"{name}_Shard_{i:03d}", proto.copy())
        bpy.context.collection.objects.link(ob)
        ob.parent = root
        ob["vm_allow_float"] = True
        ob.location = (px, py, pz)
        ob.scale = (sc * rnd.uniform(0.55, 1.15), sc * rnd.uniform(0.45, 0.95), sc * rnd.uniform(1.1, 2.2))
        # 碎片主轴顺着螺旋切线倾斜，形成强烈的气旋动势
        ob.rotation_euler = (
            math.radians(rnd.uniform(-35, 35)),
            math.radians(rnd.uniform(18, 68)),
            base_ang + math.radians(rnd.uniform(-25, 25)),
        )
        chosen_mat = mat_accent if (mat_accent and rnd.random() < accent_ratio) else mat_primary
        if chosen_mat:
            ob.data.materials.append(chosen_mat)

    bpy.context.view_layer.update()
    return root
""",

    "build_profiled_machined_ring": """
def build_profiled_machined_ring(
    name="MachinedRing",
    major_radius=4.5,
    radial_width=0.38,
    axial_height=0.26,
    location=(0.0, 0.0, 4.0),
    rotation=(0.0, 0.0, 0.0),
    segments=128,
    fin_count=48,
    mat_body=None,
    mat_glow=None,
    mat_fin=None,
    allow_float=True,
):
    '''
    用 BMesh 12 点阶梯截面旋转放样生成带径向散热鳍片的工业精密机械涡轮环（仅适用于硬核机械、推进器、精密工业核心等题材；
    普通建筑圆环、光晕丝带或生态题材切勿强行套用）。返回父级 Empty。
    '''
    import bmesh
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root.location = location
    root.rotation_euler = rotation
    if allow_float:
        root["vm_allow_float"] = True

    rw = radial_width * 0.5
    ah = axial_height * 0.5
    # 12 点工业精密阶梯截面（含内侧发光凹槽槽道）
    profile = [
        (-rw, -ah * 0.55),
        (-rw * 0.75, -ah),
        (rw * 0.75, -ah),
        (rw, -ah * 0.60),
        (rw, ah * 0.60),
        (rw * 0.75, ah),
        (-rw * 0.75, ah),
        (-rw, ah * 0.55),
        (-rw * 0.62, ah * 0.42),
        (-rw * 0.62, -ah * 0.42),
    ]
    n_p = len(profile)
    segs = max(32, int(segments))

    me = bpy.data.meshes.new(f"{name}_RingMesh")
    bm = bmesh.new()
    rings = []
    for s in range(segs):
        ang = (s / float(segs)) * math.tau
        ca, sa = math.cos(ang), math.sin(ang)
        row = []
        for dr, dz in profile:
            r = max(0.05, major_radius + dr)
            row.append(bm.verts.new((r * ca, r * sa, dz)))
        rings.append(row)

    for s in range(segs):
        r0 = rings[s]
        r1 = rings[(s + 1) % segs]
        for p in range(n_p):
            p_nxt = (p + 1) % n_p
            f = bm.faces.new((r0[p], r1[p], r1[p_nxt], r0[p_nxt]))
            # 内凹槽面（p == 8）赋予发光材质槽号 1
            if p == 8 and mat_glow is not None:
                f.material_index = 1
            else:
                f.material_index = 0

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True

    ring_ob = bpy.data.objects.new(f"{name}_Body", me)
    bpy.context.collection.objects.link(ring_ob)
    ring_ob.parent = root
    if allow_float:
        ring_ob["vm_allow_float"] = True
    if mat_body:
        ring_ob.data.materials.append(mat_body)
    if mat_glow:
        if not ring_ob.data.materials:
            ring_ob.data.materials.append(mat_body or mat_glow)
        ring_ob.data.materials.append(mat_glow)

    # 径向精密散热鳍片 / 卡扣阵列
    if fin_count and int(fin_count) > 0:
        fmat = mat_fin or mat_body
        n_f = int(fin_count)
        for fi in range(n_f):
            ang = (fi / float(n_f)) * math.tau
            is_major = (fi % 6 == 0)
            fh = axial_height * (1.42 if is_major else 1.15)
            fw = radial_width * (1.28 if is_major else 1.08)
            ft = (2.0 * math.pi * major_radius / n_f) * (0.28 if is_major else 0.16)
            bpy.ops.mesh.primitive_cube_add(
                size=1.0,
                location=(major_radius * math.cos(ang), major_radius * math.sin(ang), 0.0),
                rotation=(0.0, 0.0, ang),
            )
            fin = bpy.context.object
            fin.name = f"{name}_Fin_{fi:03d}"
            fin.scale = (fw, max(0.012, ft), fh)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            add_bevel(fin, width=min(0.006, ft * 0.25), segments=1)
            fin.parent = root
            if allow_float:
                fin["vm_allow_float"] = True
            if fmat:
                fin.data.materials.append(fmat)

    bpy.context.view_layer.update()
    return root
""",

    "build_hex_wafer_array": """
def build_hex_wafer_array(
    name="HexWaferArray",
    count=90,
    center=(0.0, 10.0, 4.0),
    spread=(6.5, 6.5, 5.0),
    radius_range=(0.09, 0.38),
    clear_radius=2.2,
    mat_wafer=None,
    mat_prism=None,
    prism_ratio=0.30,
    seed=7,
):
    '''
    生成三维倒角六边形芯片与棱晶悬浮阵列（仅适用于量子矩阵、数据核心或微粒抽象构成题材，切忌乱塞入建筑或自然生态场景）。
    '''
    import bmesh
    import random as _r
    rnd = _r.Random(seed)
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root.location = center
    root["vm_allow_float"] = True

    # 构建倒角六边形晶圆原型网格与双锥六角棱晶原型网格
    def _make_hex_proto(mesh_name, thick_ratio, tip_ext):
        me = bpy.data.meshes.new(mesh_name)
        bm = bmesh.new()
        r_outer = 1.0
        r_inner = 0.86
        hz = thick_ratio * 0.5
        top_ring, mid_top, mid_bot, bot_ring = [], [], [], []
        for k in range(6):
            a = k * math.pi / 3.0
            ca, sa = math.cos(a), math.sin(a)
            top_ring.append(bm.verts.new((r_inner * ca, r_inner * sa, hz + tip_ext)))
            mid_top.append(bm.verts.new((r_outer * ca, r_outer * sa, hz * 0.55)))
            mid_bot.append(bm.verts.new((r_outer * ca, r_outer * sa, -hz * 0.55)))
            bot_ring.append(bm.verts.new((r_inner * ca, r_inner * sa, -(hz + tip_ext))))
        bm.faces.new(top_ring)
        bm.faces.new(list(reversed(bot_ring)))
        for k in range(6):
            kn = (k + 1) % 6
            bm.faces.new((top_ring[k], mid_top[k], mid_top[kn], top_ring[kn]))
            bm.faces.new((mid_top[k], mid_bot[k], mid_bot[kn], mid_top[kn]))
            bm.faces.new((mid_bot[k], bot_ring[k], bot_ring[kn], mid_bot[kn]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        return me

    wafer_proto = _make_hex_proto(f"{name}_WaferProto", 0.16, 0.03)
    prism_proto = _make_hex_proto(f"{name}_PrismProto", 0.42, 0.24)

    placed = 0
    attempts = 0
    r_min, r_max = float(radius_range[0]), float(radius_range[1])
    while placed < int(count) and attempts < int(count) * 4:
        attempts += 1
        px = rnd.uniform(-spread[0], spread[0])
        py = rnd.uniform(-spread[1], spread[1])
        pz = rnd.uniform(-spread[2] * 0.5, spread[2] * 0.5)
        # 保持中央视线通廊不被遮挡
        if math.hypot(px, pz) < clear_radius and abs(py) < spread[1] * 0.65:
            continue
        is_prism = (mat_prism is not None and rnd.random() < prism_ratio)
        proto = prism_proto if is_prism else wafer_proto
        sc = rnd.uniform(r_min, r_max)
        ob = bpy.data.objects.new(f"{name}_Unit_{placed:03d}", proto.copy())
        bpy.context.collection.objects.link(ob)
        ob.parent = root
        ob["vm_allow_float"] = True
        ob.location = (px, py, pz)
        ob.scale = (sc, sc, sc)
        ob.rotation_euler = (
            rnd.uniform(-0.85, 0.85),
            rnd.uniform(-0.85, 0.85),
            rnd.uniform(0.0, math.tau),
        )
        mat = mat_prism if is_prism else mat_wafer
        if mat:
            ob.data.materials.append(mat)
        placed += 1

    bpy.context.view_layer.update()
    return root
""",

    "build_smooth_planter_pod": """
def build_smooth_planter_pod(
    name="PlanterPod",
    location=(0.0, 0.0, 0.0),
    radius_x=1.8,
    radius_y=1.1,
    height=0.52,
    rotation_z_deg=0.0,
    add_bench_rim=True,
    mat_shell=None,
    mat_soil=None,
    mat_bench=None,
):
    '''
    生成圆润流线型建筑种植池 / 生态休憩台座（带凹陷绿植种植槽与可选悬挑弧形座椅边檐）。
    适用于现代广场、玻璃中庭、公园、生态建筑与室内展厅。返回父级 Empty。
    '''
    import bmesh
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root.location = location
    root.rotation_euler = (0.0, 0.0, math.radians(rotation_z_deg))

    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=1.0, depth=height, location=(0.0, 0.0, height * 0.5))
    shell = bpy.context.object
    shell.name = f"{name}_Shell"
    shell.scale = (radius_x, radius_y, 1.0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for p in shell.data.polygons:
        p.use_smooth = True
    add_bevel(shell, width=min(0.05, height * 0.12), segments=3)
    shell.parent = root
    if mat_shell:
        shell.data.materials.append(mat_shell)

    # 顶部环状花坛压顶缘（高出内侧土面 4cm，形成真凹陷种植槽）
    rim_me = bpy.data.meshes.new(f"{name}_RimMesh")
    bm = bmesh.new()
    segs = 48
    in_b, out_b, in_t, out_t = [], [], [], []
    z_rb, z_rt = height - 0.04, height + 0.04
    for si in range(segs):
        ang = (si / float(segs)) * math.tau
        ca, sa = math.cos(ang), math.sin(ang)
        in_b.append(bm.verts.new((radius_x * 0.84 * ca, radius_y * 0.82 * sa, z_rb)))
        out_b.append(bm.verts.new((radius_x * 1.01 * ca, radius_y * 1.01 * sa, z_rb)))
        in_t.append(bm.verts.new((radius_x * 0.84 * ca, radius_y * 0.82 * sa, z_rt)))
        out_t.append(bm.verts.new((radius_x * 1.01 * ca, radius_y * 1.01 * sa, z_rt)))
    for si in range(segs):
        sn = (si + 1) % segs
        bm.faces.new((in_t[si], out_t[si], out_t[sn], in_t[sn]))
        bm.faces.new((out_b[si], in_b[si], in_b[sn], out_b[sn]))
        bm.faces.new((out_b[si], out_b[sn], out_t[sn], out_t[si]))
        bm.faces.new((in_t[si], in_t[sn], in_b[sn], in_b[si]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(rim_me)
    bm.free()
    for p in rim_me.polygons:
        p.use_smooth = True
    rim_ob = bpy.data.objects.new(f"{name}_LipRim", rim_me)
    bpy.context.collection.objects.link(rim_ob)
    add_bevel(rim_ob, width=0.012, segments=2)
    rim_ob.parent = root
    if mat_shell:
        rim_ob.data.materials.append(mat_shell)

    bpy.ops.mesh.primitive_cylinder_add(vertices=44, radius=1.0, depth=0.08, location=(0.0, 0.0, height - 0.04))
    bed = bpy.context.object
    bed.name = f"{name}_TurfBed"
    bed.scale = (radius_x * 0.84, radius_y * 0.82, 1.0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for p in bed.data.polygons:
        p.use_smooth = True
    bed.parent = root
    if mat_soil:
        bed.data.materials.append(mat_soil)

    if add_bench_rim:
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=1.0, depth=0.075, location=(0.0, 0.0, height * 0.72))
        bench = bpy.context.object
        bench.name = f"{name}_BenchRim"
        bench.scale = (radius_x * 1.12, radius_y * 1.12, 1.0)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        for p in bench.data.polygons:
            p.use_smooth = True
        add_bevel(bench, width=0.018, segments=2)
        bench.parent = root
        bmat = mat_bench or mat_shell
        if bmat:
            bench.data.materials.append(bmat)

    bpy.context.view_layer.update()
    return root
""",

    "build_arched_colonnade": """
def build_arched_colonnade(
    name="ArchedColonnade",
    start_pt=(-8.0, 6.0, 0.0),
    end_pt=(8.0, 6.0, 0.0),
    bay_count=4,
    height=4.4,
    depth=0.55,
    pillar_radius=0.24,
    mat_pillar=None,
    mat_arch=None,
):
    '''
    沿起止点生成真圆弧拱券柱廊（每跨均含底部柱础、圆柱、柱头、严丝合缝的实体拱腹 spandrel、平滑拱券与顶部檐梁）。
    适用于古典庭院、现代美术馆、火车站长廊、地中海海滨走廊或静谧废墟。返回父级 Empty。
    '''
    import bmesh
    from mathutils import Vector
    p0 = Vector(start_pt)
    p1 = Vector(end_pt)
    span_vec = p1 - p0
    total_len = span_vec.length
    if total_len < 0.5:
        return None
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root.location = p0
    root.rotation_euler = (0.0, 0.0, math.atan2(span_vec.y, span_vec.x))

    n_bays = max(1, int(bay_count))
    bay_w = total_len / float(n_bays)
    spring_z = height * 0.58
    arch_r = max(0.25, bay_w * 0.5 - pillar_radius * 0.85)
    amat = mat_arch or mat_pillar

    # 立柱、柱础与柱头过渡块
    for i in range(n_bays + 1):
        cx = i * bay_w
        bpy.ops.mesh.primitive_cylinder_add(vertices=28, radius=pillar_radius, depth=spring_z, location=(cx, 0.0, spring_z * 0.5))
        col = bpy.context.object
        col.name = f"{name}_Pillar_{i}"
        for p in col.data.polygons:
            p.use_smooth = True
        col.parent = root
        if mat_pillar:
            col.data.materials.append(mat_pillar)

        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, 0.0, 0.14))
        plinth = bpy.context.object
        plinth.name = f"{name}_Plinth_{i}"
        plinth.scale = (pillar_radius * 2.6, max(depth * 1.08, pillar_radius * 2.6), 0.28)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        add_bevel(plinth, width=0.018, segments=2)
        plinth.parent = root
        if mat_pillar:
            plinth.data.materials.append(mat_pillar)

        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, 0.0, spring_z - 0.06))
        cap = bpy.context.object
        cap.name = f"{name}_Capital_{i}"
        cap.scale = (pillar_radius * 2.5, max(depth * 1.06, pillar_radius * 2.5), 0.14)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        add_bevel(cap, width=0.015, segments=2)
        cap.parent = root
        if mat_pillar:
            cap.data.materials.append(mat_pillar)

    # BMesh 拱券与完整矩形拱腹填充段（两端垂直落到柱头上，绝不留三角形缺口）
    arch_segs = 28  # 4 左竖边 + 20 顶横边 + 4 右竖边
    side_segs = 4
    top_segs = 20
    for bi in range(n_bays):
        mid_x = (bi + 0.5) * bay_w
        me = bpy.data.meshes.new(f"{name}_ArchMesh_{bi}")
        bm = bmesh.new()
        hy = depth * 0.5
        front_in, front_out, back_in, back_out = [], [], [], []
        top_z = height - 0.16
        arch_rise = min(arch_r, top_z - spring_z - 0.14)
        left_x = mid_x - bay_w * 0.5
        right_x = mid_x + bay_w * 0.5

        for si in range(arch_segs + 1):
            ang = math.pi * (1.0 - si / float(arch_segs))
            ix = mid_x + arch_r * math.cos(ang)
            iz = spring_z + arch_rise * math.sin(ang)
            if si <= side_segs:
                t_s = si / float(side_segs)
                ox = left_x
                oz = spring_z + (top_z - spring_z) * t_s
            elif si >= arch_segs - side_segs:
                t_s = (si - (arch_segs - side_segs)) / float(side_segs)
                ox = right_x
                oz = top_z - (top_z - spring_z) * t_s
            else:
                t_s = (si - side_segs) / float(top_segs)
                ox = left_x + bay_w * t_s
                oz = top_z
            front_in.append(bm.verts.new((ix, -hy, iz)))
            front_out.append(bm.verts.new((ox, -hy, oz)))
            back_in.append(bm.verts.new((ix, hy, iz)))
            back_out.append(bm.verts.new((ox, hy, oz)))

        for si in range(arch_segs):
            bm.faces.new((front_in[si], front_in[si + 1], front_out[si + 1], front_out[si]))
            bm.faces.new((back_out[si], back_out[si + 1], back_in[si + 1], back_in[si]))
            f_soffit = bm.faces.new((front_in[si], back_in[si], back_in[si + 1], front_in[si + 1]))
            f_soffit.smooth = True
            bm.faces.new((front_out[si], front_out[si + 1], back_out[si + 1], back_out[si]))
        bm.faces.new((front_in[0], front_out[0], back_out[0], back_in[0]))
        bm.faces.new((back_in[-1], back_out[-1], front_out[-1], front_in[-1]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        aob = bpy.data.objects.new(f"{name}_Arch_{bi}", me)
        bpy.context.collection.objects.link(aob)
        aob.parent = root
        aob["vm_allow_float"] = True
        add_bevel(aob, width=0.008, segments=1)
        if amat:
            aob.data.materials.append(amat)

    # 顶部通长檐梁
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(total_len * 0.5, 0.0, height - 0.08))
    beam = bpy.context.object
    beam.name = f"{name}_Cornice"
    beam.scale = (total_len + pillar_radius * 2.8, depth * 1.18, 0.18)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    add_bevel(beam, width=0.02, segments=2)
    beam.parent = root
    beam["vm_allow_float"] = True
    if amat:
        beam.data.materials.append(amat)

    bpy.context.view_layer.update()
    return root
""",
}
