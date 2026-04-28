---
name: audit-hermes-agent-skills
description: >
  Audit installed Hermes Agent skills for usage frequency and heat analysis.
  Uses hermes internal API (_find_all_skills, _read_manifest, HubLockFile) as
  authoritative source for skill classification (hub/builtin/local/external),
  combined with filesystem scanning for directory paths. Queries state.db for
  skill_view/skill_manage calls, calculates time-decayed heat scores using
  exponential decay (Reddit/HN style), generates terminal audit report AND
  an interactive XLSX with Chinese descriptions, dropdown decision columns,
  and color-coded recommendations. Supports decision-based execution:
  read decisions from XLSX and apply (delete/disable/enable) accordingly.
  Smart filtering: already-disabled skills are not re-suggested for cleanup.
  Use when the user asks about Hermes skill usage statistics, wants to clean
  up unused Hermes skills, needs to disable low-usage skills, or mentions
  "技能审计", "清理技能", "不用的技能", "哪些技能可以删",
  "skill audit", "unused skills", "cleanup skills", "remove skills", "skill heat",
  "技能热度", "技能使用频率", "技能调用历史", "audit hermes skills". This skill
  is specific to Hermes Agent — do not use for other agents. Make sure to load
  this skill whenever Hermes skill management, cleanup, or usage analysis is
  mentioned.
---

# Audit Hermes Agent Skills

审计 Hermes Agent 已安装技能的使用频率，识别长期不使用的技能并安全清理。

通过 hermes 内部 API（`_find_all_skills`、`_read_manifest`、`HubLockFile`）获取权威的技能来源分类（hub/builtin/local/external），结合文件系统扫描定位实际目录路径。

本技能提供两个输出通道：
1. **终端报告** — 直接打印热度排名和清理建议
2. **XLSX 表格** — 含中文描述、下拉菜单决策列、颜色标记，用户填写后执行

## 核心原理

技能调用记录存储在 `~/.hermes/state.db` 的 `messages.tool_calls` 字段中。通过解析 `skill_view` 和 `skill_manage` 工具调用，统计每个技能的调用历史。

### 热度算法：指数衰减加权

参考 Reddit Hot 和 Hacker News Gravity 算法：

```
score = Σ e^(-λ × days_ago)
```

半衰期设计：3 天 / 7 天 / 30 天 / 90 天 四个窗口，综合分数加权融合，近期调用权重更高。

### 热度分级

| 等级 | 条件 | 含义 |
|------|------|------|
| 🔥 活跃 | 近 3 天有调用 + score_3d > 2 | 当前高频使用 |
| 🟢 常用 | 近 7 天有调用 + score_7d > 1 | 每周都在用 |
| 🟡 偶尔 | 近 30 天有调用 | 月度低频使用 |
| 🟠 历史 | 近 90 天有调用，30 天内无 | 季度偶尔用 |
| ⚪ 冷备 | 90 天前有调用，近 90 天无 | 历史用过 |
| ❌ 零调用 | 全部历史无调用 | 从未使用 |

## 使用方法

**所有脚本必须使用 uv 运行**（自动管理依赖）：

### 第一步：运行终端审计

```bash
uv run ~/.hermes/skills/audit-hermes-agent-skills/scripts/audit-hermes-agent-skills.py
```

生成终端审计报告，列出热度排名、零调用技能列表、清理建议。

### 第二步：生成 XLSX 表格

```bash
uv run ~/.hermes/skills/audit-hermes-agent-skills/scripts/generate_audit_xlsx.py
```

生成 `技能审计报告.xlsx` 到当前目录，包含：

| 列 | 说明 |
|----|------|
| 技能名称 | Hermes 技能名 |
| 来源 | 内置 / 本地创建 / skills.sh安装 / 外部共享 |
| 启用状态 | 启用 / 禁用 |
| 描述（中文） | 中文一句话描述（含 180+ 预置翻译） |
| 审计建议 | 活跃/常用/偶尔 或 建议删除/禁用 |
| 我的决策 | 下拉框：内置=启用/禁用，其他=保留/删除 |

颜色标记：🟢绿色=活跃，🔴粉色=建议删除，🟠橙色=建议禁用，⚪灰色=已禁用。

### 第三步：用户填写决策

在 Excel 中打开，通过「我的决策」列的下拉框标记每个技能的处理方式。默认值：
- **内置技能**：启用中=「启用」，已禁用=「禁用」
- **其他技能**：默认「保留」

### 第四步：读取变更并执行

```bash
uv run ~/.hermes/skills/audit-hermes-agent-skills/scripts/read_decisions.py
```

读取 XLSX 中的「我的决策」列，汇总与默认值不同的变更：
- 标记「删除」的本地技能 → 备份后删除目录
- 标记「禁用」的内置技能 → 追加到 config.yaml disabled
- 标记「启用」的内置技能 → 从 config.yaml disabled 移除

手动按汇总执行（自动备份 config.yaml 和目标目录）。

## 清理策略

### 本地技能（local）
直接删除目录。backup 目录在 `~/.hermes/skills/.audit-backups/`。

### Hub 技能（hub）
通过 `hermes skills uninstall <name>` 卸载，同时清理 Hub 锁定文件记录。

### 外部技能（external）
位于 `~/.agents/skills/`，所有 Agent（Claude Code、OpenCode、Cursor 等）共用。删除前请确认不影响其他 Agent。

### 内置技能（builtin）
通过添加到 `~/.hermes/config.yaml` 的 `skills.disabled` 列表来禁用。从 disabled 列表中移除即可重新启用。

> ⚠️ 已禁用的零调用技能不会重复建议。如果某个 builtin 已经在 `skills.disabled` 中，审计报告会将其标记为"无需操作"。

## 脚本检测逻辑

脚本通过 **hermes 内部 API + 文件系统扫描** 双重数据源确定技能来源：

### 第一优先级：hermes 内部 API（权威来源）

脚本通过定位 `hermes` 可执行文件的 shebang 找到其 venv Python，直接调用内部模块获取结构化数据：

| 内部 API | 作用 | 返回 |
|----------|------|------|
| `_find_all_skills(skip_disabled=True)` | 扫描所有物理存在的技能（含已禁用） | 名称 + 分类 |
| `_read_manifest()` | 内置技能清单（JSON manifest） | builtin 名称集合 |
| `HubLockFile().list_installed()` | Hub 锁定文件（记录从 skills.sh 等安装的技能） | hub 安装记录 |

**来源判定**（与 `hermes skills list` CLI 完全一致）：
1. 在 hub lock 中 → `hub`
2. 名称在 builtin manifest 中 → `builtin`
3. 其余 → `local`

### 第二优先级：文件系统扫描（定位目录路径）

文件系统扫描仅用于定位技能的实际目录路径（用于备份/删除操作）和获取安装时间。当 hermes 内部 API 不可用时，fallback 到纯文件系统模式（按扫描位置判断 `local`/`external`）。

### 来源类型定义

| 来源 | 含义 | 清理方式 |
|------|------|---------|
| `builtin` | Hermes 内置技能（通过 manifest 注册） | 添加到 `config.yaml` 的 `skills.disabled` |
| `hub` | 从 skills.sh 等 Hub 源安装的技能 | `hermes skills uninstall` |
| `local` | 本地安装的技能（独立目录在 `~/.hermes/skills/`） | 直接删除目录 |
| `external` | 外部 Agent 共享技能（`~/.agents/skills/`） | 删除需谨慎，影响所有 Agent |

### 已禁用技能处理

脚本读取 `config.yaml` 的 `skills.disabled` 列表：
- 已禁用的零调用技能 → **不重复建议**（已在报告中注明"无需操作"）
- 已禁用但有历史调用的技能 → 单独列出供参考
- 未禁用的零调用 builtin → 建议添加到 `skills.disabled`

## 备份恢复

```bash
# 查看备份
ls -la ~/.hermes/skills/.audit-backups/

# 恢复单个技能
tar -xzf ~/.hermes/skills/.audit-backups/skills-backup-<timestamp>.tar.gz <skill-name> -C ~/.hermes/skills/
```

## XLSX 脚本说明

`generate_audit_xlsx.py` 使用 openpyxl 并内嵌了 180+ 个技能的中文描述翻译，依赖：
- pyyaml>=6.0（读取 SKILL.md frontmatter 和 config.yaml）
- openpyxl>=3.1（生成 xlsx）

运行方式与主审计脚本相同：`uv run generate_audit_xlsx.py`。

## 注意事项

- dry-run 模式不修改任何文件
- 使用 `--execute` 参数才会实际清理
- config.yaml 修改会合并现有 disabled 列表而非覆盖
- 修改 config.yaml 前必须备份（`cp config.yaml config.yaml.bak.$(date +%Y%m%d%H%M%S)`）
- 删除目录前先备份到 `.audit-backups/`
