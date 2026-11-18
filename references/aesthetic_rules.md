# 艺术流派谱系、三维空间构成与真实材质参考

> **核心原则（彻底去锚定，拒绝参考图套路复刻）**：下文所有流派拆解与技法**仅作为造型、空间和着色的工程原理参考，绝非固定文案或必塞配件清单**。构思与提问时，**必须从用户实际输入的主题、情绪与文化语境出发**，只选取真正属于该世界观的建筑、自然或器物元素，严禁把任何特定模板或历史参考图里的标志性物件跨风格硬塞进其他题材！

---

## 一、三维空间构成四原则（摆脱“平地摆件”而不陷于套路）

1. **先定空间包裹与视野层次，再造主体**：
   - 画面张力来自**三维体量如何组织镜头视角**——可以是封闭室内采光洞、拱券柱廊、开阔自然地景、半透前景窗框、多层垂直回廊，也可以是流线曲线屋檐与露台水景或脱离地面的雕塑构成。优先用原创 `bmesh`/`CURVE` 建模结合真实 CC0 资产搭起立体空间，避免只建一块孤立小平面摆一两个简单方块。
2. **明确前、中、后三层纵深关系**：
   - **前景锚点层**（距相机 0.8~3.5 米）：符合当前画风的前景引导元素（如建筑柱廊侧翼、半透窗帘与窗台器物、浅水岸边、绿植花草或框景结构）。
   - **中景核心层**（距相机 3.5~22 米）：由多个真实结构部件拆解组成的主体空间或构筑物，避免前后正对挡死视线。
   - **远景闭合层**（距相机 22~220 米）：底座深扎地下的远山层次、晴朗天空与云层、门洞外延伸视野、或与近景呼应的天际线建筑群（**严禁暴露方形地面断口或悬空山体底边**）。
3. **色彩克制与明暗匹配主题情绪**：
   - 明亮乐观/生态/清新题材应采用通透的日光或天光比例（主色 60%~80% 清亮底色 + 15%~30% 植被/材质冷暖对比 + 5%~10% 高纯度点缀），切忌乱套灰暗阴沉雾效；冷峻、赛博或戏剧题材再拉开强对比与压暗暗部。
4. **体积雾必须“有界化”或使用柔和景深 Mist**：
   - 需要丁达尔光束时使用 `create_volumetric_light_beam` 局部雾盒；户外远景空气透视使用 `setup_daylight_sky_world`（晴朗通透）或 `setup_aerial_perspective_world`（厚重戏剧云雾）的 Mist 通道，**不要给整个 World 连高浓度无限体积散射**。

---

## 二、广谱艺术与空间流派工程指南（经典基础为先，按需适配，绝不串台）

### 1. 现代极简与光影建筑 (Minimalist Architecture / Brutalism)
- **空间骨架**：优先用原创 `bmesh` 墙体切面与天花光口建模，或按需选用 `build_enclosed_room`、`build_arched_colonnade`、`build_canyon_corridor`，靠利落的体块切口、顶棚天窗条带、浅水倒影与柱列光影撑起建筑体量。
- **材质与光影**：真实扫描混凝土/微水泥/石材 CC0 PBR 贴图（`setup_pbr_texture_material`），靠 `Sun` 斜射投影或 HDRI 自然天光拉出明暗秩序，后期按情绪可选 `"cinematic_warm"` 或 `"high_contrast_chiaroscuro"`；细节克制，**严禁在极简空间里乱塞碎晶或全息板**。

### 2. 写实自然地景与生态人文 (Grounded Horizon / Coastal / Overgrown Sanctuary)
- **空间骨架**：`spatial_mode="grounded"`。近景使用 `build_endless_ground` + 真实 CC0 植物、树木、岩石、木栈道（`make_plank_floor`）或水岸；远景（`Y = 48m ~ 240m`）视主题需要搭配 `build_grounded_backdrop_ridge` 实体远山或 `build_megastructure_horizon`（按画风选 `brutalist_fortress` / `orbital_spire` / `hovering_ovoid_ship` / `sleek_biomorphic_towers`）。

### 3. 东方园林与古典拱廊 (East Asian Courtyard / Classical / Art Deco)
- **空间骨架**：优先用自定义 `bmesh` 格栅门窗、月洞门框景、檐口梁柱与 CC0 植物器皿，配合 `build_arched_colonnade`、木栈道（`make_plank_floor`）或庭院水面，也可按需结合 `build_terraced_water_plaza` 做阶梯水台。
- **材质与光影**：温润木纹、石材砖砌 CC0 PBR 贴图、磨砂金属或温润黄铜，柔和侧逆光穿过格栅投下细密投影。

### 4. 半透窗景框景与清透二次元 (Translucent Framing / Atmospheric Anime)
- **空间骨架**：自定义窗台室内结构与布料，或按需选用 `build_window_frame_stage(add_curtains=True)`（`spatial_mode="framed"`）。机位在室内透过轻纱看窗台日常静物与窗外海天/街景。
- **色彩管理**：明快二次元或扁平插画风在 `settings` 中设 `"view": "Standard"` 保持通透色彩，搭配 `"clean_anime"` 后期。

### 5. 阈限空间与池核梦核 (Liminal Space / Poolcore)
- **空间骨架**：`build_enclosed_room(..., ceiling_coffers=(3, 4, 0.28), openings={"back": [...]})`、`build_vertical_atrium` 或自定义瓷砖回廊，相机放偏低人眼位（`Z ≈ 1.4m`）。
- **结构与光影**：洁净瓷砖地面、浅水池岸、门洞外强漫射亮区、柔和均匀天光，突出“安静空旷”的空间节奏（不要强加夸张科幻环）。

### 6. 千禧生态未来与阳光乌托邦 (Frutiger Aero / Solarpunk)
- **核心设计语法（抽象美学特征，而非单一固定建筑）**：围绕**光洁饱满的流线曲面（glossy curved forms）**、**清澈水体与蓝绿半透玻璃折射（translucent water & glass）**、**明朗晴空积云与生机植被（sky & lush foliage）**、以及洁白烤漆/温润原木/拉丝轻金属的轻盈对比展开构思。
- **多元剪影与构图（严禁每次都复刻“抛物线玻璃展馆+中央水池”）**：根据具体语义自由衍生不同空间形态，例如**滨海流线白色长廊与亲水步道（coastal promenades）**、**半嵌入草坡或水下的透明球穹（submerged / hillside domes）**、**高架轨交站台与层叠绿植交通露台（transit terraces）**、**开放阳光广场（sunlit plazas）**、或**水面折射与晴空中的透光球体及流线雕塑（translucent orbs）**。
- **造型实现与光影**：**优先使用原创 `bmesh` / `CURVE` 放样、Subdivision/SimpleDeform 曲面造型与真实 CC0 植物模型**塑造独特轮廓；仅在构想确需对应形态时，按需选用 `build_swept_ribbon_bridge`、`build_smooth_planter_pod`、`build_terraced_water_plaza`、`build_curved_glass_pavilion` 或 `build_megastructure_horizon(..., style="sleek_biomorphic_towers")`。天空优先调用 `setup_daylight_sky_world(...)` 搭配晴朗蓝天白云；后期可选 `"bright_luminous_daylight"` 或 `"vibrant_futuristic_gloss"`。

### 7. 复古太空时代未来主义 (Retro-Futurism / Googie / Space-Age)
- **核心语境**：20 世纪中叶乐观太空畅想、流畅翼型、大跨度悬挑屋檐与流线型未来感。
- **空间骨架**：优先以原创 `bmesh`/`CURVE` 塑造翼型雨棚、螺旋观景塔、抛物线拱门与曲面栏杆，亦可按需搭配 `build_swept_ribbon_bridge` 或 `build_terraced_water_plaza`。
- **材质与光影**：奶油白、薄荷青、珊瑚橙/亮黄烤漆配拉丝铬金属，搭配明朗晴空或暮色暖金日光。

### 8. 赛博朋克与全息/磁带未来 (Cyberpunk / Cassette Futurism / Holographic)
- **空间骨架**：雨后街巷/柱列/机房大厅 + 错落楼宇看板、弧面老式机柜或有节制的半透明数据屏（`build_holographic_data_matrix`，**仅在明显需要全息界面的赛博/数据主题时使用**）。
- **材质与光影**：湿润反光地面（`Roughness` 贴图映射出局部水迹反光）、局部高纯度霓虹/显示器自发光点缀（控制自发光强度避免死白）。

### 9. 超现实失重与非欧悖论 (Surrealism / Non-Euclidean Paradox)
- **空间骨架**：`spatial_mode="floating"`，根据构想选择自定义失重日常器物，或按需调用 `build_impossible_stair_loop(..., setup_ortho_camera=True)`（正交彭罗斯阶梯）、`build_gravity_flip_room`（四向重力房间）、`build_spiral_stair_ribbon`（悬空旋梯）。
- **造型注意**：只有在主题本身明确需要**崩裂废墟/破碎空间**时，才使用 `build_bmesh_fractured_slab` 与 `build_shattered_shard_vortex`；只有在明确需要**精密机械涡轮/星象环**时，才使用 `build_profiled_machined_ring`。

---

## 三、材质三阶梯（写实表面拒绝纯数学噪波塑料感）

1. **第一梯队（真实扫描 CC0 PBR 贴图集）**：
   - 混凝土、砖石、木板、金属板、礁石、泥地等写实大面积结构，优先调用 `asset_loader.download_pbr_texture_set(...)` 或 `asset_loader.search_cc0_assets("textures", [...])`，通过 `setup_pbr_texture_material(..., use_box_mapping=True)` 免展 UV 均匀包裹。
2. **第二梯队（生图定制贴图）**：
   - 需要特定花纹砖、图案壁纸、做旧斑驳墙皮或定制粗糙度遮罩时，调用生图工具生成无缝图并传入 `setup_generated_texture_material(...)`。
3. **第三梯队（程序化节点适用范围）**：
   - 透光玻璃（含 `Light Path -> Is Shadow Ray` 透光优化）、清澈水面、半透薄纱窗帘、洁净烤漆塑料、赛璐珞双阶色块（`create_procedural_toon_material`）、低多边形纯平切面、或离线兜底。

---

## 四、语境适配细节与合成器后处理预设

### 1. 细节语言必须严格服从当前画风（严禁跨画风乱塞固定物件）

| 场景语境类别 | 推荐的尺度参照与细节语言 | 严禁跨风格套用的违和元素 |
| :--- | :--- | :--- |
| **现代极简 / 室内 / 美术馆 / 古典园林** | 原创 BMesh 建筑细部、门窗框棂格、踏步台阶、真实扫描木石材质、柱廊拱券（`build_arched_colonnade`）、桌椅书本（`build_curved_open_book`）、器皿灯具、水面倒影 | **工业凸块 Greebles、无关科幻装置或悬浮碎片** |
| **自然地景 / 海岸 / 生态人文** | 大尺度地形起伏（`build_endless_ground`）、真实 CC0 植物花草树木与岩石、木栈道（`make_plank_floor`）、水岸石阶与自然光影 | **毫无来由的科技面板、违和金属护栏或硬塞的玻璃展馆** |
| **阳光生态 / Frutiger Aero / 现代公共空间** | 原创 `bmesh`/`CURVE` 光洁曲面结构、透光蓝绿玻璃与水体折射、多样轮廓（滨海长廊/山丘或水下球穹/轨交露台/透光球体）、真实植物花草与水波；按需可选 `build_smooth_planter_pod` / `build_swept_ribbon_bridge` | **重工业机械零件、破碎废墟混凝土、生锈铁栏杆、厚重暗黑堡垒塔或无关全息方板** |
| **粗野峡谷 / 硬核工业 / 废墟** | 1.05m 挑空步道护栏（`build_canyon_corridor(..., catwalk_levels=3)`）、`build_hanging_cables` 悬缆、`build_bmesh_fractured_slab` 真断裂断面 | **违和的甜美玩具配色或无支撑轻飘圆球** |
| **精密科幻核心 / 赛博全息 / 抽象雕塑** | 普通抽象构成优先用原创 BMesh/曲面几何体与光学折射玻璃；仅当主题明确需要时才选用 `build_profiled_machined_ring`、`build_hex_wafer_array`、`build_holographic_data_matrix` | **与抽象/科技主题无关的木栅栏或生活杂物** |

### 2. 合成器后处理预设 (`POST_PROCESS_PRESETS` / `br.run_post_process`)
- **温暖电影感 (`"cinematic_warm"`)**：暖金黄昏 Mist 薄雾 + 柔和 Bloom + 暖调调色 + 暗角（经典中性基础，适合日常室内、古典庭院、自然风光与暖阳叙事）。
- **清透二次元 (`"clean_anime"`)**：搭配 `"view": "Standard"`，轻柔 Bloom + 明快饱和度。
- **阈限梦核 (`"liminal_dream"`)**：微黄薄雾 + 低阈值大范围柔光 + 轻度暗角色散。
- **高反差明暗对照 (`"high_contrast_chiaroscuro"`)**：强 AO + 高对比 + 深暗角。
- **冷峻粗野 (`"sterile_cold_brutalist"`)**：冷灰蓝 Mist 雾气 + 强 AO 接触阴影 + Fog Glow + 偏冷去饱和调色（**仅适合冷峻工业/粗野题材，勿用于明快阳光场景**）。
- **超现实星芒 (`"surreal_ethereal_glow"`)**：深海蓝雾 + Bloom + 6 芒 Streaks 星芒。
- **晴朗明亮日光 (`"bright_luminous_daylight"`)**：轻柔天蓝远景空气感 + 轻度日光 Bloom + 清爽色彩还原 + 极轻暗角（适合海岸公园、阳光自然地景、Solarpunk、Frutiger Aero）。
- **通透未来光泽 (`"vibrant_futuristic_gloss"`)**：明快蓝青调亮感 + 柔和玻璃高光 Bloom + 微色散（适合洁净未来、流线曲面材质、Y2K/Space-Age）。

---

## 五、视觉自审常见问题与修复配方

| 自审发现的问题 | 根因诊断 | 确定性修复方向 |
| :--- | :--- | :--- |
| **1. 画面冒出与主题无关的齿轮圆盘、灰暗塔楼、碎晶或全息方块** | 机械套用了模板默认配件或旧参考图套路 | **立即删除所有跨画风套路构件**，改用符合用户主题语义的建筑/自然/器物结构。 |
| **2. 阳光/生态/明快场景画面灰暗发闷、像阴天或末日** | 错用了 `setup_aerial_perspective_world` 默认冷暗参数或 `"sterile_cold_brutalist"` 后期 | 改调 `setup_daylight_sky_world(...)` 并配 `"bright_luminous_daylight"` 或 `"cinematic_warm"`。 |
| **3. 玻璃屋顶下的室内地面一片漆黑** | 玻璃材质在 Cycles 下挡住了直射日光阴影 | 为自建玻璃材质接入 `Light Path -> Is Shadow Ray -> Transparent BSDF` 透光节点（`build_curved_glass_pavilion` 亦已内置该做法），或补充柔和室内天光面光。 |
| **4. 远景建筑或山体悬在半空、地面露出方形切角** | 地面半径过小或远景底座高于 `Z=0` | 改用 `build_endless_ground(radius=95)` 与 `build_grounded_backdrop_ridge(base_sink=-4.5)`，并确保外景构筑物底座扎入地下。 |
| **5. 造型已合格但光晕、雾气或明暗反差欠火候** | 属于后期调色范畴，无需重跑 3D 渲染 | 直接调用 `br.run_post_process(output_dir, post_process=..., exposure=...)` 基于 `raw_cache.exr` 秒级无损调色。 |
