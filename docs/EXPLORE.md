# 维度消融探索：137 维过完备集 × 7 种 ML 算法（SPEC-NEXT 依据 v2）

> `tools/explore_dims.py` + `tools/explore_ml.py`（spec-next 分支）· 2026-08-09

## 1. 过完备集（≥100 维要求，去重后 137）

| 来源 | 数量 | 规则 |
|------|------|------|
| 16 基础维线性项 | 16 | 原表 |
| 平方项 | 16 | x² |
| 两两乘积 | 120 | x_i·x_j（C(16,2)） |
| 气流独热 | 4 | airflow×voiced/cg 派生 |
| 方式独热 | 9 | duration/area/vel/lateral 规则派生 |
| place / glottal_state / aspiration | 3 | SPEC-NEXT 规则 |
| **原始** | **168** | 全部由显式规则派生，无手工定值 |
| **去重后** | **137** | 完全相同列仅保留一个 |

## 2. 7 种 ML 证据（全部在 Phatak 08 混淆数据上）

A. **L1 稀疏路径**（Shepard softmax 核 + ISTA 回溯；a 定标修复 w↔a 不可辨识性）
B. **稳定性选择**（50 次条件 bootstrap，λ=1e-4）
C. **随机森林置换重要性**（960 对 (i,j)×137 维回归）
D. **GBDT 置换重要性**
E. **互信息**（mutual_info_regression）
F. **mRMR**（MI 相关性 − Pearson 冗余）
G. **LassoCV**（线性配对模型，独立于核）

## 3. 共识结果

**知觉核心（≥2 票，Phatak 可识别）**：`duration²`(5) `duration`(4) `tip_pos×duration`(4)
`tip_height×duration`(4) `tip_height×voiced`(3) `tip_pos×sg`(3) **`place`(3)**
`lips_rounded`(2) `jet_focus`(2) 及 tip_pos/tip_height/lips_closed 交互项。

**IPA 必需（Phatak 零方差、ML 看不见、但全表分离必需）**：`tongue_root`、
`lateral_ratio`、`laryngeal_tension`、`airflow_direction`、`vel_open`、
`effective_oral_area`（set-cover 补维验证：缺它们 minNN→0、coll→107+）。

**派生交互项判定**：在 Phatak 上貌似有用（LOCO 21,169 < 21,564），但 IPA 空间
minNN→0.000、coll→825+，**过完备是净伤害**——证明最终设计必须用物理维度。

## 4. 收敛到 SPEC-NEXT 13 维（关键验证）

| 集合 | LOCO | minNN | coll<.35 | CV |
|------|------|-------|----------|-----|
| v8 发布权重 16 维（基线） | 22,355 | 0.215 | 11 | 0.74 |
| ML 共识 20 维（含交互项） | 21,937 | **0.000** | **107** | 0.77 |
| 物理池修复后 15 维 | 22,037 | 0.032 | 88 | 0.56 |
| **SPEC-NEXT 13 维**（debias 拟合） | **21,550** | 0.049 | 179 | 0.65 |
| SPEC-NEXT 12 维（去 tip_height） | 21,788 | 0.047 | 187 | 0.60 |

**结论**：

1. **13 维 = 16 维的知觉等价**（LOCO 21,550 vs 21,564，无退化）；ML 证据独立
   复现了 SPEC-NEXT 的设计：place 轴（3 票）替代 tip_pos+body_pos，glottal_state
   替代 cg/sg/tension（共线三轴仅一个可识别参数，B 组稳定 1.00）。
2. **14+ 维无必要**：把 Phatak 上"有用"的交互项加回只会摧毁 IPA 空间。
3. **到 12 维**：去掉 `tongue_tip_height` 是代价最小的砍法（LOCO +0.6%）；
   不可砍 `airflow_direction`/`lateral_ratio`/`tongue_root`（砍任意一个
   minNN→0 或 coll +40）。
4. **minNN/coll 对权重极敏感**（debias 拟合 vs 发布权重相差 16×）——最终
   权重必须走 fit_metric.py 完整流程（MN55 tier 先验 + 元音-辅音锚 + postprocess），
   不能以裸拟合的 minNN 断言分布合理。

## 5. 对 SPEC-NEXT 的最终修正

1. 13 维设计成立，实施时以 12 维为目标：`place, lips_closed, lips_rounded,
   tongue_root, vel_open, lateral_ratio, voiced, glottal_state, duration,
   jet_focus, effective_oral_area, airflow_direction`（tip_height 由 place 轴
   的 tip_shape 语义吸收，或按需保留为第 13 维）。
2. 保留"链中立化"要求（EXPLORE.md 结论 C）：部位步距的均匀性靠向量设计，
   不靠权重。
3. 探索脚本保留在 `tools/`，作为未来加维度时的回归检查（137 维 × 7 算法的
   消融流水线可复跑）。

## 6. 解释性：每维职责卡（白盒翻译）

黑盒排名背后的机制，用**贡献分解**（w_k·Δ²_k / d²）和 **132 表最小对分离
计数**（该维是哪些音素对的"最大分离贡献者"）翻译成语音学职责：

### 6.1 Phatak 关键对比的维度贡献分解（13 维物理集，debias 权重）

| 对比 | 贡献分解 | 解读 |
|------|---------|------|
| p–t（部位） | lips_closed 50% + tip_height 43% + place 7% | **部位族别名**：v8 表中唇/舌尖/部位轴同向冗余，拟合自由选择载体。说明 place 轴要与 lips_closed/tip_height 解耦（f/v 的 lips_closed 须归 0，SPEC-NEXT 已规定） |
| p–b, t–d（清浊） | voiced 56% + glottal_state 44% | 喉部族干净承载清浊 |
| θ–s（咝音） | jet_focus 94% | 咝音聚焦独立成维（METRIC.md 同结论） |
| s–ʃ（龈后） | lips_rounded 97% | 表中 /ʃ/ 靠圆唇区分——**编码痕迹**，实施时应收归 place 轴 |
| f–θ（唇齿/齿） | lips_closed 88% | 同上：v8 用唇闭合区分唇齿，实施后 place 轴接管 |
| m–n, b–d | lips_closed 50% + tip_height 43% + place 7% | 同 p–t 的部位族别名 |
| v–f, z–s | voiced 55% + glottal_state 42% | 清浊族 |

### 6.2 132 表分离职责（每维"最大贡献者"的最小对数量）

| 维度 | 分离对数 | 典型职责 | 音系标签 |
|------|---------|---------|---------|
| `voiced` | 1,767 | i–t̪, i–t, i–c | 清浊 |
| `lips_closed` | 1,354 | i–p, i–b, i–p̪ | 唇部位/闭合 |
| `airflow_direction` | 1,220 | i–ɓ, i–ɗ, i–ʄ | 气流机制（内爆/喌 vs 肺） |
| `lips_rounded` | 929 | i–y, i–ø | 圆展 |
| `duration` | 685 | i–d̪, i–d, i–ɟ | 方式/时长 |
| `vel_open` | 600 | i–n̪, i–n, i–ɲ | 鼻化 |
| `lateral_ratio` | 596 | i–ɬ, i–l, i–ɭ | 边音 |
| `glottal_state` | 419 | i–h, i–ɦ | 喉态（送气/气化/嘎裂/挤喉） |
| `jet_focus` | 378 | i–z, i–ʒ, i–ʑ | 咝音 |
| `effective_oral_area` | 324 | i–a, i–ɐ, i–ɑ | 元音高度/收窄度 |
| `place` | 153 | y–u, ʏ–ʊ, e–ɘ | **元音前后度**（辅音部位被 6.1 的别名吸走） |
| `tongue_tip_height` | 132 | i–ɻ, i–r, ɪ–ɹ | 舌尖姿态（卷舌/闪音） |
| `tongue_root` | 89 | i–ɪ, i–ɛ, i–ə | ATR/咽化 |

**读法**：13 维各自承载一个互不重叠的音系职责（清浊/唇部位/气流/圆展/时长/
鼻化/边音/喉态/咝音/高度/前后度/舌尖/ATR），无一冗余；`place` 轴在 132 表上
主要分离元音前后度，而辅音部位由 lips_closed/tip_height 携带——这是 v8 表的
编码别名，**实施 SPEC-NEXT 的"链中立化"（f/v 的 lips_closed=0、ʃ 的圆唇归位）
后，部位职责将回到 place 轴**，这正是 SPEC-NEXT §7 验证标准要检验的。

---

## 7. 锚点数据化：声学数据派生（2026-08-09 增补）

设计原则（用户裁定）：**13 维锚点值全部由数据产生，生理与声学冲突时优先声学**；
Phatak 混淆矩阵只用于权重；phoible 只校验组合存在性（真实分布平等支持，罕见 ≠ 更远）。

### 7.1 已获取的数据

| 数据 | 内容 | 状态 |
|------|------|------|
| phonTools (CRAN) 9 个 rda | PB52/H95/T07(英)、f73(瑞典)、p73(荷兰)、b95(西)、f99(希)、a96(希伯来)、y96(韩)：F1/F2/F3/dur 实测 | tools/data/*.rda |
| phoible (GitHub) | 2157 语言、5385 音素、35 音系特征 | tools/data/phoible.csv |
| cmudict | 发音词典 | 已下载 |

### 7.2 元音三维派生（tools/gen_vowel3d.py）

规则（全部数据驱动，零手拍）：
1. **位置锚点只对不圆唇元音**按语言内 F1/F2 极差归一化后跨语言平均；
2. **圆唇元音继承其 IPA 图上同格伙伴的位置**（i~y, e~ø, ɛ~œ, ɪ~ʏ, ɨ~ʉ, ʌ~ɔ, ɑ~ɒ, æ~ɶ —— 同一格只差圆唇）；
3. **圆唇维 = 同语言内 ΔF2(伙伴) 归一化**。

结果：圆唇对位置 8/8 完全一致；i/a 端点与 L&M 参考吻合（0.42/0.93 vs 0.4/1.0）；输出 tools/data/vowel_3d_anchors.json。

### 7.3 合理度评估发现的 DATA_GAP（等更多数据，不强行派生）

| # | 问题 | 根因 | 处理 |
|---|------|------|------|
| 1 | æ 高度反序（比 ɛ 高） | 英语 /æ/=[æ̝] 特异性 | 标 GAP；需含 æ 的非英语语言数据 |
| 2 | o~ɔ 距离 1.03 过大 | o 为 8 语言、ɔ 仅 3 语言（英/荷），混合归一化分离 | 标 GAP；需更多含 o/ɔ 对比的语言 |
| 3 | 后链排序乱（u>o>ɔ 骤降） | ʌ-ɔ 伙伴关系错（英语 ʌ≈[ɐ] 央化） | 标 GAP；伙伴表需按 IPA 手册核对 |
| 4 | ʉ/ɵ/ɞ 圆唇 = 0 | 伙伴 ɨ/ɘ/ɜ 与圆唇元音同语言共现过少（仅韩语 1 次） | 标 GAP；需土耳其语/德语等数据 |

### 7.4 元音锚点质量验证（合理度）

- 高度链 i>ɪ>e>ɛ>æ>a：部分失败（æ 见 GAP#1）；i/a 端点正确
- 圆唇对位置一致性：8/8 PASS
- 松紧对 i~ɪ 0.33, e~ɛ 0.24：合理；o~ɔ 1.03 过大（GAP#2）
- 前后度：i 0.557 < 央 0.500?（i=0.557>0.5 稍偏后，源于跨语言混合）— 记录

### 7.5 遗留：辅音锚点数据化

擦音谱峰（Jongman 2000）、VOT（Kagaya 1974）、时长（Crystal & House 1988）目前为
已发表文献值（SPEC.md §9 引用），尚未找到可下载的原始测量数据；网络对
F1/F2 之外的声学数据集不可达。待数据可得后以同法派生。
