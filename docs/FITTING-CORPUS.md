# 拟合语料清单：轴覆盖优先于样本量

> 调研日期：2026-08-09。承接 `docs/REFERENCE-COMPARISON.md`（外部对标）与
> 「声学层 / 生理层」两层讨论。**本文不含实现改动**，只做语料可得性判定。

## 1. 诊断：问题不是样本少，是轴覆盖不对

`tools/fit_metric16.py:37-40` 已经把病历写在注释里：

```python
# no signal in the 16-consonant set (constant across the 16):
# body, tongue_root, glottal_tension, larynx_height, airflow
FIXED = [1, 5, 10, 11, 15]
```

Phatak 08 的 16 个英语辅音 `p t k f θ s ʃ b d g v ð z ʒ m n`，对 16 维只激活
11 维，且 `body`/`tongue_root`/`glottal_tension`/`larynx_height`/`airflow_direction`
**在语料上恒定**——权重不是拟合出来的，是手拍的。

关键推论：**补语料要按「轴」补，不是按「样本量」补。** 再来 100 个英语元音
仍然不会给 `larynx_height` 一丁点信息；而来 100 个阿拉伯语音段会同时点亮
`tongue_root`、`body`、`place`、`vel_open` 四根。

## 2. 三类语料，三种拟合目标

| 类型 | 拟合什么 | 能否替代 Phatak | 本仓现状 |
|------|---------|----------------|---------|
| **A. 人类识别/混淆矩阵** | 知觉距离（Shepard 式拟合 $M$） | 已在用，只覆盖 11 维 | `phatak08_cm.json`（16×16 × 5 个 SNR） |
| **B. 声学测量**（F1/F2/F3/HNR/倾斜/VOT/谱峰） | 声学层 $A$，以及那 5 根死轴 | **不能替代，且是死轴唯一出路** | 仅 9 语料元音 F1/F2/F3/dur |
| **C. 音系库存 / IPA 语料**（无听觉标签） | 覆盖率审计、组合合法性、BDPA 外部标尺 | 不能替代 | `phoible.csv`（2157 语言 / 5385 音素） |

## 3. 为什么「找更大的人类混淆矩阵」这条路走不通

所有经典人类识别矩阵都是 6–40 项的小规模——这是实验室设计决定的，不是数据
缺失：Clopper/Grieve/Purser (1933) 是 6 项；Miller & Nicely (1955) 与 Phatak
(2008) 是 16 项；Shepard/Romelford/Megela (1971) 是单音节听辨。要拿到同时
覆盖「阿拉伯咽化元音 + 韩语紧音 + 挤喉/内爆」的矩阵，得跨 4 个语系各做一次
被试实验——**不可行**。

**结论：不要找更大的混淆矩阵，要自己生成等效语料。**

## 4. 可获取语料清单

### 4.1 已在手（零获取成本）

| 资源 | 规模 | 用途 | 循环论证风险 |
|------|------|------|-------------|
| `tools/data/*.rda`（9 语料） | PB52/H95/T07 英、f73 瑞典、p73 荷兰、b95 西、f99 希、a96 希伯来、y96 韩 | F1/F2/F3/dur 实测 | 无（真实测量） |
| `tools/data/phoible.csv` | 2157 语言 / 5385 音素 | 覆盖率、组合存在性校验 | **不可用于拟合权重**（见 §5） |
| `tools/data/phatak08_cm.json` | 16×16 × 5 SNR | Shepard 拟合的唯一知觉源 | 无 |
| `cmudict` | 已下载 | 音段存在性 | 无 |

### 4.2 可下载（已核实公开可取）

| 资源 | 规模 | 点亮的轴 | 获取 |
|------|------|---------|------|
| **NorthEuraLex IPA tokens** | 121,614 转写 / 107 语言 / 1.8 MB，已 tokenize | 全 IPA 空间覆盖审计 | `ipavec/data/northeuralex/ipa`（[链接](https://github.com/pavelsof/ipavec/tree/master/data/northeuralex)） |
| **SVMCC 多语语音学词典** | 9 张表：IELEX(683K)、central_asian(1.09M)、ABVD(638K)、chinese_1964/2004(263K/197K)、ob_ugrian(107K)、bai(58K)、japanese(89K)、tujia(34K)；带 `tokens` 音段列 + `cognate_class` | 跨语系音段覆盖审计、同源对 | `ipavec/data/svmcc/*.tsv`（[链接](https://github.com/pavelsof/ipavec/tree/master/data/svmcc)，CC BY-SA 4.0） |
| **BDPA** | 7198 对已对齐 IPA 序列 | **外部标尺**：跑对齐得分与 PHOIBLE 66.64% 对比 | `ipavec/data/bdpa/*.psa`（[链接](https://github.com/pavelsof/ipavec/tree/master/data/bdpa)） |
| **MFA models** | 100+ 语言的声学模型 + 发音词典（仓库已核实存在） | **声学层主力**：真实测量的逐音段声学参数 | [MontrealCorpusTools/mfa-models](https://github.com/MontrealCorpusTools/mfa-models) |
| **Epitran** | 130+ 语言-文字 正字法→IPA | 需要时把正字法语料扩成 IPA 语料 | [dmort27/epitran](https://github.com/dmort27/epitran)（pip 可装） |

**MFA 这一条是本次调研最重要的发现**：MFA 的发音词典来自**真实语言的音系
库存**，因此 `ħ ʕ ɡ͡ʔ k͈ ʔ ɓ t͡ɬ` 这类音段**天然在库存里**——那 5 根死轴
对应的音段不缺，缺的是它们的声学测量。

### 4.3 存在但本次未取到（留作后续）

| 资源 | 卡在哪 |
|------|-------|
| Wang & Hu 系 JASA 2014 混淆矩阵附表 | `web.cse.ohio-state.edu` 重定向到 `cse.osu.edu` 后 404；PDF 通道不可用 |
| Kawahara 声素距离 / probing 体系 | `rci.rutgers.edu` 返回 502 |
| EaPPA（巴勒斯坦阿拉伯语重音与咽音数据集） | Dataverse CloudFront 403 |
| 历史小规模矩阵（Clopper 1933 等） | 需手工转录，收益低 |

## 5. 循环论证红线（必须点名）

不是所有「更大的矩阵」都能用来拟合以**发音特征距离**为形式的 $M$：

| 来源 | 独立性 | 能不能拟合我们的 $M$ |
|------|--------|-------------------|
| MFA/Kaldi 后验（真实语音测量） | 独立 | **能** |
| JOSS n-gram 音系概率（Greenwood-Ng/Morgan/Zheng 2015 一路） | 独立于特征表，来自大规模音节共现语料 | **能**（但它测的是音系邻接性，不是声学相似性，只能作弱先验） |
| Phatak 08（真实被试 + 白噪声） | 独立 | 能（已在用） |
| **PHOIBLE / PanPhon 特征距离派生的混淆矩阵**（Soda & Pizza、unimath 等） | **不独立——由特征表算出** | **绝对不能**。拿它拟合以特征距离为形式的 $M$ 等于自证 |

这一条决定了 §4 的选型：只取「测量」和「大规模音系共现」两条路，
PHOIBLE/PanPhon 只留在覆盖率校验位（这与 `docs/EXPLORE.md` §7 的用户裁定一致：
phoible 只校验组合存在性）。

## 6. 推荐路径

| 优先级 | 动作 | 解锁 | 成本 |
|-------|------|------|------|
| **P0** | 覆盖率审计：拿 NorthEuraLex + SVMCC 的 `tokens` 列 ∩ 本仓 132 音素，逐根轴报「该轴在语料里有多少真实对立对」 | 把 §1 的 5 根死轴从「猜」变成「量化缺口」；顺带发现 SPEC-NEXT 是否有音素在真实语料中不存在 | 一个脚本，语料公开可下 |
| **P1** | 辅音声学锚点数据化（补 `EXPLORE.md` §7.5 的 GAP #1-4） | `place`/`tip_shape`/`jet_focus` 脱离文献手拍值 | 需找可下载的辅音测量数据 |
| **P2** | MFA 批量测 IPA 段声学参数 → 得声学层 $A$ | 5 根死轴获得**非手调**权重；`place` 的 0.15 等距步距从「约定」变成「可算」 | 中等（需装 MFA + 对齐语料） |
| **P3** | 用对齐后验生成大规模 confusion，扩充 Shepard 拟合 | 16×16 → 10⁴~10⁵ 量级的知觉距离估计 | 高，且依赖 P2 |
| **P4** | 人类矩阵只作外部 spot check（选 1-2 个小实验） | 校验 P2/P3 的生成语料没有跑偏 | 低 |

## 7. P0 结果（`tools/audit_axis_coverage.py`，2026-08-09）

语料：NorthEuraLex IPA tokens + SVMCC 九表，共 **1484 个不同 token**，
命中本仓 **112/133** 行；21 行语料中从未出现（多为 click、内爆、送气擦音、
双约束塞音：`ǀ ǁ ǂ ǃ ɠ ɡ͡b ʄ ʢ ʙ ʛ ʟ ⱱ k͡p k͡x ŋ͡m fʼ sʼ xʼ θʼ p̪ ɰ`）。

### 7.1 Phatak-16 的方差是三层的，不是两层的

| 层 | 轴 | 方差 | 承载音素数 |
|---|---|------|-----------|
| A 良定（7） | `voiced` 0.246、`lips_closed` 0.148、`duration` 0.148、`jet_focus` 0.144、`place` 0.124、`vel_open` 0.109、`tip_shape` 0.078 | 0.078–0.246 | 7–11 |
| B 名义有、实质无（3） | `glottal_aperture` 0.039 勉强算 A 尾；`lips_rounded` 0.0068、`body` 0.0044、`effective_oral_area` 0.0024 | 0.002–0.039 | 2–8 |
| C **精确为零**（5） | `tongue_root`、`glottal_tension`、`larynx_height`、`lateral_ratio`、`airflow_direction` | **0.00000** | **0** |

B 层的具体承载者要说清楚，否则会被误当成信号：
`lips_rounded` 的全部信号来自 **/ʃ/ /ʒ/ 两个音素的 0.25**（var 占比 2.8%）；
`body` 的全部信号来自 **/k/ /ɡ/**（软腭次收缩 −0.20，var 占比 1.8%）；
`effective_oral_area` 有 8 个音素偏离众数但偏离量只有 ~0.07。

**结论 A：`fit_metric16.py` 注释里的 "no signal" 说的是 C 层，但 `body` 其实不在 C 层**
（k/ɡ 带 −0.20），而 **`lateral_ratio` 才是精确零、却被当作自由参数拟合**。

### 7.2 缺陷 1：`lateral_ratio` 是一个未被识别的自由参数

`FIXED = [1, 5, 10, 11, 15]` 钉住了 `body`(1)、`tongue_root`(5)、
`glottal_tension`(10)、`larynx_height`(11)、`airflow_direction`(15)。
`lateral_ratio`(7) 不在其中，是自由参数——但在 Phatak-16 上
`n_distinct = 1`、方差 `0.00000`。

拟合的似然在 `lateral_ratio` 方向上是**平的**，`metric16.json` / `spec_next.scheme`
里的值实际来自初值 `x0` 或 `RHO=0.1` 的先验收缩，不是数据给的。
这是一个「未识别参数被当作已识别」类缺陷，与 `METRIC.md` 自己承认的
duration 权重「从来只由手调支撑」同类，但更隐蔽：**duration 至少在语料上有方差，
`lateral_ratio` 连方差都没有。**

### 7.3 缺陷 2：`glottal_aperture` 完全决定 `voiced`（离散化造成的假性可辨识）

在 133 行上，`glottal_aperture` 的 6 个取值恰好把 `voiced` 二分：

```
ap = -1.00 -0.55  0.00  0.40  0.55  1.00
voiced =  0.0    1.0   1.0   0.0   1.0   0.0
```

`voiced=0` → ap ∈ {−1.0, 0.4, 1.0}；`voiced=1` → ap ∈ {−0.55, 0.0, 0.55}。
即：**知道声门开合就完全知道清浊**。这不是语音学事实，是 6 个离散取值恰好不重叠
的巧合。

而且它一进修饰符层就破：`verify_modifiers.py` 的 `breathy_asp` 规则同时设
`glottal_aperture=0.7` 与 `voiced=1.0`——正是那个被排除的组合。也就是说
**两轴在基础行上「可分」只是假象，一旦把修饰符算进来，两根权重就开始互相串**。

### 7.4 结论 B：语料不是瓶颈，C 层里只有两根轴是真瓶颈

把同一口径跑到 112 个语料音素上：

| 轴 | Phatak-16 偏离众数 | 语料 112 行偏离众数 | 语料最小对立对 |
|---|---|---|---|
| `body` | 2 | **49** | 14 |
| `tongue_root` | 0 | **26** | 0 |
| `lips_rounded` | 2 | **25** | 10 |
| `jet_focus` | 4 | 20 | 0 |
| `tip_shape` | 9 | 42 | 0 |
| `glottal_tension` | 0 | **7** | 0 |
| `larynx_height` | 0 | **7** | 0 |
| `airflow_direction` | 0 | 3 | 0 |

**`body` 和 `tongue_root` 的缺口是语料选错了，不是语料不够**——语料里分别有 49
个和 26 个音素携带这两个轴的信号。换一套包含元音与咽音的语料，这两根轴立刻可拟合。

**真正无解的只有 `larynx_height` 和 `glottal_tension`**，因为整个 IPA 空间里
携带它们的只有 7 个音素：

```
larynx_height    : kʼ pʼ qʼ tʼ t͡ʃʼ ɓ ɗ        （5 挤喉 + 2 内爆）
glottal_tension  : kʼ pʼ qʼ tʼ t͡ʃʼ ɦ ʔ
```

两者的音素集合几乎不重叠（只有 5 个挤喉共有），所以它们**可以**被分开；
但样本上限就是 7 个音素，再多的语料也不会变。这两根轴的权重只能来自
**声学层的物理论证**（F ∝ 1/L、频谱倾斜），不能来自任何统计数据。

### 7.5 最小对立对为什么全接近 0

16 维里只有 6 根（`place` 5、`body` 14、`lips_rounded` 10、`lateral_ratio` 1、
`duration` 3、`effective_oral_area` 4）有非零最小对立对，其余 10 根为 0。
这不是缺陷，是**稠密物理描述的必然**：p/b 同时动 `voiced`、`glottal_aperture`、
`duration`，任何一对都不会只差一轴。所以「最小对立对」在本仓应当降级为参考列，
主口径用方差。

### 7.6 P0 之后该做什么（按新信息重排）

| # | 动作 | 依据 |
|---|------|------|
| 1 | **`lateral_ratio` 移入 `FIXED`**，或给它独立证据 | §7.2：该权重目前无数据支撑 |
| 2 | 修 `body` 的注释（它在 Phatak-16 上有 k/ɡ 的信号） | §7.1 |
| 3 | 决定 `glottal_aperture`/`voiced` 的编码：拆开还是接受共线 | §7.3 |
| 4 | 用语料（含元音+咽音）重跑 `body`/`tongue_root` 的权重 | §7.4：缺口已定位，语料已具备 |
| 5 | `larynx_height`/`glottal_tension` 走声学层物理论证，不再找语料 | §7.4：样本上限 7 个音素 |

## 8. 一句话结论

**不要去找更大的混淆矩阵——去找能测到那 5 根轴的真实语音。** Phatak 的 16 个
英语辅音在设计上就不可能包含喉位、紧喉、咽化、ATR 的信息；任何声称覆盖这些
的「矩阵」若不是从真实语音测出来的，就是从特征表算出来的，不能用。

P0 是唯一一个今天就能做、且做完后能把「语料不够」从模糊抱怨变成具体数字的
动作。建议先做 P0。
