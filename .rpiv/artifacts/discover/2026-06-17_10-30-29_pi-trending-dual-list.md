---
date: 2026-06-17T10:30:29+0800
author: 蔡涛
commit: 28d3693
branch: main
repository: skills
topic: "pi-trending 双榜单优化"
tags: [intent, frd, pi-trending, npm]
status: ready
last_updated: 2026-06-17T10:30:29+0800
last_updated_by: 蔡涛
---

# FRD: pi-trending 双榜单优化

## Summary

将 pi-trending 脚本从单一趋势榜拆分为「主流榜」和「新锐榜」两个榜单。主流榜按本周下载量倒排，展示生态中当下最常用的包；新锐榜按增速评分排序，发现正在快速蹿升的包。两个榜单共享同一个 500 候选池，一次性采集后分别计算排序。

## Problem & Intent

使用 pi-trending 的开发者（包括我自己）想了解 pi 生态里有什么好包。但现有单一趋势榜无法同时回答两个不同的问题：

- "大家都在用什么？"——需要看绝对下载量高的主流包
- "最近有什么新东西冒出来？"——需要看增速快的新兴包

当前的 `this²/(prev+100)` 算法偏向大包，高增速低下载量的包在候选阶段就被筛掉了。两个榜单各司其职，用户一次运行就能同时获得"生态全景"和"发现感"。

## Goals

- 主流榜按本周下载量倒排，展示 pi 生态中最常用的包
- 新锐榜按增速评分排序，展示正在快速蹿升的包
- 两个榜单共享同一个 500 候选池，避免新锐榜候选被提前截断
- 默认各输出 20 条，共 40 条
- 两个独立的 Markdown 表格，先主流榜后新锐榜
- 支持 JSON 输出模式
- 可通过 `--mainstream-max` 和 `--rising-max` 分别控制每个榜单的数量

## Non-Goals

- 不需要持久化存储（数据库/缓存）——脚本无状态运行，每次实时从 npm API 拉取
- 不需要按作者/组织聚合——每个包独立排名
- 不需要历史榜单对比——不保存历史排名、不展示排名变化
- 不要求严格的性能指标——保持现有的运行方式即可
- 不改动 `--type` 过滤和 `--json` 等已有参数的行为

## Functional Requirements

1. 脚本 SHALL 从 npm search API 采集 500 个候选包（2 页 × 250 条），作为两个榜单的共享候选池
2. 主流榜 SHALL 按候选包的 `downloads.weekly`（npm search 返回的本周下载量）降序排列，取前 `--mainstream-max` 条
3. 新锐榜 SHALL 对候选池调用 npm downloads range API 获取 14 天增量数据，按 Log-Relative 公式 `ln(this_week + 1) × (this_week - prev_week) / (prev_week + 10)` 计算增速分降序排列，取前 `--rising-max` 条
4. 相同的包 SHALL 可以同时出现在两个榜单中（互不冲突）
5. 输出 SHALL 包含两个独立的 Markdown 表格，先主流榜后新锐榜，表头分别为"主流榜"和"新锐榜"
6. 输出 SHALL 兼容现有的 JSON 模式（`--json`），以结构化数据包含榜单标签
7. CLI 参数 SHALL 增加 `--mainstream-max`（默认 20）和 `--rising-max`（默认 20），分别控制两个榜单的输出数量
8. 现有的 `--max` 参数 SHALL 保持兼容，同时设置两个榜单的数量（等量分配：`--max 10` = 各 10 条；或设置为总条数平分）
9. 新锐榜的 range 数据获取 SHALL 复用现有的批处理（scoped/unscoped 拆分、80 个一批、100ms 间隔）和并行（5 线程）逻辑
10. 主流榜 SHALL 不需要额外 API 调用——`downloads.weekly` 来自 search API 返回的元数据

## Non-Functional Requirements

- **Performance**: 无严格性能约束。现有批处理和并行逻辑保持不变，运行时间可接受即可
- **Security**: 无变更——仅调用 npm 公开 API，不处理敏感数据
- **UX / Accessibility**: 默认 Markdown 表格 LLM 友好，JSON 模式供下游工具消费
- **Reliability**: 复用现有 3 次重试 + 指数退避逻辑；range API 失败不影响主流榜输出

## Constraints & Assumptions

- npm search API 按 relevance 排序（非下载量排序），最大 250 条/页——500 候选池需要 2 页请求
- npm downloads range API 支持批量查询无作用域包（最多 80 个一批），有作用域包需单独请求——复用现有批处理逻辑
- 脚本只依赖 Python stdlib（urllib），不引入第三方包——保持 PEP 723 单脚本模式
- 假设从 search API 获取的 `downloads.weekly` 与 range API 计算出的本周下载量存在微小差异但趋势一致，主流榜不需要完全精确

## Acceptance Criteria

- [ ] 运行 `uv run --script scripts/pi_trending.py`：输出两个 Markdown 表格，主流榜前几名包含 `@pi/core` 类知名大包，新锐榜包含增速快的新兴包
- [ ] 运行 `uv run --script scripts/pi_trending.py --mainstream-max 5 --rising-max 20`：主流榜只输出 5 条，新锐榜输出 20 条
- [ ] 同一个包（如 `pi-context-map`）出现在两个榜中时，互不干扰、各自排序正确
- [ ] 运行 `uv run --script scripts/pi_trending.py --json`：输出 JSON 数组，每个元素包含 `list_type: "mainstream"` 或 `list_type: "rising"` 字段

## Recommended Approach

在现有的 `pi_trending.py` 脚本内扩展 `main()` 流程：Phase 1 搜索 API 采集候选池从 `max * 3` 改为固定 500；Phase 2 新增主流榜按 `downloads.weekly` 直接排序截取（零额外 API 成本）；Phase 3 对候选池获取 range 数据后，按 Log-Relative 公式计算新锐榜排序；输出阶段渲染两个独立的 Markdown 表格或 JSON 数组。新增 CLI 参数 `--mainstream-max` 和 `--rising-max`，保持 `--max` 向后兼容。

## Decisions

### 榜单命名与定位

**Question**: 两个榜单的具体名称和定位是什么？
**Recommended**: 双榜单方案，区分绝对热度与增速
**Chosen**: 「主流榜」（本周下载最多）vs 「新锐榜」（增速最快）
**Rationale**: 强调"成熟生态主力 vs 新兴力量"的新老对比，用户直觉理解成本低

### 榜单数量

**Question**: 两个榜单一共显示多少条？
**Recommended**: 默认各 20 条，共 40 条
**Chosen**: 各 20 条，默认共 40 条
**Rationale**: 信息密度更高，适合生态全景观察

### 非目标

**Question**: 哪些明确不作为当前版本的目标？
**Recommended**: 三个方向都排除
**Chosen**: 不需要持久化存储、不需要按作者聚合、不需要历史榜单对比
**Rationale**: 保持脚本简单无状态，一次运行就是独立快照

### 输出格式

**Question**: 两个榜单在输出中怎么展现？
**Recommended**: 两个独立的 Markdown 表格
**Chosen**: 先主流榜后新锐榜，两个独立的 Markdown 表格
**Rationale**: LLM 友好，阅读清晰，JSON 模式同样兼容

### 数量控制参数

**Question**: 每个榜单的数量怎么控制？
**Recommended**: 独立的参数分别控制
**Chosen**: `--mainstream-max`（默认 20）和 `--rising-max`（默认 20）
**Rationale**: 灵活性最高，用户可按需调整任一榜单密度

### 新锐榜评分算法

**Question**: 新锐榜用什么评分公式？
**Recommended**: Log-Relative 公式
**Chosen**: `ln(this_week + 1) × (this_week - prev_week) / (prev_week + 10)`
**Rationale**: 用 ln 压缩绝对规模差异，用增长率放大增速信号，大小包公平竞争

### 候选池大小

**Question**: 候选池采集多少条？
**Recommended**: 固定 500 候选
**Chosen**: 从 npm search API 固定采 500 条（2 页 × 250）
**Rationale**: 简单直接，API 成本低（最多 2 次请求），覆盖充分

### 设计基线（代码证据预确认）

**Question**: Pre-resolved from codebase evidence (`pi_trending.py:94-98,96-97,128-183`)
**Recommended**: 三条基线全部保留
**Chosen**: 热门榜用 search API 的 `downloads.weekly`（零额外成本）；search API 是 relevance 排序而非下载量排序；新锐榜需要 range API 获取 14 天数据
**Rationale**: `evidence: pi_trending.py:94-98,96-97,128-183 + confirmed`

### 验收标准

**Question**: 哪些场景验证通过才算功能完成？
**Recommended**: 三个维度全覆盖
**Chosen**: 主流榜前 3 为预期大包、新锐榜包含近期新增包、同一包可同时出现在两榜
**Rationale**: 覆盖了正确性、发现感、独立性三个核心维度

### 性能要求

**Question**: 对脚本运行性能有什么要求？
**Recommended**: 保持现状
**Chosen**: 无严格性能约束
**Rationale**: 现有批处理和并行逻辑已足够，不需要额外优化

## Open Questions

无 — 所有分支均已确认决策。

## Suggested Follow-ups

- 当前收敛逻辑假设 npm search API 按周下载量排序，实际是 relevance 排序 (`pi_trending.py:106-118`)。扩大候选池到 500 后此问题影响减小，但后续可清理该逻辑或改为固定页数
- 新包的增速评分当前用 `(prev_week + 10)` 做平滑分母，可进一步考虑包的 release age 作为代理信号

## References

- `/home/cnife/personal_code/skills/pi-agent/pi-trending/scripts/pi_trending.py` — 当前脚本实现
- `/home/cnife/personal_code/skills/pi-agent/pi-trending/SKILL.md` — 技能文档
