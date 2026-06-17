---
date: 2026-06-17T10:53:52+0800
author: 蔡涛
commit: 28d3693
branch: main
repository: skills
topic: "pi-trending 双榜单 — API 验证与不确定性分析"
tags: [research, pi-trending, npm-api, codebase]
status: ready
last_updated: 2026-06-17T10:53:52+0800
last_updated_by: 蔡涛
---

# Research: pi-trending 双榜单 — API 验证与不确定性分析

## Research Question

验证 npm API 行为（search API 排序方式、range API 批量限制、字段可靠性），确认双榜单设计（主流榜 + 新锐榜）的实现可行性和边界条件。

## Summary

- npm search API **支持 `sort=popularity`** 参数按下载量排序，解决了原收敛逻辑的"relevance 排序假设"缺陷。收敛逻辑可以保留并正确工作
- Range API batch size 80 保守安全，URL 长度远低于服务器限制（约 3,100 / 8,000 字符）
- 有作用域包**可以批量请求**，当前逐包获取是保守历史遗留，可以优化但不是必需
- 新锐榜公式 `ln(this_week+1) × (this_week - prev_week) / (prev_week + 10)` 需要加 `import math`（推荐 `math.log1p`），负值 clamp 到 0
- Range API 批量失败（网络/限流）会导致整批包从新锐榜丢失——决策为 failfast，抛异常让用户重试
- 安装副本有 2 个路径（`.pi/agent/skills/` 实际加载、`.agents/skills/` 文档记录），修改后都需同步。SKILL.md 当前源与安装副本不同步（多了 changelog 调查章节）
- `_determine_type` 使用 list exact member matching（`in` 算子对 list = exact match），非 substring 匹配，无歧义风险

## Detailed Findings

### npm Search API (`/-/v1/search`)

- 支持 `sort` 参数：`popularity`、`quality`、`optimal` 等值均可用
- `sort=popularity` 按下载量（严格递减）排序，第 1 页周下载范围 14~27,605，第 2 页 11~1,759
- 默认 `sort` 为 relevance（searchScore），与下载量不完全正相关
- `downloads.weekly` 字段可能缺失（新包无数据），当前代码通过 `.get("weekly", 0)` 安全兜底
- `total` 字段当前值为 4047（pi 包总数），500 候选池完全可覆盖

### npm Downloads Range API (`/downloads/range/{start}:{end}/{packages}`)

- 无文档化的 package-count 限制，实际约束是 URL 长度（nginx 默认约 8,000 字符）
- 当前 batch_size=80 保守安全：80 个包 × 30 字符名 ≈ 2,400 + base URL ≈ 3,100 字符
- 有作用域包（`@scope/name`）可在 batch URL 中正常使用 `%40scope%2Fname` 格式
- 并行：无作用域 batch 顺序执行（100ms 间隔），有作用域并行（5 线程）

### 收敛逻辑

- 加了 `sort=popularity` 后，原收敛假设（按下载量递减）成立
- 对于 `need=500`，2 页（250 × 2）= 500 包，收敛在第 2 页触发或 hard stop
- 建议简化：固定取 2 页后直接 return，去掉收敛判断逻辑

### 评分公式变更

当前：

```python
score = (this_week ** 2) / (prev_week + 100)
```

新锐榜：

```python
# 新增 import math
delta = max(0, this_week - prev_week)  # clamp 负值到 0
score = math.log1p(this_week) * delta / (prev_week + 10)
```

- `math.log1p(x)` = `ln(1+x)` 对小值数值精度更优，推荐替代 `math.log(this_week + 1)`
- `+ 10` 平滑：新包 `prev_week=0` 时 score = `ln(this_week+1) × this_week / 10`，增速奖励显著
- 负 delta clamp 到 0：下降的包得 0 分，只有增长的包进入新锐榜

### 批量失败处理

当前行为：`_json_get` 返回 None 时整批静默跳过（`pi_trending.py:241` 条件失败），包在新锐榜 score=0。

决策：**failfast**。当 range API 批量请求 3 次重试后仍失败时，抛出异常终止脚本，主流榜数据已安全输出，用户看到错误可重试。不在脚本内做逐包降级恢复。

### `--max` 向后兼容

- `--max N` → 主流榜 N 条 + 新锐榜 N 条（与默认各 20 一致）
- `--mainstream-max` 和 `--rising-max` 优先于 `--max`
- 示例：`--max 10` = 各 10，`--rising-max 5` = 主流 10 + 新锐 5

### 安装副本同步

| 路径 | 作用 | 同步来源 |
|------|------|---------|
| `~/.pi/agent/skills/pi-trending/` | **实际加载路径** | 源 `pi-agent/pi-trending/`，需要手动 cp |
| `~/.agents/skills/pi-trending/` | AGENTS.md 文档记录的安装副本 | 源 `pi-agent/pi-trending/`，需要手动 cp |

当前 SKILL.md 源与安装副本不同步（安装副本多了 changelog 调查章节 `### 8`）。修改后需要 cp 到两个路径。

## Code References

- `pi_trending.py:29` — `NPM_SEARCH` 常量
- `pi_trending.py:82-94` — `_json_get` 3 次重试 + 指数退避
- `pi_trending.py:142-205` — `fetch_top_packages()` 候选采集
- `pi_trending.py:187-197` — 收敛逻辑（将改为固定 2 页）
- `pi_trending.py:215-287` — `_fetch_range_data()` range 数据获取 + 评分
- `pi_trending.py:234` — batch_size=80
- `pi_trending.py:241` — 批量失败静默跳过（将改为 failfast）
- `pi_trending.py:267-275` — sorted_days 分割为 prev_week / this_week
- `pi_trending.py:282` — 当前评分公式（替换为新锐榜公式）
- `pi_trending.py:293-313` — `render_markdown()`
- `pi_trending.py:316-332` — `render_json()`
- `pi_trending.py:338-363` — CLI argparse
- `pi_trending.py:366-405` — `main()` 流程

## Integration Points

### Inbound References

- `SKILL.md:27` — `uv run --script scripts/pi_trending.py` 作为技能入口
- `README.md:55` — 技能表列举 pi-trending

### Outbound Dependencies

- `registry.npmjs.org/-/v1/search` — npm search API（按下载量排序）
- `api.npmjs.org/downloads/range/` — npm downloads range API
- Python stdlib 仅：argparse, json, sys, time, urllib, concurrent.futures, dataclasses, datetime, typing, **math**（新增）

### Infrastructure Wiring

- 执行：`uv run --script scripts/pi_trending.py`
- 安装副本同步：`AGENTS.md:51-54`
- 无持久化存储，无数据库，无配置

## Architecture Insights

- **双榜单共享候选池**：主流榜从 search API 响应直接取 `downloads.weekly`（零额外 API 成本），新锐榜对同 500 候选调 range API 计算增速分
- **`sort=popularity`** 使候选池采集正确且高效，主流榜数据天然有序
- **固定 2 页采集**替代收敛逻辑：去掉有问题的"relevance 假设"，简化代码
- **输出两张 Markdown 表**：主流榜列「本周下载量」，新锐榜列「趋势分」

## Precedents & Lessons

3 similar past changes analyzed.

### Precedent 1: pi-trending 初始创建

**Commit(s)**: `39ddae1` — "新增 pi-trending 技能：发现 pi 生态热门包" (2026-06-01)
**Blast radius**: 3 files, 529 insertions

- `pi-trending/SKILL.md` — 技能定义
- `pi-trending/scripts/pi_trending.py` — 脚本实现
- `README.md` — 技能表

**Follow-up fixes**:

- `215b4e8` — YAML frontmatter 缩进修复（24 分钟后）
- `00fa28f` — ruff 代码风格修复（+13 分钟）
- `d48a892` — markdown 格式化修复（+14 分钟）

**Takeaway**: SKILL.md 的 YAML frontmatter 非常脆弱，改 description 多行字符串时注意缩进

### Precedent 2: pi-trending 增加描述列

**Commit(s)**: `d4909de` — "pi-trending: 增加一句话简介列，AI翻译为中文并精简" (2026-06-05)
**Blast radius**: 3 files, 163 insertions, 13 deletions

- 纯展示层改动，零回归 bug
- FRD 流程（evidence-based 决策）有效防回归

**Takeaway**: 双榜单改动面比描述列大 4 倍（CLI + 搜索策略 + 评分 + 输出 + SKILL.md），需同样严谨的证据链

### Precedent 3: 仓库重组 — pi-trending 移至 pi-agent/

**Commit(s)**: `4b6abc2` — "重组技能仓库：按分类子目录分组" (2026-06-05)
**Blast radius**: 61 files (renames)

**Follow-up fixes**:

- `cceedf5` — AGENTS.md 增加 install-copy 同步规范（+4 天）

**Takeaway**: 安装副本同步是强制工作流。路径硬编码静默失效。改代码后必须 cp 到两个安装路径

### Composite Lessons

- `215b4e8` — SKILL.md YAML 缩进校验不可跳过
- `cceedf5` — 安装副本同步文档与实际路径有差距（`.pi/agent` vs `.agents`），需同步到两个路径
- `d4909de` — FRD 流程配合 codebase 证据链可有效防止回归

## Historical Context (from `.rpiv/artifacts/`)

- `.rpiv/artifacts/discover/2026-06-17_10-30-29_pi-trending-dual-list.md` — 双榜单 FRD，定义功能需求、决策、验收标准
- `.rpiv/artifacts/discover/2026-06-05_22-54-32_add-description-to-pi-trending.md` — 上一版描述列改动的 FRD

## Developer Context

**Q (discover: 榜单命名与定位): 两个榜单的具体名称和定位是什么？**
A: 「主流榜」（本周下载最多）vs 「新锐榜」（增速最快）

**Q (discover: 榜单数量): 两个榜单一共显示多少条？**
A: 各 20 条，默认共 40 条

**Q (discover: 非目标): 哪些明确不作为当前版本的目标？**
A: 不需要持久化存储、不需要按作者聚合、不需要历史榜单对比

**Q (discover: 输出格式): 两个榜单在输出中怎么展现？**
A: 先主流榜后新锐榜，两个独立的 Markdown 表格

**Q (discover: 数量控制参数): 每个榜单的数量怎么控制？**
A: `--mainstream-max`（默认 20）和 `--rising-max`（默认 20）

**Q (discover: 新锐榜评分算法): 新锐榜用什么评分公式？**
A: `ln(this_week + 1) × (this_week - prev_week) / (prev_week + 10)`

**Q (discover: 候选池大小): 候选池采集多少条？**
A: 固定 500 候选（2 页 × 250）

**Q (design baseline): Pre-resolved from codebase evidence — downloads.weekly, relevance sort, range API**
A: 三条基线全部确认保留

**Q (discover: 验收标准): 哪些场景验证通过才算功能完成？**
A: 主流榜前 3 为预期大包、新锐榜包含近期新增包、同一包可同时出现在两榜

**Q (discover: 性能要求): 对脚本运行性能有什么要求？**
A: 无严格性能约束

**Q (research: 收敛策略): `sort=popularity` vs 收敛逻辑？**
A: 同意使用 `sort=popularity`

**Q (research: 批量失败恢复): Range API 批量失败时加降级恢复？**
A: failfast — 抛错误让用户重试

**Q (research: 负值处理): 公式负 delta 怎么处理？**
A: clamp 到 0

## Related Research

- `.rpiv/artifacts/research/2026-06-08_09-11-50_chezmoi-sync-optimization-decisions.md` — 安装副本双路径的发现来源

## Open Questions

无 — 所有问题均已确认。

## Suggested Follow-ups

- `pi_trending.py:241` — 有作用域包可批量请求，当前逐包获取是优化机会但不是必需
- SKILL.md 源与安装副本的 changelog 章节不同步问题（源缺了 `### 8` 包更新调查章节），可后续对齐
- 当前 `_determine_type` 对无类型包返回 `"package"` 兜底，不指定 `--type` 时未分类包会出现在两个榜中，后续可考虑加过滤选项
