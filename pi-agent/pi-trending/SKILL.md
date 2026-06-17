---
name: pi-trending
description: >
  Discover trending Pi Agent packages — what's hot, what each package does, and
  how to track the latest pi ecosystem developments. 当用户想了解 pi 生态最新
  动态、寻找好用的扩展/技能/主题、比较包的热度、决定装什么包、或者任何涉及
  "看看 pi 社区有什么好东西" 的意图时，务必使用此技能。即使用户没有明确说
  "trending"，只要涉及发现/推荐/比较 pi 包就应该触发。
  Triggers: "最近有什么热门的 pi 包", "pi 生态有什么新项目",
  "trending pi packages", "pi trending", "有什么好用的 pi extension/skill/theme",
  "pi 包排行榜", "查看 pi 包排名", "推荐好用的 pi 包",
  "有没有新出的 pi 主题", "看看 pi 社区最近有什么新东西".
---

# Pi Trending

扫描 npm registry，发现最近🔥的 Pi Agent 包（extension / skill / theme / prompt template），
计算趋势分并汇总展示，帮助用户追踪 pi 生态的最新进展。

输出包含两个独立的榜单：

- **主流榜** — 按本周下载量排序，展示生态中当下最常用的包
- **新锐榜** — 按增速评分排序，展示正在快速蹿升的包

## 快速概览

运行一次命令，同时拿到主流榜和新锐榜两张 Markdown 表格（LLM 友好）。
支持按类型筛选、JSON 输出、`--verbose` 调试、分别控制榜单数量。不带任何参数时各展示 Top 20。

**AI 展示环节**：获取脚本输出的表格后，AI 应自动将「一句话介绍」列的英文 description**翻译为中文并精简到 20 字以内**，再展示给用户。翻译失败的 description 保留原文。

```bash
uv run --script scripts/pi_trending.py
```

## 原理

- **数据源**：npm registry（含 `pi-package` keyword 的 npm 包）
- **搜索策略**：`sort=popularity` 从 npm search API 按下载量排序采集 500 个候选包
- **核心类型**：`extension` · `skill` · `theme` · `prompt`（通过 npm keywords 自动识别）
- **主流榜算法**：按 `downloads.weekly`（search API 返回的本周下载量）倒排，零额外 API 成本
- **新锐榜算法**：`trending_score = ln(this_week + 1) × (this_week - prev_week) / (prev_week + 10)`
  - `ln` 压缩绝对规模的差异，增长率放大增速信号
  - `+10` 平滑新包（防止除零）
  - 仅增长中的包入榜（下降的包得 0 分）

## 脚本位置

`scripts/pi_trending.py` — 基于 uv 的 PEP 723 单文件脚本，自动托管依赖。

## 使用工作流

### 1. 用户问"最近有什么热门的 pi 包"

直接运行默认命令，获取主流榜 + 新锐榜：

```bash
uv run --script scripts/pi_trending.py
```

脚本输出（两个 Markdown 表格，description 为英文原文）：

```text
# 🔥 Pi Agent 最新热门包 (2026-06-17)

## 主流榜
| # | 包名 | 作者 | 本周下载量 | 一句话介绍 |
|---|------|------|-----------|------------|
| 1 | `@pi/core` | user | 12,345 | A core framework for building pi extensions |

> Top 20 · 按本周下载量排序

## 新锐榜
| # | 包名 | 作者 | 趋势分 | 一句话介绍 |
|---|------|------|--------|------------|
| 1 | `pi-context-map` | dev | 97,344 | Professional context profiler for Pi |
```

**AI 翻译后展示**（对两个榜单的「一句话介绍」列逐行翻译为中文并精简）：

```text
# 🔥 Pi Agent 最新热门包 (2026-06-17)

## 主流榜
| # | 包名 | 作者 | 本周下载量 | 一句话介绍 |
|---|------|------|-----------|------------|
| 1 | `@pi/core` | user | 12,345 | pi 扩展核心框架 |

> Top 20 · 按本周下载量排序

## 新锐榜
| # | 包名 | 作者 | 趋势分 | 一句话介绍 |
|---|------|------|--------|------------|
| 1 | `pi-context-map` | dev | 97,344 | pi 上下文分析工具 |
```

### 2. 用户想看特定类型

```bash
# 只看扩展
uv run --script scripts/pi_trending.py --type extension

# 只看技能
uv run --script scripts/pi_trending.py --type skill

# 只看主题
uv run --script scripts/pi_trending.py --type theme

# 只看 prompt 模板
uv run --script scripts/pi_trending.py --type prompt
```

类型过滤作用于候选池，两个榜单只显示该类型的包。

### 3. 用户想控制榜单大小

```bash
# 同时设置两个榜单的数量（各 10 条）
uv run --script scripts/pi_trending.py --max 10

# 分别控制
uv run --script scripts/pi_trending.py --mainstream-max 5 --rising-max 20

# 只读主流榜前 5
uv run --script scripts/pi_trending.py --mainstream-max 5 --rising-max 0
```

`--max` 同时设置两个榜单，`--mainstream-max` 和 `--rising-max` 可分别覆盖。

### 4. 用户需要调试/查看详细日志

```bash
uv run --script scripts/pi_trending.py --verbose
```

输出 API 请求进度、分页情况、候选包数量等到 stderr，不影响 stdout 的结果。

### 5. 用户需要结构化数据（管道给 jq 等）

```bash
uv run --script scripts/pi_trending.py --json

# 只读主流榜包名
uv run --script scripts/pi_trending.py --json | jq '.[] | select(.list_type == "mainstream") | .name'

# 只读新锐榜包名
uv run --script scripts/pi_trending.py --json | jq '.[] | select(.list_type == "rising") | .name'
```

JSON 输出包含 `list_type` 字段（`"mainstream"` 或 `"rising"`）区分榜单。

### 6. 用户问"XXX 包是做什么的"

趋势表中的包名可以直接用 npm registry 查详情，包括 README：

```bash
# 看 description（快速摘要）
npm view <包名> description

# 看完整 README（了解功能、用法）
npm view <包名> readme

# 看全部元数据
npm view <包名>
```

包名含 `@scope/` 前缀时同样适用，例如：

```bash
npm view @pi/core description
npm view @pi/core readme
```

### 7. 帮助用户决定装什么

当用户看中某个包想安装时，根据包类型给出安装提示：

- **pi-extension** → `bunx pi extension install <name>`
- **pi-skill** → `bunx skills add <name>` 或 `bunx skills add <gh-repo>`
- **pi-theme** → `bunx pi theme install <name>` 或参照主题安装指南
- **prompt-template** → `bunx pi prompt install <name>` 或写入 prompt-templates 目录

### 8. 用户问"XXX 包最近更新了什么"

趋势表里的包上升快，用户很可能追问"最近有什么变化"。用以下流程追溯近一周的变更：

```bash
# 1. 查版本发布时间线（快速了解活跃度）
npm view <包名> time --json

# 2. 找到 GitHub 仓库
npm view <包名> repository

# 3. 看 GitHub Release 说明（含 changelog）
gh release view <tag> --repo <owner/repo> --json body

# 4. 看近 30 条 commit（最细粒度）
gh api "repos/<owner/repo>/commits?per_page=30" \
  --jq '.[] | "\(.sha[0:7]) \(.commit.committer.date[0:10]) \(.commit.message | split("\n")[0])"'

# 5. 大版本间差异
gh api repos/<owner/repo>/compare/v1.0.0...v2.0.0 \
  --jq '.commits[] | "\(.sha[0:7]) \(.commit.message | split("\n")[0])"'
```

**分析要点**：

- 版本发布时间密集度 → 开发活跃度信号
- 版本号跳跃（如 1.x → 2.0）→ 重大重构或生产硬化
- 若用户追问某个特定版本号，直接 `npm view <包名> readme` 看 README 中的 changelog 段落

详细工作流见 `references/package-changelog-investigation.md`。

## 结果解读

### 主流榜

主流榜的排序依据是 `weekly_downloads`（npm search API 返回的本周下载量），反映的是**当下最常用的包**。适合回答"大家都在用什么"。

### 新锐榜

新锐榜的排序依据是 `trending_score`（增速评分），反映的是**增长速度**而非绝对热度：

| 趋势分 | 含义 |
|--------|------|
| ≥50,000 | 🚀 爆发式增长，最近一周下载量相比前一周有巨大提升 |
| ≥10,000 | 🔥 快速上升，社区关注度在显著增加 |
| ≥1,000  | 📈 温和增长，正在积累用户 |
| <1,000  | 📊 平稳或波动较小 |

⚠️ **注意事项**：

- 新包首次进入榜单时趋势分可能偏低（缺少历史数据）
- 成熟稳定的大包（如核心框架）主流榜排名靠前，但新锐榜趋势分可能不高
- **趋势分**反映增长速度，建议结合 JSON 输出的 `weekly_downloads` 一起评估（`--json`）
- 同一包可以同时出现在两个榜中（互不冲突）
