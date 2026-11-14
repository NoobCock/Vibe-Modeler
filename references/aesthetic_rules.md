# 艺术流派谱系、三维空间构成与真实材质参考

> **核心提示（不要使用示例提示同样的用词）**：下文所有流派拆解与词汇**仅作为造型、空间和着色逻辑的工程指南，绝非固定文案**。向用户提问或构思场景时，**严禁照抄本文原词或固定句式**，应结合 `profile_manager.py --hints` 抽取的方向自由混搭与延展。

---

## 一、打破“平地摆物件”：三维空间构成四原则

1. **先选空间包裹方式，再摆主体**：
   - 画面张力首先来自**三维体量怎么围合镜头**（头顶有没有顶棚梁格、左右有没有高墙夹峙、上下有没有多层回廊叠落、镜头前有没有半透帘幕框景、或者干脆取消地面让物体斜向贯穿虚空），绝不能每次都新建一块平面再放一两个孤零零的物件。
2. **明确前、中、后三层 Z/Y 纵深**：
   - **前景遮挡层**（距离相机 0.6~3 米）：半透窗帘、暗部台阶护栏、树枝剪影、失重碎片或水面反光，赋予画面纵深锚点。
   - **中景核心层**（距离相机 3~15 米）：主构筑物、楼梯转折、接待台、渡船或悬空主体，结构部件不少于 3 层。
   - **远景闭合层**（距离相机 15~80 米）：门洞外的亮光建筑、高耸尖塔与光环、有界体积光雾、或底座深埋地下的实体远山（**严禁留出方形地面断口或悬空假山底边**）。
3. **色彩克制（60-30-10 或 85-10-5 法则）**：
   - 大面积主色调（60%~85%）保持统一明度倾向，辅色（10%~30%）拉开冷暖（如暖白高光配青蓝暗部），高纯度点缀色控制在 5%~10% 以内（如灰蓝剪影里的几片珊瑚红碎片、白蓝大厅角落的一只亮色警示牌）。
4. **体积雾必须“有界化”**：
   - 需要丁达尔光束或远景薄雾时，调用 `create_volumetric_light_beam` 或建立局部雾盒（`fog_box["vm_is_volume"] = True`），**不要给整个 World 连高浓度无限体积散射**，否则会把 HDRI 天空和远景全部吞成死黑。

---

## 二、广谱艺术与空间流派工程指南

### 1. 阈限空间与池核 / 千禧洁净风 (Liminal Space / Poolcore / Frutiger Aero)
- **空间骨架**：调用 `build_enclosed_room(..., ceiling_coffers=(3, 4, 0.28), openings={"back": [...]})`，`spatial_mode="interior"`。相机放在室内偏低人眼位（`Z ≈ 1.4m`）。
- **结构特征**：藻井格栅吊顶、光滑弧形前台或浅水池岸、透明亚克力/玻璃圆柱、通往室外强光区的门洞。
- **材质与光影**：高光洁净白与天蓝色环氧地坪/瓷砖（真实瓷砖 PBR 或低粗糙度 `Roughness 0.08~0.18` 反射面），门窗外用高能量 `Sun` 在室内地面投出斜向亮斑，辅以室内柔和漫射面光防止死黑；角落点缀一两件日常小道具（防滑立牌、清洁桶、泳池扶梯）放大“空无一人”的微妙陌生感。

### 2. 粗野主义与神圣巨构峡谷 (Brutalism / Monumental Megastructure)
- **空间骨架**：调用 `build_canyon_corridor(..., alley_width=7.0, height=18.0, bay_count=8, focal_spire_height=28.0)`，低角度广角（`18~24mm`）仰拍。
- **结构特征**：成排厚重裸露混凝土肋柱、横跨头顶的压迫感过梁、尽头拔地而起的多级尖塔，或塔尖上方水平悬浮发光双环（`build_orbital_ribbons`）。
- **材质与光影**：必须使用真实扫描混凝土贴图（如 `concrete_layers_02`、`brushed_concrete_03`）配模板拉杆孔细部；地面可用雨后不均匀湿石砖（将粗糙度贴图经 `MapRange` 映射到 `0.08~0.52` 形成局部镜面水迹倒影）。

### 3. 超现实失重梦境 (Surrealism / Anti-Gravity)
- **空间骨架**：设置 `spatial_mode="floating"`，**完全不建地面**。组合 `build_spiral_stair_ribbon`（无支撑云端旋梯）、`build_orbital_ribbons`（贯穿画面的巨型倾斜金属/发光细环）、`build_suspended_shards`（漂浮花瓣或晶块）。
- **结构特征**：精细拆件或导入的日常大型器物（如三角钢琴、古典塔楼、门框）以反重力角度斜悬在高空，形成强烈的对角线动态构图。
- **材质与光影**：深色风暴云层或暮色渐变背景，冷暖逆光勾勒悬空物体轮廓，开启 `Bloom` 泛光让发光细环与晶块产生柔和光晕。

### 4. 非欧几里得与视错觉空间 (Non-Euclidean / Optical Paradox)
在 Blender 中通过以下两种可靠几何手段实现，切忌胡乱堆方块：
- **手段 A（正交视错觉闭合环）**：调用 `build_impossible_stair_loop(cam_location=..., target=..., setup_ortho_camera=True)`。利用正交相机（`ORTHO`）视线向量消隐三维高度差，让在三维里相差数米的首尾台阶在画面中严丝合缝咬合成死循环（纪念碑谷 / 彭罗斯阶梯原理）。
- **手段 B（多向重力翻转房间）**：调用 `build_gravity_flip_room(...)`。在封闭腔体的地面（`0°`）、顶棚（`180°`）、左墙（`-90°`）、右墙（`+90°`）四个重力基准面上同时建立带护栏的阶梯与门廊，搭配不同方向射入的门洞光束（埃舍尔《相对性》原理）。

### 5. 多层垂直光井与层叠回廊 (Vertical Light-Shaft Atrium)
- **空间骨架**：调用 `build_vertical_atrium(levels=4)` + `create_volumetric_light_beam`（从左上高处向右下暗部斜射），`spatial_mode="interior"`。
- **结构特征**：前景近处是冷暗石阶与立式花灯柱，中远景是 3~5 层叠落的镂空回廊栏杆，隐没在顶部倾泻而下的明亮暖雾光束中，空气中散布微光粒子（`apply_gn_floating_motes` 或 `build_shattered_shard_vortex`）。

### 6. 碎裂几何与表现主义崩塌巨构 (Shattered Silhouette / Brutalist Deconstruction)
- **空间骨架**：调用 `build_canyon_corridor(..., height=48.0, catwalk_levels=3)` + `build_bmesh_fractured_slab(...)`（带锯齿断面与外露钢筋的真崩裂板梁）+ `build_shattered_shard_vortex(..., count=140)`（大中小三级立体多面体碎晶气旋）+ `setup_aerial_perspective_world(...)`（冷青风暴云穹）。
- **材质与光影**：克制的冷灰白/青灰基调，碎晶采用高反射折射材质捕捉光束，混入 10%~18% 高纯度珊瑚红/琥珀发光碎晶与 `build_hanging_cables` 断裂悬垂线缆形成视觉爆点。**严禁只把完好长方体歪转几个角度来冒充破碎！**

### 7. 半透窗景框景与清透二次元 (Translucent Framing / Atmospheric Anime)
- **空间骨架**：调用 `build_window_frame_stage(add_curtains=True)`，`spatial_mode="framed"`。机位退到室内 `Y ≈ -1.8m`，透过前景微风吹拂的青蓝色半透明薄纱（`BsdfTransparent` + `BsdfTranslucent` 混合），聚焦窗台上的通透渐变水杯与小花，窗外是干净的海平面色块。
- **色彩管理**：清透二次元与纯平切面风格在 `settings` 中设 `"view": "Standard"` 保持色彩明快纯净；写实与强光比体积光场景保持 `"view": "AgX"` 防止亮部死白。

### 8. 真实下的科幻与巨构天际线并置 (Sci-Fi Grounded in Reality / Megastructure Horizon)
- **空间骨架**：`spatial_mode="grounded"`。近景（`Y = 2m ~ 18m`）使用 `build_endless_ground` + CC0 岩石/树木/水面与野花散布构建**触手可及的高写实自然或市井环境**；远景（`Y = 140m ~ 260m`）调用 `build_megastructure_horizon(distance_y=155.0, base_height=88.0, style="brutalist_fortress" | "orbital_spire" | "hovering_ovoid_ship", add_greebles=True)` 矗立百米级阶梯装甲要塞或静默悬浮母舰。
- **大气与光影**：必须调用 `setup_aerial_perspective_world(mist_start=16.0, mist_depth=175.0)` 并搭配合成器 `"sterile_cold_brutalist"` 或 `"cinematic_warm"` 的 Mist 雾气通道，让远景巨构被天光散射雾自然洗淡对比度，近景树叶溪石保持锐利反差，从而产生震撼的百米级真实巨物崇高感。

### 9. 全息数据矩阵与工业圣殿 (Holographic Industrial Sanctum)
- **空间骨架**：暗色重工业柱列/地下反应堆水池 + `build_holographic_data_matrix(panel_count=28, add_sky_wireframe_dome=True)`。
- **材质与光影**：沉重的粗糙混凝土/拉丝暗钢实体与轻盈半透明的青色镂空全息电路 HUD 面板、天穹六边形星盘网格罩形成强烈虚实对冲。

### 10. 天穹倒悬双城与宏观重力奇观 (Inverted Sky Metropolis / Planetary Horizon)
- **空间骨架**：地面自然湖泊/海面或城市街区 + `build_inverted_sky_megacity(ceiling_z=52.0, block_count=72, add_bridge_spire=True)`（或 `add_inverted_pyramid=True`），搭配 `setup_aerial_perspective_world(add_planetary_arc=True)`。

---

## 三、写实质感双引擎原则（写实场景拒绝单调纯噪波）

在写实、粗野主义、阈限瓷砖/微水泥或带生活痕迹的场景中，**严禁偷懒只连一个数学噪波（Noise Texture）充当材质**，按三阶梯执行：

1. **第一梯队（真实扫描 CC0 PBR 贴图集）**：
   - 混凝土、砖石、木板、金属板、礁石、泥地等大面积结构，优先调用 `asset_loader.download_pbr_texture_set(...)` 或 `asset_loader.search_cc0_assets("textures", [...])` 下载包含颜色、粗糙度、法线的真实扫描贴图，通过 `setup_pbr_texture_material(..., use_box_mapping=True)` 免展 UV 均匀包裹。
2. **第二梯队（自带生图能力定制贴图）**：
   - 需要特殊图案、手绘做旧斑驳墙皮、特定瓷砖花纹、定制划痕粗糙度遮罩时，主动调用 `image-generator` 子智能体生成无缝贴图，传入 `setup_generated_texture_material(...)` 同时驱动凹凸与反光层次。
3. **第三梯队（程序化着色适用边界）**：
   - 纯程序化节点仅用于：透光折射玻璃、半透薄纱窗帘、全息镂空电路面板、赛璐珞双阶色块（建议叠底淡淡的木纹/石纹贴图破除塑料感）、低多边形切面色块、自发光光环，或断网保底。

---

## 四、语境适配尺度锚点矩阵、高阶 BMesh 参数化算子与三大造型禁令

### 1. 语境适配尺度锚点矩阵（破除“全场景无脑塞工厂铁栏杆/纸质书”的字面死锁）
为了赋予画面令人信服的尺度感，必须放入微小参照物，但**参照物必须严格契合场景本体语境**，严禁在抽象意识空间或原始森林里生硬塞入黑色工厂铁护栏或纸质书：

| 场景语境类别 | 推荐的尺度参照物（Scale Anchors）与调用方式 | 严禁混入的违和物件 |
| :--- | :--- | :--- |
| **建筑峡谷 / 工业巨构 / 垂直中庭** | 多层挑空步道与 `1.05m` 标准护栏（`build_canyon_corridor(..., catwalk_levels=3)` 或 `build_human_scale_railing`）、`0.18m` 踏步台阶、`2.1m` 门洞、`build_hanging_cables` 悬链电缆 | 违和的现代办公家具或无支撑浮空球 |
| **抽象意识 / 量子核心 / 神圣几何** | 精密阶梯截面散热鳍片环（`build_profiled_machined_ring(..., fin_count=64)`）、三维倒角六边形硅晶圆与 14 面体棱晶阵列（`build_hex_wafer_array`）、全息刻度面板（`build_holographic_data_matrix`） | **严禁放工业工厂铁护栏 (`build_human_scale_railing`) 或纸质书本 (`build_curved_open_book`)！** |
| **真实下的科幻（自然/水岸 × 远景巨构）** | 近景乱石溪流（`make_rock` / CC0 岩石）、草丛野花散布（`apply_gn_foliage_scatter`）、木栈道（`make_plank_floor`）、岸边系缆桩或路灯 | 悬浮在半空的无意义几何方块 |
| **书房 / 展厅 / 超现实人文梦境** | S 型拱曲书页与卷曲飞页（`build_curved_open_book`）、画框、器皿、旋转阶梯（`build_spiral_stair_ribbon`） | 粗重的水泥工业管道 |

### 2. 三大造型铁律（直接调用高阶 BMesh 模板，告别低幼积木）
- **铁律一（真破碎 vs 假破碎）**：表现崩裂台阶、折断横梁、废墟残骸或碎裂空间时，**严禁把完好无损的 `_vm_arch_box` 长方体歪转 $5^\circ\sim 15^\circ$ 冒充破碎**！必须调用 `build_bmesh_fractured_slab(...)` 生成带锯齿断面与外露钢筋的真断裂板体，并配合 `build_shattered_shard_vortex(..., count=120)` 生成大中小三级立体多面体碎晶场。
- **铁律二（精密机械环 vs 光秃甜甜圈）**：表现科幻星环、日冕光环、神圣几何环或核心陀螺仪时，优先调用 `build_profiled_machined_ring(...)` 生成带 12 点阶梯法兰、内凹发光槽与径向散热鳍片的精密结构，避免直接裸放单调的 `primitive_torus_add` 光秃甜甜圈。
- **铁律三（程序化体积云海 vs 拍扁球体煎饼云）**：表现云端、云海或天空浮岛时，**绝对禁止使用 `primitive_uv_sphere_add` 压扁堆叠成“煎饼/大便状”假云团**！必须调用 `build_procedural_cloud_deck(...)`（多层网格噪波置换次表面云海）或 `setup_aerial_perspective_world(...)`。

### 3. 风格化合成器后处理预设 (`POST_PROCESS_PRESETS` / `br.run_post_process`)
- **冷峻粗野/真实下的科幻 (`"sterile_cold_brutalist"`)**：冷灰蓝 Mist 景深空气透视 (`strength=0.32`) + 强 AO 接触阴影 (`0.38`) + Fog Glow 柔光 + 冷青暗部/微暖高光分离调色 + 边缘色散与微锐化。
- **温暖电影感 (`"cinematic_warm"`)**：暖金黄昏 Mist 薄雾 + 柔和 Bloom + 暖调 Lift/Gamma/Gain + 暗角压边。
- **阈限梦核 (`"liminal_dream"`)**：线性微黄雾气 + 低阈值大范围柔光 (`threshold=0.72, size=0.68`) + 镜头暗角与轻度边缘色散 (`dispersion=0.015`)。
- **超现实失重星芒 (`"surreal_ethereal_glow"`)**：深海幽蓝景深雾 + 双层 Glare（`Bloom` 柔光 + 6 芒 `Streaks` 星芒）+ 光学微色散。
- **高反差明暗对照 (`"high_contrast_chiaroscuro"`)**：强 AO 压暗 (`0.42`) + 高对比度 (`contrast=14`) + 深暗角 (`0.42`)。
- **清透二次元 (`"clean_anime"`)**：搭配 `"view": "Standard"`，轻柔 Bloom + 提亮高饱和度 + 极轻暗角。

---

## 五、视觉自审确定性代码修复配方表（Deterministic Remediation Recipes）与熔断机制

在看图自审阶段，如果发现画面存在以下问题，**不要盲目乱改坐标或反复新建输出目录**（单次生成任务最多允许 **3~4 轮微调**，严禁陷入超过 4 轮的无效重跑死循环），请直接按以下确定性代码配方精确修复：

| 自审发现的典型病灶 | 根因诊断 | 确定性一行/参数级修复配方（直接写入 `patch_code`） |
| :--- | :--- | :--- |
| **1. 宏大/峡谷场景画面上方 1/3 是一片死黑或单调纯色** | 未配置双路径天空着色器，或焦段过长拍不到天际线云层 | 调用 `setup_aerial_perspective_world(sky_zenith=(0.05,0.11,0.22), sky_horizon=(0.42,0.56,0.72), cloud_contrast=0.68)`，并将相机焦段设为 `cam.data.lens = 20.0` ~ `24.0` 低机位微仰拍。 |
| **2. 远景巨构/高塔看起来像 3 米高的塑料玩具，毫无宏大感** | 距离相机太近（`<30m`）、无空气透视雾、缺少二级/三级 Greeble 细节或近中景无尺度参照 | ① 将远景巨构替换为 `build_megastructure_horizon(distance_y=155.0, base_height=88.0, add_greebles=True)`；② 启用 `setup_aerial_perspective_world(mist_start=16, mist_depth=175)`；③ 在中近景补入语境匹配的尺度参照（步道护栏 `catwalk_levels=3` 或 `build_hex_wafer_array`）。 |
| **3. “破碎/崩塌”场景看起来像没摆正的完整积木方块** | 用 `_vm_arch_box` 完整长方体旋转角度冒充破碎 | 删除歪放的长方体，改调 `build_bmesh_fractured_slab(..., crack_irregularity=0.25, rebar_count=5)` 与 `build_shattered_shard_vortex(..., count=140)`，补入 `build_hanging_cables` 垂落断缆。 |
| **4. 构图中心重叠拥挤，前景或光环死死挡住远景主角** | 前中后景全都堆在 `X = 0` 中轴线上 | 执行**左右错位对角线呼应**：将中景主焦点移至 `X = -1.6m`，远景巨门/高塔移至 `X = +1.2m`；或调用 `build_hex_wafer_array(..., clear_radius=2.5)` 自动清空中央视线通廊。 |
| **5. 发光环/核心显得死白刺眼、像塑料灯管，淹没表面细节** | 自发光强度过高（`Emission Strength > 15`）或圆环无截面细节 | 将大体积主环的 `Emission Strength` 降至 `1.8 ~ 3.5`（改用高金属度 `Metallic=0.92, Roughness=0.18` 靠反射接光，仅内凹槽道保留 `Strength=6.0`），并改用 `build_profiled_machined_ring(..., fin_count=48)`。 |
| **6. 颜色调整、光晕或雾气浓淡不理想，但三维造型与构图已合格** | 属于后期调色/合成范畴，**切勿重跑耗时 3D 渲染** | 直接调用 `br.run_post_process(output_dir, post_process={...}, exposure=...)`，1 秒内基于 `raw_cache.exr` 完成无损重调色！ |
