"""
profile_manager.py
Vibe-Modeler 用户需求导出与打分偏好记录工具
1. 导出用户本次生成的所有需求参数为单独的 JSON 文件
2. 记录逐项 0~5 星打分，按选项累计平均分
3. 提问前读取历史偏好（get_preference_hints），决定哪个选项标推荐、哪个往后放、哪些画面最近用过不要重复
4. 生成单次流程图

命令行：python scripts/profile_manager.py --hints   打印偏好提示（JSON）
"""

import os
import sys
import json
import time

PROFILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "user_profile.json"))

DEFAULT_PROFILE = {
    "version": "2.0",
    "updated_at": "",
    "aesthetic_weights": {
        "warmth_affinity": 0.0,      # -1.0 (极冷) 到 +1.0 (极暖)
        "contrast_affinity": 0.0,    # -1.0 (柔和低反差) 到 +1.0 (高张力硬光)
        "stylized_vs_realism": 0.0,  # -1.0 (纯写实) 到 +1.0 (纯卡通/赛璐珞)
        "composition_affinity": "thirds"
    },
    # 每个提问类别下，每个选项的累计得分：{"类别": {"选项": {"count": n, "sum": 总分}}}
    "option_ratings": {},
    "history_stats": {
        "total_creations": 0,
        "style_counts": {},
        "favorite_keywords": [],
        "recent_scenes": []   # 最近用过的灵感 / 主角 / 环境，避免下次重复
    },
    "sessions": []
}

# 每个提问类别用哪几项打分来衡量
CATEGORY_DIMENSIONS = {
    "geometry_form": ("atmosphere", "modeling"),
    "material_shading": ("atmosphere", "modeling"),
    "color_temperature": ("lighting",),
    "color_saturation": ("lighting",),
    "camera": ("composition",),
}

CATEGORY_LABELS = {
    "geometry_form": "画面风格",
    "material_shading": "整体画面材质",
    "color_temperature": "色温",
    "color_saturation": "浓淡",
    "camera": "画幅与镜头",
}


def load_profile():
    profile = None
    if os.path.exists(PROFILE_PATH):
        try:
            with open(PROFILE_PATH, "r", encoding="utf-8") as f:
                profile = json.load(f)
        except Exception:
            profile = None
    base = json.loads(json.dumps(DEFAULT_PROFILE))
    if not profile:
        return base
    # 旧版档案补齐新字段
    for k, v in base.items():
        profile.setdefault(k, v)
    for k, v in base["history_stats"].items():
        profile["history_stats"].setdefault(k, v)
    return profile


def save_profile(profile):
    profile["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)


def _session_options(session_data):
    """从本次需求里取出每个类别用户选了什么。"""
    camera = " + ".join(x for x in (session_data.get("ratio"), session_data.get("camera_lens")) if x)
    return {
        "geometry_form": session_data.get("geometry_form") or session_data.get("style"),
        "material_shading": session_data.get("material_shading"),
        "color_temperature": session_data.get("color_temperature") or session_data.get("tone"),
        "color_saturation": session_data.get("color_saturation"),
        "camera": camera or None,
    }


def export_requirements(session_data, output_path=None):
    """
    导出本次画图确认的所有用户需求为单独的 JSON 文件，便于后续比对与调优。
    output_path 不传时写到 session_data["output_dir"]/session_requirements.json（没有 output_dir 则写到当前目录）。
    """
    if not output_path:
        out_dir = session_data.get("output_dir") or os.getcwd()
        output_path = os.path.join(out_dir, "session_requirements.json")
    req_data = {
        "export_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "style": {
            "form_and_geometry": session_data.get("geometry_form", session_data.get("style", "")),
            "material_shading": session_data.get("material_shading", ""),
            "lighting_mood": session_data.get("lighting_mood", "")
        },
        "color": {
            "temperature": session_data.get("color_temperature", session_data.get("tone", "")),
            "saturation": session_data.get("color_saturation", ""),
            "custom_palette": session_data.get("custom_palette", "")
        },
        "scene": {
            "selected_inspiration": session_data.get("keyword", ""),
            "hero_subject": session_data.get("subject", ""),
            "stage_environment": session_data.get("scene", ""),
            "user_custom_detail": session_data.get("user_detail", "")
        },
        "camera": {
            "aspect_ratio": session_data.get("ratio", ""),
            "lens_preset": session_data.get("camera_lens", "")
        },
        "assets_used": session_data.get("assets_used", []),
        "artifacts": {
            "output_dir": session_data.get("output_dir", ""),
            "render_image": session_data.get("render_file", ""),
            "blend_project": session_data.get("blend_file", "")
        }
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(req_data, f, ensure_ascii=False, indent=2)
    return os.path.abspath(output_path)


def record_session(session_data, rating_data):
    """
    记录单次完整的生成与打分数据（打分范围 0~5 星）。
    rating_data: {"atmosphere": 0~5, "modeling": 0~5, "lighting": 0~5, "composition": 0~5}
    """
    profile = load_profile()
    stats = profile["history_stats"]
    stats["total_creations"] += 1

    style = session_data.get("geometry_form") or session_data.get("style") or "未记录"
    stats["style_counts"][style] = stats["style_counts"].get(style, 0) + 1

    kw = session_data.get("keyword")
    if kw and kw not in stats["favorite_keywords"]:
        stats["favorite_keywords"].append(kw)
        if len(stats["favorite_keywords"]) > 10:
            stats["favorite_keywords"].pop(0)

    for item in (session_data.get("keyword"), session_data.get("subject"), session_data.get("scene")):
        if item:
            stats["recent_scenes"].append(item)
    stats["recent_scenes"] = stats["recent_scenes"][-15:]

    # 按选项累计得分
    for category, option in _session_options(session_data).items():
        if not option:
            continue
        dims = CATEGORY_DIMENSIONS[category]
        score = sum(rating_data.get(d, 3) for d in dims) / float(len(dims))
        bucket = profile["option_ratings"].setdefault(category, {}).setdefault(option, {"count": 0, "sum": 0.0})
        bucket["count"] += 1
        bucket["sum"] += score

    # 0~5 星加权：5星 +0.20, 4星 +0.10, 3星 0, 2星 -0.10, 1星 -0.20, 0星 -0.30
    avg_score = sum(rating_data.get(k, 3) for k in ("atmosphere", "modeling", "lighting", "composition")) / 4.0
    impact = (avg_score - 3.0) * 0.10
    weights = profile["aesthetic_weights"]
    temp = str(session_data.get("color_temperature") or session_data.get("tone") or "")
    if "暖" in temp or "warm" in temp:
        weights["warmth_affinity"] = max(-1.0, min(1.0, weights["warmth_affinity"] + impact))
    elif "冷" in temp or "cold" in temp:
        weights["warmth_affinity"] = max(-1.0, min(1.0, weights["warmth_affinity"] - impact))

    profile["sessions"].append({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "session": session_data,
        "rating": rating_data
    })
    save_profile(profile)
    export_requirements(session_data)
    return profile


def get_preference_hints(profile=None):
    """
    提问前调用。返回：
      prefer:  各类别里平均 ≥4 星的选项 → 可以标 (Recommended)
      caution: 平均 2~3 星的选项 → 照常列出，但不要标推荐
      avoid:   平均 <2 星（含 0 星）的选项 → 不标推荐，排到最后，并在选项后注明“上次评分低”
      recent_scenes: 最近用过的灵感、主角、环境 → 这次现场构思时不要重复
      warmth_affinity: 冷暖倾向（正数偏暖，负数偏冷）
    """
    profile = profile or load_profile()
    hints = {"total_creations": profile["history_stats"]["total_creations"],
             "prefer": {}, "caution": {}, "avoid": {},
             "recent_scenes": profile["history_stats"].get("recent_scenes", [])[-10:],
             "warmth_affinity": round(profile["aesthetic_weights"].get("warmth_affinity", 0.0), 2)}
    for category, options in profile.get("option_ratings", {}).items():
        label = CATEGORY_LABELS.get(category, category)
        for option, b in options.items():
            if not b["count"]:
                continue
            avg = round(b["sum"] / b["count"], 2)
            entry = {"option": option, "avg_stars": avg, "times": b["count"]}
            bucket = "prefer" if avg >= 4 else ("caution" if avg >= 2 else "avoid")
            hints[bucket].setdefault(label, []).append(entry)
    for bucket in ("prefer", "caution", "avoid"):
        for label in hints[bucket]:
            hints[bucket][label].sort(key=lambda e: -e["avg_stars"])
    return hints


def generate_mermaid_trace(session_data, rating_data):
    style = session_data.get("geometry_form", session_data.get("style", "未记录"))
    kw = session_data.get("keyword", "未记录")
    subj = session_data.get("subject", "未记录")
    sc = session_data.get("scene", "未记录")
    tone = session_data.get("color_temperature", session_data.get("tone", "未记录"))
    ratio = session_data.get("ratio", "未记录")

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
    S6 --> S7["评分: 氛围 {score_atm}星 / 造型 {score_mod}星 / 色彩 {score_lit}星 / 镜头 {score_cam}星"]
```"""


if __name__ == "__main__":
    if "--hints" in sys.argv:
        print(json.dumps(get_preference_hints(), ensure_ascii=False, indent=2))
    else:
        print("用法: python scripts/profile_manager.py --hints")
