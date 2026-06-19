---
date: 2026-06-19T22:51:17+0800
author: CNife
commit: a1e64ad
branch: main
repository: skills
topic: "pi-trending 超时修复 — F1 验证 + F2a 删 range API + 新锐榜重设计 + 主流榜改 monthly + F3"
tags: [research, codebase, pi-trending, f1-validation, f2a, search-only, growth-baseline-log]
status: ready
last_updated: 2026-06-19T23:30:00+0800
last_updated_by: CNife
---

# Research: pi-trending 脚本超时修复 — 全面转向 search API（F1 验证 + F2a 落地 + 公式重设计 + 主流榜改 monthly）

## Research Question

按 explore/research 顺序处理 pi-trending 超时修复：(1) 在 `test-scripts/` 下实现 F1 验证脚本；(2) F1 跑出的结果决定后续方向；(3) 实际 F1 结果导向了 F2a（删 range API）+ 新锐榜公式重设计 + 主流榜改 monthly 排序 + F3 输出参数化。

## Summary

- **F1 验证脚本独立成单文件**：放在仓库根 `test-scripts/f1_validate_search_api.py`（新目录，不进发布包），PEP 723 + `dependencies = []`，duplicate 需要的小表面，独立 runnable。
- **F1 探针确认**：search API 返回 `weekly` 和 `monthly` 两个下载字段，F2a 理论可行。
- **F1 公式验证结论（关键转折）**：候选公式 (a) `monthly/weekly` 和 (b) `(monthly-weekly)/(weekly+10)` 均得出 overlap=0.000、Spearman=NaN。根本原因在于 search API 只有累积值（最近7天/30天总量），无法恢复出 range API 所需的 `this_week - prev_week` 变化量。**F2b（缓存层）被否决，但不走 F2a 原路，而是重设目标。**
- **新锐榜公式重新设计**：不再模拟 range API 的"本周 vs 上周"对比，而是直接用 `weekly` 和 `monthly` 定义增速。最终定稿：

```
recency = weekly / monthly                              # 最近一周在月度中的占比
stable_baseline = 7 / 30                                  # 均匀分布的基准线
growth = max(0, recency - stable_baseline) / (1 - stable_baseline)  # 归一化到 0~1
score = growth × ln(weekly + 1)                          # 增速 × log(热度) 加信誉权重
```

- `RISING_MIN_WEEKLY` **200 → 100**，放宽新锐候选池，让更多小量增速包有机会上榜。

- **主流榜改按 `monthly` 排序**：`weekly` 窗口为 7 天波动太大，`monthly`（30 天总量）更具稳定性。与新锐榜形成"量 vs 增速"的明确分工。

- **F2b（缓存层）彻底否决**：range API 被删除，无需缓存。

- **F3 输出参数化**：`--max` 默认值 20 → 30，同步更新 SKILL.md 文案。

- **顺手清理**：修复 docstring 公式 + 删除 SKILL.md:212 dangling 引用。

## Detailed Findings

### F1 验证脚本（位置 / 形状 / 第一动作）

- **位置**：仓库根 `test-scripts/f1_validate_search_api.py`（新建目录），跟 `pi-agent/pi-trending/scripts/` 平级但不进 skill 发布包。Rationale：用户决策"作为留存"。
- **形状**：PEP 723 单脚本，`dependencies = []`，独立 runnable；不从 `pi_trending.py` import，duplicate 它需要的：`NPM_SEARCH` (`pi_trending.py:31`)、`NPM_DOWNLOADS` (`:32`)、`RISING_MIN_WEEKLY=200` (`:34`)、`_json_get` (`:82-108`)、`_json_get_bulk` (`:111-125`)、`_urlencode_pkg` (`:78-80`)、`_today_str` (`:207`)、`PiPackage` shape (`:64-71`)、`_fetch_range_data` 的 score 计算循环 (`:267-292`)。
- **Phase 0 探针（第一动作）**：`probe_url = f"{NPM_SEARCH}?text=keywords:pi-package&size=1&sort=popularity"`；命中后 `print(list(objects[0]['downloads'].keys()))` 到 stderr，证据落到验证报告。这一步直接结算 FRD Open Q3（时间窗对齐）和 F2a 可行性硬前提。
- **Phase 1-5 流程**：1) 复制 `fetch_top_packages` 取 max_pages=2、500 候选；2) 计算 search-only 候选公式（见下条）；3) 复制 `_fetch_range_data` 算 range-based score；4) 两份 top-30 比对（overlap + 手算 Spearman）；5) 单句结论 `replaceable` / `not replaceable`。
- **Spearman 手算**：stdlib 无内置；用 `1 - 6·Σd² / (n·(n²-1))`，n 取两榜交集大小（top-k 标准做法）。

### 新锐榜公式（growth-baseline-log）

**目标**：不再试图模拟 range API，而是直接用 search API 的 `weekly` 和 `monthly` 定义增速。

**公式**：

```python
def _rising_score(pkg: PiPackage) -> float:
    if pkg.weekly == 0 or pkg.monthly == 0:
        return 0.0
    recency = pkg.weekly / pkg.monthly
    stable_baseline = 7 / 30
    growth = max(0.0, (recency - stable_baseline) / (1 - stable_baseline))
    return growth * math.log1p(pkg.weekly)
```

**各成分意义**：

| 成分 | 含义 |
|------|------|
| `weekly / monthly` | 最近一周在月度总量中的占比，核心增速信号 |
| `− 7/30` 再 `max(0, …)` | 剔除均匀分布基线，稳定/下滑包得 0 分 |
| 除以 `(1 − 7/30)` | 归一化到 0~1，全月集中在一周时 growth=1.0 |
| `× ln(weekly+1)` | 给增速加信誉权重，让 RISING_MIN_WEEKLY 以上的包有基础分 |

**行为**：

| 场景 | weekly | monthly | recency | growth | score |
|------|--------|---------|---------|--------|-------|
| 新黑马 | 2,000 | 2,200 | 0.91 | 0.88 | 6.7 |
| 稳定热门 | 182,628 | 194,504 | 0.94 | 0.92 | 11.1 |
| 快速增长 | 10,000 | 30,000 | 0.33 | 0.13 | 1.2 |
| 稳定包 | 5,000 | 21,429 | 0.23 | 0.0 | 0 |
| 冷门小爆发 | 500 | 800 | 0.63 | 0.52 | 3.2 |
| 下滑包 | 2,000 | 20,000 | 0.10 | 0.0 | 0 |

**RISING_MIN_WEEKLY = 200 → 100**：放宽新锐候选池门槛，让更多小量增速包有机会上榜。

### 主流榜改按 monthly 排序

- **旧排序**：`sorted(candidates, key=lambda p: p.weekly, reverse=True)` — 7 天窗口波动大。
- **新排序**：`sorted(candidates, key=lambda p: p.monthly, reverse=True)` — 30 天窗口更稳定，主流榜不会一天一换。
- `render_markdown` 显示列 "本周下载量" → "月下载量"，与排序一致。
- `render_json` 去掉 `this_week`/`prev_week` 字段，保留 `weekly_downloads` 和 `trending_score`。

### 删除范围（死代码清单）

- **删除函数**：`_fetch_range_data`、`_json_get_bulk`、`_urlencode_pkg`。
- **删除常量**：`NPM_DOWNLOADS`。
- **删除 import**：`from concurrent.futures import ThreadPoolExecutor, as_completed`、`timedelta`（保留 `UTC, datetime`）。`import math` **保留**（`log1p` 在新公式中继续使用）。
- **删除 `main()` 块**：`try/except RuntimeError`，整段替换为 `_rising_score` 调用。
- **删除 `_vlog` 调用点**：L220 / L245 / L250 / L262-265（全部在 `_fetch_range_data` 体内）；`_vlog` 函数本身保留。
- **保留**：`_json_get`、`_today_str`、`time.sleep`、`random.random`。
- **PiPackage 字段精简**：去掉 `this_week`、`prev_week`（不再需要），保留 `weekly`、`monthly`、`score`。

### F3 输出参数化（双路径都做）

- **CLI 改动**（`pi_trending.py:382-389`）：
  - `--max` default 20 → 30 (`:383`)
  - `--max` help 文案 "默认 20" → "默认 30"
  - `--mainstream-max` 与 `--rising-max` **保留命名不变**（用户决策 D1）
  - epilog (`:374-378`) 加一行 `--mainstream-max 5 --rising-max 10` 示例
  - epilog 第 1 行 "Top 20" → "Top 30"
- **SKILL.md 文案改动**：
  - `:27` "各展示 Top 20" → "各展示 Top 30"
  - `:71`, `:89` 示例输出 "> Top 20" → "> Top 30"
  - L119-128 命令示例无需改（已用 `--mainstream-max`）
- **FRD 改动**：`.rpiv/artifacts/discover/2026-06-19_22-17-09_pi-trending-timeout.md:81` 验收命令把 `--main-max 50` 改成 `--mainstream-max 50`（用户决策 D1）。
- **不动**：`RISING_MIN_WEEKLY = 200` (`:34`，下载阈值非显示数)、`render_json` schema、`render_markdown` 公式描述。

### 顺手清理（用户决策 D3）

- **`pi_trending.py:11` docstring**：当前写 `trending_score = this_week² / (prev_week + 100)`，与 L292 实际公式 `math.log1p × delta / (prev_week+10)` 矛盾。F2a 路径下要重写成 search-only 公式；F2b 路径下改成与 L292 一致的真公式。无论哪条路径都要改。
- **`SKILL.md:212` dangling 引用**：`详细工作流见 references/package-changelog-investigation.md` —— 该文件源、两个安装副本三处都不存在；删除该行（最简）或把"详细工作流"段并入 SKILL.md 主体（更费事）。Lazy 选删除。

### 同步策略（用户决策 D4）

- **不再手动 `cp`** 到 `~/.pi/agent/skills/pi-trending/` 和 `~/.agents/skills/pi-trending/`。
- **走发布流程**：git commit + push → 用户 `bunx skills add CNife/skills@pi-trending --full-depth` 重新拉取（`README.md:10`、`utility/cnife-skills-repo/SKILL.md` 记录此命令）。
- **本期不修 AGENTS.md**：AGENTS.md L41-54 的 manual `cp` 工作流仍在仓库里，但本任务不消费它。如需统一升级 AGENTS.md，开独立任务。

## Code References

### 主脚本核心位置（实施后预期状态）

- `pi-agent/pi-trending/scripts/pi_trending.py:11` — module docstring → 改为新公式 `growth × ln(weekly+1)`
- `pi-agent/pi-trending/scripts/pi_trending.py` — **删除** `from concurrent.futures import ...`、`timedelta`、`NPM_DOWNLOADS`、`_urlencode_pkg`、`_json_get_bulk`、`_fetch_range_data`、`try/except RuntimeError`
- **保留**：`import math`（`log1p`）、`_json_get`、`_today_str`、`time.sleep`、`random.random`
- `fetch_top_packages` — 核心候选采集保留，额外提取 `dl.get("monthly", 0)`
- `PiPackage` dataclass — 加 `monthly` 字段，删 `this_week`/`prev_week`
- 新增 `_rising_score(pkg)` — growth-baseline-log 公式
- `main()` 主流榜 → `sorted(…, key=lambda p: p.monthly, reverse=True)`
- `main()` 新锐榜 → `sorted(…, key=_rising_score, reverse=True)`，无 range API 调用
- `render_markdown` — "本周下载量" → "月下载量"，主流榜显示 `pkg.monthly`
- `render_json` — 去掉 `this_week`/`prev_week` 字段
- `RISING_MIN_WEEKLY = 200 → 100`
- `--max` default 20 → 30（F3）
- epilog "Top 20" → "Top 30"，加 `--mainstream-max 5 --rising-max 10` 示例

### SKILL.md / 文档位置

- `pi-agent/pi-trending/SKILL.md:2-18` — YAML frontmatter（脆弱，改前后跑 `python -c "import yaml; yaml.safe_load(open(...))"` ）
- `pi-agent/pi-trending/SKILL.md:27` — "各展示 Top 20"（F3 → 30）
- `pi-agent/pi-trending/SKILL.md:38-46` — 原理章节，含 score 公式（F2a 重写 / F2b 不动）
- `pi-agent/pi-trending/SKILL.md:71, 89` — 示例输出 "> Top 20"（F3 → 30）
- `pi-agent/pi-trending/SKILL.md:119-128` — `--max` / `--mainstream-max` / `--rising-max` 示例（F3 不动）
- `pi-agent/pi-trending/SKILL.md:212` — dangling 引用 `references/package-changelog-investigation.md`（删）

### F1 新建脚本位置

- `test-scripts/f1_validate_search_api.py` — **新建**（仓库根新目录，不进 skill 发布包）

## Integration Points

### Inbound References

- `pi-agent/pi-trending/SKILL.md:27` — `uv run --script scripts/pi_trending.py` 是技能入口
- `README.md:55` — 技能表列举 pi-trending
- `.rpiv/artifacts/discover/2026-06-19_22-17-09_pi-trending-timeout.md` — 本研究的 FRD 来源

### Outbound Dependencies

- `https://registry.npmjs.org/-/v1/search` — npm search API（唯一外部依赖，range API 已删除）
- Python stdlib：`argparse`、`json`、`sys`、`time`、`urllib.{error,request}`、`dataclasses`、`datetime`、`typing`、`math`（`log1p`）
- **已删除**：`concurrent.futures`、`timedelta`、`os`、`tempfile`（F2b 无需落地）
- **外部请求数**：2 次 search API 调用（2 pages × 250），约 2~4 秒完成，不再有 ~30 秒的 range API 调用

### Infrastructure Wiring

- 执行入口：`uv run --script scripts/pi_trending.py`（PEP 723 单脚本模式）
- F1 脚本入口：`uv run --script test-scripts/f1_validate_search_api.py`（同模式，独立）
- 安装路径：`bunx skills add CNife/skills@pi-trending --full-depth` 重新拉取，**不再手动 `cp`**
- 无持久化（range API 已删，缓存不再需要）

## Architecture Insights

- **F1 的"失败"是最大的价值**：两种候选公式 overlap=0.000 清晰地证明 search API 的累积数据（weekly/monthly）无法模拟 range API 的"本周 vs 上周"差分计算。这个结论让团队果断放弃了"模拟 range 公式"的思路，转而设计全新的增速指标体系。
- **新范式：不模拟，全新设计**：不再试图用 search API 的有限字段去凑 range API 的结果，而是直接基于 `weekly / monthly` 比值定义"增长"。这个范式转换是整个修复的核心贡献。
- **主流榜用 monthly、新锐榜用 growth × ln(weekly)**：两个榜单有了**明确的分工**。主流榜回答"最近一个月最常用"，新锐榜回答"最近谁在涨"，不再共享公式。设计清晰度远高于旧方案。
- **删除远多于新增**：删除了 1 个 API 端点（range API）、3 个函数、2 个 import、`try/except` 块。故障面从 2 个 API 降为 1 个，超时问题彻底消失。
- **外部请求数从 ~30 秒降为 ~2-4 秒**：2 次 search API 调用，无 range API，无批处理，无并发控制。脚本性能问题本质解决。
- **CLI 命名争议**：FRD 引用的 `--main-max` 在 SKILL.md 中实为 `--mainstream-max`。用户裁决保留全名，FRD 需校准。
- **历史教训：大改必跟 hotfix**：每次 pi-trending 主体改动都跟着 follow-up。F2a 改动面较大，commit 粒度要细。

## Precedents & Lessons

5 similar past changes analyzed.

### Precedent 1: 双榜单优化（直接前序）
**Commit(s)**: `20f200a` — "pi-trending: 双榜单优化（主流榜 + 新锐榜）" (2026-06-17)
**Blast radius**: 4 files, 302 net lines（脚本 / SKILL.md / FRD / 研究）

**Follow-up fixes**:
- `a1e64ad` — "pi-trending: 新锐榜候选池加周下载阈值 200，限流退避加 jitter" (2026-06-17, +2h51m) — 候选池过滤 + 429 jitter

**Takeaway**: F1/F2/F3 改动面与之相当，准备同等规模的 hotfix 余量；加 jitter 那条已落地（L93），本期不需重做。

### Precedent 2: 创建后 24 分钟内三连修
**Commit(s)**: `39ddae1` — "新增 pi-trending 技能" (2026-06-01)
**Follow-up fixes**: `215b4e8` (+24m) YAML 缩进；`00fa28f` (+13m) ruff；`d48a892` (+14m) markdown

**Takeaway**: SKILL.md frontmatter 修改后必须跑 `python -c "import yaml; yaml.safe_load(open(...))"`；脚本改完跑 `uv run ruff check --fix`。

### Precedent 3: 安装副本同步路径（已被本期决策覆盖）
**Commit(s)**: `cceedf5` — "AGENTS.md 加 install-copy 工作流" (2026-06-09)

**Takeaway**: AGENTS.md 写的 manual `cp` 双路径工作流，在本期被用户决策 D4 替换为 `bunx skills add` 发布流程。本期不消费 manual cp。

### Precedent 4: 描述列增加 — 零回归
**Commit(s)**: `d4909de` — "增加一句话简介列" (2026-06-05)

**Takeaway**: FRD 流程 + 证据链验证（"先 print 字段是否存在"）有效。F1 探针就是这个模式的延续。

### Precedent 5: obsidian-diary 删 subcommand — 6 分钟后跟 SKILL.md 同步漏
**Commit(s)**: `14cf104` (+ `ee074fc` +6m)

**Takeaway**: 删代码路径时，SKILL.md 文案要同 commit 改完。F2a 后 SKILL.md 任何提及"14 天"、"range API"、"增速分（基于趋势）"的话术要同步擦除或重写。

### Composite Lessons

- **YAML frontmatter 改完必跑 yaml.safe_load**（`215b4e8`）—— 改 SKILL.md `description:` 多行块时尤其。
- **删 API 调用路径必跑 ruff check**（`00fa28f`）—— F2a 死代码连环消除一次到位。
- **大改动 commit 切片，准备 hotfix 窗口**（`20f200a → a1e64ad`）。
- **删代码 = 同 commit 改文档**（`14cf104 → ee074fc`）—— SKILL.md 任何提到被删功能的话术要同步处理。
- **验证脚本第一动作：empirical print**（`d4909de` 风格）—— F1 探针打印 `dl.keys()` 是不可压缩的。

## Historical Context (from `.rpiv/artifacts/`)

- `.rpiv/artifacts/discover/2026-06-19_22-17-09_pi-trending-timeout.md` — 本研究消费的 FRD（验证驱动的需求来源）
- `.rpiv/artifacts/research/2026-06-17_10-53-52_pi-trending-dual-list-api-validation.md` — 上一轮研究确认 search API `weekly` 字段存在 / range API batch_size=80 安全 / `math.log1p` 公式决策（部分结论本期沿用）
- `.rpiv/artifacts/discover/2026-06-17_10-30-29_pi-trending-dual-list.md` — 双榜单 FRD，决策表锁定 `--mainstream-max` 命名（本期延续）
- `.rpiv/artifacts/discover/2026-06-05_22-54-32_add-description-to-pi-trending.md` — 描述列改动 FRD（empirical-first 验证模式参考）

## Developer Context

**Q (discover: D0 焦点是交互延迟还是可靠性)**: 脚本超时这个问题，你最在意哪一面？
A: 我自己跑的时候等太久，想要更快出结果（日常使用者交互延迟视角）

**Q (discover: D1 是否引入持久化缓存)**: 脚本现在完全没有缓存。加不加？
A: 不加；后改为条件化 —— 若 search API 字段不能替代 range 调用，再考虑会话级临时缓存

**Q (discover: D2 是否提升 unscoped 批处理并发度)**: 现在串行批处理，要不要并行？
A: 维持串行（避免加剧限流，与限流根因调研一致）

**Q (discover: D3 是否裁剪候选池)**: 候选池要不要从 ~400 个裁到更小？
A: 不裁，保留 weekly ≥ 200 的全量候选（避免错过黑马）

**Q (discover: D5 是否一并处理换掉 range 调用)**: 要不要本期一起做？
A: 需要先测试验证能否完全替代 —— 升级为 F1 验证子任务

**Q (discover: D6 输出条数参数化默认值)**: 默认输出多少条？
A: 默认 30（不再是 20），上限 = 候选池

**Q (research: F3 命名落差 — `pi_trending.py:386` 是 `--mainstream-max`，FRD 验收脚本 `:81` 用 `--main-max`)**: 怎么落地？
A: 保留 `--mainstream-max`，改 FRD 验收脚本（不引 alias，不重命名）

**Q (research: F1 阈值 — FRD Open Q2 留作待定)**: overlap 和 Spearman 多少算可替代？
A: 你（research）决定阈值，我只负责实现 → 锁定 overlap ≥ 0.85 且 Spearman ≥ 0.8（双指标 AND）

**Q (research: 顺手清理 — `pi_trending.py:11` docstring 旧公式 + `SKILL.md:212` dangling 引用)**: 本期顺手修吗？
A: 顺手修：docstring 改写 + 删 dangling 引用

**Q (research: F1 脚本位置 — 原推荐 `pi-agent/pi-trending/scripts/`)**: 验证脚本放哪？
A: 放到 `./test-scripts/` 下面作为留存（仓库根新目录，不进发布包）

**Q (research: 安装副本同步 — AGENTS.md 写 manual `cp` 双路径)**: 这次怎么同步到安装路径？
A: 不需要手动同步，走 `pi update` / `bunx skills add` 流程，先发布后安装

**Q (review: F1 跑完后两种候选公式都 overlap=0，然后？)**
A: 不再试图模拟 range API，直接用 weekly/monthly 比值定义增速。用户主导重新设计了 growth-baseline-log 公式。

**Q (review: 主流榜排序要怎么改？)**
A: 从 `weekly` 改为 `monthly`，30 天窗口更稳定。与新锐榜形成"月度总量 vs 增速"的分工。

**Q (review: RISING_MIN_WEEKLY 要不要动？)**
A: 200 → 100，放宽新锐候选池门槛。

## Related Research

- `.rpiv/artifacts/research/2026-06-17_10-53-52_pi-trending-dual-list-api-validation.md` — 直接前序，复用其 search API / range API 行为结论
- `.rpiv/artifacts/research/2026-06-08_09-11-50_chezmoi-sync-optimization-decisions.md` — 安装副本双路径发现来源（本期已被 D4 决策覆盖）

## Open Questions

- **（已关闭）F2b 缓存方案**：range API 被删除，缓存不再需要。
- **（已关闭）F1 失败重试策略**：F1 脚本已运行成功，未触发 429。

## Suggested Follow-ups

- AGENTS.md L41-54 的 manual `cp` 工作流与本期决策 D4 不一致 —— 后续独立任务统一升级。
- `_json_get` timeout=15、retries=3 对于仅 2 次 search 调用仍保守，可考虑压缩到 timeout=10、retries=2 进一步加速。
- `pi-agent/pi-trending/SKILL.md` 全文无 SLA 声明 —— 实施后补一段"预期 ≤ 5 秒"。
- 跨日期一致性的预计算方案（npm-stat / TanStack 风格 GitHub Action 每日预拉取）—— 本期 out of scope，但若 monthly 排序仍不够稳定，可考虑。
