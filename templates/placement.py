"""
templates/placement.py
Vibe-Modeler 摆放、多模式空间体检与智能全景辅助图模板

1. snap_to_ground：用射线检测把物体落到真实地面上（自动跳过体积雾盒）
2. preflight_check：支持 spatial_mode ("grounded" / "interior" / "floating" / "framed")：
   - grounded（贴地开阔/街景）：检查相机、主角构图与遮挡，同时全场景排查近中景配景/远山悬空漏底、地面方边断口穿帮
   - interior（封闭室内/阈限空间/垂直中庭）：放宽建筑结构占画幅上限，豁免地面边缘检查，重点排查穿墙与死黑欠曝
   - floating（失重超现实/非欧空间）：豁免浮空与地下误报，专注构图、穿模与曝光
   - framed（窗框/纱帘近景框景）：适配前景框景遮挡与近景构图
3. check_render_exposure：出图后快速抽样像素亮度，自动拦截“封闭房间忘打光一片死黑”或“大面积死白过曝”
4. scene_diagnostics：打印场景物体范围、灯光、相机朝向、世界环境
5. render_overview：围绕“主相机 + 核心主体”智能取景（不被百米远山拉缩成小点），室内模式自动临时隐藏天花板透视内部结构
"""

PLACEMENT_SNIPPETS = {
    "_placement_helpers": """
def _vm_family(obj):
    '''物体本身加上它所有子孙物体。'''
    fam = [obj]
    stack = list(obj.children)
    while stack:
        o = stack.pop()
        fam.append(o)
        stack.extend(o.children)
    return fam

def _vm_is_volume_or_helper(obj):
    '''判断物体是否为体积雾盒或临时辅助体（无实体表面，不应参与射线贴地、穿模与遮挡判定）。'''
    if obj is None:
        return True
    if obj.name.startswith("VM_TMP_") or obj.get("vm_is_volume"):
        return True
    if getattr(obj, "display_type", "") in ("WIRE", "BOUNDS"):
        # 若材质仅有 Volume 输出而无 Surface 输出，则属于体积雾盒
        mats = [s.material for s in getattr(obj, "material_slots", []) if s.material and s.material.use_nodes]
        if mats:
            has_surface = False
            for m in mats:
                for n in m.node_tree.nodes:
                    if n.type == 'OUTPUT_MATERIAL' and n.inputs["Surface"].is_linked:
                        has_surface = True
            if not has_surface:
                return True
    return False

def _vm_world_bbox(obj):
    '''物体及其子孙中所有实体网格的世界坐标包围盒，返回 (min Vector, max Vector)；没有网格时返回 None。'''
    from mathutils import Vector
    pts = []
    for o in _vm_family(obj):
        if o.type in ('MESH', 'CURVE', 'FONT', 'SURFACE', 'META') and not _vm_is_volume_or_helper(o):
            pts.extend(o.matrix_world @ Vector(c) for c in o.bound_box)
    if not pts:
        return None
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))

def _vm_ray(origin, direction, ignore_names, max_dist=1000.0, max_skips=24):
    '''射线检测，自动跳过 ignore_names 与体积雾盒，返回 (位置, 法线, 物体) 或 None。'''
    from mathutils import Vector
    scene = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    o = Vector(origin)
    d = Vector(direction).normalized()
    travelled = 0.0
    for _ in range(max_skips):
        hit, loc, nor, _idx, hit_obj, _m = scene.ray_cast(dg, o, d, distance=max_dist - travelled)
        if not hit:
            return None
        orig_obj = hit_obj.original if hasattr(hit_obj, "original") else hit_obj
        name = orig_obj.name
        if name not in ignore_names and not _vm_is_volume_or_helper(orig_obj):
            return (loc, nor, orig_obj)
        travelled += (loc - o).length + 1e-4
        o = loc + d * 1e-4
    return None

def _vm_ground_ray(x, y, obj_mn_z, obj_mx_z, ignore_names, max_skips=32):
    '''
    专用于寻地与贴地体检的向下射线：
    1. 从物体下半部高度起射（而非 mx.z + 100m），避免把几十米高空的峡谷横梁、天桥栈道或吊顶误判为地面；
    2. 自动跳过标记了 vm_allow_float / vm_is_ceiling 的物体，以及自身最低点仍显著高于待测物底部的悬空横梁/顶棚。
    '''
    from mathutils import Vector
    scene = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    obj_h = max(0.1, obj_mx_z - obj_mn_z)
    start_z = min(obj_mx_z + 0.25, obj_mn_z + max(1.2, obj_h * 0.35))
    o = Vector((x, y, start_z))
    d = Vector((0.0, 0.0, -1.0))
    travelled = 0.0
    max_dist = 1000.0
    for _ in range(max_skips):
        hit, loc, nor, _idx, hit_obj, _m = scene.ray_cast(dg, o, d, distance=max_dist - travelled)
        if not hit:
            return None
        orig_obj = hit_obj.original if hasattr(hit_obj, "original") else hit_obj
        name = orig_obj.name
        skip = (
            name in ignore_names
            or _vm_is_volume_or_helper(orig_obj)
            or bool(orig_obj.get("vm_allow_float"))
            or bool(orig_obj.get("vm_is_ceiling"))
        )
        if not skip:
            root = orig_obj
            while root.parent is not None:
                root = root.parent
            if root.get("vm_allow_float") or root.get("vm_is_ceiling"):
                skip = True
            else:
                hbb = _vm_world_bbox(orig_obj)
                if hbb is not None and hbb[0].z > obj_mn_z + 1.0:
                    skip = True
        if not skip:
            return (loc, nor, orig_obj)
        travelled += (loc - o).length + 1e-4
        o = loc + d * 1e-4
    return None
""",

    "snap_to_ground": """
def snap_to_ground(obj, mode="average", sink=0.02, align_to_normal=False, ignore=None):
    '''
    把物体（或导入模型的空物体父级）落到它正下方的地面上。
    mode: "average" 取脚下几个采样点的平均高度（默认，石头、树、房子）
          "highest" 底部落在最高点上（椅子、桌子等带腿的物体，避免腿陷进地里）
          "lowest"  底部落在最低点上（愿意让一部分埋进土里的物体）
    sink: 往下多埋一点（米），避免看起来是放在地面上的贴纸。
    align_to_normal: True 时让物体顺着坡面倾斜。
    ignore: 额外要跳过的物体列表（比如水面、散布样本）。
    返回 {"ground_z": ..., "moved": ...}；脚下没有地面时返回 None 并打印警告。
    '''
    from mathutils import Vector
    bpy.context.view_layer.update()
    bb = _vm_world_bbox(obj)
    if bb is None:
        print(f"[Placement] {obj.name} 没有实体网格，无法贴地")
        return None
    mn, mx = bb
    ignore_names = {o.name for o in _vm_family(obj)} | {o.name for o in (ignore or [])}
    cx, cy = (mn.x + mx.x) / 2, (mn.y + mx.y) / 2
    hx, hy = (mx.x - mn.x) * 0.4, (mx.y - mn.y) * 0.4
    samples = [(cx, cy), (cx - hx, cy - hy), (cx + hx, cy - hy), (cx - hx, cy + hy), (cx + hx, cy + hy)]
    hits = []
    center_normal = None
    for i, (x, y) in enumerate(samples):
        h = _vm_ground_ray(x, y, mn.z, mx.z, ignore_names)
        if h is None:
            h = _vm_ray((x, y, mx.z + 25.0), (0, 0, -1), ignore_names)
        if h:
            hits.append(h[0].z)
            if i == 0:
                center_normal = h[1]
    if not hits:
        print(f"[Placement] 警告：{obj.name} 正下方没有地面")
        return None
    if mode == "highest":
        ground_z = max(hits)
    elif mode == "lowest":
        ground_z = min(hits)
    else:
        ground_z = sum(hits) / len(hits)
    delta = (ground_z - sink) - mn.z
    obj.matrix_world.translation.z += delta

    if align_to_normal and center_normal is not None:
        rot = Vector((0, 0, 1)).rotation_difference(center_normal)
        obj.rotation_mode = 'XYZ'
        obj.rotation_euler.rotate(rot)
    bpy.context.view_layer.update()
    return {"ground_z": round(ground_z, 4), "moved": round(delta, 4)}
""",

    "preflight_check": """
def preflight_check(
    subjects,
    camera=None,
    spatial_mode="grounded",
    min_coverage=0.025,
    max_coverage=0.75,
    float_tolerance=0.06,
):
    '''
    渲染前空间体检。
    spatial_mode:
      - "grounded"（默认贴地场景）：检查相机、主角构图与遮挡、主角及近中景配景/远山悬空漏底、方形地面边缘穿帮
      - "interior"（封闭室内/阈限大厅/多层中庭）：允许建筑结构大画幅包裹，豁免地面边缘检查
      - "floating"（超现实失重/非欧空间）：豁免浮空与相机在地下误报
      - "framed"（窗框/纱帘近景框景）：适配框景构图，豁免远端地面边缘检查
    '''
    import json
    import math as _m
    from mathutils import Vector
    from bpy_extras.object_utils import world_to_camera_view

    scene = bpy.context.scene
    bpy.context.view_layer.update()
    cam = camera or scene.camera
    mode = str(spatial_mode or "grounded").lower().strip()
    if mode in ("interior", "framed"):
        max_coverage = max(max_coverage, 0.94)

    issues = []
    warnings = []
    report = {"ok": True, "spatial_mode": mode, "issues": issues, "warnings": warnings, "subjects": {}}
    if cam is None:
        issues.append("场景里没有相机")
        report["ok"] = False
        print("[VM_PREFLIGHT] " + json.dumps(report, ensure_ascii=False))
        return report

    cam_loc = cam.matrix_world.translation.copy()

    # 1. 相机是否钻进了实体薄壳之外的实心网格内部（跳过大型室内外壳的整体包围盒，改测超近距离贴墙）
    near_hit = _vm_ray(cam_loc, cam.matrix_world.to_quaternion() @ Vector((0, 0, -1)), {cam.name}, max_dist=0.18)
    if near_hit is not None:
        issues.append(f"相机镜头前 18cm 内被 {near_hit[2].name} 死死贴脸挡住，可能穿墙或机位太近")

    if mode != "interior":
        for o in scene.objects:
            if o.type != 'MESH' or o.hide_render or _vm_is_volume_or_helper(o):
                continue
            bb = _vm_world_bbox(o)
            if bb is None:
                continue
            mn, mx = bb
            dims = (mx.x - mn.x, mx.y - mn.y, mx.z - mn.z)
            # 跳过空腔房间组件或超大地形包围盒，只抓实心道具/岩石穿模
            if min(dims) >= 0.08 and max(dims) < 12.0 and all(mn[i] < cam_loc[i] < mx[i] for i in range(3)):
                issues.append(f"相机位于实体物体 {o.name} 内部，可能钻进了模型里")

    # 2. 贴地模式下检查相机是否掉到地面以下
    if mode == "grounded":
        up = _vm_ray(cam_loc, (0, 0, 1), {cam.name})
        down = _vm_ray(cam_loc, (0, 0, -1), {cam.name})
        if up is not None and down is None:
            issues.append(f"相机可能在地面以下（上方有 {up[2].name}，下方是空的）")

    # 找出主地面（供全场景浮空与方边穿帮检查）
    ground_candidates = []
    for o in scene.objects:
        if o.type == 'MESH' and not o.hide_render and not _vm_is_volume_or_helper(o) and o.parent is None:
            bb = _vm_world_bbox(o)
            if bb:
                mn, mx = bb
                area = (mx.x - mn.x) * (mx.y - mn.y)
                if area > 100.0 and mn.z <= 1.5 and (mx.z - mn.z) < max(mx.x - mn.x, mx.y - mn.y) * 0.35:
                    ground_candidates.append((area, o, mn, mx))
    ground_candidates.sort(key=lambda x: -x[0])
    main_ground = ground_candidates[0][1] if ground_candidates else None

    subject_family_all = set()
    for subj in (subjects or []):
        for fo in _vm_family(subj):
            subject_family_all.add(fo.name)
        bb = _vm_world_bbox(subj)
        if bb is None:
            continue
        mn, mx = bb
        corners = [Vector((x, y, z)) for x in (mn.x, mx.x) for y in (mn.y, mx.y) for z in (mn.z, mx.z)]
        proj = [world_to_camera_view(scene, cam, c) for c in corners]
        in_front = [p for p in proj if p.z > 0]
        info = {}
        if not in_front:
            issues.append(f"{subj.name} 在相机背后，画面里看不到")
            info["visible"] = False
        else:
            xs = [p.x for p in in_front]; ys = [p.y for p in in_front]
            x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
            cx0, cx1, cy0, cy1 = max(0, x0), min(1, x1), max(0, y0), min(1, y1)
            coverage = max(0.0, cx1 - cx0) * max(0.0, cy1 - cy0)
            full_area = max(1e-6, (x1 - x0) * (y1 - y0))
            visible_ratio = coverage / full_area
            info.update({
                "screen_center": [round((cx0 + cx1) / 2, 3), round((cy0 + cy1) / 2, 3)],
                "coverage": round(coverage, 3),
                "visible_ratio": round(visible_ratio, 3),
            })
            if coverage <= 0:
                issues.append(f"{subj.name} 完全在画面外")
            elif mode == "grounded" and visible_ratio < 0.75 and full_area < 0.85:
                issues.append(f"{subj.name} 有 {round((1 - visible_ratio) * 100)}% 被画面边缘裁掉")
            if 0 < coverage < min_coverage:
                issues.append(f"{subj.name} 只占画面 {coverage:.1%}，太小看不清")
            if coverage > max_coverage:
                issues.append(f"{subj.name} 占画面 {coverage:.1%}，太大撑满了")

        # 多采样点遮挡检测（中心 + 4 个内缩角点，至少 4 点被非透光实心物挡住才报遮挡，避免前景细杆/纱帘误报）
        center = (mn + mx) / 2
        fam_names = {o.name for o in _vm_family(subj)}
        sx, sy, sz = (mx.x - mn.x) * 0.22, (mx.y - mn.y) * 0.22, (mx.z - mn.z) * 0.22
        test_pts = [
            center,
            center + Vector((-sx, 0, sz)),
            center + Vector((sx, 0, sz)),
            center + Vector((-sx, 0, -sz)),
            center + Vector((sx, 0, -sz)),
        ]
        blockers = []
        for tp in test_pts:
            dist = (tp - cam_loc).length
            if dist < 0.05:
                continue
            hit = _vm_ray(cam_loc, tp - cam_loc, {cam.name}, max_dist=dist - 0.05)
            if hit is not None and hit[2].name not in fam_names and not hit[2].get("vm_allow_float"):
                blockers.append(hit[2].name)
        if len(blockers) >= 4:
            top_blocker = max(set(blockers), key=blockers.count)
            issues.append(f"{subj.name} 大部分被 {top_blocker} 挡住了")
            info["occluded_by"] = top_blocker

        # 贴地模式下检查主角浮空 / 陷地
        if mode == "grounded" and not subj.get("vm_allow_float") and subj != main_ground:
            fam_hits = []
            hx, hy = (mx.x - mn.x) * 0.4, (mx.y - mn.y) * 0.4
            bcx, bcy = (mn.x + mx.x) / 2, (mn.y + mx.y) / 2
            for (x, y) in [(bcx, bcy), (bcx - hx, bcy - hy), (bcx + hx, bcy - hy), (bcx - hx, bcy + hy), (bcx + hx, bcy + hy)]:
                g = _vm_ground_ray(x, y, mn.z, mx.z, fam_names)
                if g is not None:
                    fam_hits.append(g[0].z)
            if fam_hits:
                gap = mn.z - max(fam_hits)
                sink_depth = (sum(fam_hits) / len(fam_hits)) - mn.z
                info["gap_to_ground"] = round(gap, 3)
                if gap > float_tolerance:
                    issues.append(f"{subj.name} 底部离地 {gap:.2f} 米，浮在空中（用 snap_to_ground 修正）")
                elif sink_depth > 0.30 * max(0.05, mx.z - mn.z):
                    issues.append(f"{subj.name} 陷进地面约 {sink_depth:.2f} 米，埋得太深")
            else:
                issues.append(f"{subj.name} 正下方没有任何地面承接，悬在半空")
        report["subjects"][subj.name] = info

    # 3. 贴地模式下：全场景排查非主角大件配景与远山悬空漏底（抓“前景巨石悬空”和“远山悬在半空漏出底边天空”）
    if mode == "grounded":
        checked_roots = set()
        for o in scene.objects:
            if o.hide_render or _vm_is_volume_or_helper(o):
                continue
            root = o
            while root.parent is not None:
                root = root.parent
            if root.name in checked_roots or root.name in subject_family_all or root == main_ground:
                continue
            checked_roots.add(root.name)
            if root.get("vm_allow_float") or root.get("vm_is_ceiling"):
                continue
            # 跳过隐藏散布源或灯光相机
            if root.type not in ('MESH', 'EMPTY'):
                continue
            vis_meshes = [m for m in _vm_family(root) if m.type == 'MESH' and not m.hide_render and not _vm_is_volume_or_helper(m)]
            if not vis_meshes:
                continue
            bb = _vm_world_bbox(root)
            if bb is None:
                continue
            mn, mx = bb
            # 只检查画面视野前方的可见物体
            corners = [Vector((x, y, z)) for x in (mn.x, mx.x) for y in (mn.y, mx.y) for z in (mn.z, mx.z)]
            proj = [world_to_camera_view(scene, cam, c) for c in corners]
            if not any(p.z > 0 and -0.1 <= p.x <= 1.1 and -0.1 <= p.y <= 1.1 for p in proj):
                continue
            fam_names = {fo.name for fo in _vm_family(root)}
            hx, hy = (mx.x - mn.x) * 0.38, (mx.y - mn.y) * 0.38
            bcx, bcy = (mn.x + mx.x) / 2, (mn.y + mx.y) / 2
            hits = []
            for (x, y) in [(bcx, bcy), (bcx - hx, bcy - hy), (bcx + hx, bcy - hy), (bcx - hx, bcy + hy), (bcx + hx, bcy + hy)]:
                g = _vm_ground_ray(x, y, mn.z, mx.z, fam_names)
                if g is not None:
                    hits.append(g[0].z)
            if hits:
                gap = mn.z - max(hits)
                if gap > max(float_tolerance, 0.12):
                    issues.append(f"配景/远山 {root.name} 底部悬空 {gap:.2f} 米（请用 snap_to_ground 贴地，远山请用 build_grounded_backdrop_ridge 把底座扎入地下）")
            elif mn.z > 0.25:
                issues.append(f"配景/远山 {root.name} (最低点 Z={mn.z:.2f}m) 下方无地面且未扎入地下 Z<=0，在镜头里会悬空漏底")

        # 4. 贴地模式下：检查方形小地面边缘是否在镜头中后景直接穿帮露出断口
        if main_ground is not None:
            _, _, gmn, gmx = ground_candidates[0]
            span = min(gmx.x - gmn.x, gmx.y - gmn.y)
            if span < 65.0:
                edge_pts = []
                for t_i in range(9):
                    f = t_i / 8.0
                    edge_pts.extend([
                        Vector((gmn.x + (gmx.x - gmn.x) * f, gmn.y, gmx.z)),
                        Vector((gmn.x + (gmx.x - gmn.x) * f, gmx.y, gmx.z)),
                        Vector((gmn.x, gmn.y + (gmx.y - gmn.y) * f, gmx.z)),
                        Vector((gmx.x, gmn.y + (gmx.y - gmn.y) * f, gmx.z)),
                    ])
                exposed = 0
                for ep in edge_pts:
                    pv = world_to_camera_view(scene, cam, ep)
                    if pv.z > 0 and 0.06 < pv.x < 0.94 and 0.06 < pv.y < 0.88:
                        # 看从相机到该边缘点之间有没有墙或山挡住
                        d = (ep - cam_loc).length
                        h = _vm_ray(cam_loc, ep - cam_loc, {cam.name, main_ground.name}, max_dist=max(0.1, d - 0.3))
                        if h is None:
                            exposed += 1
                if exposed >= 2:
                    issues.append(
                        f"地面 {main_ground.name} 尺寸偏小({gmx.x-gmn.x:.0f}x{gmx.y-gmn.y:.0f}m)，生硬的地面断口边缘在画面内直接穿帮（请改用 build_endless_ground(radius=95) 或用围墙/远山遮挡边界）"
                    )

    # 5. 立柱 / 支撑柱与上方吊顶脱节检查（拦截柱顶差 10~50cm 没接上天花板的穿帮）
    if mode in ("interior", "grounded"):
        for o in scene.objects:
            if o.type != 'MESH' or o.hide_render or _vm_is_volume_or_helper(o):
                continue
            lname = o.name.lower()
            if not any(k in lname for k in ("pillar", "column", "support_post", "col_")):
                continue
            bb = _vm_world_bbox(o)
            if bb is None:
                continue
            mn, mx = bb
            if (mx.z - mn.z) < 1.8:
                continue
            tcx, tcy = (mn.x + mx.x) * 0.5, (mn.y + mx.y) * 0.5
            up_hit = _vm_ray((tcx, tcy, mx.z - 0.02), (0, 0, 1), {fo.name for fo in _vm_family(o)}, max_dist=0.65)
            if up_hit is not None:
                top_gap = up_hit[0].z - mx.z
                if 0.05 < top_gap < 0.55:
                    issues.append(
                        f"立柱 {o.name} 柱顶(Z={mx.z:.2f}m)与上方顶板 {up_hit[2].name}(Z={up_hit[0].z:.2f}m) 之间悬空脱节 {top_gap:.2f} 米，请拉高柱高嵌入顶板"
                    )

    report["ok"] = not issues
    print("[VM_PREFLIGHT] " + json.dumps(report, ensure_ascii=False))
    return report
""",

    "check_render_exposure": """
def check_render_exposure(image_path, spatial_mode="grounded"):
    '''
    渲染完成后对输出图片做全局 + 九宫格（3x3 分区）亮度与对比度体检：
    1. 拦截全局死黑欠曝或全局死白过曝；
    2. 拦截九宫格局部强光死白过曝（例如聚光灯怼脸把前景窗框/墙面照成一片纯白）；
    3. 拦截全图灰蒙蒙缺乏光影层次（动态范围 p95 - p05 过窄或标准差过低）；
    4. 生成针对性的 Blender Compositor 后处理建议（post_process_recommendations）。
    '''
    import os
    import math as _m
    if not image_path or not os.path.exists(image_path):
        return None
    img = bpy.data.images.load(image_path, check_existing=False)
    try:
        w, h = img.size[0], img.size[1]
        if w <= 0 or h <= 0:
            return None
        px = img.pixels[:]
        grid_lumas = [[[] for _ in range(3)] for _ in range(3)]
        lumas = []
        step_x = max(1, w // 64)
        step_y = max(1, h // 64)
        for y in range(0, h, step_y):
            gy = min(2, (y * 3) // h)
            row_off = y * w * 4
            for x in range(0, w, step_x):
                gx = min(2, (x * 3) // w)
                idx = row_off + x * 4
                r, g, b = px[idx], px[idx + 1], px[idx + 2]
                lv = 0.2126 * r + 0.7152 * g + 0.0722 * b
                lumas.append(lv)
                grid_lumas[gy][gx].append(lv)
        if not lumas:
            return None
        lumas_sorted = sorted(lumas)
        n = len(lumas_sorted)
        mean_luma = sum(lumas_sorted) / n
        variance = sum((v - mean_luma) ** 2 for v in lumas_sorted) / n
        std_luma = _m.sqrt(variance)
        p05 = lumas_sorted[min(n - 1, int(n * 0.05))]
        p95 = lumas_sorted[min(n - 1, int(n * 0.95))]
        dynamic_range = p95 - p05
        dark_ratio = sum(1 for v in lumas_sorted if v < 0.025) / n
        bright_ratio = sum(1 for v in lumas_sorted if v > 0.96) / n

        cell_bright_ratios = []
        cell_dark_ratios = []
        blown_cells = []
        zone_names = [
            ["左下", "中下", "右下"],
            ["左中", "中心", "右中"],
            ["左上", "中上", "右上"],
        ]
        for gy in range(3):
            for gx in range(3):
                cl = grid_lumas[gy][gx]
                if not cl:
                    continue
                cb = sum(1 for v in cl if v > 0.96) / len(cl)
                cd = sum(1 for v in cl if v < 0.022) / len(cl)
                cmean = sum(cl) / len(cl)
                cell_bright_ratios.append(cb)
                cell_dark_ratios.append(cd)
                if cb > 0.50 and cmean > 0.86:
                    blown_cells.append(f"{zone_names[gy][gx]}区(死白占{cb:.0%})")

        max_cell_bright = max(cell_bright_ratios) if cell_bright_ratios else 0.0
        max_cell_dark = max(cell_dark_ratios) if cell_dark_ratios else 0.0

        issue = None
        warnings = []
        recommendations = []

        if mean_luma < 0.022 or dark_ratio > 0.90:
            issue = f"渲染画面几乎全黑（平均亮度 {mean_luma:.3f}，暗部占比 {dark_ratio:.0%}），请检查灯光能量、室内天窗/补光或体积雾是否过浓"
        elif mean_luma > 0.92 and bright_ratio > 0.82:
            issue = f"渲染画面全局严重过曝死白（平均亮度 {mean_luma:.3f}，死白占比 {bright_ratio:.0%}），请调低灯光/HDRI 强度或 exposure"
        elif blown_cells:
            issue = f"画面局部区域严重过曝死白：{', '.join(blown_cells)}，请检查是否有高能量聚光灯/面光过近直怼前景或墙面"
        elif dynamic_range < 0.14 and std_luma < 0.045:
            issue = f"画面整体灰蒙发平、缺乏明暗层次（动态范围仅 {dynamic_range:.2f}，亮度标准差 {std_luma:.3f}），请拉开主光与环境补光光比，或开启 AgX - Medium High Contrast 与后期对比度"

        if not issue:
            if max_cell_bright > 0.30 or bright_ratio > 0.12:
                warnings.append(f"局部高光偏强（最亮九宫格死白占比 {max_cell_bright:.0%}），建议开启后期 Glare 柔化高光边缘或微降 exposure")
                recommendations.append("开启 Glare (Bloom / Fog Glow) 柔化高光硬边")
            if dynamic_range < 0.28 or std_luma < 0.085:
                warnings.append(f"画面明暗反差偏温和（动态范围 {dynamic_range:.2f}），建议在后处理中开启 ao_boost 与 contrast_saturation 强化立体感")
                recommendations.append("开启 ao_boost + contrast_saturation + vignette 提升空间纵深与立体反差")
            if dark_ratio > 0.65 and str(spatial_mode).lower() != "floating":
                warnings.append(f"暗部面积偏大（占 {dark_ratio:.0%}），注意确认暗部建筑结构细节是否可读")
                recommendations.append("适当使用 color_balance 抬升暗部 Lift 或补充微弱体积雾/反射补光")
            if not recommendations:
                recommendations.append("可叠加 Mist 景深雾气 + 微弱色散 (dispersion=0.008) + 暗角 (vignette) 消除 CG 塑料硬边感")

        return {
            "mean_luma": round(mean_luma, 4),
            "std_luma": round(std_luma, 4),
            "p05_luma": round(p05, 4),
            "p95_luma": round(p95, 4),
            "dynamic_range": round(dynamic_range, 4),
            "dark_ratio": round(dark_ratio, 4),
            "bright_ratio": round(bright_ratio, 4),
            "max_cell_bright_ratio": round(max_cell_bright, 4),
            "max_cell_dark_ratio": round(max_cell_dark, 4),
            "issue": issue,
            "warnings": warnings,
            "post_process_recommendations": recommendations,
        }
    finally:
        bpy.data.images.remove(img)

check_render_quality = check_render_exposure
""",

    "scene_diagnostics": """
def scene_diagnostics():
    '''打印场景物体范围、灯光、相机朝向、世界环境，输出一行 [VM_DIAG] {...}。预览图发黑、发空时先看这个。'''
    import json
    from mathutils import Vector
    scene = bpy.context.scene
    bpy.context.view_layer.update()
    r = lambda v: [round(x, 2) for x in v]
    data = {"objects": [], "lights": [], "camera": None, "world": None}
    all_pts = []
    for o in scene.objects:
        if o.type == 'MESH' and not o.hide_render and not _vm_is_volume_or_helper(o):
            bb = _vm_world_bbox(o)
            if bb:
                all_pts += [bb[0], bb[1]]
                data["objects"].append({"name": o.name, "min": r(bb[0]), "max": r(bb[1]),
                                        "materials": [s.material.name for s in o.material_slots if s.material]})
        elif o.type == 'LIGHT':
            fwd = o.matrix_world.to_quaternion() @ Vector((0, 0, -1))
            data["lights"].append({"name": o.name, "type": o.data.type, "energy": o.data.energy,
                                   "color": r(o.data.color), "location": r(o.matrix_world.translation),
                                   "points_to": r(fwd)})
    if all_pts:
        data["scene_min"] = r(Vector((min(p.x for p in all_pts), min(p.y for p in all_pts), min(p.z for p in all_pts))))
        data["scene_max"] = r(Vector((max(p.x for p in all_pts), max(p.y for p in all_pts), max(p.z for p in all_pts))))
    cam = scene.camera
    if cam:
        fwd = cam.matrix_world.to_quaternion() @ Vector((0, 0, -1))
        dof = cam.data.dof
        data["camera"] = {"name": cam.name, "location": r(cam.matrix_world.translation), "looking": r(fwd),
                          "lens_mm": cam.data.lens if cam.data.type == 'PERSP' else None,
                          "cam_type": cam.data.type,
                          "dof": dof.use_dof,
                          "focus_object": dof.focus_object.name if dof.focus_object else None,
                          "fstop": dof.aperture_fstop}
    w = scene.world
    if w and w.node_tree:
        env = [n for n in w.node_tree.nodes if n.type == 'TEX_ENVIRONMENT']
        bgs = [n.inputs["Strength"].default_value for n in w.node_tree.nodes if n.type == 'BACKGROUND']
        data["world"] = {"hdri": env[0].image.name if env and env[0].image else None, "background_strength": bgs}
    data["engine"] = scene.render.engine
    data["view_transform"] = scene.view_settings.view_transform
    data["exposure"] = scene.view_settings.exposure
    print("[VM_DIAG] " + json.dumps(data, ensure_ascii=False))
    return data
""",

    "render_overview": """
def render_overview(filepath, resolution=640, subjects=None, spatial_mode="grounded"):
    '''
    从斜上方拍一张聚焦在“主相机 + 核心主体区域”的全景辅助图（主相机位置放红色圆锥箭头）。
    1. 优先围绕 subjects 与主相机取景，不会被几十米外的远山或大地面把主体拉缩成看不见的小点。
    2. 在室内模式（spatial_mode=="interior"）或存在 vm_is_ceiling 标记时，自动临时隐藏顶棚天花板并补一盏俯视观察灯。
    3. 自动检测并临时隐藏挡在俯视相机与核心主体视线之间的高大峡谷侧墙/走廊高墙（如 50m 高的 Canyon MassWall），确保全景图不变成白墙。
    '''
    import math as _m
    from mathutils import Vector
    scene = bpy.context.scene
    bpy.context.view_layer.update()
    main_cam = scene.camera
    mode = str(spatial_mode or "grounded").lower().strip()

    subj_names = set()
    focus_pts = []
    for subj in (subjects or []):
        for fo in _vm_family(subj):
            subj_names.add(fo.name)
        bb = _vm_world_bbox(subj)
        if bb:
            # 防止某个超长走廊主体拉得过远，限制单物体对焦半径贡献
            sc = (bb[0] + bb[1]) * 0.5
            ext = Vector((min(12.0, (bb[1].x - bb[0].x) * 0.5),
                          min(12.0, (bb[1].y - bb[0].y) * 0.5),
                          min(10.0, (bb[1].z - bb[0].z) * 0.5)))
            focus_pts.extend([sc - ext, sc + ext])

    if main_cam:
        focus_pts.append(main_cam.matrix_world.translation.copy())

    if len(focus_pts) < 2:
        for o in scene.objects:
            if o.type == 'MESH' and not o.hide_render and not _vm_is_volume_or_helper(o):
                bb = _vm_world_bbox(o)
                if bb and max(bb[1].x - bb[0].x, bb[1].y - bb[0].y) < 50.0:
                    focus_pts.extend([bb[0], bb[1]])
    if not focus_pts:
        return None

    mn = Vector((min(p.x for p in focus_pts), min(p.y for p in focus_pts), min(p.z for p in focus_pts)))
    mx = Vector((max(p.x for p in focus_pts), max(p.y for p in focus_pts), max(p.z for p in focus_pts)))
    center = (mn + mx) * 0.5
    radius = min(max((mx - mn).length * 0.55, 3.5), 24.0)

    # 室内透视：临时隐藏标记为 vm_is_ceiling 的吊顶，或位于相机上方的大面积水平顶板
    hidden_ceilings = []
    cam_z = main_cam.matrix_world.translation.z if main_cam else 1.6
    for o in scene.objects:
        if o.type != 'MESH' or o.hide_render:
            continue
        is_ceil = bool(o.get("vm_is_ceiling"))
        if not is_ceil and mode == "interior":
            bb = _vm_world_bbox(o)
            if bb:
                bmn, bmx = bb
                if bmn.z > cam_z + 0.6 and (bmx.z - bmn.z) < 1.2 and (bmx.x - bmn.x) > 3.0 and (bmx.y - bmn.y) > 3.0:
                    is_ceil = True
        if is_ceil:
            hidden_ceilings.append(o)
            o.hide_render = True

    cam_data = bpy.data.cameras.new("VM_TMP_OverviewCam")
    cam_data.lens = 26
    cam_obj = bpy.data.objects.new("VM_TMP_OverviewCam", cam_data)
    scene.collection.objects.link(cam_obj)
    fov = 2 * _m.atan(cam_data.sensor_width / (2 * cam_data.lens))
    dist = radius / _m.sin(fov / 2) * 1.08
    direction = Vector((0.65, -0.85, 1.55 if (hidden_ceilings or mode == "interior") else 1.05)).normalized()
    cam_obj.location = center + direction * dist
    cam_obj.rotation_euler = (center - cam_obj.location).to_track_quat('-Z', 'Y').to_euler()
    cam_data.clip_end = max(300.0, dist * 5)
    bpy.context.view_layer.update()

    # 峡谷/高墙剖切透视：若俯视相机到中心焦点之间被高大侧墙（高 > 4.5m）挡死，自动临时隐藏该遮挡墙体
    probe_targets = [center, center + Vector((0, 0, 1.5)), center + Vector((0, -3.0, 1.0)), center + Vector((0, 3.0, 1.0))]
    if main_cam:
        probe_targets.append(main_cam.matrix_world.translation.copy())
    for pt in probe_targets:
        for _ in range(8):
            ray_vec = pt - cam_obj.location
            ray_len = ray_vec.length
            if ray_len < 0.2:
                break
            hit = _vm_ray(
                cam_obj.location,
                ray_vec,
                {cam_obj.name} | subj_names | {o.name for o in hidden_ceilings},
                max_dist=ray_len - 0.15,
            )
            if hit is None:
                break
            ho = hit[2]
            hbb = _vm_world_bbox(ho)
            if hbb is not None and (hbb[1].z - hbb[0].z) > 4.5:
                hidden_ceilings.append(ho)
                ho.hide_render = True
                bpy.context.view_layer.update()
            else:
                break

    marker = None
    tmp_sun = None
    if main_cam:
        bpy.ops.mesh.primitive_cone_add(radius1=radius * 0.045, depth=radius * 0.14)
        marker = bpy.context.object
        marker.name = "VM_TMP_CamMarker"
        m = bpy.data.materials.new("VM_TMP_Red")
        m.use_nodes = True
        b = m.node_tree.nodes.get("Principled BSDF")
        b.inputs["Base Color"].default_value = (1, 0.05, 0.05, 1)
        if "Emission Color" in b.inputs:
            b.inputs["Emission Color"].default_value = (1, 0.05, 0.05, 1)
            b.inputs["Emission Strength"].default_value = 6.0
        marker.data.materials.append(m)
        fwd = main_cam.matrix_world.to_quaternion() @ Vector((0, 0, -1))
        marker.location = main_cam.matrix_world.translation
        marker.rotation_mode = 'QUATERNION'
        marker.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(fwd)

    if hidden_ceilings or mode == "interior":
        sdata = bpy.data.lights.new("VM_TMP_OverviewSun", 'SUN')
        sdata.energy = 1.2
        tmp_sun = bpy.data.objects.new("VM_TMP_OverviewSun", sdata)
        scene.collection.objects.link(tmp_sun)
        tmp_sun.rotation_euler = (_m.radians(25), _m.radians(15), _m.radians(-35))

    saved = (scene.camera, scene.render.filepath, scene.render.resolution_x, scene.render.resolution_y,
             scene.render.engine, scene.render.resolution_percentage)
    try:
        scene.camera = cam_obj
        scene.render.filepath = filepath
        scene.render.resolution_x = resolution
        scene.render.resolution_y = int(resolution * 0.75)
        scene.render.resolution_percentage = 100
        for e in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
            try:
                scene.render.engine = e
                break
            except Exception:
                continue
        bpy.ops.render.render(write_still=True)
    finally:
        for o in hidden_ceilings:
            o.hide_render = False
        (scene.camera, scene.render.filepath, scene.render.resolution_x, scene.render.resolution_y,
         eng, scene.render.resolution_percentage) = saved
        try:
            scene.render.engine = eng
        except Exception:
            pass
        bpy.data.objects.remove(cam_obj, do_unlink=True)
        bpy.data.cameras.remove(cam_data)
        if tmp_sun:
            sd = tmp_sun.data
            bpy.data.objects.remove(tmp_sun, do_unlink=True)
            bpy.data.lights.remove(sd)
        if marker:
            mat = marker.data.materials[0] if marker.data.materials else None
            mesh = marker.data
            bpy.data.objects.remove(marker, do_unlink=True)
            bpy.data.meshes.remove(mesh)
            if mat:
                bpy.data.materials.remove(mat)
    print(f"[VM_OVERVIEW] {filepath}")
    return filepath
""",
}
