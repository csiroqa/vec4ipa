# 外部对标：PanPhon / PHOIBLE / Epitran / IPAVec

> 调研日期：2026-08-09。本文档只做调研与对照，**不改实现、不改权重**。
> 用途：把 SPEC-NEXT 16 维放到外部公认标尺上，指出哪些设计有文献背书、
> 哪些是空白、哪些是本仓独有的未验证假设。

## 0. 关于「phonetic-box」

GitHub 上不存在 `phonetic-box` / `PhoneticBox` / `phobox` 等同名仓库（仓库名、
描述、正文三种检索均无命中）。本仓自述的题目是「IPA → 数值向量 → 可逆重建 →
加权距离 → 最近邻」，因此按下述四类实际可比项目对标：

| 项目 | 定位 | 与本仓关系 |
|------|------|-----------|
| [PanPhon](https://github.com/dmort27/PanPhon) | IPA 段 → 发音学特征向量（COLING 2016） | **最接近**：同一张表的竞争实现 |
| [Epitran](https://github.com/dmort27/epitran) | 多语言正字法→IPA，附 PanPhon 向量（LREC 2018） | 同一张表的**消费方** + 覆盖率证据 |
| [IPAVec](https://github.com/pavelsof/ipavec) | 用向量表示做 IPA 序列对齐（Sofroniev & Çöltekin 2018 学位论文） | **同一空间的外部评测标尺** |
| [PHOIBLE](https://phoible.org/) | 1672 语言 / 2160 IPA 段的特征表（Bruce & Moisik 体系） | IPAVec 里的「手工特征」对照组 |

若「phonetic-box」实际指别的东西（形态学 IPA 图表 UI？），本节结论需重做。

---

## 1. 外部项目的事实清单

### 1.1 PanPhon：22 个三值特征

特征集 `spe+` 定义在 `panphon/data/ipa_all.csv`，值域 `{+, 0, -}` 映射到
`{+1, 0, -1}`。特征名（PanPhon README 原文列出，共 22）：

```
syl son cons cont delrel lat nas strid voi sg cg ant cor distr
lab hi lo back round velaric tense long
```

- **表由规则生成**：`ipa_bases.csv`（无修饰符的基本段）+ `diacritic_definitions.yml`
  → `ipa_all.csv`。修饰符的适用范围由 `conditions`（特征谓词）决定。
- **距离**：`Distance.feature_edit_distance` 每特征编辑代价 `1/22`；
  `hamming_feature_edit_distance` 把 unspecified→specified 也算 `1/22`；
  另有 `weighted_feature_edit_distance` 按特征类加权。
- 排序键里还有 `hitone`/`hireg`，说明高频变体另有处理（未取到确切语义）。

### 1.2 Epitran：PanPhon 特征 + 多语言 G2P

- `epitran.vector.VectorsWithIPASpace.word_to_segs()` 返回
  `(category, case, orth, phon, id, feature_vector)`；README 明确
  「向量长度由 panphon 定义的特征数决定」。
- README 示例中向量长度为 **21**（与 PanPhon 文档的 22 差 1，具体缺哪一维
  **未取到**，不猜测）。
- 特征值 `{−1, 0, +1}`；查不到的字符整向量填 0。
- 支持 130+ 语言-文字对（梵文、天城文、西里尔、谚文、阿拉伯、泰文……），
  声调 ˩˨˧˦˥ 走独立开关。

### 1.3 IPAVec：把向量当对齐打分函数

- 打分函数固定为**余弦距离** `1 − cos(u,v)`，接标准 Needleman–Wunsch。
- 评测语料 BDPA：7198 对已对齐 IPA 序列、12 个来源集、6 个语系。
- 全局（global）分数：

| one-hot | PHOIBLE(39) | phon2vec | NN | NN+RNN | SCA |
|--------:|-------------:|---------:|---:|-------:|----:|
| 51.83% | 66.64% | 66.99% | 75.88% | 78.45% | 84.84% |

- **PHOIBLE-PC**（39 维 PCA 降到 29 维）**一致变差**：Bai 62.77→0.23、
  Sinitic 28.57→0.00、Germanic 51.78→45.89。

---

## 2. 正交对照：PanPhon/PHOIBLE 特征 ↔ SPEC-NEXT 16 维

| SPEC-NEXT 轴 | PanPhon/PHOIBLE 对应物 | 编码差异 |
|--------------|------------------------|---------|
| `place` | `ant` `cor` `distr` `lab` `dorsal` `hi` `lo` `back` | **本仓单一连续等距轴**（13 锚点 × 0.15）；外部是 6~8 个部位二值/三值的**聚合** |
| `body`（含元音前后度） | `hi` `lo` `back` `round` | 外部拆成高低/前后/圆唇四轴；本仓压成一轴 |
| `tip_shape` | `cor` `ant` `distr` + `hi` | 外部无语义等价单轴 |
| `lips_closed` | `lab` + `cons`（近似） | 本仓有独立 0/1 轴 |
| `lips_rounded` | `round` | 语义同，编码不同（三值 vs −1..+1 连续） |
| `tongue_root` | PHOIBLE `retracted/advanced tongue root` | 本仓 −1..+1 单轴 vs 外部两轴 |
| `vel_open` | `nas` | 本仓 0..1 连续（含 0.6 鼻化中间态），外部三值 |
| `lateral_ratio` | `lat` | 同 |
| `voiced` | `voi` | 同 |
| `glottal_aperture` | `sg` + `cg`（两轴） | 本仓单连续轴 |
| `glottal_tension` | `tense` | 同（外部另有 PHOIBLE 的声门类特征） |
| `larynx_height` | PHOIBLE `raised/lowered larynx` | 本仓唯一动机 |
| `duration` | `long`（仅长短二分） | **本仓连续 0..2，且按 place/voicing 渐变** |
| `jet_focus` | `strid` + PHOIBLE `fortis` | 本仓连续 0..1.0（s/ɕ/ʃ/ʂ 有序 0.95/0.90/0.85/0.80） |
| `effective_oral_area` | `syl`/`hi`/`lo` 的间接结果 | 本仓显式轴 |
| `airflow_direction` | `velaric`（仅 click） | 本仓 +1/0/−1 覆盖外呼/内吸 |
| **（无）** | `delrel` `syllabic` | 本仓不做音节标记（属超音段/元音机制） |
| **（无）** | PHOIBLE `periodic glottal source` `epilaryngeal` `labiodental` `stress` `tone` `delayed release` | 本仓走 metadata / 修饰符叠加 |

---

## 3. 文献直接支持本仓的五点

1. **手工特征化距离打不过统计学习**。PHOIBLE 39 维手工特征 66.64%，
   学出来的 64 维嵌入 78.45%，差 11.8 个百分点。作者归因于「PHOIBLE 向量
   的二值性与特征数偏少」。→ 若本仓目标是**演化推断 / 序列对齐**，
   16 维手工轴不是最优解；若目标是**可解释最近邻 UI / 可逆重建**，本仓路线
   仍然正确（SCA 那类声类法也不可逆）。
2. **无监督去相关（PCA）有害**。39→29 维 PCA 全面下降，作者明说假设被证伪。
   注意：PCA 破坏特征语义，**不能**推广成「降维无效」；只能推广成「靠统计
   去相关来平衡特征代价没有用」。本仓 `docs/EXPLORE.md` 里 137 维过完备集
   LOCO 更好但 minNN→0，是同一现象的另一面。
3. **罕见特征被等权对待是真问题**。作者原话：PHOIBLE「cosine 距离同等受
   常见维度与罕见维度影响，例如一对向量中『advanced tongue root』的存在就
   可能造成超出对齐需要的距离」。这正是本仓「等距 place 链 + 逐轴拟合权重」
   想解决的问题——**批评成立，本仓的解法在文献里没有对应的验证实验**。
4. **覆盖率是硬约束**。作者明说 PHOIBLE 未覆盖 BDPA 全部 IPA 段；NorthEuraLex
   只有普通话一个带调语言，NN 在 Sinitic 上只有 72.46%（SCA 98.95%）。
   → 任何「本仓 132 音素 vs PanPhon 表」的对比都必须先报覆盖率。
5. **修饰符组合爆炸只能靠规则枚举**。PanPhon 用 yml 规则批量生成修饰符段，
   本质是有限枚举。本仓要求修饰符在锚点值上**叠加偏移且可组合**
   （SPEC-NEXT §3：±0.15 内叠加、不覆盖）。这是结构性差异，不是覆盖度问题。

---

## 4. 本仓三处无文献背书的设计（按风险排序）

1. **place 单轴等距（最高风险、最高回报）**。文献里没有第二个人把部位做成
   一根连续等距轴。含义：这是可证伪的假设，但也意味着**目前没有任何外部
   证据支持或反对它**。它同时也是本仓「双脣→喉全链擦音平等支持」这个核心
   需求的唯一实现手段。
2. **连续分级编码**。全部外部手工特征表都是 `{−1,0,+1}` 三值；分级轴
   （lips_rounded −1..+1、duration 0..2、jet_focus 有序）**在任何 IPAVec
   对齐实验里都没有被测过**。本仓 METRIC.md 的权重拟合流程假设的正是分级
   语义，但拟合目标（Phatak 08 混淆数据）与对齐任务不是一回事。
3. **larynx_height**（SPEC-NEXT v0.3 新增）。PHOIBLE 有 `raised/lowered larynx`
   但 IPavec 未把它单列成轴做消融。本仓给它 3 号权重、F4 物理论证完整，但
   **无任何外部对照**。

---

## 5. 建议的下一步（按性价比排序，均不改实现）

### A. 把本仓放进 BDPA 标尺（最高价值）

IPAVec 的 `data/bdpa/*.psa` 是公开的对齐语料（7198 对，含 `global.psa`）。
本仓已有向量与加权距离，只缺一个约 30 行的 Python driver：读 `.psa` 对 →
取本仓 `vec4ipa` 向量 → 算 D(x,y) → Needleman–Wunsch → 按 Sofroniev 的
`n/m` 评分。判据：本仓 16 维的 global 分数 **≥ PHOIBLE 66.64%** 才算在
手工特征路线上站住；低于 one-hot 51.83% 说明向量设计在跨语言任务上失效。

数据：<https://github.com/pavelsof/ipavec/tree/master/data/bdpa>

### B. 单变量消融：place 连续等距 vs 部位类别独热

把 `place` 轴拆成 PanPhon 式 `lab/ant/cor/distr/dorsal/back` 六位独热，其余
15 维不动，重跑 A。若独热胜出，说明本仓核心设计在演化任务上是负资产；若
等距胜出，则这是文献里没有的、可写进论文的结论。EXPLORE.md 的 137 维流水线
可直接改造成这个消融。

### C. 覆盖率互查

对 `panphon/data/ipa_all.csv` 与本仓 `tools/data/spec_next.scheme` 的交集，
逐音素核对三点：(1) 本仓 16 维是否把 PanPhon 表里不同名的段错误合并；
(2) 本仓修饰符（ʰ ˤ ʲ ː ˞ 协同调音）PanPhon 是否覆盖；
(3) 本仓 `place` 等距假设在 PanPhon 视为同段的音素对上是否成立
（如 ɸ/f 与 ʃ/ɕ 的相对距离）。现有工具：`tools/test_metric_space.py`
的 132 表最小对分离计数。

---

## 6. 引用

- Mortensen, Littell, Bharadwaj, Goyal, Dyer, Levin (2016). *PanPhon: A Resource
  for Mapping IPA Segments to Articulatory Feature Vectors.* COLING 2016.
  <https://github.com/dmort27/PanPhon>
- Mortensen, Dalmia, Littell (2018). *Epitran: Precision G2P for Many Languages.*
  LREC 2018. <https://github.com/dmort27/epitran>
- Sofroniev, Çöltekin (2018). *IPA alignment using vector representations.*
  Bachelor thesis, Tübingen. <https://github.com/pavelsof/ipavec>
- Moran & McCloy (eds.). *PHOIBLE — The Phonological Inventory Database.*
  <https://phoible.org/>
- List, Prokić et al. (2014). *BDPA — Benchmark Database for Phonetic Alignments.*
  <http://alignments.lingpy.org/>
- Kondrak (2000–2003). ALINE：多值 + 二值发音特征加权打分。
- Jäger (2013). PMI 声似度打分。
