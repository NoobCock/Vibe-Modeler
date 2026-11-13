"""
profile_manager.py
Vibe-Modeler 双模式用户需求导出、偏好画像与广谱艺术/空间发散抽样工具 (v3.0)

1. 自动剥离选项里的 "(Recommended)" / "（上次评分低）" 等标签，防止脏数据写入画像
2. 同时支持“简易模式（1 题总评）”与“详细模式（4 维打分）”，记录沟通模式偏好、空间拓扑与艺术流派
3. 提问前调用 `--hints`：读取历史评分，并从 6 大空间拓扑 + 14 种艺术流派谱系中动态抽取不重复的跨流派发散建议（强制包含至少 3 种非平地空间拓扑与至少 3 种非常规/前卫空间流派）
4. 生成单次创作流程图

命令行：python scripts/profile_manager.py --hints
"""

import os
import re
import sys
import json
import time
import random

PROFILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "user_profile.json"))

# 六大平等空间拓扑（打破“平地+摆件”定势）
SPATIAL_ARCHETYPES = [
    {
        "id": "interior_hall",
        "name": "封闭室内与走廊大厅",
        "spatial_mode": "interior",
        "builder_hint": "build_enclosed_room",
        "brief": "相机位于有顶棚、墙面、门窗洞或柱列的内部空间（如白蓝水池大厅、无限走廊、静谧展厅）",
    },
    {
        "id": "vertical_atrium",
        "name": "多层垂直中庭与阶梯深井",
        "spatial_mode": "interior",
        "builder_hint": "build_vertical_atrium + create_volumetric_light_beam",
        "brief": "纵向多层回廊、铁艺/混凝土阳台与跨层楼梯叠落，高处斜射丁达尔光束",
    },
    {
        "id": "canyon_megastructure",
        "name": "两侧夹峙建筑峡谷与巨构",
        "spatial_mode": "grounded",
        "builder_hint": "build_canyon_corridor",
        "brief": "左右高耸肋柱或建筑立面夹出深邃纵向通道，低角度仰望尽头尖塔或天光窄缝",
    },
    {
        "id": "floating_noneuclidean",
        "name": "无地面失重悬浮与非欧错觉空间",
        "spatial_mode": "floating",
        "builder_hint": "build_spiral_stair_ribbon / build_orbital_ribbons / build_impossible_stair_loop / build_gravity_flip_room",
        "brief": "彻底取消地面，悬浮旋梯、倒置器物、贯穿虚空的巨环、彭罗斯死循环阶梯或多向重力房间",
    },
    {
        "id": "window_framing",
        "name": "近景窗框与半透帘幕框景",
        "spatial_mode": "framed",
        "builder_hint": "build_window_frame_stage",
        "brief": "透过微风吹拂的半透明前景纱帘与窗框，近看窗台器皿小花与窗外极简远景",
    },
    {
        "id": "open_landscape",
        "name": "开阔自然地景与水域",
        "spatial_mode": "grounded",
        "builder_hint": "build_endless_ground + build_grounded_backdrop_ridge",
        "brief": "无方边穿帮的大尺度自然地表/浅水岸线与底座扎入地下的远山层次",
    },
]

# 广谱艺术与空间设计流派库（avant_garde=True 代表跳出传统写实沙盘的前卫/非常规空间范式）
ART_MOVEMENTS = [
    {
        "id": "liminal_poolcore",
        "name": "阈限空间与池核 (Liminal / Poolcore)",
        "avant_garde": True,
        "recommended_archetypes": ["interior_hall", "vertical_atrium"],
        "cues": "空无一人的白蓝瓷砖大厅或浅水走廊，头顶格栅透下均匀柔光，整个空间明亮干净却带着安静的疏离感",
    },
    {
        "id": "brutalism_megastructure",
        "name": "粗野主义混凝土巨构 (Brutalism)",
        "avant_garde": True,
        "recommended_archetypes": ["canyon_megastructure", "vertical_atrium", "interior_hall"],
        "cues": "成排高耸的裸露水泥巨柱夹出窄深通道，头顶只留一线天光，用强烈的体量对比衬出人在里面的渺小",
    },
    {
        "id": "surrealism_antigravity",
        "name": "超现实失重梦境 (Surrealism)",
        "avant_garde": True,
        "recommended_archetypes": ["floating_noneuclidean", "window_framing"],
        "cues": "把平时沉重的日常器物倒着悬在云层里，周围绕着没有支撑的螺旋阶梯或细长的金属光环",
    },
    {
        "id": "non_euclidean_paradox",
        "name": "非欧几里得与视错觉空间 (Non-Euclidean)",
        "avant_garde": True,
        "recommended_archetypes": ["floating_noneuclidean", "vertical_atrium"],
        "cues": "用正交视角做出首尾咬合的死循环阶梯，或者让四面墙和天花板上各自长出打破上下重力的楼梯",
    },
    {
        "id": "vertical_lightshaft_atrium",
        "name": "垂直光井与层叠回廊 (Light-Shaft Atrium)",
        "avant_garde": True,
        "recommended_archetypes": ["vertical_atrium"],
        "cues": "近处是偏暗的石阶与街灯，往上是好几层叠在一起的镂空回廊，淹没在从高处斜照下来的明亮暖雾里",
    },
    {
        "id": "shattered_expressionism",
        "name": "碎裂几何与表现主义剪影 (Shattered Silhouette)",
        "avant_garde": True,
        "recommended_archetypes": ["floating_noneuclidean", "canyon_megastructure"],
        "cues": "冷灰蓝底色里立着倾斜的主体剪影，半空定格着反光的碎镜片，只用极少量亮色碎片点亮画面",
    },
    {
        "id": "translucent_window_dream",
        "name": "半透窗景与微风极简 (Translucent Framing)",
        "avant_garde": True,
        "recommended_archetypes": ["window_framing"],
        "cues": "微风吹起的半透明薄纱贴在镜头前，透过柔光看窗台上装着冷暖渐变水的玻璃杯和窗外干净的海天",
    },
    {
        "id": "sacred_monument_halo",
        "name": "对称巨塔与天顶光环 (Monumental Halo)",
        "avant_garde": True,
        "recommended_archetypes": ["canyon_megastructure", "floating_noneuclidean"],
        "cues": "两侧建筑把视线夹向中央拔地而起的高塔，塔尖正对着天空发光的水平圆环，雨后地面还能映出倒影",
    },
    {
        "id": "atmospheric_anime",
        "name": "清透空气感二次元 (Atmospheric Anime)",
        "avant_garde": False,
        "recommended_archetypes": ["window_framing", "open_landscape", "interior_hall"],
        "cues": "像动画电影背景一样清爽的明暗色块配细线描边，明亮通透又带着日常生活的温度",
    },
    {
        "id": "bauhaus_constructivism",
        "name": "包豪斯构成主义几何 (Bauhaus / De Stijl)",
        "avant_garde": False,
        "recommended_archetypes": ["floating_noneuclidean", "interior_hall"],
        "cues": "红黄蓝原色几何板片和细黑钢架在空中穿插咬合，画面干净利落，充满现代构成感",
    },
    {
        "id": "cassette_futurism",
        "name": "复古磁带未来工业 (Cassette Futurism)",
        "avant_garde": False,
        "recommended_archetypes": ["interior_hall", "canyon_megastructure"],
        "cues": "米白配暗橙色的厚重圆角机柜排成一排，老式荧光屏在暗房间里泛着绿光或琥珀色微光",
    },
    {
        "id": "chiaroscuro_stage",
        "name": "戏剧明暗舞台 (Chiaroscuro Stage)",
        "avant_garde": False,
        "recommended_archetypes": ["interior_hall", "vertical_atrium"],
        "cues": "大片安静的暗背景里只打下一束聚光灯，把中间主体的轮廓和地上的影子清清楚楚切出来",
    },
    {
        "id": "minimalist_architecture",
        "name": "现代极简建筑空间 (Minimalist Architecture)",
        "avant_garde": False,
        "recommended_archetypes": ["interior_hall", "canyon_megastructure", "open_landscape"],
        "cues": "干净的微水泥墙面上留出利落的采光口，阳光穿过浅水庭院在墙上映出安静的光斑",
    },
    {
        "id": "lowpoly_faceted",
        "name": "低多边形硬切面构成 (Low-Poly)",
        "avant_garde": False,
        "recommended_archetypes": ["open_landscape", "floating_noneuclidean"],
        "cues": "故意保留硬朗利落的多边形切角面，让相邻面片在冷暖灯光下呈现出像折纸一样的块面感",
    },
]

DEFAULT_PROFILE = {
    "version": "3.0",
    "updated_at": "",
    "aesthetic_weights": {
        "warmth_affinity": 0.0,      # -1.0 (极冷) 到 +1.0 (极暖)
        "contrast_affinity": 0.0,    # -1.0 (柔和低反差) 到 +1.0 (高张力硬光)
        "stylized_vs_realism": 0.0,  # -1.0 (纯写实) 到 +1.0 (纯卡通/赛璐珞)
        "composition_affinity": "thirds",
    },
    "option_ratings": {},
    "history_stats": {
        "total_creations": 0,
        "mode_counts": {"simple": 0, "detailed": 0},
        "style_counts": {},
        "archetype_counts": {},
        "favorite_keywords": [],
        "recent_scenes": [],
        "recent_movements": [],
        "recent_archetypes": [],
    },
    "sessions": [],
}

CATEGORY_DIMENSIONS = {
    "tone_mode": ("atmosphere", "modeling", "lighting", "composition"),
    "interaction_mode": ("atmosphere", "modeling", "lighting", "composition"),
    "spatial_archetype": ("atmosphere", "composition"),
    "art_movement": ("atmosphere", "modeling"),
    "geometry_form": ("atmosphere", "modeling"),
    "material_shading": ("atmosphere", "modeling"),
    "color_temperature": ("lighting",),
    "color_saturation": ("lighting",),
    "camera": ("composition",),
}

CATEGORY_LABELS = {
    "tone_mode": "语气风格",
    "interaction_mode": "沟通模式",
    "spatial_archetype": "空间拓扑",
    "art_movement": "艺术流派",
    "geometry_form": "画面风格",
    "material_shading": "整体画面材质",
    "color_temperature": "色温",
    "color_saturation": "浓淡",
    "camera": "画幅与镜头",
}

_TAG_PATTERNS = [
    r"^\s*\(Recommended\)\s*",
    r"\s*\(Recommended\)\s*$",
    r"^\s*（推荐）\s*",
    r"\s*（推荐）\s*$",
    r"\s*[（(]上次评分低[)）]\s*$",
]


def _clean_option_text(val):
    """剥离选项前后的 (Recommended) / （上次评分低）等 UI 标记，防止脏数据污染画像。"""
    if val is None:
        return None
    s = str(val).strip()
    for pat in _TAG_PATTERNS:
        s = re.sub(pat, "", s, flags=re.IGNORECASE).strip()
    return s or None


def _normalize_session_data(session_data):
    cleaned = {}
    for k, v in (session_data or {}).items():
        if isinstance(v, str) and k not in ("output_dir", "render_file", "blend_file"):
            cleaned[k] = _clean_option_text(v) or ""
        else:
            cleaned[k] = v
    mode = str(cleaned.get("interaction_mode") or "detailed").lower().strip()
    cleaned["interaction_mode"] = "simple" if mode in ("simple", "childlike", "简易", "简易模式") else "detailed"
    return cleaned


def _normalize_rating_data(rating_data):
    """支持简易模式单题总评（int/float 或 {"overall": x}）以及详细模式四维评分。"""
    if isinstance(rating_data, (int, float)):
        v = float(rating_data)
        return {"overall": v, "atmosphere": v, "modeling": v, "lighting": v, "composition": v}
    if not isinstance(rating_data, dict):
        return {"overall": 3.0, "atmosphere": 3.0, "modeling": 3.0, "lighting": 3.0, "composition": 3.0}
    if "overall" in rating_data and not all(k in rating_data for k in ("atmosphere", "modeling", "lighting", "composition")):
        v = float(rating_data["overall"])
        return {
            "overall": v,
            "atmosphere": float(rating_data.get("atmosphere", v)),
            "modeling": float(rating_data.get("modeling", v)),
            "lighting": float(rating_data.get("lighting", v)),
            "composition": float(rating_data.get("composition", v)),
        }
    atm = float(rating_data.get("atmosphere", 3))
    mod = float(rating_data.get("modeling", 3))
    lit = float(rating_data.get("lighting", 3))
    cam = float(rating_data.get("composition", 3))
    ov = round((atm + mod + lit + cam) / 4.0, 2)
    return {"overall": ov, "atmosphere": atm, "modeling": mod, "lighting": lit, "composition": cam}


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
    for k, v in base.items():
        if k != "version":
            profile.setdefault(k, v)
    profile["version"] = "3.0"
    for k, v in base["history_stats"].items():
        profile["history_stats"].setdefault(k, v)
    return profile


def save_profile(profile):
    profile["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)


def _session_options(session_data):
    camera = " + ".join(x for x in (session_data.get("ratio"), session_data.get("camera_lens")) if x)
    return {
        "tone_mode": session_data.get("tone_mode"),
        "interaction_mode": session_data.get("interaction_mode"),
        "spatial_archetype": session_data.get("spatial_archetype"),
        "art_movement": session_data.get("art_movement"),
        "geometry_form": session_data.get("geometry_form") or session_data.get("style"),
        "material_shading": session_data.get("material_shading"),
        "color_temperature": session_data.get("color_temperature") or session_data.get("tone"),
        "color_saturation": session_data.get("color_saturation"),
        "camera": camera or None,
    }


def export_requirements(session_data, output_path=None):
    """导出本次画图确认的所有用户需求（兼容简易模式与详细模式）为单独 JSON 文件。"""
    s = _normalize_session_data(session_data)
    if not output_path:
        out_dir = s.get("output_dir") or os.getcwd()
        output_path = os.path.join(out_dir, "session_requirements.json")
    req_data = {
        "export_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tone_mode": s.get("tone_mode", "较富有激情的"),
        "interaction_mode": s.get("interaction_mode", "detailed"),
        "spatial_topology": {
            "spatial_archetype": s.get("spatial_archetype", ""),
            "spatial_mode": s.get("spatial_mode", "grounded"),
        },
        "style": {
            "art_movement": s.get("art_movement", ""),
            "form_and_geometry": s.get("geometry_form", s.get("style", "")),
            "material_shading": s.get("material_shading", ""),
            "lighting_mood": s.get("lighting_mood", s.get("mood", "")),
        },
        "color": {
            "temperature": s.get("color_temperature", s.get("tone", "")),
            "saturation": s.get("color_saturation", ""),
            "custom_palette": s.get("custom_palette", ""),
        },
        "scene": {
            "selected_inspiration": s.get("keyword", ""),
            "hero_subject": s.get("subject", ""),
            "stage_environment": s.get("scene", ""),
            "user_custom_detail": s.get("user_detail", ""),
        },
        "camera": {
            "aspect_ratio": s.get("ratio", ""),
            "lens_preset": s.get("camera_lens", ""),
        },
        "assets_used": s.get("assets_used", []),
        "artifacts": {
            "output_dir": s.get("output_dir", ""),
            "render_image": s.get("render_file", ""),
            "blend_project": s.get("blend_file", ""),
        },
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(req_data, f, ensure_ascii=False, indent=2)
    return os.path.abspath(output_path)


def record_session(session_data, rating_data):
    """
    记录单次生成与打分数据（0~5 星）。
    - 详细模式可传 {"atmosphere": 4, "modeling": 3, "lighting": 4, "composition": 4}
    - 简易模式可直接传单题分数（如 4 或 {"overall": 4}）
    """
    s = _normalize_session_data(session_data)
    r = _normalize_rating_data(rating_data)
    profile = load_profile()
    stats = profile["history_stats"]
    stats["total_creations"] += 1

    mode = s["interaction_mode"]
    stats["mode_counts"][mode] = stats["mode_counts"].get(mode, 0) + 1

    style = s.get("art_movement") or s.get("geometry_form") or s.get("style") or "未记录"
    stats["style_counts"][style] = stats["style_counts"].get(style, 0) + 1

    arch = s.get("spatial_archetype")
    if arch:
        stats["archetype_counts"][arch] = stats["archetype_counts"].get(arch, 0) + 1
        stats["recent_archetypes"].append(arch)
        stats["recent_archetypes"] = stats["recent_archetypes"][-6:]

    mov = s.get("art_movement")
    if mov:
        stats["recent_movements"].append(mov)
        stats["recent_movements"] = stats["recent_movements"][-8:]

    kw = s.get("keyword")
    if kw and kw not in stats["favorite_keywords"]:
        stats["favorite_keywords"].append(kw)
        if len(stats["favorite_keywords"]) > 10:
            stats["favorite_keywords"].pop(0)

    for item in (s.get("keyword"), s.get("subject"), s.get("scene")):
        if item:
            stats["recent_scenes"].append(item)
    stats["recent_scenes"] = stats["recent_scenes"][-18:]

    for category, option in _session_options(s).items():
        opt_clean = _clean_option_text(option)
        if not opt_clean:
            continue
        dims = CATEGORY_DIMENSIONS[category]
        score = sum(r.get(d, 3.0) for d in dims) / float(len(dims))
        bucket = profile["option_ratings"].setdefault(category, {}).setdefault(opt_clean, {"count": 0, "sum": 0.0})
        bucket["count"] += 1
        bucket["sum"] = round(bucket["sum"] + score, 4)

    avg_score = r["overall"]
    impact = (avg_score - 3.0) * 0.10
    weights = profile["aesthetic_weights"]
    temp = str(s.get("color_temperature") or s.get("tone") or s.get("custom_palette") or "")
    if any(w in temp for w in ("暖", "金", "橙", "粉", "黄", "warm")):
        weights["warmth_affinity"] = round(max(-1.0, min(1.0, weights["warmth_affinity"] + impact)), 3)
    elif any(w in temp for w in ("冷", "蓝", "青", "冰", "cold", "cool")):
        weights["warmth_affinity"] = round(max(-1.0, min(1.0, weights["warmth_affinity"] - impact)), 3)

    profile["sessions"].append({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "session": s,
        "rating": r,
    })
    save_profile(profile)
    export_requirements(s)
    return profile


def sample_divergent_directions(profile=None, seed=None):
    """
    每次新对话动态抽取不重复的空间拓扑与广谱艺术流派建议：
    - 强制包含至少 3 种非开阔平地的空间拓扑（避免落回“地面摆物件”）
    - 强制包含至少 3 种前卫/非常规空间流派（阈限空间、粗野主义、超现实失重、非欧错觉等）
    - 自动避开最近几次刚用过的流派与拓扑
    """
    profile = profile or load_profile()
    rnd = random.Random(seed if seed is not None else time.time_ns())
    stats = profile.get("history_stats", {})
    recent_movs = set(stats.get("recent_movements", [])[-3:])
    recent_archs = set(stats.get("recent_archetypes", [])[-1:])

    # 1. 抽取 4 种空间拓扑（至少 3 种非 open_landscape）
    non_flat = [a for a in SPATIAL_ARCHETYPES if a["id"] != "open_landscape" and a["id"] not in recent_archs and a["name"] not in recent_archs]
    if len(non_flat) < 3:
        non_flat = [a for a in SPATIAL_ARCHETYPES if a["id"] != "open_landscape"]
    picked_archs = rnd.sample(non_flat, 3)
    remaining_archs = [a for a in SPATIAL_ARCHETYPES if a not in picked_archs]
    picked_archs.append(rnd.choice(remaining_archs))
    rnd.shuffle(picked_archs)

    # 2. 抽取 5 种艺术流派（至少 3 种 avant_garde=True，避开最近用过的）
    avant_pool = [m for m in ART_MOVEMENTS if m["avant_garde"] and m["id"] not in recent_movs and m["name"] not in recent_movs]
    if len(avant_pool) < 3:
        avant_pool = [m for m in ART_MOVEMENTS if m["avant_garde"]]
    classic_pool = [m for m in ART_MOVEMENTS if not m["avant_garde"] and m["id"] not in recent_movs and m["name"] not in recent_movs]
    if len(classic_pool) < 2:
        classic_pool = [m for m in ART_MOVEMENTS if not m["avant_garde"]]

    n_avant = rnd.choice([3, 4])
    picked_movs = rnd.sample(avant_pool, min(n_avant, len(avant_pool)))
    n_classic = 5 - len(picked_movs)
    picked_movs.extend(rnd.sample(classic_pool, min(n_classic, len(classic_pool))))
    rnd.shuffle(picked_movs)

    return {
        "suggested_archetypes": picked_archs,
        "suggested_movements": picked_movs,
        "usage_note": "以上为本轮随机抽取的发散跳板（严禁照抄原词），向用户提问时请用连贯舒展的自然口语描述，切忌用逗号、顿号或斜杠切碎成密集的四字词碎片",
    }


def get_preference_hints(profile=None, seed=None):
    """提问前调用，返回历史高分偏好、低分避雷、沟通模式倾向与本轮动态抽取的广谱空间/流派种子。"""
    profile = profile or load_profile()
    stats = profile["history_stats"]
    mc = stats.get("mode_counts", {})
    s_cnt, d_cnt = mc.get("simple", 0), mc.get("detailed", 0)
    preferred_mode = "auto"
    if s_cnt + d_cnt >= 2:
        if s_cnt > d_cnt:
            preferred_mode = "simple"
        elif d_cnt > s_cnt:
            preferred_mode = "detailed"

    hints = {
        "total_creations": stats["total_creations"],
        "preferred_mode": preferred_mode,
        "mode_counts": mc,
        "prefer": {},
        "caution": {},
        "avoid": {},
        "recent_scenes": stats.get("recent_scenes", [])[-10:],
        "warmth_affinity": round(profile["aesthetic_weights"].get("warmth_affinity", 0.0), 2),
        "divergent_suggestions": sample_divergent_directions(profile, seed=seed),
    }
    for category, options in profile.get("option_ratings", {}).items():
        label = CATEGORY_LABELS.get(category, category)
        for option, b in options.items():
            if not b["count"]:
                continue
            avg = round(b["sum"] / b["count"], 2)
            entry = {"option": _clean_option_text(option) or option, "avg_stars": avg, "times": b["count"]}
            bucket = "prefer" if avg >= 4 else ("caution" if avg >= 2 else "avoid")
            hints[bucket].setdefault(label, []).append(entry)
    for bucket in ("prefer", "caution", "avoid"):
        for label in hints[bucket]:
            hints[bucket][label].sort(key=lambda e: -e["avg_stars"])
    return hints


def generate_mermaid_trace(session_data, rating_data):
    s = _normalize_session_data(session_data)
    r = _normalize_rating_data(rating_data)
    mode_str = "简易模式" if s["interaction_mode"] == "simple" else "详细模式"
    arch = s.get("spatial_archetype") or s.get("spatial_mode") or "未指定"
    style = s.get("art_movement") or s.get("geometry_form") or s.get("style") or "未记录"
    kw = s.get("keyword") or s.get("subject") or "未记录"
    tone = s.get("color_temperature") or s.get("custom_palette") or s.get("tone") or "未记录"
    ratio = s.get("ratio") or "未记录"

    if s["interaction_mode"] == "simple":
        score_txt = f"总评 {r['overall']:g}星"
    else:
        score_txt = (
            f"氛围 {r['atmosphere']:g}星 / 造型 {r['modeling']:g}星 / "
            f"色彩 {r['lighting']:g}星 / 镜头 {r['composition']:g}星"
        )

    return f"""```mermaid
flowchart LR
    S0["{mode_str}"] --> S1["空间骨架: {arch}"]
    S1 --> S2["流派风格: {style}"]
    S2 --> S3["画面核心: {kw}"]
    S3 --> S4["色彩与画幅: {tone} / {ratio}"]
    S4 --> S5["三维构建与体检"]
    S5 --> S6["{score_txt}"]
```"""


if __name__ == "__main__":
    if "--hints" in sys.argv:
        print(json.dumps(get_preference_hints(), ensure_ascii=False, indent=2))
    else:
        print("用法: python scripts/profile_manager.py --hints")
