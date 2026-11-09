"""
blender_runner.py
Vibe-Modeler Blender 执行调度核心
支持：
1. 拼装多 Subagent 生成的 bpy 模块为完整脚本
2. 调度 Blender CLI 后台运行建模、渲染与自省循环
3. 支持基于现有 .blend 工程的增量局部修改与重新渲染（改图管线）
4. 联动 RPC 服务向运行中的 Blender 推送指令
"""

import os
import sys
import subprocess
import json
import urllib.request
import urllib.error

# Import local finder
try:
    from scripts.blender_finder import find_blender
except ImportError:
    from blender_finder import find_blender

DEFAULT_BLENDER_PATH = find_blender()

def clean_scene_header():
    return """
import bpy
import math
from mathutils import Vector, Euler

# 1. 清空默认多余场景物体
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# 清理无用材质和网格孤儿数据
for block in bpy.data.meshes:
    if block.users == 0: bpy.data.meshes.remove(block)
for block in bpy.data.materials:
    if block.users == 0: bpy.data.materials.remove(block)
"""

def assemble_script(env_code, mesh_code, camera_code, render_settings):
    """
    拼接完整的 Blender Python 自动化脚本
    """
    res_x = render_settings.get("width", 1920)
    res_y = render_settings.get("height", 1080)
    engine = render_settings.get("engine", "BLENDER_EEVEE_NEXT")
    samples = render_settings.get("samples", 64)
    out_img = render_settings.get("output_image", "render.png").replace("\\", "/")
    out_blend = render_settings.get("output_blend", "scene.blend").replace("\\", "/")

    render_footer = f"""
# ==========================================
# 渲染与输出设置
# ==========================================
scene = bpy.context.scene
scene.render.resolution_x = {res_x}
scene.render.resolution_y = {res_y}
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = r"{out_img}"

try:
    scene.render.engine = "{engine}"
    if "{engine}" == "CYCLES":
        scene.cycles.samples = {samples}
    elif hasattr(scene, "eevee"):
        if hasattr(scene.eevee, "max_samples"):
            scene.eevee.max_samples = {samples}
        elif hasattr(scene.eevee, "taa_render_samples"):
            scene.eevee.taa_render_samples = {samples}
except Exception as e:
    print(f"[RenderEngine] Warning: {{e}}")

# 触发单帧渲染
bpy.ops.render.render(write_still=True)
print(f"[Vibe-Modeler] 图像渲染完成: {{scene.render.filepath}}")

# 保存工程文件
try:
    bpy.ops.wm.save_as_mainfile(filepath=r"{out_blend}")
    print(f"[Vibe-Modeler] 工程文件保存完成: {out_blend}")
except Exception as e:
    print(f"[Vibe-Modeler] 保存工程警告: {{e}}")
"""

    full_script = f"""# -*- coding: utf-8 -*-
{clean_scene_header()}

# ==========================================
# 1. 场景环境与灯光架构 (scene-architect)
# ==========================================
{env_code}

# ==========================================
# 2. 主体与配景几何建模 (mesh-modeler)
# ==========================================
{mesh_code}

# ==========================================
# 3. 构图与镜头拍摄系统 (camera-director)
# ==========================================
{camera_code}

{render_footer}
"""
    return full_script

def run_cli_render(script_path, base_blend_path=None, blender_path=None):
    """
    运行 Blender 后台渲染。
    若传入 base_blend_path，则在加载现有 .blend 基础上运行脚本（用于增量改图）。
    """
    if not blender_path:
        blender_path = DEFAULT_BLENDER_PATH
    if not blender_path or not os.path.isfile(blender_path):
        raise FileNotFoundError(f"未找到可用的 Blender 可执行文件，请检查安装或设置 BLENDER_PATH: {blender_path}")

    cmd = [blender_path, "-b"]
    if base_blend_path and os.path.isfile(base_blend_path):
        cmd.append(base_blend_path)
    cmd.extend(["--python-exit-code", "1", "-P", script_path])

    print(f"[*] 启动 Blender CLI: {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        print("[!] Blender 报错日志:\n", proc.stderr or proc.stdout)
        raise RuntimeError(f"Blender 运行异常退出 (Code {proc.returncode}):\n{proc.stderr[-800:]}")
    print("[*] Blender CLI 执行成功！")
    return proc.stdout

def run_incremental_patch(base_blend_path, patch_code, render_settings, blender_path=None):
    """
    基于现有 .blend 工程执行局部增量修改并重新渲染
    """
    out_img = render_settings.get("output_image", "render_tweaked.png").replace("\\", "/")
    out_blend = render_settings.get("output_blend", base_blend_path).replace("\\", "/")
    engine = render_settings.get("engine", "BLENDER_EEVEE_NEXT")
    samples = render_settings.get("samples", 64)

    patch_wrapper = f"""# -*- coding: utf-8 -*-
import bpy
import math
from mathutils import Vector, Euler

# 执行增量修改指令
{patch_code}

# 重新触发渲染与保存
scene = bpy.context.scene
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = r"{out_img}"
try:
    scene.render.engine = "{engine}"
    if "{engine}" == "CYCLES":
        scene.cycles.samples = {samples}
    elif hasattr(scene, "eevee"):
        if hasattr(scene.eevee, "max_samples"):
            scene.eevee.max_samples = {samples}
        elif hasattr(scene.eevee, "taa_render_samples"):
            scene.eevee.taa_render_samples = {samples}
except Exception:
    pass

bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=r"{out_blend}")
print("[*] 增量修改渲染与保存完成")
"""
    patch_script_file = os.path.abspath("temp_patch.py")
    with open(patch_script_file, "w", encoding="utf-8") as f:
        f.write(patch_wrapper)

    try:
        res = run_cli_render(patch_script_file, base_blend_path=base_blend_path, blender_path=blender_path)
        return res
    finally:
        if os.path.exists(patch_script_file):
            try: os.remove(patch_script_file)
            except Exception: pass

def run_rpc_execute(code_str, rpc_url="http://127.0.0.1:9876/execute"):
    payload = json.dumps({"code": code_str}).encode("utf-8")
    req = urllib.request.Request(rpc_url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def check_rpc_status(rpc_url="http://127.0.0.1:9876/status"):
    try:
        req = urllib.request.Request(rpc_url)
        with urllib.request.urlopen(req, timeout=2) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
