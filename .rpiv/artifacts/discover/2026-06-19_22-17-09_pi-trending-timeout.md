---
date: 2026-06-19T22:17:09+0800
author: CNife
commit: a1e64ad
branch: main
repository: skills
topic: "pi-trending 脚本超时修复（验证驱动）"
tags: [intent, frd, pi-trending, performance, npm-rate-limit]
status: ready
last_updated: 2026-06-19T22:17:09+0800
last_updated_by: CNife
---

# FRD: pi-trending 脚本超时修复（验证驱动）

## Summary

`pi-agent/pi-trending/scripts/pi_trending.py` 经常超时，日常使用者跑一次要等太久。诊断已锁定根因为 npm registry CDN 层（Cloudflare）对 `api.npmjs.org/downloads/range` 的匿名 per-IP 限流。本期工作以**验证驱动**展开：先验证能否用 `registry.npmjs.org/-/v1/search` 返回中自带的 `downloads.weekly`/`monthly` 字段彻底替代 `downloads/range` 调用；如能替代则消除限流根因，缓存方案不再需要；如不能替代则退回到会话级临时缓存方案。同时本期内把输出条数参数化、默认值从 20 抬到 30。

## Problem & Intent

> "之前优化了一版 @pi-agent/pi-trending/，出现了脚本经常超时的问题，我想解决这个问题。"
>
> "我自己跑的时候等太久，想要更快出结果。"
>
> "目前来看，主要卡点就是 NPM 的限流问题。"

定位：日常使用者视角的交互延迟。期望"一次跑完不等很久"，且不再被限流中断。

## Goals

- 显著降低日常使用者跑一次 `pi-trending` 的等待时间，主观上"不卡"。
- 消除（或在不可消除时显著降低）npm registry 限流（429 / Cloudflare 1015）触发频率。
- 输出条数可参数化，使用者能在同一会话中按需要看 30、40 或更多条结果。
- 默认输出条数从当前的 20 抬到 30。

## Non-Goals

- **不增加 npm API 同时请求并发度**——保持现状，避免加剧限流（决策 D2）。
- **不裁剪候选池规模**——保留 weekly ≥ 200 的全量候选，避免错过黑马（决策 D3）。
- **不为可靠性而修**——本期不解决"返回部分数据"或"重试策略"问题，专注交互延迟（决策 D0）。
- **不引入持久化数据库 / 长期缓存层**——`npm-stat`、`tanstack` 那种每日预拉取全量数据的架构超出本期范围。
- **不引入新的运行时依赖**（`httpx`、`requests` 等）除非验证阶段证明必须。

## Functional Requirements

1. **F1 — search-API-only 替代方案验证**：本期内必须先实现一个验证脚本或一次实测，对比"使用 `downloads.range` 14 天斜率得出的新锐榜 top-30"与"仅使用 search API 返回的 `downloads.weekly`/`monthly` 比值得出的新锐榜 top-30"两份榜单的差异。差异阈值由 explore/research 阶段定义，重叠率与排名相关性都要可量化。
2. **F2 — 条件分支处理**：基于 F1 的验证结果，落实下述两条之一：
   - **F2a（如验证通过）**：从 `pi_trending.py` 中删去对 `api.npmjs.org/downloads/range` 的全部调用（`_fetch_range_data` 及其在 `main()` 中的调用点），新锐榜 score 公式改用搜索 API 自带的 weekly/monthly 比值。**此时不引入缓存**。
   - **F2b（如验证不通过）**：保留现有 range 调用结构，新增会话级临时缓存层，命中时跳过对应 HTTP 请求。缓存粒度等细节回到决策环节再敲定（见 Open Question Q1）。
3. **F3 — 输出条数参数化**：CLI 接受 `--main-max` / `--rising-max`（或同等名称的参数），默认值改为 30，最大值 = 候选池上限（不设硬上限，超过即按候选池上限自然截断）。SKILL.md 同步更新参数说明与示例。

## Non-Functional Requirements

- **Performance**：
  - 在 F2a 路径下，单次跑完应仅需 search API 的 2 次 HTTP 调用，总耗时预期 ≤ 5s（取决于网络）。
  - 在 F2b 路径下，**首次冷启动按现状不恶化**（仍 16-38s 区间），同一缓存窗口内的二次以上调用 ≤ 1s。
  - 验证脚本本身耗时不计入 SLA。
- **Security**：无。脚本只读 npm 公开 API，无凭据、无写远端。临时缓存放 `tempfile.gettempdir()`，不要写入用户主目录。
- **UX / Accessibility**：现有命令行交互保持不变，新参数不破坏老调用方式（默认行为只改输出条数 20→30）。
- **Reliability**：
  - 验证脚本必须能复现，结果可量化。
  - F2a 落地后，因依赖端点从 2 个降到 1 个，整体故障面减小。
  - F2b 落地后，缓存读写失败必须降级为绕过缓存直拉，不能让缓存层成为新的失败源。

## Constraints & Assumptions

- **运行时**：`uv run --script` PEP 723 单文件脚本模式；保留尽量少的第三方依赖（当前只用 stdlib `urllib`）。
- **数据源**：仅限 `registry.npmjs.org` 与 `api.npmjs.org`。npmmirror 不提供下载量 API；GitHub Stars 作 proxy 不可行（已在调研中排除）。
- **限流模型假设**：限流为 per-IP、Cloudflare 层、阈值不公开、429 不一定带 `Retry-After`。无法通过加 token 豁免（社区请求 #179506 至今 dormant）。
- **scoped 包批量端点假设**：官方文档明确"scoped packages are not yet supported in bulk queries"，本期不指望它出现。
- **search API 字段假设**：search API 响应每个 package 对象里**确实**包含 `downloads.weekly` / `downloads.monthly`——这一点需在 F1 验证脚本里第一步打印确认。
- **黑马识别假设**：用户认为新锐发现必须看到 weekly ≥ 200 的全部候选，不能裁剪。F2a 替代是否破坏黑马识别——这是 F1 要回答的核心问题。

## Acceptance Criteria

- [ ] **F1 验证产出**：仓库下存在一份验证报告（建议放 `pi-agent/pi-trending/`下或 `.rpiv/artifacts/research/`），内容包含：(a) search API 响应是否含 `downloads.weekly`/`monthly` 字段的实测证据；(b) 同一时刻两种 score 公式产出的新锐榜 top-30 列表对比；(c) 重叠率（如 `len(set(A) & set(B)) / 30`）和 Spearman 等级相关系数等量化指标；(d) 一句话结论"可替代"或"不可替代"。
- [ ] **F2 二选一落地**：取决于 F1 结论：
  - 若可替代：`uv run --script pi-agent/pi-trending/scripts/pi_trending.py` 执行后用 `rg "downloads/range" pi-agent/pi-trending/scripts/pi_trending.py` 应返回零行；脚本运行 `time uv run --script pi-agent/pi-trending/scripts/pi_trending.py` 应在 ≤ 10s 内退出（含网络往返）。
  - 若不可替代：临时目录下出现命中文件（`ls -la $(python -c 'import tempfile; print(tempfile.gettempdir())') | grep pi-trending`），同一窗口内第二次跑 ≤ 1s。
- [ ] **F3 参数化**：`uv run --script pi-agent/pi-trending/scripts/pi_trending.py --main-max 50 --rising-max 50` 正常输出 50 条主流榜与 50 条新锐榜（受候选池上限自然截断）；不带参数时输出各 30 条；SKILL.md 中能 grep 到新参数的使用示例。
- [ ] **回归**：跑一次默认调用，主观上"不再卡"——以"二次跑命中"或"首次只需 ≤ 5s"为体感门槛（具体取决于走的是 F2a 还是 F2b 路径）。

## Recommended Approach

按 explore/research 顺序处理：(1) 先在 `pi-agent/pi-trending/` 下实现一个独立的 F1 验证脚本，仅用 stdlib `urllib`，输出两份榜单 + 重叠/相关性指标 + 结论；(2) 根据结论分叉走 F2a（删 range 调用、改写 score 公式）或 F2b（新增 `tempfile.gettempdir()` 下的 JSON 缓存层）；(3) F3 输出参数化与 F2 同步落地。

## Decisions

### D0 — 焦点是交互延迟还是可靠性？
**Question**: 脚本超时这个问题，你最在意哪一面？
**Recommended**: n/a — `intent` 问题
**Chosen**: 我自己跑的时候等太久，想要更快出结果（日常使用者交互延迟视角）
**Rationale**: 用户原话；锁定本期目标为缩短交互延迟，不是修复"返回部分数据"或"硬 deadline"。

### D1 — 是否引入持久化缓存
**Question**: 脚本现在完全没有缓存（`pi_trending.py` 全文无 cache/disk 读写）。加不加？
**Recommended**: 加缓存
**Chosen**: 不加（在第一轮回答时）；后改为**条件化**——若 search API 字段不能替代 range 调用，再考虑会话级临时缓存（决策 D5 / Open Q1）
**Rationale**: 用户原话"缓存没有必要，因为本来这个技能的执行就不会太频繁，我预期比如一天两天才会看一次"；后续在 D5 中引入"先验证"约束，使缓存决策依赖于 F1 验证结果。

### D2 — 是否提升 unscoped 批处理并发度
**Question**: 无作用域包现在是串行批处理（`pi_trending.py:230-248`），同文件里有作用域包是 8 线程并行（L255）。改不改为一致？
**Recommended**: 改为一致（并行化）
**Chosen**: 维持串行
**Rationale**: 用户原话"是有意为之，留着串行"——意在避免加剧 npm 限流。后续调研也佐证"限流是瓶颈、加并发只会更糟"。

### D3 — 是否裁剪候选池
**Question**: 现在脚本为所有 weekly ≥ 200 的包（可能 300-400 个）拉 14 天下载趋势，但只展示 top-20 新锐。要不要裁裁候选池？
**Recommended**: 不裁，保留完整候选池
**Chosen**: 不裁
**Rationale**: 用户原话"目前的候选池大小最好能保留，因为这样就不会错过那些黑马了"；evidence: `pi_trending.py:425-433, 437`。

### D4 — 加速来源选哪条
**Question**: 除外，还有哪些加速可走？连接复用 / 压缩 retry 预算 / 流式输出 / 其它？
**Recommended**: HTTP 连接复用（次推荐：流式输出）
**Chosen**: 先调研 npm 限流应对方案，根据调研结果再定
**Rationale**: 用户判断主要卡点是 npm 限流，要求先用 GitHub research 定位真因再下结论。调研结果（见 References）颠覆了"加速来源"问题——发现 search API 自带 weekly/monthly 字段可能直接消除 range 调用。

### D5 — 是否一并处理"换掉 range 调用"
**Question**: 考虑到临时缓存 + 输出可调是已明确需要的，这次还要不要一起处理"换掉 range 调用"这个根治选项？
**Recommended**: 只做缓存 + 输出可调（最小 diff）
**Chosen**: 需要先测试验证，能不能完全替代掉目前的功能、满足新锐榜的需求
**Rationale**: 用户原话；从"列入 Open Question"升级为"本期内必须做的验证子任务"——验证驱动后续条件分支。这把所谓的"根治选项"从 explore 里拉到本期 must-do。

### D6 — 验证未定时缓存方案是否落地
**Question**: 临时缓存的 key 粒度（按日期 / 按 PID）；输出条数参数化（默认与上限）？
**Recommended**: 缓存按日期；输出默认 20、上限 = 候选池
**Chosen**: 缓存粒度先不定（待 F1 验证结果）；输出默认 30、上限 = 候选池
**Rationale**: 用户原话"如果（search API 替代）能的话代价降低，就不需要加缓存了"；缓存决策从"必做"降级为"条件化"。输出参数化部分用户给出新约束（默认 30 而非 20）。

## Open Questions

- **Q1 — 缓存粒度**（仅 F2b 路径才需回答）：若 F1 验证不通过、需走会话级临时缓存路径，缓存 key 的粒度选哪个？候选：(a) 按日期键值（`pi-trending-YYYY-MM-DD.json`，覆盖最广、跨进程命中、实现最简单）；(b) 按当前父进程 PID（语义最贴"会话级"原话，但跨会话失效、覆盖窄）；(c) 滚动小时窗口。**等待 F1 结论再回头敲定。**
- **Q2 — F1 验证的"差异阈值"**：两份榜单 top-30 的重叠率 / 相关系数达到多少才算"可替代"？建议在下一轮 explore 中明确量化（例如重叠率 ≥ 0.85 且 Spearman ≥ 0.8 即视为可替代）。
- **Q3 — search API 与 range API 的数据时间窗对齐**：search API 的 `downloads.weekly`/`monthly` 是哪个时间区间？是否包含当天数据？这影响 F1 比对的时间口径，需在验证脚本第一步打印确认。

## Suggested Follow-ups

- **`urllib.request.urlopen()` 无连接复用**——`pi_trending.py:93`：每个请求新建 TCP+TLS。本期不动（如走 F2a 后只剩 2 次 HTTP 调用，连接复用收益微乎其微）；如果将来回到多请求路径再考虑切到 `httpx.Client` / `requests.Session`。
- **`_json_get` retry 预算偏长**——`pi_trending.py:83, 89-108`：默认 `timeout=15, retries=3`，最坏单请求 ~48s。本期不动（限流根因若被消除，retry 自然不会触发）；如果未来仍频繁超时，可独立做一轮"压缩 retry 预算"的小修。
- **SKILL.md 缺性能预算声明**——`pi-agent/pi-trending/SKILL.md` 全文无 SLA / 预期耗时；建议在 F2 落地后顺手补一段"预期 ≤ X 秒"。
- **跨日期一致性的预计算方案**（业界主流做法，参考 npm-stat / TanStack / libraries.io）：每日 GitHub Action 跑一次全量、产出 JSON 静态文件、运行时直接读。这是更彻底的方案，但超出本期范围。

## References

- 输入：用户原话 "之前优化了一版 @pi-agent/pi-trending/，出现了脚本经常超时的问题，我想解决这个问题"
- 源码：`pi-agent/pi-trending/scripts/pi_trending.py`（453 行）；`pi-agent/pi-trending/SKILL.md`（236 行）
- 关键 evidence 行：
  - 限流防护痕迹（已是当前现状）：`pi_trending.py:230-248`（unscoped 串行 + 批间 sleep 0.1s）；`pi_trending.py:255`（scoped 8 线程）
  - 重试模型：`pi_trending.py:83, 89-108`（`_json_get` 默认 timeout=15, retries=3）
  - 候选池规模：`pi_trending.py:170, 425-433`（max_pages=2 → 500 包；weekly ≥ 200 阈值）
  - score 公式（待 F1 验证后可能重写）：`pi_trending.py:269-291`
- 调研产出（见本会话内 web-search-researcher 报告）：
  - npm registry 限流为 per-IP Cloudflare 层、阈值不公开、无 token 豁免：[npm/feedback#658](https://github.com/npm/feedback/discussions/658)、[community#179506](https://github.com/orgs/community/discussions/179506)
  - scoped 包无批量端点（官方文档）：[npm/registry download-counts.md](https://github.com/npm/registry/blob/master/docs/download-counts.md#bulk-queries)
  - search API 自带 downloads 字段：[npm api docs - search](https://api-docs.npmjs.com/#tag/search)
  - 同类项目实践：[pvorb/npm-stat.com](https://github.com/pvorb/npm-stat.com)（每日预拉取）、[tanstack/tanstack.com](https://github.com/tanstack/tanstack.com)（24h TTL + 8 并发 + 6h 刷新）、[librariesio/libraries.io](https://github.com/librariesio/libraries.io)（自建 DB）
