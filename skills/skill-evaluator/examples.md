# 完整评估案例：MarkItDown Skills 对比

本案例演示了从搜索到推荐的完整评估流程，以 "PDF/文档转 Markdown" 需求为例。

---

## 阶段 1：搜索候选

### 执行搜索

```bash
bunx skills find markitdown
```

### 搜索结果

找到 6 个候选 skills：

| # | Skill 名称 | 安装量 | 来源仓库 |
|---|-----------|--------|---------|
| 1 | davila7/claude-code-templates@markitdown | 645 | github.com/davila7/claude-code-templates |
| 2 | julianobarbosa/claude-code-skills@markitdown-skill | 83 | github.com/julianobarbosa/claude-code-skills |
| 3 | rysweet/amplihack@markitdown | 62 | github.com/rysweet/amplihack |
| 4 | ovachiever/droid-tings@markitdown | 36 | github.com/ovachiever/droid-tings |
| 5 | jackspace/claudeskillz@markitdown | 34 | github.com/jackspace/claudeskillz |
| 6 | smallnest/langgraphgo@markitdown | 26 | github.com/smallnest/langgraphgo |

---

## 阶段 2：信息收集

### 2.1 功能详情（并行访问 skills.sh 页面）

访问每个 skill 的详情页面：
- `https://skills.sh/davila7/claude-code-templates/markitdown`
- `https://skills.sh/julianobarbosa/claude-code-skills/markitdown-skill`
- `https://skills.sh/rysweet/amplihack/markitdown`
- 等等...

### 2.2 仓库活跃度（并行访问 GitHub）

访问仓库主页获取 stars/forks/issues：
- `https://github.com/davila7/claude-code-templates` → 24.5k stars, 2.4k forks
- `https://github.com/rysweet/amplihack` → 46 stars, 33 forks
- `https://github.com/julianobarbosa/claude-code-skills` → 52 stars, 12 forks
- 等等...

### 2.3 更新频率（并行调用 GitHub API）

调用 API 获取最近提交：
```
https://api.github.com/repos/davila7/claude-code-templates/commits?per_page=5
https://api.github.com/repos/rysweet/amplihack/commits?per_page=5
https://api.github.com/repos/julianobarbosa/claude-code-skills/commits?per_page=5
```

从返回的 `commit.author.date` 字段分析：
- davila7：每天 2-5 次提交 → **高度活跃**
- rysweet：每周 3-5 次 → **活跃维护**
- julianobarbosa：每 1-2 周一次 → **维护中**
- ovachiever：4.5 个月未更新 → **已停止**
- jackspace：4.8 个月未更新 → **已停止**

### 2.4 信息汇总表

| 指标 | davila7 | julianobarbosa | rysweet | ovachiever | jackspace | smallnest |
|------|---------|---------------|---------|------------|-----------|-----------|
| 安装量 | 645 | 83 | 62 | 36 | 34 | 26 |
| Stars | 24.5k | 52 | 46 | 35 | 14 | 229 |
| 最近提交 | 今天 | 10天前 | 昨天 | 4.5月前 | 4.8月前 | 1.5月前 |
| 更新频率 | 每日多次 | 每周几次 | 每周多次 | 已停止 | 已停止 | 每月几次 |
| Agent Trust Hub | Fail | Warn | Pass | Pass | Pass | Fail |
| Socket | Pass | Pass | Pass | Pass | Pass | Pass |
| Snyk | Warn | Warn | Warn | Warn | Warn | Warn |

---

## 阶段 3：安全评估

### 3.1 读取源码

访问每个 skill 的 SKILL.md：
```
https://raw.githubusercontent.com/davila7/claude-code-templates/main/skills/markitdown/SKILL.md
https://raw.githubusercontent.com/rysweet/amplihack/main/.claude/skills/markitdown/SKILL.md
```

同时读取引用的文件（如有）：
```
https://raw.githubusercontent.com/rysweet/amplihack/main/.claude/skills/markitdown/patterns.md
https://raw.githubusercontent.com/rysweet/amplihack/main/.claude/skills/markitdown/reference.md
```

### 3.2 安全审计结果

#### davila7/claude-code-templates

**安全评分：6.5/10（中等风险）**

| 维度 | 评级 | 发现 |
|------|------|------|
| Prompt 注入 | ✅ 通过 | 无隐藏指令 |
| 凭证处理 | ⚠️ 警告 | 示例使用 `api_key="your-openrouter-api-key"` 字面量；`--api-key` CLI 参数暴露到 shell 历史 |
| 代码执行 | ✅ 通过 | 无 eval/exec/subprocess |
| 数据外泄 | ⚠️ 警告 | AI 功能启用时文档内容发送到 OpenRouter/Azure |
| 文件系统 | ⚠️ 警告 | 路径未做穿越防护 |
| 插件系统 | ❌ 高风险 | entry_points 加载任意 pip 包，无签名验证 |
| 混淆内容 | ✅ 通过 | 无 |

**关键问题：**
- `allowed-tools: [Read, Write, Edit, Bash]` 授予无限制 shell 权限
- 插件系统默认可能启用，任何 pip 包可注册为转换器执行任意代码

#### rysweet/amplihack

**安全评分：8.5/10（低风险）**

| 维度 | 评级 | 发现 |
|------|------|------|
| Prompt 注入 | ✅ 通过 | 无隐藏指令 |
| 凭证处理 | ✅ 通过 | 强调 NEVER 硬编码；使用 `os.getenv()` |
| 代码执行 | ✅ 通过 | 无 eval/exec/subprocess |
| 数据外泄 | ⚠️ 注意 | 与 davila7 相同（预期行为） |
| 文件系统 | ✅ 通过 | 明确列出路径遍历为反模式并提供修复代码 |
| 插件系统 | ⚠️ 注意 | 默认禁用 |
| 混淆内容 | ✅ 通过 | 无 |

**安全加分项：**
- 独立 `patterns.md` 专章详述安全模式
- 提供 `SecureConverter`（MIME 验证 + 大小限制）
- 提供 `SandboxedConverter`（临时目录隔离）
- 有速率限制、熔断器实现

### 3.3 仓库信誉

| 指标 | davila7 | rysweet |
|------|---------|---------|
| 维护者 | davila7 + CI/CD 自动化 | rysweet + 多人团队 |
| 提交验证 | 部分 Verified | 大部分 Verified |
| Issues 响应 | 68 开放 issues | 265 开放 issues（项目更大） |
| 安全修复 | 无公开记录 | 有 heredoc injection 修复记录 |

---

## 阶段 4：对比与推荐

### 4.1 综合对比表

| 指标 | davila7 | rysweet |
|------|---------|---------|
| 安装量 | 645 ✅ | 62 |
| Stars | 24.5k ✅ | 46 |
| 更新频率 | 每日多次 ✅ | 每周多次 ✅ |
| 安全评分 | 6.5/10 ⚠️ | 8.5/10 ✅ |
| Agent Trust Hub | Fail ❌ | Pass ✅ |
| 安全文档 | 零散提及 | 独立专章 ✅ |
| 功能完整度 | 最全（含科学图表）✅ | 标准功能 |

### 4.2 分级推荐

**安全优先型用户：**
> 推荐 `rysweet/amplihack@markitdown`
> 理由：安全评分最高（8.5/10），Agent Trust Hub 通过，有完整安全文档和实现，插件默认禁用

**功能优先型用户：**
> 推荐 `davila7/claude-code-templates@markitdown`
> 理由：功能最全（含科学图表生成），更新最活跃（每日多次），社区验证最多（645 安装，24.5k stars）

**组合安装策略（推荐）：**
> 同时安装两个 skills：
> - 日常使用 davila7（功能全、更新快）
> - 安全参考用 rysweet（最佳实践、安全实现）

### 4.3 安装命令

```bash
# 安全优先
bunx skills add rysweet/amplihack@markitdown -g -y

# 功能优先
bunx skills add davila7/claude-code-templates@markitdown -g -y
```

### 4.4 安装后验证

安装完成后检查：
- 安装路径：`~/.agents/skills/markitdown`
- 安全审计结果与预期一致
- 提醒用户：安装后审查 SKILL.md 内容再使用

---

## 关键教训

1. **安装量不是唯一指标** — davila7 安装量最高但安全评分较低
2. **Agent Trust Hub Fail 是重要警示** — 通常与权限过大或插件系统有关
3. **更新频率反映维护状态** — 超过 4 个月未更新的 skill 大概率已停止维护
4. **安全文档质量是重要加分项** — 有独立安全章节的 skill 通常更可靠
5. **插件系统是主要风险面** — 默认启用且无验证的插件系统应视为高风险

---

## 实战案例：Fallback 策略演示（搜索清理 home 目录 skill）

本案例演示当 `web_extract` 被拦截、`bunx skills find` 超时时，如何用备用方案获取 skill 信息。

### 问题

用户需求：搜索清理 home 目录的 skill。`web_extract` 将 GitHub/skills.sh 判定为内网地址拒绝访问，`bunx skills find` 超时。

### 解决方案

**步骤 1：并行搜索 SkillHub + GitHub API**

```bash
# SkillHub 搜索
skillhub search clean home directory

# GitHub API 搜索
curl -s "https://api.github.com/search/repositories?q=home+cleanup+skill+agent" \
  | jq '.items[] | {full_name, stars: .stargazers_count, updated: .pushed_at}'
```

结果：找到 `b4dnewz/clean-home-dir`（SkillHub slug）和 GitHub 仓库。

**步骤 2：Git Clone 获取完整源码**

```bash
TMPDIR=$(mktemp -d)
git clone --depth 1 "https://github.com/b4dnewz/clean-home-dir.git" "$TMPDIR"

# 查看文件结构
find "$TMPDIR" -type f
# 输出：
#   SKILL.md
#   scripts/analyze.sh
#   scripts/cleanup.sh
#   references/defaults.md
```

**步骤 3：本地读取所有文件**

```bash
cat "$TMPDIR/SKILL.md"
find "$TMPDIR/scripts" -type f | while read f; do echo "=== $f ==="; cat "$f"; done
```

**步骤 4：安全审计**

检查 `scripts/analyze.sh` 和 `scripts/cleanup.sh`：
- 无 eval/exec
- 无数据外泄
- 路径硬编码：`$HOME`（正确，使用环境变量而非写死路径）
- 有 `--dry-run` 模式
- 有 before/after 磁盘使用对比

**步骤 5：GitHub API 获取元数据**

```bash
curl -s "https://api.github.com/repos/b4dnewz/clean-home-dir" | jq '{stargazers_count, forks_count, pushed_at, description, license}'
# 输出：
# {
#   "stargazers_count": 320,
#   "forks_count": 8,
#   "pushed_at": "2026-01-15T10:30:00Z",
#   "description": "Clean up home directory files - analyze and cleanup unnecessary files",
#   "license": { "spdx_id": "MIT" }
# }
```

**步骤 6：SkillHub 详情页面**

```bash
# 用 curl 直接访问（web_extract 被拦截时）
curl -sL "https://skills.sh/b4dnewz/clean-home-dir/clean-home-dir" | head -500
```

**步骤 7：清理临时目录**

```bash
rm -rf "$TMPDIR"
```

### 结果

最终推荐：
> 推荐 `b4dnewz/clean-home-dir@clean-home-dir`
>
> - GitHub 320 stars，MIT 许可证，2026-01-15 更新
> - 安全评分 8.5/10（无致命风险）
> - `--dry-run` 安全模式，`$HOME` 环境变量（无硬编码路径）
> - 附带 analyze.sh + cleanup.sh 两个脚本
> - Agent Trust Hub 通过
