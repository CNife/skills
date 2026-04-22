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

### 内置技能
不删除文件（Hermes 升级会恢复），添加到 `~/.hermes/config.yaml` 的 `skills.disabled` 列表。Hermes 加载技能时会跳过这些技能，需要时可从 config 移除重新启用。

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
