"""
templates/spatial_archetypes.py
Vibe-Modeler 模块化三维空间骨架生成器

为六大空间拓扑提供零穿模、法线干净、尺寸真实的底层三维结构积木，
帮助空间能力较弱的模型先搭稳三维大空间，再自由组合细节、材质与资产：
1. build_enclosed_room：封闭室内 / 阈限大厅 / 池核空间（支持真门窗开洞、藻井格栅顶、柱列，自动标记天花板供全景图透视）
2. build_vertical_atrium：多层垂直中庭 / 回廊楼梯深井（自动生成叠层回廊、跨层斜梯、护栏与立柱）
3. build_canyon_corridor：两侧夹峙建筑峡谷 / 粗野主义巨构柱廊（阵列肋柱、可选拱券连廊与尽头高耸塔碑）
4. build_spiral_stair_ribbon / build_orbital_ribbons / build_suspended_shards：超现实失重旋梯、贯穿太空弧环、悬浮碎片场
5. build_impossible_stair_loop / build_gravity_flip_room：非欧几里得视错觉彭罗斯阶梯、多向重力翻转房间
6. build_window_frame_stage：近景窗框与半透微风纱帘框景台
7. build_endless_ground / build_grounded_backdrop_ridge / create_volumetric_light_beam：无方边穿帮大圆地面、底座深扎地下的不漏底远山、有界体积光束
"""

SPATIAL_ARCHETYPE_SNIPPETS = {
    "spatial_box_helper": """
def _vm_arch_box(name, center, dims, mat=None, bevel_width=0.015, parent=None, allow_float=False):
    '''内部通用结构块：按真实米制尺寸建长方体并应用缩放与倒角。'''
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
    ob = bpy.context.object
    ob.name = name
    ob.scale = (max(0.004, float(dims[0])), max(0.004, float(dims[1])), max(0.004, float(dims[2])))
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel_width and bevel_width > 0:
        add_bevel(ob, width=min(bevel_width, min(dims) * 0.22), segments=2)
    if mat is not None:
        if ob.data.materials:
            ob.data.materials[0] = mat
        else:
            ob.data.materials.append(mat)
    if allow_float:
        ob["vm_allow_float"] = True
    if parent is not None:
        ob.parent = parent
    return ob

def _vm_sliced_wall(name_prefix, wall_axis, fixed_coord, span_min, span_max, z_min, z_max,
                    thickness, openings, mat=None, parent=None):
    '''
    用精确分块（窗台/过梁/左右墙垛）代替布尔挖洞，生成零破面的带门窗墙体。
    wall_axis: 'Y' 表示墙沿 X 展开（前/后墙，fixed_coord 为 Y）；'X' 表示墙沿 Y 展开（左/右墙，fixed_coord 为 X）。
    openings: [{"pos": 中心水平坐标, "width": 宽, "z_bottom": 底高, "height": 高}, ...]
    '''
    parts = []
    ops = sorted(openings or [], key=lambda d: float(d.get("pos", 0.0)))
    cursor = float(span_min)

    def _place_seg(tag, s0, s1, zb, zt):
        w = s1 - s0
        h = zt - zb
        if w <= 0.005 or h <= 0.005:
            return
        mid_s = (s0 + s1) * 0.5
        mid_z = (zb + zt) * 0.5
        if wall_axis == 'Y':
            center = (mid_s, fixed_coord, mid_z)
            dims = (w, thickness, h)
        else:
            center = (fixed_coord, mid_s, mid_z)
            dims = (thickness, w, h)
        parts.append(_vm_arch_box(f"{name_prefix}_{tag}_{len(parts)}", center, dims, mat=mat, parent=parent))

    for op in ops:
        w = max(0.2, float(op.get("width", 1.6)))
        h = max(0.2, float(op.get("height", 2.1)))
        pos = float(op.get("pos", 0.0))
        zb = max(z_min, float(op.get("z_bottom", 0.0)))
        zt = min(z_max, zb + h)
        o0 = max(cursor, pos - w * 0.5)
        o1 = min(span_max, pos + w * 0.5)
        if o1 <= o0:
            continue
        if o0 > cursor:
            _place_seg("pier", cursor, o0, z_min, z_max)
        if zb > z_min:
            _place_seg("sill", o0, o1, z_min, zb)
        if zt < z_max:
            _place_seg("lintel", o0, o1, zt, z_max)
        cursor = o1

    if cursor < span_max:
        _place_seg("pier", cursor, span_max, z_min, z_max)
    return parts
""",

    "build_enclosed_room": """
def build_enclosed_room(
    name="EnclosedRoom",
    width=12.0,
    length=16.0,
    height=4.2,
    wall_thickness=0.28,
    openings=None,
    ceiling_coffers=None,
    skylight_strips=0,
    pillars=None,
    floor_mat=None,
    wall_mat=None,
    ceiling_mat=None,
):
    '''
    构建封闭室内 / 阈限大厅 / 池核房间（原点位于房间地面中心，相机建议放在 Y 负半轴朝 +Y 拍）。
    openings: 字典，键可选 "back"(+Y), "front"(-Y), "left"(-X), "right"(+X)，
              值为 [{"pos": 0.0, "width": 2.4, "z_bottom": 0.0, "height": 2.6}, ...]
    ceiling_coffers: (nx, ny, depth) 例如 (3, 4, 0.28)，生成藻井格栅吊顶；None 为平顶。
    skylight_strips: >0 时在顶面嵌入发光天窗灯带条数，避免封闭房间死黑。
    pillars: [(x, y, radius), ...] 在房间内生成顶天立地的圆柱。
    返回根空物体 root。顶板自动带 root/child["vm_is_ceiling"]=True，方便 overview 全景俯拍自动透视内部。
    '''
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    hw, hl = width * 0.5, length * 0.5
    t = wall_thickness
    wmat = wall_mat or floor_mat
    cmat = ceiling_mat or wmat
    ops = openings or {}

    # 地板
    _vm_arch_box(f"{name}_Floor", (0, 0, -t * 0.5), (width + t * 2, length + t * 2, t), mat=floor_mat, parent=root)

    # 四面分块实墙（支持无破面门窗洞）
    _vm_sliced_wall(f"{name}_WallBack", 'Y', hl + t * 0.5, -hw, hw, 0.0, height, t, ops.get("back"), mat=wmat, parent=root)
    _vm_sliced_wall(f"{name}_WallFront", 'Y', -hl - t * 0.5, -hw, hw, 0.0, height, t, ops.get("front"), mat=wmat, parent=root)
    _vm_sliced_wall(f"{name}_WallLeft", 'X', -hw - t * 0.5, -hl, hl, 0.0, height, t, ops.get("left"), mat=wmat, parent=root)
    _vm_sliced_wall(f"{name}_WallRight", 'X', hw + t * 0.5, -hl, hl, 0.0, height, t, ops.get("right"), mat=wmat, parent=root)

    # 吊顶与可选格栅藻井
    ceil_parts = []
    top_slab = _vm_arch_box(f"{name}_CeilingTop", (0, 0, height + (0.25 if ceiling_coffers else 0.0) + t * 0.5),
                            (width + t * 2, length + t * 2, t), mat=cmat, parent=root)
    ceil_parts.append(top_slab)

    if ceiling_coffers and len(ceiling_coffers) == 3:
        nx, ny, cdepth = int(ceiling_coffers[0]), int(ceiling_coffers[1]), float(ceiling_coffers[2])
        beam_w = min(width / max(nx, 1), length / max(ny, 1)) * 0.18
        for i in range(nx + 1):
            bx = -hw + (width / max(nx, 1)) * i
            b = _vm_arch_box(f"{name}_CofferBeamX_{i}", (bx, 0, height + cdepth * 0.5), (beam_w, length, cdepth), mat=cmat, parent=root)
            ceil_parts.append(b)
        for j in range(ny + 1):
            by = -hl + (length / max(ny, 1)) * j
            b = _vm_arch_box(f"{name}_CofferBeamY_{j}", (0, by, height + cdepth * 0.5), (width, beam_w, cdepth), mat=cmat, parent=root)
            ceil_parts.append(b)

    if skylight_strips and skylight_strips > 0:
        emit_mat = bpy.data.materials.new(f"{name}_SkylightEmit")
        emit_mat.use_nodes = True
        bsdf = emit_mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.95, 0.98, 1.0, 1.0)
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = (0.92, 0.97, 1.0, 1.0)
                bsdf.inputs["Emission Strength"].default_value = 8.0
        for k in range(int(skylight_strips)):
            sx = -hw * 0.65 + (width * 0.65 * 2 / max(1, skylight_strips - 1)) * k if skylight_strips > 1 else 0.0
            strip = _vm_arch_box(f"{name}_Skylight_{k}", (sx, 0, height - 0.02), (0.32, length * 0.78, 0.04), mat=emit_mat, bevel_width=0.005, parent=root)
            ceil_parts.append(strip)

    for cp in ceil_parts:
        cp["vm_is_ceiling"] = True

    for idx, pspec in enumerate(pillars or []):
        px, py = float(pspec[0]), float(pspec[1])
        pr = float(pspec[2]) if len(pspec) > 2 else 0.28
        bpy.ops.mesh.primitive_cylinder_add(vertices=28, radius=pr, depth=height, location=(px, py, height * 0.5))
        col = bpy.context.object
        col.name = f"{name}_Pillar_{idx}"
        col.parent = root
        for poly in col.data.polygons:
            poly.use_smooth = True
        add_bevel(col, width=min(0.015, pr * 0.1), segments=2)
        if wmat:
            col.data.materials.append(wmat)

    bpy.context.view_layer.update()
    return root
""",

    "build_vertical_atrium": """
def build_vertical_atrium(
    name="VerticalAtrium",
    width=11.0,
    length=13.0,
    levels=4,
    level_height=3.4,
    walkway_width=1.8,
    enclosed_walls=True,
    add_stairs=True,
    add_railings=True,
    mat_structure=None,
    mat_railing=None,
):
    '''
    构建多层垂直中庭 / 层叠阶梯光井（支持阈限电梯井、哥特/工业多层回廊、纪念碑式深井）。
    levels 层回廊围绕中央挑空井道排列，自动建立跨层斜向楼梯与栏杆。
    '''
    import math as _m
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    hw, hl = width * 0.5, length * 0.5
    ww = min(walkway_width, min(width, length) * 0.35)
    total_h = levels * level_height
    rmat = mat_railing or mat_structure

    # 底层地面
    _vm_arch_box(f"{name}_BaseFloor", (0, 0, -0.15), (width + 0.6, length + 0.6, 0.30), mat=mat_structure, parent=root)

    # 四周外围墙（顶部留空采光井）
    if enclosed_walls:
        t = 0.28
        _vm_arch_box(f"{name}_WallBack", (0, hl + t * 0.5, total_h * 0.5), (width + t * 2, t, total_h), mat=mat_structure, parent=root)
        _vm_arch_box(f"{name}_WallLeft", (-hw - t * 0.5, 0, total_h * 0.5), (t, length, total_h), mat=mat_structure, parent=root)
        _vm_arch_box(f"{name}_WallRight", (hw + t * 0.5, 0, total_h * 0.5), (t, length, total_h), mat=mat_structure, parent=root)

    # 四角贯通立柱
    ix, iy = hw - ww, hl - ww
    for cx, cy in [(-ix, -iy), (ix, -iy), (-ix, iy), (ix, iy)]:
        _vm_arch_box(f"{name}_CoreCol_{cx:.1f}_{cy:.1f}", (cx, cy, total_h * 0.5), (0.34, 0.34, total_h), mat=mat_structure, parent=root)

    for lv in range(1, int(levels) + 1):
        z = lv * level_height
        slab_t = 0.22
        # 后、左、右三面回廊楼板（前侧留给机位仰拍/俯拍纵深）
        _vm_arch_box(f"{name}_WalkBack_L{lv}", (0, hl - ww * 0.5, z - slab_t * 0.5), (width, ww, slab_t), mat=mat_structure, parent=root)
        _vm_arch_box(f"{name}_WalkLeft_L{lv}", (-hw + ww * 0.5, -ww * 0.5, z - slab_t * 0.5), (ww, length - ww, slab_t), mat=mat_structure, parent=root)
        _vm_arch_box(f"{name}_WalkRight_L{lv}", (hw - ww * 0.5, -ww * 0.5, z - slab_t * 0.5), (ww, length - ww, slab_t), mat=mat_structure, parent=root)

        if add_railings:
            rh = 0.98
            # 内圈顶部扶手与竖向栏杆柱
            _vm_arch_box(f"{name}_RailBack_L{lv}", (0, iy, z + rh), (ix * 2, 0.06, 0.06), mat=rmat, bevel_width=0.008, parent=root)
            _vm_arch_box(f"{name}_RailLeft_L{lv}", (-ix, -ww * 0.5, z + rh), (0.06, length - ww, 0.06), mat=rmat, bevel_width=0.008, parent=root)
            _vm_arch_box(f"{name}_RailRight_L{lv}", (ix, -ww * 0.5, z + rh), (0.06, length - ww, 0.06), mat=rmat, bevel_width=0.008, parent=root)
            bal_n = max(4, int((ix * 2) / 0.55))
            for b_i in range(bal_n + 1):
                bx = -ix + (ix * 2 / bal_n) * b_i
                _vm_arch_box(f"{name}_BalB_{lv}_{b_i}", (bx, iy, z + rh * 0.5), (0.035, 0.035, rh), mat=rmat, bevel_width=0.004, parent=root)

        if add_stairs and lv <= levels:
            # 交替在井道内侧架设跨层斜向楼梯
            z0 = (lv - 1) * level_height
            steps = 14
            run_len = min(length * 0.46, 5.2)
            sx = (-ix + 0.65) if (lv % 2 == 1) else (ix - 0.65)
            dir_y = 1.0 if (lv % 2 == 1) else -1.0
            y_start = -run_len * 0.45 * dir_y
            for s in range(steps):
                frac = (s + 0.5) / steps
                sy = y_start + dir_y * run_len * frac
                sz = z0 + level_height * frac
                _vm_arch_box(f"{name}_Step_L{lv}_{s}", (sx, sy, sz - 0.04), (1.15, run_len / steps * 1.15, 0.09), mat=mat_structure, parent=root)

    bpy.context.view_layer.update()
    return root
""",

    "build_canyon_corridor": """
def build_canyon_corridor(
    name="CanyonCorridor",
    alley_width=7.2,
    length=38.0,
    height=18.0,
    bay_count=8,
    rib_depth=0.9,
    overhead_beams=True,
    focal_spire_height=0.0,
    catwalk_levels=0,
    add_railings=True,
    ground_mat=None,
    wall_mat=None,
    rail_mat=None,
):
    '''
    构建两侧夹峙的粗野主义巨构长廊 / 建筑峡谷（相机沿 Y 负轴向 +Y 仰拍或平拍）。
    overhead_beams: True 时在上方架设重复横梁产生强烈透视光影韵律。
    focal_spire_height: >0 时在走廊尽头 (+Y) 竖立高耸多级尖塔/纪念碑，形成神圣巨构视觉中心。
    catwalk_levels: >0 时在两侧峡谷高墙内壁生成多层挑空步道与 1.05m 标准人体尺度护栏（立刻赋予巨构真实崇高感）。
    '''
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    hx = alley_width * 0.5
    wmat = wall_mat or ground_mat
    rmat = rail_mat or wmat

    # 纵向街道地面（两侧被高墙完全夹住，绝不露边缘）
    _vm_arch_box(f"{name}_Floor", (0, length * 0.35, -0.2), (alley_width + rib_depth * 6, length * 1.35, 0.4), mat=ground_mat, parent=root)

    # 左右巨构主墙
    wall_t = 1.6
    for side, tag in ((-1.0, "L"), (1.0, "R")):
        wx = side * (hx + rib_depth + wall_t * 0.5)
        _vm_arch_box(f"{name}_MassWall_{tag}", (wx, length * 0.35, height * 0.5 - 0.2), (wall_t, length * 1.2, height + 0.4), mat=wmat, parent=root)

    # 阵列巨型竖向肋柱与顶部横梁
    y_start = -length * 0.18
    step_y = (length * 1.05) / max(1, bay_count - 1)
    rib_w = step_y * 0.28
    for i in range(int(bay_count)):
        ry = y_start + i * step_y
        for side, tag in ((-1.0, "L"), (1.0, "R")):
            rx = side * (hx + rib_depth * 0.5)
            _vm_arch_box(f"{name}_Rib_{tag}_{i}", (rx, ry, height * 0.5), (rib_depth, rib_w, height), mat=wmat, parent=root)
        if overhead_beams and i % 2 == 0:
            _vm_arch_box(f"{name}_SkyBeam_{i}", (0, ry, height - 0.45), (alley_width + rib_depth * 2, rib_w * 0.85, 0.85), mat=wmat, parent=root, allow_float=True)

    # 可选：两侧高墙多层挑空栈桥与 1.05m 标准人体尺度护栏
    if catwalk_levels and int(catwalk_levels) > 0:
        n_lv = int(catwalk_levels)
        cw_w = min(1.35, alley_width * 0.16)
        for lv in range(1, n_lv + 1):
            cz = (height * 0.78) * (lv / float(n_lv))
            for side, tag in ((-1.0, "L"), (1.0, "R")):
                cx = side * (hx - cw_w * 0.45)
                inner_x = side * (hx - cw_w * 0.92)
                _vm_arch_box(f"{name}_Catwalk_{tag}_L{lv}", (cx, length * 0.35, cz - 0.11),
                             (cw_w, length * 1.12, 0.22), mat=wmat, parent=root, allow_float=True)
                if add_railings:
                    rh = 1.05
                    _vm_arch_box(f"{name}_CW_TopRail_{tag}_L{lv}", (inner_x, length * 0.35, cz + rh),
                                 (0.045, length * 1.12, 0.045), mat=rmat, bevel_width=0.005, parent=root, allow_float=True)
                    _vm_arch_box(f"{name}_CW_MidRail_{tag}_L{lv}", (inner_x, length * 0.35, cz + rh * 0.52),
                                 (0.030, length * 1.12, 0.030), mat=rmat, bevel_width=0.004, parent=root, allow_float=True)
                    n_posts = max(6, int(length / 2.2))
                    for p_i in range(n_posts + 1):
                        py = y_start + (length * 1.08) * (p_i / float(n_posts))
                        _vm_arch_box(f"{name}_CW_Post_{tag}_L{lv}_{p_i}", (inner_x, py, cz + rh * 0.5),
                                     (0.038, 0.038, rh), mat=rmat, bevel_width=0.004, parent=root, allow_float=True)

    # 可选：尽头高耸层级塔碑
    if focal_spire_height and focal_spire_height > 0:
        sy = length * 0.92
        tiers = 4
        for t_i in range(tiers):
            frac0 = t_i / tiers
            frac1 = (t_i + 1) / tiers
            th = focal_spire_height * (frac1 - frac0)
            tz = focal_spire_height * frac0 + th * 0.5
            tw = alley_width * 0.58 * ((1.0 - frac0 * 0.72) ** 1.15)
            _vm_arch_box(f"{name}_SpireTier_{t_i}", (0, sy, tz), (tw, tw, th), mat=wmat, parent=root)
        bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=alley_width * 0.12, radius2=0.04,
                                        depth=focal_spire_height * 0.28,
                                        location=(0, sy, focal_spire_height * 1.12))
        tip = bpy.context.object
        tip.name = f"{name}_SpireApex"
        tip.parent = root
        if wmat:
            tip.data.materials.append(wmat)

    bpy.context.view_layer.update()
    return root
""",

    "surreal_and_noneuclidean_builders": """
def build_spiral_stair_ribbon(
    name="SkyStairs",
    turns=1.6,
    radius=4.2,
    rise=8.5,
    steps_per_turn=22,
    step_width=1.35,
    center=(0.0, 0.0, 0.0),
    tilt_deg=(0.0, 0.0, 0.0),
    mat=None,
):
    '''超现实悬空螺旋阶梯：无地面束缚，支持任意三维倾斜角贯穿云端或虚空。'''
    import math as _m
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root.location = center
    root.rotation_euler = (_m.radians(tilt_deg[0]), _m.radians(tilt_deg[1]), _m.radians(tilt_deg[2]))
    total_steps = max(6, int(turns * steps_per_turn))
    for i in range(total_steps):
        t = i / float(total_steps)
        ang = t * turns * 2.0 * _m.pi
        sx = radius * _m.cos(ang)
        sy = radius * _m.sin(ang)
        sz = t * rise
        step = _vm_arch_box(f"{name}_Step_{i:03d}", (sx, sy, sz), (step_width, 0.42, 0.10), mat=mat, bevel_width=0.012, parent=root)
        step.rotation_euler = (0.0, 0.0, ang)
    bpy.context.view_layer.update()
    return root

def build_orbital_ribbons(
    name="OrbitalRings",
    count=3,
    base_radius=7.5,
    tube_thickness=0.09,
    center=(0.0, 0.0, 4.0),
    seed=0,
    mat=None,
):
    '''构建超现实/神圣几何空间里的巨大倾斜交错光环或金属丝带环（参考倒悬钢琴/巨塔光环意象）。'''
    import math as _m, random as _r
    rnd = _r.Random(seed)
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root.location = center
    for i in range(int(count)):
        rad = base_radius * (0.78 + 0.26 * i)
        bpy.ops.mesh.primitive_torus_add(
            major_radius=rad,
            minor_radius=tube_thickness * (1.0 - 0.12 * min(i, 4)),
            major_segments=96,
            minor_segments=16,
            location=(0, 0, 0),
        )
        ring = bpy.context.object
        ring.name = f"{name}_Ring_{i}"
        ring.parent = root
        ring["vm_allow_float"] = True
        ring.rotation_euler = (
            _m.radians(rnd.uniform(-58, 58)),
            _m.radians(rnd.uniform(-58, 58)),
            _m.radians(rnd.uniform(0, 180)),
        )
        for p in ring.data.polygons:
            p.use_smooth = True
        if mat:
            ring.data.materials.append(mat)
    bpy.context.view_layer.update()
    return root

def build_suspended_shards(
    name="SuspendedShards",
    count=36,
    center=(0.0, 0.0, 3.0),
    spread=(5.5, 5.5, 4.5),
    scale_range=(0.12, 0.52),
    seed=0,
    mat=None,
):
    '''在空中散布锋利的碎裂镜面/几何薄片（表现碎裂空间、失重残片或飘散花瓣晶块）。'''
    import math as _m, random as _r
    rnd = _r.Random(seed)
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root.location = center
    for i in range(int(count)):
        px = rnd.uniform(-spread[0], spread[0])
        py = rnd.uniform(-spread[1], spread[1])
        pz = rnd.uniform(-spread[2] * 0.5, spread[2] * 0.5)
        s = rnd.uniform(scale_range[0], scale_range[1])
        verts = [
            (0.0, 0.0, 0.0),
            (s, rnd.uniform(-0.3, 0.4) * s, 0.0),
            (rnd.uniform(0.1, 0.8) * s, s * rnd.uniform(0.6, 1.3), rnd.uniform(-0.08, 0.08) * s),
        ]
        me = bpy.data.meshes.new(f"{name}_Mesh_{i}")
        me.from_pydata(verts, [], [(0, 1, 2)])
        me.update()
        ob = bpy.data.objects.new(f"{name}_Shard_{i}", me)
        bpy.context.collection.objects.link(ob)
        ob.parent = root
        ob["vm_allow_float"] = True
        ob.location = (px, py, pz)
        ob.rotation_euler = (rnd.uniform(0, _m.tau), rnd.uniform(0, _m.tau), rnd.uniform(0, _m.tau))
        add_solidify(ob, thickness=max(0.008, s * 0.04))
        add_bevel(ob, width=0.003, segments=1)
        if mat:
            ob.data.materials.append(mat)
    bpy.context.view_layer.update()
    return root

def build_gravity_flip_room(
    name="GravityFlipSpace",
    size=13.0,
    height=9.5,
    arch_count=4,
    mat_primary=None,
    mat_accent=None,
):
    '''
    构建非欧几里得 / 多向重力空间：地板、左墙、右墙与天花板四个方向同时生长出对称旋转的楼梯与门廊，
    打破上下重力常识（埃舍尔 Relativity 式空间骨架）。
    '''
    import math as _m
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    hs = size * 0.5
    amat = mat_accent or mat_primary

    # 外壳围合腔体（保留顶面标记以便 overview 查看）
    floor_o = _vm_arch_box(f"{name}_PlaneBottom", (0, 0, -0.2), (size, size, 0.4), mat=mat_primary, parent=root)
    top_o = _vm_arch_box(f"{name}_PlaneTop", (0, 0, height + 0.2), (size, size, 0.4), mat=mat_primary, parent=root)
    top_o["vm_is_ceiling"] = True
    _vm_arch_box(f"{name}_PlaneBack", (0, hs + 0.2, height * 0.5), (size, 0.4, height), mat=mat_primary, parent=root)
    _vm_arch_box(f"{name}_PlaneLeft", (-hs - 0.2, 0, height * 0.5), (0.4, size, height), mat=mat_primary, parent=root)
    _vm_arch_box(f"{name}_PlaneRight", (hs + 0.2, 0, height * 0.5), (0.4, size, height), mat=mat_primary, parent=root)

    # 在 4 个重力基准面上分别生长阶梯桥与门框（地面 0°、顶面 180°、左墙 -90°、右墙 +90°）
    planes = [
        ("Down", (0, 0, 0), (0, 0, 0)),
        ("Up", (0, 1.2, height), (_m.pi, 0, _m.pi * 0.5)),
        ("LeftWall", (-hs, -0.8, height * 0.48), (0, _m.pi * 0.5, 0)),
        ("RightWall", (hs, 1.0, height * 0.55), (0, -_m.pi * 0.5, _m.pi)),
    ]
    for tag, loc, rot in planes:
        zone = bpy.data.objects.new(f"{name}_GravityZone_{tag}", None)
        bpy.context.collection.objects.link(zone)
        zone.parent = root
        zone.location = loc
        zone.rotation_euler = rot
        # 阶梯段
        for s in range(10):
            _vm_arch_box(f"{name}_{tag}_Step_{s}", (0, -2.2 + s * 0.36, 0.14 + s * 0.22),
                         (1.3, 0.38, 0.14), mat=amat, parent=zone)
        # 顶部挑台与门廊框
        _vm_arch_box(f"{name}_{tag}_Landing", (0, 1.9, 2.35), (2.2, 1.6, 0.22), mat=mat_primary, parent=zone)
        for px in (-0.75, 0.75):
            _vm_arch_box(f"{name}_{tag}_PortalPier_{px}", (px, 2.4, 3.55), (0.26, 0.28, 2.2), mat=amat, parent=zone)
        _vm_arch_box(f"{name}_{tag}_PortalLintel", (0, 2.4, 4.75), (1.76, 0.30, 0.26), mat=amat, parent=zone)

    bpy.context.view_layer.update()
    return root

def build_impossible_stair_loop(
    name="ImpossiblePenroseLoop",
    cam_location=(9.0, -9.0, 8.2),
    target=(0.0, 0.0, 1.2),
    scale=2.6,
    mat=None,
    setup_ortho_camera=True,
):
    '''
    构建正交视线精确闭合的彭罗斯不可能阶梯（Non-Euclidean Penrose Stairs）：
    四段阶梯严格保持 X/Y 正交 90° 转角且每级真实向上攀升 step_rise，
    通过精确分配四边水平跨度使终点等于 P0 + k * view_ray，在正交镜头下 100% 无缝咬合闭合！
    '''
    from mathutils import Vector
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    cam_v = Vector(cam_location)
    tgt_v = Vector(target)
    view_ray = (cam_v - tgt_v).normalized()
    if abs(view_ray.z) < 0.2:
        view_ray = Vector((0.58, -0.58, 0.57)).normalized()

    s = float(scale)
    steps_per_side = 5
    total_steps = steps_per_side * 4
    step_rise = 0.14 * (s / 2.6)
    total_rise = total_steps * step_rise

    # 闭合条件：终点 = 起点 + k0 * view_ray，且终点 Z - 起点 Z = total_rise
    k0 = total_rise / view_ray.z
    dx_total = k0 * view_ray.x
    dy_total = k0 * view_ray.y

    # 将 dx_total, dy_total 分配到正方向或负方向边长，保证四条边全部 >= 2*s 且严格沿 X/Y 轴正交
    len_pos_x = 2.0 * s + max(0.0, dx_total)
    len_neg_x = 2.0 * s + max(0.0, -dx_total)
    len_pos_y = 2.0 * s + max(0.0, dy_total)
    len_neg_y = 2.0 * s + max(0.0, -dy_total)

    # 从屏幕最下方的近角 (+s, -s) 起步（逆时针 +Y -> -X -> -Y -> +X），
    # 视错觉搭接点落在最下方外缘，梁体无需削薄也不会遮挡内圈任何阶梯！
    p0 = Vector((s, -s, 0.0)) + tgt_v
    flights = [
        Vector((0.0, len_pos_y, 0.0)),
        Vector((-len_neg_x, 0.0, 0.0)),
        Vector((0.0, -len_neg_y, 0.0)),
        Vector((len_pos_x, 0.0, 0.0)),
    ]

    beam_h = 0.85 * (s / 2.6)
    tread_w = 0.44 * s
    cur_xy = Vector((p0.x, p0.y, 0.0))
    idx = 0
    for side, fvec in enumerate(flights):
        fdir = fvec.normalized()
        inner_span = max(0.2, fvec.length - tread_w)
        step_len = inner_span / float(steps_per_side)
        is_x = abs(fvec.x) > abs(fvec.y)
        cb_z = p0.z + idx * step_rise
        cb = _vm_arch_box(f"{name}_Corner_{side}", (cur_xy.x, cur_xy.y, cb_z - beam_h * 0.5),
                          (tread_w, tread_w, beam_h), mat=mat, bevel_width=0.006, parent=root)
        cb["vm_allow_float"] = True
        if hasattr(cb, "visible_shadow"):
            cb.visible_shadow = False
        for k in range(steps_per_side):
            pos_xy = cur_xy + fdir * (tread_w * 0.5 + step_len * (k + 0.5))
            top_z = p0.z + (idx + 1) * step_rise
            dims = (step_len * 1.02, tread_w, beam_h) if is_x else (tread_w, step_len * 1.02, beam_h)
            st = _vm_arch_box(f"{name}_Step_{idx:02d}", (pos_xy.x, pos_xy.y, top_z - beam_h * 0.5),
                              dims, mat=mat, bevel_width=0.006, parent=root)
            st["vm_allow_float"] = True
            if hasattr(st, "visible_shadow"):
                st.visible_shadow = False
            idx += 1
        cur_xy = cur_xy + fvec

    # 放置最终闭合角台 Corner_4（三维位置恰好等于 Corner_0 + k0 * view_ray，在正交画面中与起点无缝重合）
    cb_end = _vm_arch_box(f"{name}_Corner_End", (cur_xy.x, cur_xy.y, p0.z + idx * step_rise - beam_h * 0.5),
                          (tread_w, tread_w, beam_h), mat=mat, bevel_width=0.006, parent=root)
    cb_end["vm_allow_float"] = True
    if hasattr(cb_end, "visible_shadow"):
        cb_end.visible_shadow = False

    if setup_ortho_camera:
        cam_data = bpy.data.cameras.new(f"{name}_OrthoCam")
        cam_data.type = 'ORTHO'
        cam_data.ortho_scale = max(len_pos_x, len_neg_x, len_pos_y, len_neg_y) * 1.95
        cam_obj = bpy.data.objects.new("Main_Camera", cam_data)
        bpy.context.collection.objects.link(cam_obj)
        cam_obj.location = cam_v
        cam_obj.rotation_euler = (tgt_v - cam_v).to_track_quat('-Z', 'Y').to_euler()
        bpy.context.scene.camera = cam_obj

    bpy.context.view_layer.update()
    return root
""",

    "build_window_frame_stage": """
def build_window_frame_stage(
    name="WindowStage",
    win_width=2.8,
    win_height=1.9,
    sill_z=0.88,
    sill_depth=0.48,
    add_curtains=True,
    curtain_sway=0.32,
    wall_mat=None,
    curtain_mat=None,
):
    '''
    构建近景窗框 + 宽窗台 + 微风吹拂半透明前景纱帘（参考清透夏日海景窗台框景）。
    相机放在 (0, -1.6~-2.4, sill_z + 0.55) 朝 +Y 拍摄，透过两侧纱帘看到窗台小物件与窗外海天。
    '''
    import math as _m
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)

    # 窗墙（在 Y=0 处开大窗洞）
    _vm_sliced_wall(
        f"{name}_Wall", 'Y', 0.0, -4.5, 4.5, -0.5, 4.0, 0.26,
        openings=[{"pos": 0.0, "width": win_width, "z_bottom": sill_z, "height": win_height}],
        mat=wall_mat, parent=root,
    )
    # 宽阔窗台台面（供摆放玻璃水杯、花瓶、书本）
    sill = _vm_arch_box(f"{name}_WindowSill", (0.0, -0.10, sill_z - 0.04),
                        (win_width + 0.36, sill_depth, 0.08), mat=wall_mat, bevel_width=0.01, parent=root)

    # 窗框外缘细框
    hw = win_width * 0.5
    _vm_arch_box(f"{name}_FrameTop", (0.0, 0.02, sill_z + win_height - 0.03), (win_width, 0.08, 0.06), mat=wall_mat, parent=root)
    _vm_arch_box(f"{name}_FrameLeft", (-hw + 0.03, 0.02, sill_z + win_height * 0.5), (0.06, 0.08, win_height), mat=wall_mat, parent=root)
    _vm_arch_box(f"{name}_FrameRight", (hw - 0.03, 0.02, sill_z + win_height * 0.5), (0.06, 0.08, win_height), mat=wall_mat, parent=root)

    if add_curtains:
        cmat = curtain_mat
        if cmat is None:
            cmat = bpy.data.materials.new(f"{name}_SheerCurtainMat")
            cmat.use_nodes = True
            if hasattr(cmat, "surface_render_method"):
                cmat.surface_render_method = 'BLENDED'
            nt = cmat.node_tree
            nt.nodes.clear()
            out = nt.nodes.new("ShaderNodeOutputMaterial")
            trans = nt.nodes.new("ShaderNodeBsdfTransparent")
            trans.inputs["Color"].default_value = (0.72, 0.93, 1.0, 1.0)
            transl = nt.nodes.new("ShaderNodeBsdfTranslucent")
            transl.inputs["Color"].default_value = (0.78, 0.95, 1.0, 1.0)
            lw = nt.nodes.new("ShaderNodeLayerWeight")
            lw.inputs["Blend"].default_value = 0.35
            mix = nt.nodes.new("ShaderNodeMixShader")
            nt.links.new(lw.outputs["Facing"], mix.inputs["Fac"])
            nt.links.new(trans.outputs["BSDF"], mix.inputs[1])
            nt.links.new(transl.outputs["BSDF"], mix.inputs[2])
            nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])

        for side, tag in ((-1.0, "Left"), (1.0, "Right")):
            nx, nz = 28, 36
            verts, faces = [], []
            c_w = win_width * 0.46
            c_h = win_height + 0.45
            z_top = sill_z + win_height + 0.15
            for iz in range(nz + 1):
                vz = iz / float(nz)  # 0 顶部固定，1 底部随风飘起
                z = z_top - vz * c_h
                sway = (vz ** 1.55) * curtain_sway
                for ix in range(nx + 1):
                    ux = ix / float(nx)
                    base_x = side * (hw + 0.08 - ux * c_w) - side * sway * (0.4 + 0.6 * ux)
                    pleat = 0.045 * _m.sin(ux * _m.pi * 5.0) * (0.35 + 0.65 * vz)
                    billow = -0.28 * _m.sin(vz * _m.pi * 0.85) * (0.3 + 0.7 * ux)
                    y = -0.26 + pleat + billow
                    verts.append((base_x, y, z))
            for iz in range(nz):
                for ix in range(nx):
                    k = iz * (nx + 1) + ix
                    faces.append((k, k + 1, k + nx + 2, k + nx + 1))
            me = bpy.data.meshes.new(f"{name}_Curtain_{tag}")
            me.from_pydata(verts, [], faces)
            me.update()
            cob = bpy.data.objects.new(f"{name}_Curtain_{tag}", me)
            bpy.context.collection.objects.link(cob)
            cob.parent = root
            cob["vm_allow_float"] = True
            for p in cob.data.polygons:
                p.use_smooth = True
            cob.data.materials.append(cmat)

    bpy.context.view_layer.update()
    return root
""",

    "horizon_and_volumetrics": """
def build_endless_ground(
    name="EndlessGround",
    radius=95.0,
    subdivide_level=6,
    height_scale=0.18,
    noise_scale=0.16,
    mat=None,
):
    '''
    构建无方形切角穿帮的大尺度圆形地景基底（半径默认 95 米），彻底杜绝 30x30 米方形地毯露边穿帮。
    '''
    bpy.ops.mesh.primitive_circle_add(vertices=96, radius=radius, fill_type='TRIFAN', location=(0.0, 0.0, 0.0))
    ground = bpy.context.object
    ground.name = name
    if mat:
        ground.data.materials.append(mat)
    if height_scale and height_scale > 0.001:
        apply_gn_terrain_displacement(ground, height_scale=height_scale, noise_scale=noise_scale, subdivide_level=subdivide_level)
    else:
        for p in ground.data.polygons:
            p.use_smooth = True
    bpy.context.view_layer.update()
    return ground

def build_grounded_backdrop_ridge(
    name="GroundedRidge",
    distance_y=48.0,
    span_x=120.0,
    peak_height=14.0,
    base_sink=-4.5,
    depth_y=22.0,
    seed=0,
    mat=None,
):
    '''
    构建底座强制深扎入地下（默认 Z=-4.5 米）的闭合三维实体远山/岩壁，
    从几何结构上 100% 杜绝弱模型自写网格导致远山悬空漏出底部天空的 Bug。
    '''
    import math as _m, random as _r
    rnd = _r.Random(seed)
    nx, ny = 56, 14
    verts, faces = [], []
    ph1 = rnd.uniform(0, 6.28)
    ph2 = rnd.uniform(0, 6.28)
    ph3 = rnd.uniform(0, 6.28)

    for iy in range(ny + 1):
        vy = iy / float(ny)  # 0 前坡脚 -> 0.65 主峰脊 -> 1.0 后坡底
        y = distance_y + (vy - 0.3) * depth_y
        # 前后两端强制回落到 base_sink（深埋地下），绝不可能翘起漏底！
        profile = _m.sin(vy * _m.pi) ** 1.25
        for ix in range(nx + 1):
            ux = ix / float(nx)
            x = (ux - 0.5) * span_x
            edge_taper = _m.sin(ux * _m.pi) ** 0.65
            ridge_wave = (
                0.55
                + 0.25 * _m.sin(x * 0.07 + ph1)
                + 0.14 * _m.cos(x * 0.19 + ph2)
                + 0.08 * _m.sin(x * 0.43 + vy * 2.5 + ph3)
            )
            if iy == 0 or iy == ny:
                z = base_sink
            else:
                z = base_sink + (peak_height - base_sink) * profile * edge_taper * max(0.15, ridge_wave)
            verts.append((x, y, z))

    for iy in range(ny):
        for ix in range(nx):
            k = iy * (nx + 1) + ix
            faces.append((k, k + 1, k + nx + 2, k + nx + 1))

    me = bpy.data.meshes.new(name + "_Mesh")
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    for p in ob.data.polygons:
        p.use_smooth = True
    add_noise_displace(ob, strength=min(1.2, peak_height * 0.07), noise_scale=0.25)
    if mat:
        ob.data.materials.append(mat)
    bpy.context.view_layer.update()
    return ob

def create_volumetric_light_beam(
    name="VolumetricLightShaft",
    source_location=(-4.0, 2.0, 11.0),
    target_location=(0.5, 0.0, 0.5),
    box_size=(14.0, 14.0, 14.0),
    density=0.024,
    anisotropy=0.45,
    color=(1.0, 0.94, 0.84),
    spot_energy=2400.0,
    spot_angle_deg=38.0,
):
    '''
    一键创建“有界局部体积雾盒 + 对准目标的高能聚光灯束（丁达尔光柱/神圣天光）”。
    使用有界雾盒而非世界全局体积，避免把远景天空和 HDRI 反射全部吞成死黑。
    '''
    import math as _m
    from mathutils import Vector
    src = Vector(source_location)
    tgt = Vector(target_location)
    mid = (src + tgt) * 0.5

    fog_mat = bpy.data.materials.new(f"{name}_FogMat")
    fog_mat.use_nodes = True
    nodes = fog_mat.node_tree.nodes
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    vol = nodes.new("ShaderNodeVolumeScatter")
    vol.inputs["Color"].default_value = (color[0], color[1], color[2], 1.0)
    vol.inputs["Density"].default_value = density
    vol.inputs["Anisotropy"].default_value = anisotropy
    fog_mat.node_tree.links.new(vol.outputs["Volume"], out.inputs["Volume"])

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=mid)
    fog_box = bpy.context.object
    fog_box.name = f"{name}_VolumeBox"
    fog_box.scale = box_size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    fog_box.display_type = 'WIRE'
    fog_box["vm_is_volume"] = True
    fog_box["vm_allow_float"] = True
    fog_box.data.materials.append(fog_mat)

    ldata = bpy.data.lights.new(name=f"{name}_Spot", type='SPOT')
    ldata.energy = spot_energy
    ldata.color = color[:3]
    ldata.spot_size = _m.radians(spot_angle_deg)
    ldata.spot_blend = 0.42
    ldata.shadow_soft_size = 0.35
    lobj = bpy.data.objects.new(name=f"{name}_Spot", object_data=ldata)
    bpy.context.collection.objects.link(lobj)
    lobj.location = src
    lobj.rotation_euler = (tgt - src).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.view_layer.update()
    return {"volume_box": fog_box, "spot_light": lobj}
""",

    "scifi_in_reality_and_megastructures": """
def build_megastructure_horizon(
    name="DistantMegastructure",
    distance_y=155.0,
    span_x=175.0,
    base_height=88.0,
    tower_count=3,
    style="brutalist_fortress",
    add_greebles=True,
    add_window_lights=True,
    mat_hull=None,
    mat_rib=None,
    mat_glow=None,
    seed=10,
):
    '''
    构建“真实下的科幻”（参考 imageref3 bg013 / images.jpg / 20211026）远景百米级巨型科幻构筑物群。
    位于 Y = 120m ~ 300m 远方天际线，底座深扎地下 Z = -8.0m 绝不悬空漏底（hovering_ovoid_ship 除外，自动标记 vm_allow_float）。
    style 可选:
      - "brutalist_fortress": 阶梯内倾巨型装甲要塞 + 悬挑飞扶壁肋梁 + 表面高频工业 Greeble 凸起与舷窗微光
      - "orbital_spire": 拔地而起的轨道电梯巨塔 + 多层环形停泊船坞平台 + 顶部高耸天线阵列
      - "hovering_ovoid_ship": 静默悬浮于湖面/山谷上空的哑光白/深灰巨型椭圆母舰（带机械进气槽缝与底舱微光）
    '''
    import bmesh
    import math as _m, random as _r
    rnd = _r.Random(seed)
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    hmat = mat_hull
    rmat = mat_rib or mat_hull
    gmat = mat_glow
    if gmat is None and add_window_lights:
        gmat = bpy.data.materials.new(f"{name}_BeaconGlow")
        gmat.use_nodes = True
        bsdf = gmat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.55, 0.92, 1.0, 1.0)
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = (0.45, 0.88, 1.0, 1.0)
                bsdf.inputs["Emission Strength"].default_value = 5.5

    st = str(style or "brutalist_fortress").lower().strip()
    if st == "hovering_ovoid_ship":
        root["vm_allow_float"] = True
        for i in range(max(1, int(tower_count))):
            ux = (i / max(1.0, float(tower_count - 1)) - 0.5) if tower_count > 1 else 0.0
            cx = ux * span_x * 0.55 + rnd.uniform(-6.0, 6.0)
            cy = distance_y + abs(ux) * 28.0 + rnd.uniform(-8.0, 8.0)
            cz = base_height * (0.48 if i == 0 else rnd.uniform(0.35, 0.62))
            rad = base_height * (0.34 if i == 0 else rnd.uniform(0.18, 0.26))
            bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=rad, location=(cx, cy, cz))
            hull = bpy.context.object
            hull.name = f"{name}_OvoidHull_{i}"
            hull.scale = (0.76, 0.68, 1.38)
            hull.rotation_euler = (_m.radians(rnd.uniform(-6, 6)), _m.radians(rnd.uniform(-8, 8)), _m.radians(rnd.uniform(-25, 25)))
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            for p in hull.data.polygons:
                p.use_smooth = True
            hull.parent = root
            hull["vm_allow_float"] = True
            if hmat:
                hull.data.materials.append(hmat)
            # 腰部内凹机械进气环槽与悬挂稳定翼
            for band_z in (-rad * 0.25, rad * 0.18):
                ring = _vm_arch_box(f"{name}_IntakeSlot_{i}_{band_z:.1f}", (cx, cy - rad * 0.52, cz + band_z),
                                    (rad * 0.88, rad * 0.24, rad * 0.08), mat=rmat, bevel_width=0.04, parent=root, allow_float=True)
                if gmat:
                    _vm_arch_box(f"{name}_SlotGlow_{i}_{band_z:.1f}", (cx, cy - rad * 0.62, cz + band_z),
                                 (rad * 0.72, 0.12, rad * 0.025), mat=gmat, bevel_width=0.01, parent=root, allow_float=True)
        bpy.context.view_layer.update()
        return root

    # brutalist_fortress 或 orbital_spire：底座一律深扎 Z = -8.0m
    sink_z = -8.0
    n_t = max(1, int(tower_count))
    for i in range(n_t):
        ux = (i / float(n_t - 1) - 0.5) if n_t > 1 else 0.0
        is_hero = (i == n_t // 2)
        tx = ux * span_x * 0.68 + (0.0 if is_hero else rnd.uniform(-9.0, 9.0))
        ty = distance_y + (0.0 if is_hero else abs(ux) * 32.0 + rnd.uniform(-6.0, 12.0))
        th = base_height * (1.08 if is_hero else rnd.uniform(0.68, 0.88))
        tw = th * (0.22 if st == "orbital_spire" else 0.42)
        td = tw * 0.82

        # 1. 一级阶梯/内倾主装甲体（tiers=4）
        tiers = 5 if st == "orbital_spire" else 4
        for t_i in range(tiers):
            f0 = t_i / float(tiers)
            f1 = (t_i + 1) / float(tiers)
            z0 = sink_z if t_i == 0 else th * f0
            z1 = th * f1
            seg_h = z1 - z0
            taper = (1.0 - f0 * (0.64 if st == "orbital_spire" else 0.46))
            sw = tw * taper
            sd = td * taper
            _vm_arch_box(
                f"{name}_Hull_{i}_T{t_i}",
                (tx, ty, (z0 + z1) * 0.5),
                (sw, sd, seg_h),
                mat=hmat,
                bevel_width=0.12,
                parent=root,
            )
            # 2. 二级悬挑肋梁 / 巨型反应堆护翼 / 环形停泊船坞
            for side in (-1.0, 1.0):
                rib_x = tx + side * (sw * 0.52)
                _vm_arch_box(
                    f"{name}_Buttress_{i}_T{t_i}_{'L' if side < 0 else 'R'}",
                    (rib_x, ty - sd * 0.12, (z0 + z1) * 0.5),
                    (sw * 0.16, sd * 1.14, seg_h * 0.92),
                    mat=rmat,
                    bevel_width=0.08,
                    parent=root,
                )
            if t_i in (1, 2, 3):
                _vm_arch_box(
                    f"{name}_CantileverDeck_{i}_T{t_i}",
                    (tx + rnd.uniform(-0.12, 0.12) * sw, ty - sd * 0.48, z1 - seg_h * 0.18),
                    (sw * 1.38, sd * 0.45, max(1.4, seg_h * 0.14)),
                    mat=rmat,
                    bevel_width=0.06,
                    parent=root,
                    allow_float=True,
                )

            # 3. 三级高频工业 Greebles（表面装甲凸块、竖向散热槽、微光舷窗点阵）
            if add_greebles:
                n_g = 10 if is_hero else 6
                for g_i in range(n_g):
                    gx = tx + rnd.uniform(-0.42, 0.42) * sw
                    gz = max(2.0, z0 + rnd.uniform(0.12, 0.88) * seg_h)
                    gw = rnd.uniform(0.08, 0.22) * sw
                    gh = rnd.uniform(0.10, 0.28) * seg_h
                    gd = rnd.uniform(0.6, 2.2)
                    _vm_arch_box(
                        f"{name}_Greeble_{i}_{t_i}_{g_i}",
                        (gx, ty - sd * 0.5 - gd * 0.35, gz),
                        (gw, gd, gh),
                        mat=rmat if g_i % 2 == 0 else hmat,
                        bevel_width=0.03,
                        parent=root,
                        allow_float=True,
                    )
            if add_window_lights and gmat is not None and t_i >= 1:
                for w_i in range(3):
                    wx = tx + (w_i - 1) * (sw * 0.28)
                    wz = z0 + seg_h * (0.32 + 0.22 * w_i)
                    _vm_arch_box(
                        f"{name}_BeaconStrip_{i}_{t_i}_{w_i}",
                        (wx, ty - sd * 0.52, wz),
                        (sw * 0.18, 0.25, max(0.35, seg_h * 0.035)),
                        mat=gmat,
                        bevel_width=0.01,
                        parent=root,
                        allow_float=True,
                    )

        # 顶部高耸通信天线塔阵列
        for a_i in range(3):
            ax = tx + (a_i - 1) * (tw * 0.14)
            ah = th * rnd.uniform(0.16, 0.28)
            _vm_arch_box(
                f"{name}_AntennaSpire_{i}_{a_i}",
                (ax, ty, th + ah * 0.45),
                (max(0.28, tw * 0.025), max(0.28, tw * 0.025), ah),
                mat=rmat,
                bevel_width=0.02,
                parent=root,
                allow_float=True,
            )

    bpy.context.view_layer.update()
    return root

def build_holographic_data_matrix(
    name="HolographicMatrix",
    center=(0.0, 11.0, 3.8),
    span=(9.5, 12.0, 5.5),
    panel_count=26,
    add_sky_wireframe_dome=False,
    dome_radius=68.0,
    glow_color=(0.08, 0.88, 1.0),
    emission_strength=4.2,
    seed=21,
):
    '''
    构建“真实下的科幻”全息数据矩阵与天体线框罩（参考 imageref3 bg014a / Wbg6 / Act1bg）。
    自动创建程序化镂空电路/刻度纹理的半透明青蓝/琥珀全息 HUD 屏幕阵列（绝非死板实心色块），
    可选开启 add_sky_wireframe_dome 在天穹生成巨型六边形/经纬线天体星盘线框网格罩。
    '''
    import math as _m, random as _r
    rnd = _r.Random(seed)
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root.location = center
    root["vm_allow_float"] = True

    # 创建程序化全息网格/电路半透明材质（用 Brick + Checker 混合驱动 Alpha 与自发光）
    holo_mat = bpy.data.materials.new(f"{name}_HoloCircuitMat")
    holo_mat.use_nodes = True
    if hasattr(holo_mat, "surface_render_method"):
        holo_mat.surface_render_method = 'BLENDED'
    elif hasattr(holo_mat, "blend_method"):
        holo_mat.blend_method = 'BLEND'
    nt = holo_mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    mix_sh = nt.nodes.new("ShaderNodeMixShader")
    trans = nt.nodes.new("ShaderNodeBsdfTransparent")
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (glow_color[0], glow_color[1], glow_color[2], 1.0)
    emit.inputs["Strength"].default_value = emission_strength

    coord = nt.nodes.new("ShaderNodeTexCoord")
    brick = nt.nodes.new("ShaderNodeTexBrick")
    brick.inputs["Scale"].default_value = 18.0
    brick.inputs["Mortar Size"].default_value = 0.035
    brick.inputs["Color1"].default_value = (0.08, 0.08, 0.08, 1.0)
    brick.inputs["Color2"].default_value = (0.32, 0.32, 0.32, 1.0)
    brick.inputs["Mortar"].default_value = (1.0, 1.0, 1.0, 1.0)
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.05
    ramp.color_ramp.elements[0].color = (0.04, 0.04, 0.04, 1.0)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = (0.68, 0.68, 0.68, 1.0)

    nt.links.new(coord.outputs["Generated"], brick.inputs["Vector"])
    nt.links.new(brick.outputs["Color"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], mix_sh.inputs["Fac"])
    nt.links.new(trans.outputs["BSDF"], mix_sh.inputs[1])
    nt.links.new(emit.outputs["Emission"], mix_sh.inputs[2])
    nt.links.new(mix_sh.outputs["Shader"], out.inputs["Surface"])

    # 在两侧与高空分层排布全息数据面板（留出中央主视觉通廊）
    for i in range(int(panel_count)):
        side = -1.0 if i % 2 == 0 else 1.0
        px = side * rnd.uniform(span[0] * 0.22, span[0] * 0.55)
        py = rnd.uniform(-span[1] * 0.45, span[1] * 0.55)
        pz = rnd.uniform(-span[2] * 0.35, span[2] * 0.55)
        pw = rnd.uniform(0.85, 2.45)
        ph = pw * rnd.uniform(0.45, 0.78)
        bpy.ops.mesh.primitive_plane_add(size=1.0, location=(px, py, pz))
        pan = bpy.context.object
        pan.name = f"{name}_HUDPanel_{i:02d}"
        pan.scale = (pw, ph, 1.0)
        pan.rotation_euler = (_m.radians(90.0 + rnd.uniform(-12, 12)), 0.0, _m.radians(-side * rnd.uniform(12, 38)))
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        add_solidify(pan, thickness=0.006)
        pan.parent = root
        pan["vm_allow_float"] = True
        if hasattr(pan, "visible_shadow"):
            pan.visible_shadow = False
        pan.data.materials.append(holo_mat)

    if add_sky_wireframe_dome:
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=dome_radius, location=(0.0, 0.0, 0.0))
        dome = bpy.context.object
        dome.name = f"{name}_CelestialWireDome"
        dome.parent = root
        dome["vm_allow_float"] = True
        if hasattr(dome, "visible_shadow"):
            dome.visible_shadow = False
        wmod = dome.modifiers.new("Wireframe", 'WIREFRAME')
        wmod.thickness = max(0.06, dome_radius * 0.0022)
        wmod.use_even_offset = True
        dome.data.materials.append(holo_mat)

    bpy.context.view_layer.update()
    return root

def build_inverted_sky_megacity(
    name="InvertedSkyCity",
    ceiling_z=52.0,
    y_range=(18.0, 145.0),
    span_x=115.0,
    block_count=72,
    add_bridge_spire=True,
    add_inverted_pyramid=False,
    mat_building=None,
    mat_window_glow=None,
    seed=33,
):
    '''
    构建天穹倒悬大都会 / 倒置金字塔奇观（参考 imageref3 5aee37 / BG_epilogue / v2-ad53）。
    在 Z = ceiling_z 的高空倒挂密集的高低错落建筑群与跨天引桥，可选中央贯通天地巨塔或倒置黑曜石金字塔。
    '''
    import math as _m, random as _r
    rnd = _r.Random(seed)
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root["vm_allow_float"] = True

    # 顶层天穹倒挂基座板
    y_mid = (y_range[0] + y_range[1]) * 0.5
    y_len = y_range[1] - y_range[0]
    _vm_arch_box(
        f"{name}_SkyCrustSlab",
        (0.0, y_mid, ceiling_z + 2.0),
        (span_x * 1.15, y_len * 1.12, 4.0),
        mat=mat_building,
        bevel_width=0.1,
        parent=root,
        allow_float=True,
    )

    for i in range(int(block_count)):
        bx = rnd.uniform(-span_x * 0.48, span_x * 0.48)
        by = rnd.uniform(y_range[0], y_range[1])
        # 中央留出视觉走廊给连接巨塔或天际线光带
        if abs(bx) < 6.5 and not add_bridge_spire:
            bx += 8.5 if bx >= 0 else -8.5
        bw = rnd.uniform(2.4, 7.5)
        bd = rnd.uniform(2.4, 7.5)
        bh = rnd.uniform(6.0, ceiling_z * 0.46)
        bz = ceiling_z - bh * 0.5
        _vm_arch_box(
            f"{name}_InvBlock_{i:03d}",
            (bx, by, bz),
            (bw, bd, bh),
            mat=mat_building,
            bevel_width=0.05,
            parent=root,
            allow_float=True,
        )
        if mat_window_glow and i % 3 == 0:
            _vm_arch_box(
                f"{name}_InvWinBand_{i:03d}",
                (bx, by - bd * 0.51, ceiling_z - bh * 0.72),
                (bw * 0.78, 0.08, 0.35),
                mat=mat_window_glow,
                bevel_width=0.01,
                parent=root,
                allow_float=True,
            )

    if add_bridge_spire:
        sy = y_range[0] + y_len * 0.55
        for t_i in range(3):
            tw = 6.2 - t_i * 1.4
            _vm_arch_box(
                f"{name}_BridgeTowerTier_{t_i}",
                (0.0, sy, ceiling_z * 0.5),
                (tw, tw, ceiling_z + 6.0),
                mat=mat_building,
                bevel_width=0.08,
                parent=root,
            )

    if add_inverted_pyramid:
        py_y = y_range[0] + y_len * 0.42
        py_h = ceiling_z * 0.48
        bpy.ops.mesh.primitive_cone_add(
            vertices=4,
            radius1=py_h * 0.75,
            radius2=0.08,
            depth=py_h,
            location=(0.0, py_y, ceiling_z - py_h * 0.5),
            rotation=(_m.pi, 0.0, _m.radians(45.0)),
        )
        pyr = bpy.context.object
        pyr.name = f"{name}_InvertedMonolithPyramid"
        pyr.parent = root
        pyr["vm_allow_float"] = True
        if mat_building:
            pyr.data.materials.append(mat_building)

    bpy.context.view_layer.update()
    return root

def build_procedural_cloud_deck(
    name="ProceduralCloudDeck",
    z_height=-2.2,
    span_xy=180.0,
    layers=3,
    thickness=3.2,
    cloud_color=(0.94, 0.96, 1.0),
    shadow_tint=(0.45, 0.54, 0.72),
    seed=5,
):
    '''
    构建高拟真多层波浪起伏程序化云海（采用高频网格细分 + 双层噪波置换 + 次表面/透射柔光材质）。
    严禁弱模型使用拍扁的 primitive_uv_sphere_add 堆叠“煎饼/大便状”假云团！
    '''
    import random as _r
    rnd = _r.Random(seed)
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root["vm_allow_float"] = True

    cmat = bpy.data.materials.new(f"{name}_CloudSeaMat")
    cmat.use_nodes = True
    nt = cmat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (cloud_color[0], cloud_color[1], cloud_color[2], 1.0)
        bsdf.inputs["Roughness"].default_value = 0.88
        if "Subsurface Weight" in bsdf.inputs:
            bsdf.inputs["Subsurface Weight"].default_value = 0.65
        if "Subsurface Radius" in bsdf.inputs:
            bsdf.inputs["Subsurface Radius"].default_value = (shadow_tint[0], shadow_tint[1], shadow_tint[2])
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 8.5
        noise.inputs["Detail"].default_value = 6.0
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.35
        nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    for lv in range(max(1, int(layers))):
        lz = z_height - lv * (thickness * 0.75)
        rad = span_xy * (0.55 + 0.18 * lv)
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=96, y_subdivisions=96, size=rad * 2.0, location=(0.0, rad * 0.25, lz))
        sheet = bpy.context.object
        sheet.name = f"{name}_Layer_{lv}"
        sheet.parent = root
        sheet["vm_allow_float"] = True
        for p in sheet.data.polygons:
            p.use_smooth = True
        add_solidify(sheet, thickness=thickness * (0.85 + 0.2 * lv))
        add_noise_displace(sheet, strength=thickness * (1.35 + 0.25 * lv), noise_scale=0.14 + 0.04 * lv, texture_type='CLOUDS')
        sheet.data.materials.append(cmat)

    bpy.context.view_layer.update()
    return root

def setup_aerial_perspective_world(
    sky_zenith=(0.05, 0.11, 0.22),
    sky_horizon=(0.42, 0.56, 0.72),
    cloud_bright=(0.82, 0.88, 0.96),
    cloud_contrast=0.65,
    add_planetary_arc=False,
    mist_start=16.0,
    mist_depth=175.0,
    ambient_strength=0.45,
):
    '''
    构建宏大场景与“真实下的科幻”专用双路径（Light Path）大气透视天空与体积云穹着色器：
    1. 相机直接看到的背景呈现高反差层积风暴云海与可选行星级弯曲弧面地平线（参考 imageref3 32a3 / sterile_organ_canyon_v2），彻底杜绝画面顶部死黑虚空；
    2. 场景漫反射照明走柔和环境光路径，不过曝不抢主光；
    3. 自动配置 Blender Mist 雾气通道起点与深度，配合远景巨构立即产生百米级空气透视（Aerial Perspective）纵深感。
    '''
    scene = bpy.context.scene
    if hasattr(scene.world, "mist_settings"):
        scene.world.mist_settings.use_mist = True
        scene.world.mist_settings.start = float(mist_start)
        scene.world.mist_settings.depth = float(mist_depth)
        scene.world.mist_settings.falloff = 'QUADRATIC'

    world = scene.world or bpy.data.worlds.new("VM_AerialWorld")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputWorld")
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix_bg = nt.nodes.new("ShaderNodeMixShader")

    bg_illum = nt.nodes.new("ShaderNodeBackground")
    bg_illum.inputs["Color"].default_value = (sky_horizon[0] * 0.65, sky_horizon[1] * 0.68, sky_horizon[2] * 0.75, 1.0)
    bg_illum.inputs["Strength"].default_value = float(ambient_strength)

    bg_cam = nt.nodes.new("ShaderNodeBackground")
    bg_cam.inputs["Strength"].default_value = 1.15

    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1.8, 1.8, 4.2 if not add_planetary_arc else 2.2)

    noise_hi = nt.nodes.new("ShaderNodeTexNoise")
    noise_hi.inputs["Scale"].default_value = 5.5
    noise_hi.inputs["Detail"].default_value = 9.0
    noise_hi.inputs["Roughness"].default_value = 0.62

    ramp = nt.nodes.new("ShaderNodeValToRGB")
    c_lo = max(0.10, 0.42 - cloud_contrast * 0.25)
    c_hi = min(0.92, 0.62 + cloud_contrast * 0.22)
    ramp.color_ramp.elements[0].position = c_lo
    ramp.color_ramp.elements[0].color = (sky_zenith[0], sky_zenith[1], sky_zenith[2], 1.0)
    ramp.color_ramp.elements[1].position = c_hi
    ramp.color_ramp.elements[1].color = (cloud_bright[0], cloud_bright[1], cloud_bright[2], 1.0)

    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    horizon_ramp = nt.nodes.new("ShaderNodeValToRGB")
    horizon_ramp.color_ramp.elements[0].position = 0.0
    horizon_ramp.color_ramp.elements[0].color = (sky_horizon[0], sky_horizon[1], sky_horizon[2], 1.0)
    horizon_ramp.color_ramp.elements[1].position = 0.38 if not add_planetary_arc else 0.55
    horizon_ramp.color_ramp.elements[1].color = (sky_zenith[0], sky_zenith[1], sky_zenith[2], 1.0)

    mix_col = nt.nodes.new("ShaderNodeMixRGB")
    mix_col.blend_type = 'MIX'
    mix_col.inputs["Fac"].default_value = 0.62

    nt.links.new(coord.outputs["Generated"], mapping.inputs["Vector"])
    nt.links.new(coord.outputs["Generated"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], horizon_ramp.inputs["Fac"])
    nt.links.new(mapping.outputs["Vector"], noise_hi.inputs["Vector"])
    nt.links.new(noise_hi.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(horizon_ramp.outputs["Color"], mix_col.inputs["Color1"])
    nt.links.new(ramp.outputs["Color"], mix_col.inputs["Color2"])
    nt.links.new(mix_col.outputs["Color"], bg_cam.inputs["Color"])

    nt.links.new(lp.outputs["Is Camera Ray"], mix_bg.inputs["Fac"])
    nt.links.new(bg_illum.outputs["Background"], mix_bg.inputs[1])
    nt.links.new(bg_cam.outputs["Background"], mix_bg.inputs[2])
    nt.links.new(mix_bg.outputs["Shader"], out.inputs["Surface"])
    return world
""",
}
