"""
blender_runner.py
Vibe-Modeler Blender 执行调度核心

1. 把 templates/ 下所有模板函数自动注入生成的脚本，场景代码里可以直接调用（不需要自己复制模板代码）
2. 预览模式（EEVEE）：渲染前自动做相机与摆放检查、打印场景诊断、拍一张全景辅助图
3. 正式模式（Cycles + GPU + 降噪）：最终分辨率出图
4. 每次运行建一个带时间戳的输出文件夹，保存 .blend 前把外部贴图打包进文件
5. 在现有 .blend 基础上做局部修改（改图），原文件保留不覆盖
6. 联动 RPC 服务向运行中的 Blender 推送指令
"""

import os
import sys
import time
import json
import subprocess
import urllib.request
import urllib.error

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    from scripts.blender_finder import find_blender
except ImportError:
    from blender_finder import find_blender

from templates import materials, geo_nodes, modeling, placement, render_pipeline, lighting_rigs, spatial_archetypes
from scripts import asset_loader

DEFAULT_BLENDER_PATH = find_blender()
OUTPUTS_DIR = os.path.join(ROOT_DIR, "outputs")


# ==========================================
# 输出文件夹
# ==========================================

def new_output_dir(tag=None):
    """建一个 outputs/年月日_时分秒[_tag]/ 文件夹并返回绝对路径，每次生成互不覆盖。"""
    name = time.strftime("%Y%m%d_%H%M%S")
    if tag:
        safe = "".join(c for c in str(tag) if c.isalnum() or c in "-_")[:40]
        if safe:
            name += "_" + safe
    path = os.path.join(OUTPUTS_DIR, name)
    os.makedirs(path, exist_ok=True)
    return path


# ==========================================
# 模板工具箱注入
# ==========================================

def build_toolkit():
    """把所有模板函数拼成一段代码，放在生成脚本的开头。"""
    parts = [
        "import sys, os",
        f"sys.path.insert(0, r\"{ROOT_DIR}\")",
        "# 资产下载函数：asset_loader.download_pbr_texture_set / download_cc0_model / download_cc0_asset / search_cc0_assets",
        "from scripts import asset_loader",
    ]
    for snippets in (render_pipeline.RENDER_PIPELINE_SNIPPETS, placement.PLACEMENT_SNIPPETS,
                     geo_nodes.GEO_NODES_SNIPPETS, modeling.MODELING_SNIPPETS,
                     spatial_archetypes.SPATIAL_ARCHETYPE_SNIPPETS,
                     materials.MATERIAL_SNIPPETS, lighting_rigs.LIGHTING_RIG_SNIPPETS):
        for code in snippets.values():
            parts.append(code.strip("\n"))
    for code in (asset_loader.PROCEDURAL_SKY_BPY, asset_loader.PROCEDURAL_TOON_SHADER_BPY,
                 asset_loader.PROCEDURAL_VOLUMETRIC_FOG_BPY):
        parts.append(code.strip("\n"))
    return "\n\n".join(parts)


def clean_scene_header():
    return """
import bpy
import math
from mathutils import Vector, Euler

# 清空默认场景
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for block in list(bpy.data.meshes):
    if block.users == 0: bpy.data.meshes.remove(block)
for block in list(bpy.data.materials):
    if block.users == 0: bpy.data.materials.remove(block)
"""


def _render_footer(settings, out_dir, image_name, blend_name):
    """渲染、检查、打包、保存的收尾代码。"""
    mode = settings.get("mode", "preview")
    cfg = {
        "mode": mode,
        "width": settings.get("width", 1920),
        "height": settings.get("height", 1080),
        "samples": settings.get("samples"),
        "view": settings.get("view", "AgX"),
        "look": settings.get("look", "AgX - Base Contrast"),
        "exposure": settings.get("exposure", 0.0),
        "bloom": settings.get("bloom"),
        "transparent": settings.get("transparent", False),
    }
    subjects = settings.get("subjects", [])
    spatial_mode = settings.get("spatial_mode", "grounded")
    overview = settings.get("overview", mode == "preview")
    pack = settings.get("pack", True)
    out_dir_s = out_dir.replace("\\", "/")
    return f"""
# ==========================================
# 渲染设置、检查、出图、打包、保存
# ==========================================
import json as _vm_json
_vm_out = r"{out_dir_s}"
_vm_spatial_mode = {spatial_mode!r}
configure_render(**{cfg!r})
scene = bpy.context.scene

_vm_subject_names = {list(subjects)!r}
_vm_subjects = [bpy.data.objects[n] for n in _vm_subject_names if n in bpy.data.objects]
_vm_missing = [n for n in _vm_subject_names if n not in bpy.data.objects]
_vm_preflight = preflight_check(_vm_subjects, spatial_mode=_vm_spatial_mode)
_vm_report = {{
    "mode": "{mode}",
    "spatial_mode": _vm_spatial_mode,
    "missing_subjects": _vm_missing,
    "preflight": _vm_preflight,
    "diagnostics": scene_diagnostics(),
}}
_vm_report["missing_images"] = [img.name for img in bpy.data.images
                                if img.source == 'FILE' and not img.packed_file
                                and not os.path.exists(bpy.path.abspath(img.filepath))]
if {overview!r}:
    try:
        _vm_report["overview_image"] = render_overview(
            os.path.join(_vm_out, "overview.png"),
            subjects=_vm_subjects,
            spatial_mode=_vm_spatial_mode,
        )
    except Exception as _e:
        print(f"[Vibe-Modeler] 全景辅助图失败: {{_e}}")

scene.render.filepath = os.path.join(_vm_out, "{image_name}")
bpy.ops.render.render(write_still=True)
_vm_report["image"] = scene.render.filepath
try:
    _vm_exp = check_render_exposure(scene.render.filepath, spatial_mode=_vm_spatial_mode)
    _vm_report["exposure_check"] = _vm_exp
    if _vm_exp and _vm_exp.get("issue"):
        _vm_preflight["issues"].append(_vm_exp["issue"])
        _vm_preflight["ok"] = False
except Exception as _e:
    print(f"[Vibe-Modeler] 曝光抽检警告: {{_e}}")
print(f"[Vibe-Modeler] 图像渲染完成: {{scene.render.filepath}}")

if {pack!r}:
    try:
        bpy.ops.file.pack_all()
        print("[Vibe-Modeler] 外部贴图已打包进 .blend")
    except Exception as _e:
        print(f"[Vibe-Modeler] 打包贴图警告: {{_e}}")
_vm_blend = os.path.join(_vm_out, "{blend_name}")
bpy.context.preferences.filepaths.save_version = 0  # 不生成 .blend1 备份文件（只影响这次后台运行）
bpy.ops.wm.save_as_mainfile(filepath=_vm_blend)
_vm_report["blend"] = _vm_blend
with open(os.path.join(_vm_out, "report_{os.path.splitext(image_name)[0]}.json"), "w", encoding="utf-8") as _f:
    _vm_json.dump(_vm_report, _f, ensure_ascii=False, indent=2)
print(f"[Vibe-Modeler] 工程文件保存完成: {{_vm_blend}}")
"""


def assemble_script(env_code, mesh_code, camera_code, render_settings):
    """
    拼接完整的 Blender 脚本：清空场景 → 模板工具箱 → 环境与布光 → 建模 → 相机 → 检查与出图。
    render_settings 常用键：
      mode: "preview"（EEVEE 自审用）/ "final"（Cycles GPU 正式出图）
      output_dir: 输出文件夹（默认自动新建 outputs/时间戳/）
      width, height, samples, view, look, exposure, bloom, transparent
      subjects: 主角物体名字列表，用于渲染前检查（导入模型填它的空物体父级名字）
      overview: 是否拍全景辅助图（预览模式默认开）
      pack: 保存前是否打包贴图（默认开）
    """
    out_dir = render_settings.get("output_dir") or new_output_dir()
    render_settings["output_dir"] = out_dir
    mode = render_settings.get("mode", "preview")
    image_name = "preview.png" if mode == "preview" else "render.png"
    blend_name = "scene_preview.blend" if mode == "preview" else "scene.blend"

    return f"""# -*- coding: utf-8 -*-
{clean_scene_header()}

# ==========================================
# 0. 模板工具箱（自动注入，下面的代码可以直接调用这些函数）
# ==========================================
{build_toolkit()}

# ==========================================
# 1. 场景环境与灯光 (scene-architect)
# ==========================================
{env_code}

# ==========================================
# 2. 主体与配景建模 (mesh-modeler)
# ==========================================
{mesh_code}

# ==========================================
# 3. 构图与相机 (camera-director)
# ==========================================
{camera_code}

{_render_footer(render_settings, out_dir, image_name, blend_name)}
"""


# ==========================================
# 运行
# ==========================================

def run_cli_render(script_path, base_blend_path=None, blender_path=None, timeout=1800):
    """
    后台运行 Blender。传入 base_blend_path 时先打开该 .blend 再执行脚本（改图用）。
    """
    blender_path = blender_path or DEFAULT_BLENDER_PATH
    if not blender_path or not os.path.isfile(blender_path):
        raise FileNotFoundError(f"未找到可用的 Blender 可执行文件，请检查安装或设置 BLENDER_PATH: {blender_path}")

    cmd = [blender_path, "-b"]
    if base_blend_path and os.path.isfile(base_blend_path):
        cmd.append(base_blend_path)
    cmd.extend(["--python-exit-code", "1", "-P", script_path])

    print(f"[*] 启动 Blender CLI: {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if proc.returncode != 0:
        log = (proc.stdout or "")[-2000:] + "\n" + (proc.stderr or "")[-2000:]
        raise RuntimeError(f"Blender 运行异常退出 (Code {proc.returncode}):\n{log}")
    print("[*] Blender CLI 执行成功")
    return proc.stdout


def _collect_result(out_dir, image_name, stdout):
    report_path = os.path.join(out_dir, f"report_{os.path.splitext(image_name)[0]}.json")
    report = None
    if os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)
    return {"output_dir": out_dir, "report_file": report_path, "report": report, "stdout_tail": stdout[-1500:]}


def run_scene(env_code, mesh_code, camera_code, render_settings, blender_path=None):
    """
    一步完成：拼脚本 → 存到输出文件夹（scene_script.py，方便复查和重跑）→ 后台运行 → 读回检查报告。
    返回 {"output_dir", "report_file", "report", "stdout_tail"}。
    report["preflight"]["issues"] 不为空时，先修好再出正式图。
    """
    script = assemble_script(env_code, mesh_code, camera_code, render_settings)
    out_dir = render_settings["output_dir"]
    mode = render_settings.get("mode", "preview")
    script_path = os.path.join(out_dir, f"scene_script_{mode}.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)
    stdout = run_cli_render(script_path, blender_path=blender_path)
    return _collect_result(out_dir, "preview.png" if mode == "preview" else "render.png", stdout)


def run_incremental_patch(base_blend_path, patch_code, render_settings, blender_path=None):
    """
    在现有 .blend 上执行局部修改并重新渲染。
    结果存为同一文件夹下的 tweak_01.png / scene_tweak_01.blend（序号自动递增），原文件保留，方便退回。
    """
    out_dir = render_settings.get("output_dir") or os.path.dirname(os.path.abspath(base_blend_path))
    os.makedirs(out_dir, exist_ok=True)
    n = 1
    while os.path.exists(os.path.join(out_dir, f"tweak_{n:02d}.png")) or \
            os.path.exists(os.path.join(out_dir, f"scene_tweak_{n:02d}.blend")):
        n += 1
    image_name = f"tweak_{n:02d}.png"
    blend_name = f"scene_tweak_{n:02d}.blend"
    settings = dict(render_settings)
    settings.setdefault("overview", False)

    patch_script = f"""# -*- coding: utf-8 -*-
import bpy
import math
from mathutils import Vector, Euler

{build_toolkit()}

# ==========================================
# 增量修改
# ==========================================
{patch_code}

{_render_footer(settings, out_dir, image_name, blend_name)}
"""
    script_path = os.path.join(out_dir, f"patch_{n:02d}.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(patch_script)
    stdout = run_cli_render(script_path, base_blend_path=base_blend_path, blender_path=blender_path)
    return _collect_result(out_dir, image_name, stdout)


# ==========================================
# RPC 模式（联动已打开的 Blender）
# ==========================================

def run_rpc_execute(code_str, rpc_url="http://127.0.0.1:9876/execute", with_toolkit=True, timeout=120):
    """向运行中的 Blender 发送代码。with_toolkit=True 时先注入模板函数。不会清空用户当前场景。"""
    if with_toolkit:
        code_str = "import bpy, math\nfrom mathutils import Vector, Euler\n" + build_toolkit() + "\n\n" + code_str
    payload = json.dumps({"code": code_str}).encode("utf-8")
    req = urllib.request.Request(rpc_url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_rpc_status(rpc_url="http://127.0.0.1:9876/status"):
    try:
        req = urllib.request.Request(rpc_url)
        with urllib.request.urlopen(req, timeout=2) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
