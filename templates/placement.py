"""
templates/placement.py
Vibe-Modeler 摆放与检查模板

1. snap_to_ground：用射线检测把物体落到真实地面上（地形起伏后不再假设 Z=0）
2. preflight_check：渲染前检查相机和主角（相机有没有钻进物体或地下、主角在不在画面里、有没有被挡住、有没有浮空或陷地）
3. scene_diagnostics：打印场景里所有物体的位置范围、灯光、相机朝向，预览图看不出问题时用来排错
4. render_overview：从斜上方拍一张全景辅助图，并在主相机位置放一个红色箭头，一眼看出相机朝哪、物体在哪
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

def _vm_world_bbox(obj):
    '''物体及其子孙中所有网格的世界坐标包围盒，返回 (min Vector, max Vector)；没有网格时返回 None。'''
    from mathutils import Vector
    pts = []
    for o in _vm_family(obj):
        if o.type in ('MESH', 'CURVE', 'FONT', 'SURFACE', 'META'):
            pts.extend(o.matrix_world @ Vector(c) for c in o.bound_box)
    if not pts:
        return None
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))

def _vm_ray(origin, direction, ignore_names, max_dist=1000.0, max_skips=16):
    '''射线检测，跳过 ignore_names 里的物体，返回 (位置, 法线, 物体) 或 None。'''
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
        name = hit_obj.original.name if hasattr(hit_obj, "original") else hit_obj.name
        if name not in ignore_names:
            return (loc, nor, hit_obj)
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
        print(f"[Placement] {obj.name} 没有网格，无法贴地")
        return None
    mn, mx = bb
    ignore_names = {o.name for o in _vm_family(obj)} | {o.name for o in (ignore or [])}
    cx, cy = (mn.x + mx.x) / 2, (mn.y + mx.y) / 2
    hx, hy = (mx.x - mn.x) * 0.4, (mx.y - mn.y) * 0.4
    samples = [(cx, cy), (cx - hx, cy - hy), (cx + hx, cy - hy), (cx - hx, cy + hy), (cx + hx, cy + hy)]
    top = mx.z + 100.0
    hits = []
    center_normal = None
    for i, (x, y) in enumerate(samples):
        h = _vm_ray((x, y, top), (0, 0, -1), ignore_names)
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
def preflight_check(subjects, camera=None, min_coverage=0.03, max_coverage=0.70, float_tolerance=0.05):
    '''
    渲染前检查。subjects 是主角物体列表（导入模型传它的空物体父级）。
    检查项：相机是否存在、相机是否钻进物体或地下、主角是否在画面内、主角占画面比例、
            主角有没有被别的东西挡住、主角有没有浮空或陷进地里。
    打印一行 [VM_PREFLIGHT] {...}，返回 {"ok": bool, "issues": [...], "subjects": {...}}。
    有 issues 时先修好再渲染，不要带着问题出图。
    '''
    import json
    from mathutils import Vector
    from bpy_extras.object_utils import world_to_camera_view
    scene = bpy.context.scene
    bpy.context.view_layer.update()
    cam = camera or scene.camera
    issues = []
    report = {"ok": True, "issues": issues, "subjects": {}}
    if cam is None:
        issues.append("场景里没有相机")
        report["ok"] = False
        print("[VM_PREFLIGHT] " + json.dumps(report, ensure_ascii=False))
        return report

    cam_loc = cam.matrix_world.translation.copy()
    # 相机是否在某个物体的包围盒里面
    for o in scene.objects:
        if o.type != 'MESH' or o.hide_render:
            continue
        bb = _vm_world_bbox(o)
        if bb is None:
            continue
        mn, mx = bb
        thin = min(mx.x - mn.x, mx.y - mn.y, mx.z - mn.z) < 0.05
        if not thin and all(mn[i] < cam_loc[i] < mx[i] for i in range(3)):
            issues.append(f"相机位于物体 {o.name} 的包围盒内部，可能钻进了物体里")
    # 相机是否在地面以下：向上打射线碰到东西、向下却什么都没碰到
    up = _vm_ray(cam_loc, (0, 0, 1), {cam.name})
    down = _vm_ray(cam_loc, (0, 0, -1), {cam.name})
    if up is not None and down is None:
        issues.append(f"相机可能在地面以下（上方有 {up[2].name}，下方是空的）")

    for subj in subjects:
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
            elif visible_ratio < 0.85:
                issues.append(f"{subj.name} 有 {round((1 - visible_ratio) * 100)}% 被画面边缘裁掉")
            if 0 < coverage < min_coverage:
                issues.append(f"{subj.name} 只占画面 {coverage:.1%}，太小看不清")
            if coverage > max_coverage:
                issues.append(f"{subj.name} 占画面 {coverage:.1%}，太大撑满了")
        # 遮挡：从相机向主角中心打射线，看第一个碰到的是不是主角自己
        center = (mn + mx) / 2
        fam_names = {o.name for o in _vm_family(subj)}
        hit = _vm_ray(cam_loc, center - cam_loc, {cam.name}, max_dist=(center - cam_loc).length + 1.0)
        if hit is not None:
            hit_name = hit[2].original.name if hasattr(hit[2], "original") else hit[2].name
            if hit_name not in fam_names:
                issues.append(f"{subj.name} 被 {hit_name} 挡住了")
                info["occluded_by"] = hit_name
        # 浮空 / 陷地：脚下 5 个采样点，任何一点碰到地面就不算浮空；平均高度用来判断陷得多深
        fam_hits = []
        hx, hy = (mx.x - mn.x) * 0.4, (mx.y - mn.y) * 0.4
        bcx, bcy = (mn.x + mx.x) / 2, (mn.y + mx.y) / 2
        for (x, y) in [(bcx, bcy), (bcx - hx, bcy - hy), (bcx + hx, bcy - hy), (bcx - hx, bcy + hy), (bcx + hx, bcy + hy)]:
            g = _vm_ray((x, y, mx.z + 100.0), (0, 0, -1), fam_names)
            if g is not None:
                fam_hits.append(g[0].z)
        if fam_hits:
            gap = mn.z - max(fam_hits)
            sink_depth = (sum(fam_hits) / len(fam_hits)) - mn.z
            info["gap_to_ground"] = round(gap, 3)
            if gap > float_tolerance:
                issues.append(f"{subj.name} 底部离地 {gap:.2f} 米，浮在空中（用 snap_to_ground 修正）")
            elif sink_depth > 0.25 * max(0.01, mx.z - mn.z):
                issues.append(f"{subj.name} 陷进地面约 {sink_depth:.2f} 米，埋得太深")
        report["subjects"][subj.name] = info

    report["ok"] = not issues
    print("[VM_PREFLIGHT] " + json.dumps(report, ensure_ascii=False))
    return report
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
        if o.type == 'MESH' and not o.hide_render:
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
                          "lens_mm": cam.data.lens, "dof": dof.use_dof,
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
def render_overview(filepath, resolution=640):
    '''
    从斜上方拍一张能看到整个场景的辅助图，主相机位置放一个红色箭头指向它的拍摄方向。
    拍完自动删除临时相机和箭头，恢复原来的相机和渲染设置。
    '''
    import math as _m
    from mathutils import Vector
    scene = bpy.context.scene
    bpy.context.view_layer.update()
    pts = []
    for o in scene.objects:
        if o.type == 'MESH' and not o.hide_render:
            bb = _vm_world_bbox(o)
            if bb:
                pts += [bb[0], bb[1]]
    if not pts:
        return None
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    # 太大的地面会把视野拉得很远，范围上限放在主角附近 60 米
    center = (mn + mx) / 2
    radius = min(max((mx - mn).length / 2, 1.0), 30.0)
    main_cam = scene.camera

    marker = None
    if main_cam:
        bpy.ops.mesh.primitive_cone_add(radius1=radius * 0.04, depth=radius * 0.12)
        marker = bpy.context.object
        marker.name = "VM_TMP_CamMarker"
        m = bpy.data.materials.new("VM_TMP_Red")
        m.use_nodes = True
        b = m.node_tree.nodes.get("Principled BSDF")
        b.inputs["Base Color"].default_value = (1, 0, 0, 1)
        if "Emission Color" in b.inputs:
            b.inputs["Emission Color"].default_value = (1, 0, 0, 1)
            b.inputs["Emission Strength"].default_value = 5.0
        marker.data.materials.append(m)
        fwd = main_cam.matrix_world.to_quaternion() @ Vector((0, 0, -1))
        marker.location = main_cam.matrix_world.translation
        marker.rotation_mode = 'QUATERNION'
        marker.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(fwd)
        pts_cam = main_cam.matrix_world.translation
        mn = Vector((min(mn.x, pts_cam.x), min(mn.y, pts_cam.y), min(mn.z, pts_cam.z)))
        mx = Vector((max(mx.x, pts_cam.x), max(mx.y, pts_cam.y), max(mx.z, pts_cam.z)))
        center = (mn + mx) / 2
        radius = min(max((mx - mn).length / 2, 1.0), 30.0)

    cam_data = bpy.data.cameras.new("VM_TMP_OverviewCam")
    cam_data.lens = 24
    cam_obj = bpy.data.objects.new("VM_TMP_OverviewCam", cam_data)
    scene.collection.objects.link(cam_obj)
    fov = 2 * _m.atan(cam_data.sensor_width / (2 * cam_data.lens))
    dist = radius / _m.sin(fov / 2) * 1.05
    direction = Vector((1.0, -1.0, 1.1)).normalized()
    cam_obj.location = center + direction * dist
    cam_obj.rotation_euler = (center - cam_obj.location).to_track_quat('-Z', 'Y').to_euler()
    cam_data.clip_end = dist * 4

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
        (scene.camera, scene.render.filepath, scene.render.resolution_x, scene.render.resolution_y,
         eng, scene.render.resolution_percentage) = saved
        try:
            scene.render.engine = eng
        except Exception:
            pass
        bpy.data.objects.remove(cam_obj, do_unlink=True)
        bpy.data.cameras.remove(cam_data)
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
