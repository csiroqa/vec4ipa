# tools/ — 生成、拟合、审计与研究脚本

本目录承载该仓库除 C 核心外的全部 Python 工具：从原始声学数据生成
`spec_next.scheme`、拟合度量权重、审计锚点空间、跑测试套件、做维度探索。
**所有脚本都是设计/研究工具，不参与运行时**——C 二进制（`ipa2vec` /
`vec2ipa` / `vec4ipa`）只编译 `src/vectors.h` 与 `src/ipa2vec_core.h`，
编译产物不依赖本目录的任何 Python 文件。

从仓库根运行一切脚本（`python tools/<name>.py`），下面解释为什么必须这样。

## 权威与派生

本仓库围绕**一个运行时权威**组织，所有数据文件都能沿一条可复现的链
溯源到它：

```
tools/data/spec_next.scheme  ← 唯一运行时权威（手调定稿）
        │
        ├─> src/vectors.h          (gen_vectors_h.py 生成，C 二进制编译它)
        │
        └─> tools/data/vec_table_16.json  (gen_vec_table.py 生成的
                                           JSON 视图，与 scheme 逐值一致；
                                           test_spec_next.py 校验两者的同步)
```

| 角色 | 文件 | 说明 |
|------|------|------|
| **权威** | `data/spec_next.scheme` | 133 段 × 16 维 + 运行时权重（`weight`/`lambda` 行），`Makefile` 默认 `SCHEME`，`gen_vectors_h.py` 由此生成 `src/vectors.h` |
| 派生 | `data/vec_table_16.json` | scheme 的 JSON 视图；`gen_vec_table.py` 写出，`test_spec_next.py` 校验与 scheme 逐值一致 |
| 派生 | `data/metric16.json` | 拟合设计权重（tip_shape 5 / duration 25）；**不同于** scheme 的运行时权重（tip_shape 4 / duration 5），见 `METRIC.md` |
| 原始 | `data/phoible.csv`、`data/phatak08_cm.json`、`data/*.rda`/`*.Rd` | 语言音素库、Phatak 08 混淆矩阵、已发表声学测量——拟合与锚点推导的底层数据 |
| 研究产物 | `data/anchors.json`、`data/vowel_3d_anchors.json`、`data/vowel_acoustic_anchors.json`、`data/vowel_bark_anchors.json`、`data/vowel_opt.json`、`data/distribution_fit.json`、`data/audit_input.json` | 锚点推导链的中间/输出产物，记录研究过程，不进入运行时 |

> **两个权重权威（有意）**：`metric16.json` 是拟合设计权重（由
> `fit_masked.py`/`fit_metric16.py` 输出、`test_spec_next.py` 校验），
> `spec_next.scheme` 的 `weight` 行是手调运行时权重（由 `test_suite.py`/
> `test_metric_space.py` 校验）。`export_scheme.py` 从 JSON 导出 scheme 时
> **保留**已存在的 weight 行，避免用拟合值覆盖手调值（见该脚本头注）。

## 为什么是单目录（不拆 gen/research/tests）

仓库刻意把所有脚本放在一个 `tools/` 目录，原因是一个**Python 导入机制**：
脚本被 `python tools/<name>.py` 运行时，其所在目录（`tools/`）会被 Python
自动加入 `sys.path[0]`，于是脚本之间用**同目录导入**共享代码：

```python
import _common                      # 测试/生成/拟合脚本共享的助手
from place_anchors import PLACE     # 部位锚点表
import gen_vec_table as gvt         # test_spec_next 复用它做可重现性检查
import explore_dims                 # explore_ml 复用它做消融
```

若把脚本拆进 `tools/tests/`、`tools/gen/` 等子目录，这些 `import` 会全部
失效（`sys.path[0]` 变成子目录，不再含 `_common`/`place_anchors`），
必须给每个脚本手动加 `sys.path.insert(0, ROOT/"tools")` 并同步全部
Makefile 引用——改动量大而运行时收益为零。**单目录是刻意的简单设计**；
要整理的收益点（职责分区）由下面的分类表补足。

## 共享模块与依赖图

| 模块 | 职责 | 被谁依赖 |
|------|------|---------|
| `_common.py` | 测试助手：`run(exe,args)` 子进程封装、`check()` 断言、`fmt_vec`、v8 行解析、`BIN_SUFFIX` | fit_metric, fuzz_metric_space, gen_vectors_h, test_alignment, test_metric_space, test_standard_chinese, test_suite, validate_alignment |
| `place_anchors.py` | SPEC-NEXT 部位锚点表（`PLACE` 字典，span `[-0.9,+0.9]`）+ `remap()` 旧压缩域换算 | fit_distribution, gen_vec_table |
| `gen_vec_table.py` | 从 v8 表 + 声学锚点 + 部位表**生成** `vec_table_16.json`；`build()` 纯函数 | test_spec_next（复现性检查） |
| `explore_dims.py` | 维度探索的第一版（过完备维度集 + 消融） | explore_ml |

依赖关系（`A -> B` 表示 A import B）：

```
test_suite / test_metric_space / test_alignment / test_standard_chinese
        -> _common                     （且调用仓库根的二进制）
validate_alignment / fuzz_metric_space -> _common
gen_vectors_h -> _common
fit_metric -> _common
gen_vec_table -> place_anchors
fit_distribution -> place_anchors
test_spec_next -> gen_vec_table
explore_ml -> explore_dims
```

## 脚本分类

### 生成器（gen_*）
| 脚本 | 输入 → 输出 |
|------|------------|
| `gen_vectors_h.py` | `data/spec_next.scheme` → `src/vectors.h`（**Makefile `gen` 目标**；C 二进制由此编译） |
| `gen_vec_table.py` | `IPA_VECTORS.md`（v8 历史表）+ 声学锚点 + `place_anchors.PLACE` → `data/vec_table_16.json` |
| `gen_readme_embed.py` | `README.md` → `src/readme_embed.h`（**Makefile `gen` 目标**） |
| `gen_acoustic_anchors.py` | 已发表声学测量（`.rda`）→ `data/vowel_acoustic_anchors.json` |
| `gen_bark_anchors.py` | F1/F2/F3 → Bark → MDS → `data/vowel_bark_anchors.json` |
| `gen_vowel3d.py` | 多语言声学测量 → `data/vowel_3d_anchors.json` |
| `gen_anchors.py` | 数据驱动 → `data/anchors.json`（早期 13 维推导链） |
| `export_scheme.py` | `data/vec_table_16.json` + `data/metric16.json` → `data/spec_next.scheme`（保留手调权重行） |

### 拟合器（fit_*）
| 脚本 | 用途 |
|------|------|
| `fit_metric.py` | 按 METRIC.md §2 重新拟合度量权重（历史 16 维 v8） |
| `fit_metric16.py` | 16 维 SPEC-NEXT 权重拟合到 Phatak 08 混淆数据 |
| `fit_masked.py` | 掩码距离拟合与验证 → `data/metric16.json` |
| `fit_distribution.py` | 把（早期 13 维）空间拟合到真实语言分布（phoible） |
| `opt_vowels.py` | 在硬约束下优化元音锚点坐标 → `data/vowel_opt.json` |
| `plan_anchors.py` | 锚点规划器：为全部段分配 16 维坐标（设计期） |

### 审计与验证（audit / verify / validate）
| 脚本 | 用途 |
|------|------|
| `audit_anchors.py` | 锚点空间审计：近碰撞、反直觉距离、部位链步距；**合并前自动核对 EXTRA 表与核心 `EXTRA_BASE`** |
| `verify_modifiers.py` | 修饰符规则的设计模型验证（Python 复刻，**已同步** C 核心 MODS） |
| `validate_alignment.py` | `-A` 对齐公理的属性式 fuzz（对称性、恒等、吸收律） |
| `fix_audit.py` | 已废弃（SUPERSEDED）：审计修复清单，从未应用 |

### 测试套件（test_*）
| 脚本 | 依赖二进制 | 断言数 | 运行 |
|------|-----------|--------|------|
| `test_suite.py` | ipa2vec/vec2ipa/vec4ipa | 217 | `make test` |
| `test_metric_space.py` | ipa2vec/vec2ipa | 681 | `make test` |
| `test_alignment.py` | ipa2vec | 57 | `make test` |
| `test_standard_chinese.py` | ipa2vec | 448 | `make test` |
| `test_spec_next.py` | 无（纯 Python） | 124 | `make test` |
| `fuzz_metric_space.py` | ipa2vec/vec2ipa | （随机 fuzz，慢） | 手动 |

> `make test` 跑全部六个（fuzz 排除：慢、可选）。测试从仓库根运行，
> `_common.EXE` 指向仓库根的二进制（`ROOT = Path(__file__).parents[1]`）。

### 维度探索（explore_*）
- `explore_dims.py` — 过完备维度集 + 消融（SPEC-NEXT 草案期）
- `explore_ml.py` — 同一维集的 ML 消融套件（sklearn）

### 注意事项

- **必须从仓库根运行**：`python tools/test_suite.py`（不是 cd 进 tools/）。
  脚本用 `ROOT = Path(__file__).resolve().parents[1]` 定位仓库根，且
  `import _common` 依赖 `tools/` 在 `sys.path` 中（见上文导入机制）。
- **`__pycache__/` 是 Python 缓存**，可安全删除；`data/` 是数据目录，
  与脚本同处 `tools/` 下，不属于分类表中的"脚本"。
- 修改 scheme 后需重跑 `make gen` 使 `src/vectors.h` 同步，再跑
  `make test` 全量回归；若只改了 `vec_table_16.json` 派生物，
  `test_spec_next.py` 的 scheme 同步检查会拦截任何与 scheme 的漂移。