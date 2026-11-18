"""
profile_manager.py
Vibe-Modeler 双模式用户需求导出、偏好画像与广谱艺术/空间发散抽样工具 (v3.2)

1. 自动剥离选项里的 "(Recommended)" / "（上次评分低）" 等标签，防止脏数据写入画像
2. 同时支持“简易模式（1 题总评）”与“详细模式（4 维打分）”，记录沟通模式偏好、空间拓扑与艺术流派
3. 开场前调用 `--hints`：仅输出用户历史偏好（prefer/caution/avoid/recent_scenes/preferred_mode/warmth_affinity），不注入随机场景种子
4. 仅当用户主动选择“提供场景灵感”时调用 `--inspire`：从六大美学家族与十大空间拓扑中均衡抽取跨流派灵感跳板（不绑定任何单一参考图或固定模板组合）
5. 生成单次创作流程图

命令行：
  python scripts/profile_manager.py --hints
  python scripts/profile_manager.py --inspire
"""

import os
import re
import sys
import json
import time
import random

PROFILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "user_profile.json"))

# 十大平等空间拓扑（以经典通用基础拓扑为先，涵盖室内、自然地景、柱廊峡谷、框景、抽象构成与公共空间，不预设固定模板组合配方）
SPATIAL_ARCHETYPES = [
    {
        "id": "interior_hall",
        "name": "封闭室内与安静大厅",
        "spatial_mode": "interior",
        "family": "enclosure_light",
        "brief": "相机位于有顶棚、墙面、门窗洞或柱列的内部空间（如展厅、起居室、泳池大厅或复古机房），可用原创 BMesh 建构或可选空间骨架",
    },
    {
        "id": "open_landscape",
        "name": "开阔自然地景与海岸山谷",
        "spatial_mode": "grounded",
        "family": "landscape_plaza",
        "brief": "无方边穿帮的大尺度自然地表/浅水岸线与底座扎入地下的远山层次，结合 CC0 植物岩石与程序化地貌",
    },
    {
        "id": "canyon_megastructure",
        "name": "两侧夹峙建筑峡谷与拱券柱廊",
        "spatial_mode": "grounded",
        "family": "architectural_axis",
        "brief": "左右高耸柱廊、拱券或街巷立面夹出深邃纵向通道，形成明确透视引导线",
    },
    {
        "id": "vertical_atrium",
        "name": "多层垂直中庭与阶梯深井",
        "spatial_mode": "interior",
        "family": "enclosure_light",
        "brief": "纵向多层回廊、阳台与跨层楼梯叠落，高处斜射自然天光或体积光束",
    },
    {
        "id": "window_framing",
        "name": "近景窗框与半透帘幕框景",
        "spatial_mode": "framed",
        "family": "intimate_framed",
        "brief": "透过微风吹拂的半透明前景纱帘与窗框，近看窗台日常器皿与窗外明朗远景",
    },
    {
        "id": "abstract_geometric_void",
        "name": "纯粹几何构成与光学雕塑虚空",
        "spatial_mode": "floating",
        "family": "abstract_paradox",
        "brief": "脱离现实房间与地面约束，用自定义 BMesh/CURVE 交错悬浮的彩玻板片、金属弧面与光学棱柱构筑雕塑感抽象构成",
    },
    {
        "id": "megastructure_horizon",
        "name": "写实近景与远景天际线建筑并置",
        "spatial_mode": "grounded",
        "family": "landscape_plaza",
        "brief": "近处是亲切的自然水岸、草坡或街道，远方天际线矗立着流线型高塔或大型构筑物",
    },
    {
        "id": "terraced_water_plaza",
        "name": "多级弧形露台与水景花园广场",
        "spatial_mode": "grounded",
        "family": "landscape_plaza",
        "brief": "层叠弧形平台、洁净镜面水池、飘带式步行天桥与曲线绿植槽构成的开放公共空间或海岸观景台",
    },
    {
        "id": "curved_glass_pavilion",
        "name": "曲线玻璃穹顶与通透生态展馆",
        "spatial_mode": "interior",
        "family": "enclosure_light",
        "brief": "流畅曲面玻璃天顶、通透采光结构与室内水景绿植共同组成的明亮开放大厅或生态温室",
    },
    {
        "id": "floating_noneuclidean",
        "name": "无地面失重与非欧视错觉空间",
        "spatial_mode": "floating",
        "family": "abstract_paradox",
        "brief": "打破常规重力方向，正交闭合死循环阶梯、四向重力翻转房间或云端无支撑螺旋阶梯",
    },
]

# 广谱艺术与空间设计流派库（以经典建筑与自然地景为先，按 6 大美学家族分层抽样，拒绝单一参考图绑架）
ART_MOVEMENTS = [
    # --- 家族 1：建筑空间与文化光影 (family="architectural_interior") ---
    {
        "id": "minimalist_architecture",
        "name": "现代极简光影空间 (Minimalist Architecture)",
        "avant_garde": False,
        "family": "architectural_interior",
        "recommended_archetypes": ["interior_hall", "canyon_megastructure", "open_landscape"],
        "cues": "干净舒展的清水混凝土或白墙切面留出利落采光口，阳光穿过浅水庭院在墙面上映出安静的切割光斑",
    },
    {
        "id": "east_asian_courtyard",
        "name": "东方园林与木构光影 (East Asian Courtyard)",
        "avant_garde": False,
        "family": "architectural_interior",
        "recommended_archetypes": ["window_framing", "interior_hall", "open_landscape"],
        "cues": "深色木格栅门窗、月洞门框景、静水倒影与青苔汀步石，光影穿过格栅投下细密柔和的影子",
    },
    {
        "id": "art_deco_monument",
        "name": "装饰艺术与对称几何殿堂 (Art Deco)",
        "avant_garde": False,
        "family": "architectural_interior",
        "recommended_archetypes": ["vertical_atrium", "interior_hall", "canyon_megastructure"],
        "cues": "对称竖向凹槽壁柱、阶梯拱门、磨砂琥珀洗墙灯与深色大理石配温润黄铜线条，秩序庄重而华丽",
    },
    {
        "id": "brutalism_megastructure",
        "name": "粗野主义混凝土巨构 (Brutalism)",
        "avant_garde": True,
        "family": "architectural_interior",
        "recommended_archetypes": ["canyon_megastructure", "vertical_atrium", "interior_hall"],
        "cues": "成排高耸的裸露水泥巨柱与挑空栈桥夹出窄深通道，用强烈的体量对比衬出建筑的厚重纪念碑感",
    },
    {
        "id": "vertical_lightshaft_atrium",
        "name": "垂直光井与层叠回廊 (Light-Shaft Atrium)",
        "avant_garde": True,
        "family": "architectural_interior",
        "recommended_archetypes": ["vertical_atrium"],
        "cues": "多层次叠落的回廊栏杆与阶梯，高处斜射下来的明亮体积光束切开安静的室内空间",
    },

    # --- 家族 2：自然地景与生态人文 (family="nature_and_horizon") ---
    {
        "id": "pastoral_coastal_horizon",
        "name": "明媚海岸与自然地景画卷 (Coastal / Pastoral)",
        "avant_garde": False,
        "family": "nature_and_horizon",
        "recommended_archetypes": ["open_landscape", "window_framing", "terraced_water_plaza"],
        "cues": "清澈海面或起伏绿丘、自然植被碎石与远山层叠，搭配木栈道、灯塔或海滨白色拱廊，气氛舒朗放松",
    },
    {
        "id": "overgrown_sanctuary",
        "name": "静谧废墟与植物共生圣所 (Overgrown Sanctuary)",
        "avant_garde": False,
        "family": "nature_and_horizon",
        "recommended_archetypes": ["canyon_megastructure", "open_landscape", "interior_hall"],
        "cues": "被蕨类、藤蔓与野花悄然接管的古典石柱拱廊或老旧建筑，林间天光透下安静温柔的时间感",
    },
    {
        "id": "scifi_grounded_reality",
        "name": "写实近景与远景异质构筑并置 (Sci-Fi in Reality)",
        "avant_garde": True,
        "family": "nature_and_horizon",
        "recommended_archetypes": ["megastructure_horizon", "open_landscape"],
        "cues": "近处是亲切的日常街道、草地或水岸，百米外天际线在空气透视雾中隐约耸立着流线高塔或大型飞行器",
    },

    # --- 家族 3：超现实、阈限与风格化动画 (family="surreal_and_liminal") ---
    {
        "id": "liminal_poolcore",
        "name": "阈限空间与池核梦核 (Liminal / Poolcore)",
        "avant_garde": True,
        "family": "surreal_and_liminal",
        "recommended_archetypes": ["interior_hall", "vertical_atrium"],
        "cues": "空无一人的干净瓷砖水池或无限延展的柔和走廊，均匀天光下带着安静而微妙的梦境疏离感",
    },
    {
        "id": "translucent_window_dream",
        "name": "半透窗景与微风静物 (Translucent Framing)",
        "avant_garde": True,
        "family": "surreal_and_liminal",
        "recommended_archetypes": ["window_framing"],
        "cues": "微风吹起的半透明薄纱贴在镜头前，透过柔光看窗台上的日常玻璃器皿与窗外明朗海天",
    },
    {
        "id": "surrealism_antigravity",
        "name": "超现实失重梦境 (Surrealism)",
        "avant_garde": True,
        "family": "surreal_and_liminal",
        "recommended_archetypes": ["floating_noneuclidean", "abstract_geometric_void"],
        "cues": "熟悉的日常门框、家具或植物违背重力悬停在云海与长阶之上，用反常识的构图表达诗意梦境",
    },
    {
        "id": "atmospheric_anime",
        "name": "清透空气感二次元 (Atmospheric Anime)",
        "avant_garde": False,
        "family": "surreal_and_liminal",
        "recommended_archetypes": ["window_framing", "open_landscape", "canyon_megastructure"],
        "cues": "像动画电影背景一样清爽的明暗色块与柔和光斑，通透轻盈又带着鲜明的色彩情绪",
    },
    {
        "id": "stylized_miniature_diorama",
        "name": "微缩模型与切片微景箱 (Miniature Diorama)",
        "avant_garde": False,
        "family": "surreal_and_liminal",
        "recommended_archetypes": ["interior_hall", "window_framing", "open_landscape"],
        "cues": "像精雕细琢的建筑模型或手办沙盘，温润黏土/原木质感配柔和浅景深棚拍灯光",
    },

    # --- 家族 4：赛博都市与科技工业 (family="cyber_and_scifi") ---
    {
        "id": "cyberpunk_neon_alley",
        "name": "赛博朋克与雨夜霓虹街景 (Cyberpunk Neon)",
        "avant_garde": False,
        "family": "cyber_and_scifi",
        "recommended_archetypes": ["canyon_megastructure", "vertical_atrium"],
        "cues": "雨后反光的湿润街巷、高架轨道与密集管线、暖橙与品红/青色霓虹招牌在夜雾里交错映照",
    },
    {
        "id": "cassette_futurism",
        "name": "复古磁带未来工业 (Cassette Futurism)",
        "avant_garde": False,
        "family": "cyber_and_scifi",
        "recommended_archetypes": ["interior_hall", "canyon_megastructure"],
        "cues": "米白配暗橙色的厚重圆角控制台与磁带机柜排成阵列，弧面老式显示器泛着温暖的琥珀或荧光绿微光",
    },
    {
        "id": "holographic_industrial_sanctum",
        "name": "全息数据中心与硬核工业 (Holographic Industrial)",
        "avant_garde": True,
        "family": "cyber_and_scifi",
        "recommended_archetypes": ["canyon_megastructure", "vertical_atrium", "interior_hall"],
        "cues": "深色混凝土/拉丝钢结构内景与半透明数据投影面板形成虚实对照",
    },

    # --- 家族 5：纯粹抽象与视错觉几何 (family="abstract_and_paradox") ---
    {
        "id": "suprematism_kinetic_geometry",
        "name": "至上主义与动态几何构成 (Suprematism / Kinetic Geometry)",
        "avant_garde": True,
        "family": "abstract_and_paradox",
        "recommended_archetypes": ["abstract_geometric_void", "floating_noneuclidean"],
        "cues": "纯粹由悬浮咬合的哑光色彩切片、磨砂折射玻璃体、细长平衡杆与切割光束构成张力十足的抽象雕塑画面",
    },
    {
        "id": "non_euclidean_paradox",
        "name": "非欧几里得与视错觉悖论 (Non-Euclidean Paradox)",
        "avant_garde": True,
        "family": "abstract_and_paradox",
        "recommended_archetypes": ["floating_noneuclidean"],
        "cues": "用正交镜头做出首尾咬合的死循环阶梯，或者让上下左右四个方向的重力同时翻转，构筑挑战空间直觉的几何迷宫",
    },
    {
        "id": "sculptural_light_geometry",
        "name": "极简光学折射与曲面雕塑 (Optical Glass Sculpture)",
        "avant_garde": True,
        "family": "abstract_and_paradox",
        "recommended_archetypes": ["abstract_geometric_void", "interior_hall"],
        "cues": "在纯净背景里摆放半透色散棱镜、流线型哑光雕塑曲面与柔和焦散光影，强调光色折射与纯粹形式美",
    },
    {
        "id": "bauhaus_constructivism",
        "name": "包豪斯构成主义几何 (Bauhaus / De Stijl)",
        "avant_garde": False,
        "family": "abstract_and_paradox",
        "recommended_archetypes": ["abstract_geometric_void", "interior_hall"],
        "cues": "原色几何板片、半透彩玻圆弧与细长金属轴线在空间中穿插咬合，画面干净利落充满现代构成韵律",
    },
    {
        "id": "lowpoly_faceted",
        "name": "低多边形硬切面构成 (Low-Poly Faceted)",
        "avant_garde": False,
        "family": "abstract_and_paradox",
        "recommended_archetypes": ["open_landscape", "abstract_geometric_void"],
        "cues": "故意保留硬朗利落的多边形切角晶面，让相邻几何面片在冷暖灯光下呈现出折纸雕塑般的块面感",
    },

    # --- 家族 6：未来图景与生态乐观主义 (family="future_utopia") ---
    {
        "id": "frutiger_aero_utopia",
        "name": "千禧生态玻璃与水景未来 (Frutiger Aero)",
        "avant_garde": False,
        "family": "future_utopia",
        "recommended_archetypes": ["open_landscape", "terraced_water_plaza", "window_framing", "curved_glass_pavilion"],
        "cues": "明亮晴空与蓬松白云下，以光洁流线曲面、通透蓝绿玻璃与清澈水体折射、翠绿植物群落为抽象设计语法，可自由构筑滨海长廊、嵌入草坡或水下的球穹、阳光交通露台或透光球体装置，洋溢轻盈乐观的千禧未来感",
    },
    {
        "id": "solarpunk_botanical",
        "name": "阳光生态乌托邦 (Solarpunk)",
        "avant_garde": False,
        "family": "future_utopia",
        "recommended_archetypes": ["open_landscape", "terraced_water_plaza", "megastructure_horizon", "curved_glass_pavilion"],
        "cues": "暖阳下的弧形木构与生态露台、攀援绿植与垂直花园、流动水渠和半嵌入丘陵的透明采光穹顶，展现人与自然科技温柔共生的多样空间剪影",
    },
    {
        "id": "retro_futurism_space_age",
        "name": "复古太空时代未来主义 (Space-Age / Googie)",
        "avant_garde": False,
        "family": "future_utopia",
        "recommended_archetypes": ["open_landscape", "interior_hall", "terraced_water_plaza"],
        "cues": "上世纪中叶乐观太空幻想：悬挑翼型屋檐、奶油白配珊瑚橙/薄荷绿烤漆曲面、流线型观景平台与高架轨道线条",
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
    parent_dir = os.path.dirname(os.path.abspath(output_path))
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    req_data = {
        "export_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tone_mode": s.get("tone_mode", "较富有激情的"),
        "interaction_mode": s.get("interaction_mode", "detailed"),
        "spatial_topology": {
            "spatial_archetype": s.get("spatial_archetype", ""),
            "spatial_mode": s.get("spatial_mode", "grounded"),
            "complexity_tier": s.get("complexity_tier", "tier2_architectural"),
            "structural_entropy": s.get("structural_entropy", "intact_order"),
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
    当用户尚未设定具体主题/画面时，从 6 大美学家族与 10 种空间拓扑中均衡抽取不重复的灵感跳板：
    - 每次从 6 个美学家族中随机选 5 个不同家族（避免任何单一美学流派或特定道具霸榜）
    - 从不同空间家族抽取 4 种形态各异的空间拓扑（涵盖展馆、露台广场、室内、柱廊峡谷、自然地景或非欧/抽象等）
    - 自动避开最近几次刚用过的流派与拓扑
    """
    profile = profile or load_profile()
    rnd = random.Random(seed if seed is not None else time.time_ns())
    stats = profile.get("history_stats", {})
    recent_movs = set(stats.get("recent_movements", [])[-4:])
    recent_archs = set(stats.get("recent_archetypes", [])[-2:])

    # 1. 从不同空间家族均匀抽取 4 种空间拓扑
    arch_families = list(dict.fromkeys(a.get("family", "other") for a in SPATIAL_ARCHETYPES))
    rnd.shuffle(arch_families)
    picked_archs = []
    for fam in arch_families[:4]:
        pool = [
            a for a in SPATIAL_ARCHETYPES
            if a.get("family") == fam and a["id"] not in recent_archs and a["name"] not in recent_archs
        ] or [a for a in SPATIAL_ARCHETYPES if a.get("family") == fam]
        if pool:
            picked_archs.append(rnd.choice(pool))
    rnd.shuffle(picked_archs)

    # 2. 从 6 大美学家族中抽取 5 个不同家族，每个家族选 1 种流派，确保广谱多样性而不偏科
    mov_families = list(dict.fromkeys(m.get("family", "other") for m in ART_MOVEMENTS))
    rnd.shuffle(mov_families)
    picked_movs = []
    for fam in mov_families[:5]:
        fresh = [
            m for m in ART_MOVEMENTS
            if m.get("family") == fam and m["id"] not in recent_movs and m["name"] not in recent_movs
        ] or [m for m in ART_MOVEMENTS if m.get("family") == fam]
        if fresh:
            picked_movs.append(rnd.choice(fresh))
    rnd.shuffle(picked_movs)

    return {
        "suggested_archetypes": [{k: v for k, v in a.items() if k != "builder_hint"} for a in picked_archs],
        "suggested_movements": picked_movs,
        "guidance_scope": (
            "仅在用户还没想好要画什么、主动要求“提供场景灵感”时作为跨流派参考跳板使用。"
            "只要用户已提出自己的主题、意象、时代情绪或具体画面描述，必须优先贴合用户意象的真实审美语境自由构思，"
            "严禁拿无关的随机种子或历史高分流派强行覆盖用户意图！"
        ),
        "usage_note": (
            "请用连贯自然的日常语言现场自由改写，严禁照抄原词；建模时优先用原创 bmesh/CURVE 与 CC0 资产塑造契合主题的三维结构，"
            "切勿把某类特定模板或构件当成万能配方跨风格硬塞"
        ),
    }


def get_preference_hints(profile=None, seed=None, include_inspirations=True):
    """
    提问前调用，返回历史高分偏好、低分避雷、沟通模式倾向。
    - include_inspirations=True（默认，兼容直接 Python 调用）：附带 divergent_suggestions 跨流派灵感跳板；
    - include_inspirations=False（CLI `--hints` 模式）：仅输出用户历史偏好，不预注入随机场景种子，避免 Turn 1 污染用户意图。
    """
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
    }
    if include_inspirations:
        hints["divergent_suggestions"] = sample_divergent_directions(profile, seed=seed)
    else:
        hints["inspiration_note"] = (
            "当前仅返回用户历史偏好，未附带随机场景种子。"
            "只要用户已经给出主题、意象或大概画面，严禁再去拉取随机灵感种子；"
            "仅当用户主动选择“先给我提供几个场景灵感挑一挑”（路径 ③）时，再执行 `python scripts/profile_manager.py --inspire`。"
        )
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
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(encoding="utf-8")
            except Exception:
                pass
    args = set(sys.argv[1:])
    if "--hints" in args and "--inspire" in args:
        print(json.dumps(get_preference_hints(include_inspirations=True), ensure_ascii=False, indent=2))
    elif "--hints" in args:
        print(json.dumps(get_preference_hints(include_inspirations=False), ensure_ascii=False, indent=2))
    elif "--inspire" in args:
        print(json.dumps({"divergent_suggestions": sample_divergent_directions()}, ensure_ascii=False, indent=2))
    else:
        print("用法: python scripts/profile_manager.py --hints | --inspire")
