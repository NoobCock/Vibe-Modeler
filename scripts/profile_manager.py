"""
profile_manager.py
Vibe-Modeler 用户需求导出与打分偏好记录工具
1. 导出用户本次生成的所有需求参数为单独的 JSON 文件
2. 记录逐项 1~5 星打分，更新偏好统计，生成流程图
"""

import os
import json
import time

PROFILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "user_profile.json"))

DEFAULT_PROFILE = {
    "version": "1.0",
    "updated_at": "",
    "aesthetic_weights": {
        "warmth_affinity": 0.0,      # -1.0 (极冷) 到 +1.0 (极暖)
        "contrast_affinity": 0.0,    # -1.0 (柔和低反差) 到 +1.0 (高张力硬光)
        "stylized_vs_realism": 0.0,  # -1.0 (纯写实) 到 +1.0 (纯卡通/赛璐珞)
        "composition_affinity": "thirds"
    },
    "history_stats": {
        "total_creations": 0,
        "style_counts": {},
        "favorite_keywords": []
    },
    "sessions": []
}

def load_profile():
    if os.path.exists(PROFILE_PATH):
        try:
            with open(PROFILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return json.loads(json.dumps(DEFAULT_PROFILE))

def save_profile(profile):
    profile["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

def export_requirements(session_data, output_path="session_requirements.json"):
    """
    导出本次画图确认的所有用户需求为单独的 JSON 文件，便于后续比对与调优。
    """
    req_data = {
        "export_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "style": {
            "form_and_geometry": session_data.get("geometry_form", session_data.get("style", "现代极简构筑")),
            "material_shading": session_data.get("material_shading", "PBR物理微质感"),
            "lighting_mood": session_data.get("lighting_mood", session_data.get("tone", "日照晴空"))
        },
        "color": {
            "temperature": session_data.get("color_temperature", session_data.get("tone", "偏暖")),
            "saturation": session_data.get("color_saturation", "低饱和灰调"),
            "custom_palette": session_data.get("custom_palette", "")
        },
        "scene": {
            "selected_inspiration": session_data.get("keyword", ""),
            "hero_subject": session_data.get("subject", ""),
            "stage_environment": session_data.get("scene", ""),
            "user_custom_detail": session_data.get("user_detail", "")
        },
        "camera": {
            "aspect_ratio": session_data.get("ratio", "16:9"),
            "lens_preset": session_data.get("camera_lens", "标准视角（带景深）")
        },
        "artifacts": {
            "render_image": session_data.get("render_file", "render.png"),
            "blend_project": session_data.get("blend_file", "scene.blend")
        }
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(req_data, f, ensure_ascii=False, indent=2)
    return os.path.abspath(output_path)

def record_session(session_data, rating_data):
    """
    记录单次完整的生成与打分数据（打分范围 1~5 星）。
    """
    profile = load_profile()
    stats = profile["history_stats"]
    stats["total_creations"] += 1
    
    style = session_data.get("style", "现代极简构筑")
    stats["style_counts"][style] = stats["style_counts"].get(style, 0) + 1

    kw = session_data.get("keyword")
    if kw and kw not in stats["favorite_keywords"]:
        stats["favorite_keywords"].append(kw)
        if len(stats["favorite_keywords"]) > 10:
            stats["favorite_keywords"].pop(0)

    # 1~5 星完整加权：
    # 5星: +0.20, 4星: +0.10, 3星: 0.0, 2星: -0.10, 1星: -0.20
    avg_score = (
        rating_data.get("atmosphere", 3) +
        rating_data.get("modeling", 3) +
        rating_data.get("lighting", 3) +
        rating_data.get("composition", 3)
    ) / 4.0
    impact = (avg_score - 3.0) * 0.10

    weights = profile["aesthetic_weights"]
    if session_data.get("tone") in ["warm", "偏暖"]:
        weights["warmth_affinity"] = max(-1.0, min(1.0, weights["warmth_affinity"] + impact))
    elif session_data.get("tone") in ["cold", "偏冷"]:
        weights["warmth_affinity"] = max(-1.0, min(1.0, weights["warmth_affinity"] - impact))

    record = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "session": session_data,
        "rating": rating_data
    }
    profile["sessions"].append(record)
    save_profile(profile)

    # 同时导出单次需求 JSON
    export_requirements(session_data)
    return profile

def generate_mermaid_trace(session_data, rating_data):
    style = session_data.get("geometry_form", session_data.get("style", "极简建筑"))
    kw = session_data.get("keyword", "画风初定")
    subj = session_data.get("subject", "主体")
    sc = session_data.get("scene", "地表")
    tone = session_data.get("tone", "偏暖")
    ratio = session_data.get("ratio", "16:9")
    
    score_atm = rating_data.get("atmosphere", 3)
    score_mod = rating_data.get("modeling", 3)
    score_lit = rating_data.get("lighting", 3)
    score_cam = rating_data.get("composition", 3)

    return f"""```mermaid
flowchart LR
    S1["风格: {style}"] --> S2["灵感: {kw}"]
    S2 --> S3["主体: {subj}"]
    S3 --> S4["环境: {sc}"]
    S4 --> S5["色温: {tone} / 画幅: {ratio}"]
    S5 --> S6["渲染与检查"]
    S6 --> S7["评分:<br>氛围: {score_atm}星<br>造型: {score_mod}星<br>色彩: {score_lit}星<br>镜头: {score_cam}星"]
```"""
