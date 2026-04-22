---
name: audit-hermes-agent-skills
description: >
  Audit installed Hermes Agent skills for usage frequency and heat analysis.
  Scans all installed skills in ~/.hermes/skills/, queries state.db for
  skill_view/skill_manage calls, calculates time-decayed heat scores using
  exponential decay (Reddit/HN style), identifies skill sources (builtin/
  external/standalone), and generates cleanup recommendations with backup.
  Use when the user asks about Hermes skill usage statistics, wants to clean
  up unused Hermes skills, needs to disable low-usage skills, or mentions
  "技能审计", "清理技能", "不用的技能", "哪些技能可以删", "skill audit",
  "unused skills", "cleanup skills", "remove skills", "skill heat", "技能热度",
  "技能使用频率", "技能调用历史", "audit hermes skills". This skill is specific
  to Hermes Agent — do not use for other agents. Make sure to load this skill
  whenever Hermes skill management, cleanup, or usage analysis is mentioned.
---

# Audit Hermes Agent Skills

审计 Hermes Agent 已安装技能的使用频率，识别长期不使用的技能并安全清理。

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

**必须使用 uv 运行脚本**（自动管理依赖）：

```bash
uv run ~/.hermes/skills/audit-hermes-agent-skills/scripts/audit-hermes-agent-skills.py
```

### 第一步：运行审计（默认 dry-run）

```bash
uv run audit-hermes-agent-skills.py
```

生成审计报告，列出所有技能的热度排名、零调用技能列表、清理建议。

### 第二步：审查报告

报告分组展示：
- 🔥🟢🟡🟠⚪ 有调用的技能（按热度排序）
- 🗑️ 建议删除的 external/standalone 零调用技能
- ⚠️ 建议禁用的 builtin 零调用技能（按分类分组）

### 第三步：确认清理

用户确认后执行实际清理：

```bash
uv run audit-hermes-agent-skills.py --execute
```

清理前自动备份所有目标技能到 `~/.hermes/skills/.audit-backups/skills-backup-<timestamp>.tar.gz`。

## 清理策略

### 外部/独立技能
直接删除目录，不影响 Hermes 核心功能。

### 内置技能（builtin）— 分两类，清理策略不同！

#### Bundled skills（`hermes-agent/skills/`）
Hermes 每次启动时通过 `tools/skills_sync.py` 自动同步到 `~/.hermes/skills/`。
- **不要删除目录**，Hermes 升级/重启后会自动恢复
- 正确做法：添加到 `~/.hermes/config.yaml` 的 `skills.disabled` 列表
- 需要时可从 config 移除重新启用

#### Optional skills（`hermes-agent/optional-skills/`）
官方可选技能，需通过 `hermes skills install` 手动安装。
- **`sync_skills()` 不会同步这些技能**（它只扫描 `skills/` 目录，第 49 行：`Path(__file__).parent.parent / "skills"`）
- 删除 `~/.hermes/skills/` 下的 optional skills 副本后**不会自动恢复**
- 可以直接删除，需要时用 `hermes skills install` 重新安装

> ⚠️ 关键区别：审计脚本必须同时检查 `skills/` 和 `optional-skills/` 两个目录才能正确识别 builtin 副本，否则会误判为 standalone。

## 脚本检测逻辑

脚本通过以下规则判断技能来源（优先级从高到低）：

1. **external**：在 `~/.agents/skills/` 下存在 → 全局共享（所有 Agent 共用）
2. **builtin**：在 `~/.hermes/skills/` 下，同时 `hermes-agent/skills/` 或 `hermes-agent/optional-skills/` 递归目录中存在同名 SKILL.md → 内置副本
3. **standalone**：仅在 `~/.hermes/skills/` 下存在 → 独立安装

> 注意：MLOps 等技能嵌套在二级子目录下（如 `mlops/training/axolotl/`），必须使用 `rglob("SKILL.md")` 递归搜索，不能只用一层 `iterdir()`。

## 备份恢复

```bash
# 查看备份
ls -la ~/.hermes/skills/.audit-backups/

# 恢复单个技能
tar -xzf ~/.hermes/skills/.audit-backups/skills-backup-<timestamp>.tar.gz <skill-name> -C ~/.hermes/skills/
```

## 注意事项

- dry-run 模式不修改任何文件
- 使用 `--execute` 参数才会实际清理
- config.yaml 修改会合并现有 disabled 列表而非覆盖
