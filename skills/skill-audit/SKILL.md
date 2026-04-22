---
name: skill-audit
description: >
  Audit installed Hermes Agent skills for usage frequency and heat analysis.
  Scans all installed skills, queries state.db for skill_view/skill_manage calls,
  calculates time-decayed heat scores using exponential decay (Reddit/HN style),
  identifies skill sources (builtin/external/standalone), and generates cleanup
  recommendations with backup. Use when the user asks about skill usage statistics,
  wants to clean up unused skills, needs to disable low-usage skills, or mentions
  "技能审计", "清理技能", "不用的技能", "哪些技能可以删", "skill audit",
  "unused skills", "cleanup skills", "remove skills", "skill heat", "技能热度",
  "技能使用频率", "技能调用历史". Make sure to load this skill whenever skill
  management, cleanup, or usage analysis is mentioned — even if the user doesn't
  explicitly say "audit". The audit always runs in dry-run mode first, showing
  the report and waiting for user confirmation before any deletion or disable action.
---

# Skill Audit

审计 Hermes Agent 已安装技能的使用频率，识别长期不使用的技能并安全清理。

## 核心原理

技能调用记录存储在 `~/.hermes/state.db` 的 `messages.tool_calls` 字段中。通过解析 `skill_view` 和 `skill_manage` 工具调用，可以统计每个技能的调用历史。

### 热度算法：指数衰减加权

参考 Reddit Hot 和 Hacker News Gravity 算法，使用指数衰减函数计算热度：

```
score = Σ e^(-λ × days_ago)
```

半衰期设计：
- λ = ln(2) / 3 ≈ 0.231（3 天半衰期）
- λ = ln(2) / 7 ≈ 0.099（7 天半衰期）
- λ = ln(2) / 30 ≈ 0.023（30 天半衰期）

综合分数 = 0.50 × score_3d + 0.25 × score_7d + 0.15 × score_30d + 0.10 × score_90d

这样近期调用的权重更高，避免"以前常用但现在不用"的技能排名虚高。

### 热度分级

| 等级 | 条件 | 含义 |
|------|------|------|
| 🔥 活跃 | 近 3 天有调用 + score_3d > 2 | 当前高频使用 |
| 🟢 常用 | 近 7 天有调用 + score_7d > 1 | 每周都在用 |
| 🟡 偶尔 | 近 30 天有调用 | 月度低频使用 |
| 🟠 历史 | 近 90 天有调用，30 天内无 | 季度偶尔用 |
| ⚪ 冷备 | 90 天前有调用，近 90 天无 | 历史用过 |
| ❌ 零调用 | 全部历史无调用 | 从未使用 |

## 使用流程

### 第一步：运行审计（默认 dry-run）

```bash
python3 ~/.hermes/skills/skill-audit/scripts/audit.py
```

这会生成审计报告，列出所有技能的热度排名、零调用技能列表、清理建议。

### 第二步：审查报告

报告会按以下分组展示：
- 🔥🟢🟡🟠⚪ 有调用的技能（按热度排序）
- 🗑️ 建议删除的 external/standalone 零调用技能
- ⚠️ 建议禁用的 builtin 零调用技能（按分类分组）

### 第三步：确认清理

用户确认后，执行实际清理：

```bash
python3 ~/.hermes/skills/skill-audit/scripts/audit.py --execute
```

清理前会自动备份所有目标技能到 `~/.hermes/skills/.audit-backups/skills-backup-<timestamp>.tar.gz`。

## 清理策略

### 外部/独立技能（external/standalone）
直接删除目录。这些是通过 `bunx skills add` 或手动安装的技能，删除不会影响 Hermes 核心功能。

### 内置技能（builtin）
不删除文件（Hermes 升级会恢复），而是添加到 `~/.hermes/config.yaml` 的 `skills.disabled` 列表。

Hermes 在加载技能时会检查这个列表，禁用的技能不会出现在 `skills_list` 中，也不会被自动加载。需要时可以从 config 中移除重新启用。

```yaml
skills:
  disabled:
    - marketing-douyin-strategist
    - engineering-ai-engineer
    # ...
```

## 备份机制

所有清理操作执行前，会将目标技能打包为 tar.gz 存放到 `~/.hermes/skills/.audit-backups/`。

恢复方法：
```bash
# 查看备份
ls -la ~/.hermes/skills/.audit-backups/

# 恢复单个技能
tar -xzf ~/.hermes/skills/.audit-backups/skills-backup-<timestamp>.tar.gz <skill-name> -C ~/.hermes/skills/

# 恢复全部
tar -xzf ~/.hermes/skills/.audit-backups/skills-backup-<timestamp>.tar.gz -C ~/.hermes/skills/
```

## 注意事项

- 审计脚本是只读的（dry-run 模式），不会修改任何文件
- 只有使用 `--execute` 参数才会实际执行清理
- config.yaml 修改前会读取现有配置，合并 disabled 列表而非覆盖
- 分类目录下的所有零调用技能可以批量禁用，减少配置量
