"""
profile_manager.py
Vibe-Modeler 用户美学偏好持久化与推测引擎
记录历史生成轨迹、4 维度打分，并推测用户潜在的美学倾向（色温、对比度、构图与风格偏好），
自动生成 Mermaid 决策溯源图。
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
        "composition_affinity": "thirds" # thirds / center / cinematic_wide
    },
    "history_stats": {
        "total_creations": 0,
        "style_counts": {"realistic": 0, "cartoon": 0},
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

def record_session(session_data, rating_data):
    """
    session_data:
      - style: "realistic" | "cartoon"
      - keyword: str
      - subject: str
      - scene: str
      - tone: "warm" | "cold" | "neutral"
      - contrast: "high" | "low" | "medium"
      - ratio: "16:9" | "21:9" | "1:1" | "9:16"
      - camera_lens: "wide" | "standard" | "portrait_dof"
      - blend_file: str
      - render_file: str

    rating_data:
      - atmosphere: int (1~5)
      - modeling: int (1~5)
      - lighting: int (1~5)
      - composition: int (1~5)
      - user_comment: str
    """
    profile = load_profile()
    stats = profile["history_stats"]
    stats["total_creations"] += 1
    
    style = session_data.get("style", "cartoon")
    if style in stats["style_counts"]:
        stats["style_counts"][style] += 1
    else:
        stats["style_counts"][style] = 1

    kw = session_data.get("keyword")
    if kw and kw not in stats["favorite_keywords"]:
        stats["favorite_keywords"].append(kw)
        if len(stats["favorite_keywords"]) > 10:
            stats["favorite_keywords"].pop(0)

    # 动态推测并更新美学权重 (根据用户打分加权更新)
    weights = profile["aesthetic_weights"]
    avg_score = (rating_data.get("atmosphere", 4) + rating_data.get("lighting", 4)) / 2.0
    impact = 0.15 if avg_score >= 4 else -0.05

    # 色调倾向更新
    if session_data.get("tone") == "warm":
        weights["warmth_affinity"] = max(-1.0, min(1.0, weights["warmth_affinity"] + impact))
    elif session_data.get("tone") == "cold":
        weights["warmth_affinity"] = max(-1.0, min(1.0, weights["warmth_affinity"] - impact))

    # 对比度倾向更新
    if session_data.get("contrast") == "high":
        weights["contrast_affinity"] = max(-1.0, min(1.0, weights["contrast_affinity"] + impact))
    elif session_data.get("contrast") == "low":
        weights["contrast_affinity"] = max(-1.0, min(1.0, weights["contrast_affinity"] - impact))

    # 风格倾向更新
    if style == "cartoon":
        weights["stylized_vs_realism"] = max(-1.0, min(1.0, weights["stylized_vs_realism"] + impact))
    else:
        weights["stylized_vs_realism"] = max(-1.0, min(1.0, weights["stylized_vs_realism"] - impact))

    record = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "session": session_data,
        "rating": rating_data
    }
    profile["sessions"].append(record)
    save_profile(profile)
    return profile

def get_aesthetic_insight(profile=None):
    if profile is None:
        profile = load_profile()
    weights = profile["aesthetic_weights"]
    stats = profile["history_stats"]

    warmth_text = "偏好温暖治愈调性（日落金橙、温润暖光）" if weights["warmth_affinity"] > 0.2 else (
        "偏好清冷静谧调性（月光蓝、清冽青冷光）" if weights["warmth_affinity"] < -0.2 else "冷暖平衡或随场景自适应"
    )
    contrast_text = "喜好高反差光影张力（明显明暗面、雕刻轮廓）" if weights["contrast_affinity"] > 0.2 else (
        "喜好柔和漫射空气感（微光弥漫、低反差层次）" if weights["contrast_affinity"] < -0.2 else "自然均衡反差"
    )
    style_text = "倾向二次元/卡通赛璐珞唯美风" if weights["stylized_vs_realism"] > 0.2 else (
        "倾向写实电影级光影 PBR 质感" if weights["stylized_vs_realism"] < -0.2 else "风格多元包容"
    )

    return {
        "total_creations": stats["total_creations"],
        "warmth_text": warmth_text,
        "contrast_text": contrast_text,
        "style_text": style_text,
        "top_keywords": stats["favorite_keywords"][-5:]
    }

def generate_mermaid_trace(session_data, rating_data):
    style = "写实风格" if session_data.get("style") == "realistic" else "唯美卡通"
    kw = session_data.get("keyword", "晨曦微光")
    subj = session_data.get("subject", "孤岛灯塔")
    sc = session_data.get("scene", "悬崖与云海")
    tone = "暖色调（晨昏金橙）" if session_data.get("tone") == "warm" else "冷色调（青蓝幽静）"
    contrast = "高对比度（硬光雕刻）" if session_data.get("contrast") == "high" else "低对比度（柔光弥漫）"
    ratio = session_data.get("ratio", "16:9 宽屏")
    
    score_atm = rating_data.get("atmosphere", 5)
    score_mod = rating_data.get("modeling", 5)
    score_lit = rating_data.get("lighting", 5)
    score_cam = rating_data.get("composition", 5)

    mermaid_code = f"""```mermaid
flowchart LR
    subgraph S1 ["1. 灵感与风格"]
        F1["风格: {style}"] --> F2["核心词: {kw}"]
    end

    subgraph S2 ["2. 主体与场景"]
        F3["主体: {subj}"] --> F4["场景: {sc}"]
    end

    subgraph S3 ["3. 视效预设"]
        F5["色调: {tone}"]
        F6["反差: {contrast}"]
        F7["画幅: {ratio}"]
    end

    subgraph S4 ["4. Subagents 协同建模"]
        P1["环境布光师"]
        P2["主体建模师"]
        P3["运镜导演"]
    end

    subgraph S5 ["5. 视觉自省与微调"]
        R1["EEVEE 秒级预览"] --> R2["Agent 看图自省微调"]
        R2 --> R3["最终成品输出"]
    end

    subgraph S6 ["6. 用户多维评价"]
        Score["⭐ 唯美氛围: {score_atm}/5<br>⭐ 主体造型: {score_mod}/5<br>⭐ 色彩光影: {score_lit}/5<br>⭐ 构图运镜: {score_cam}/5"]
    end

    S1 --> S2 --> S3 --> S4 --> S5 --> S6
```"""
    return mermaid_code
