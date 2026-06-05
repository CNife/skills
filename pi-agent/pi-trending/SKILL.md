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

## 快速概览

运行一次命令，直接拿到 Markdown 表格（LLM 友好）：包的排名、名称、作者、趋势分、一句话介绍（英文 description）。
支持按类型筛选、JSON 输出、`--verbose` 调试、调整数量。不带任何参数时展示 Top 20。

**AI 展示环节**：获取脚本输出的表格后，AI 应自动将「一句话介绍」列的英文 description**翻译为中文并精简到 20 字以内**，再展示给用户。翻译失败的 description 保留原文。

```bash
uv run --script scripts/pi_trending.py
```

## 原理

- **数据源**：npm registry（含 `pi-package` keyword 的 npm 包）
- **核心类型**：`extension` · `skill` · `theme` · `prompt`（通过 npm keywords 自动识别）
- **趋势算法**：`trending_score = this_week² / (prev_week + 100)`
  - 本周下载量与上周下载量的比值，平方放大加速迹象
  - `+100` 平滑新包（防止除零）
  - 分数越高 → 近期增长越快，而非绝对下载量高
- **搜索策略**：逐页获取 npm search API，智能收敛——当新页面的最高周下载低于当前 Top N 门槛即停止

## 脚本位置

`scripts/pi_trending.py` — 基于 uv 的 PEP 723 单文件脚本，自动托管依赖。

## 使用工作流

### 1. 用户问"最近有什么热门的 pi 包"

直接运行默认命令，获取 Top 20 趋势表：

```bash
uv run --script scripts/pi_trending.py
```

脚本输出（Markdown 表格，description 为英文原文）：

```text
| # | 包名 | 作者 | 趋势分 | 一句话介绍 |
|---|------|------|--------|------------|
| 1 | `@pi/core` | user | 89,234 | A core framework for building pi extensions |
```

**AI 翻译后展示**（对「一句话介绍」列逐行翻译为中文并精简）：

```text
| # | 包名 | 作者 | 趋势分 | 一句话介绍 |
|---|------|------|--------|------------|
| 1 | `@pi/core` | user | 89,234 | pi 扩展核心框架 |
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

### 3. 用户想只看 Top N

```bash
uv run --script scripts/pi_trending.py --max 10
```

### 4. 用户需要调试/查看详细日志

```bash
uv run --script scripts/pi_trending.py --verbose
```

输出 API 请求进度、分页情况、候选包筛选决策等到 stderr，不影响 stdout 的 Markdown 结果。

### 5. 用户需要结构化数据（管道给 jq 等）

```bash
uv run --script scripts/pi_trending.py --json

# 结合 jq 只看包名
uv run --script scripts/pi_trending.py --json | jq '.[].name'
```

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

## 结果解读

趋势分（trending_score）反映的是**增长速度**而非绝对热度：

| 趋势分 | 含义 |
|--------|------|
| ≥50,000 | 🚀 爆发式增长，最近一周下载量相比前一周有巨大提升 |
| ≥10,000 | 🔥 快速上升，社区关注度在显著增加 |
| ≥1,000  | 📈 温和增长，正在积累用户 |
| <1,000  | 📊 平稳或波动较小 |

⚠️ **注意事项**：

- 新包首次进入榜单时趋势分可能偏低（缺少历史数据）
- 成熟稳定的大包（如核心框架）趋势分可能不高，但绝对下载量依然巨大
- **趋势分**反映增长速度，建议结合 JSON 输出的 `weekly_downloads` 一起评估（`--json`）
