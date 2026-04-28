---
name: audit-hermes-agent-skills
description: >
  Audit installed Hermes Agent skills for usage frequency and generates an
  interactive XLSX with Chinese descriptions, dropdown decision columns, and
  color-coded recommendations. Supports apply mode: reads decisions from XLSX
  and executes cleanup (delete/disable/enable) after user confirmation, with
  automatic backup. Smart filtering: already-disabled skills are not
  re-suggested for cleanup. Uses hermes internal API for authoritative skill
  classification (builtin/hub/local/external). Use when the user asks about
  Hermes skill usage statistics, wants to clean up unused Hermes skills, needs
  to disable low-usage skills, or mentions "技能审计", "清理技能",
  "不用的技能", "哪些技能可以删", "技能热度", "技能使用频率",
  "audit hermes skills". This skill is specific to Hermes Agent — do not use
  for other agents. Make sure to load this skill whenever Hermes skill
  management, cleanup, or usage analysis is mentioned.
---

# Audit Hermes Agent Skills

审计 Hermes Agent 已安装技能的使用频率，识别长期不使用的技能并安全清理。

通过 hermes 内部 API（`_find_all_skills`、`_read_manifest`、`HubLockFile`）获取权威的技能来源分类（hub/builtin/local/external），结合文件系统扫描定位实际目录路径。

## 使用方式

**所有命令使用 uv 运行**（自动管理依赖）：

### 第一步：生成审计 XLSX

```bash
uv run ~/.hermes/skills/audit-hermes-agent-skills/scripts/audit.py
```

打印简单概览后生成 `技能审计报告.xlsx` 到当前目录。

### 第二步：在 Excel 中填写决策

打开 `技能审计报告.xlsx`，通过「我的决策」列的下拉框标记每个技能：

| 技能来源 | 下拉选项 | 默认值 |
|---------|---------|--------|
| 内置技能 | 启用 / 禁用 | 当前状态 |
| 其他技能 | 保留 / 删除 | 保留 |

颜色标记：🟢绿色=在用，🔴粉色=建议删除，🟠橙色=建议禁用，⚪灰色=已禁用。

### 第三步：执行清理

```bash
uv run ~/.hermes/skills/audit-hermes-agent-skills/scripts/audit.py --apply
```

先打印变更摘要（删除/禁用/启用各多少），用户确认 y 后自动执行：
- 备份 `config.yaml`
- 备份要删除的技能目录到 `~/.hermes/skills/.audit-backups/` 并删除
- 更新 `config.yaml` 的 `skills.disabled` 列表（合并新增和移除）

## 核心原理

技能调用记录存储在 `~/.hermes/state.db` 的 `messages.tool_calls` 字段中。通过解析 `skill_view` 和 `skill_manage` 工具调用，统计每个技能的调用历史。

脚本通过 **hermes 内部 API + 文件系统扫描** 双重数据源确定技能来源：

| 来源 | 含义 | 清理方式 |
|------|------|---------|
| `builtin` | Hermes 内置技能 | 添加到 config.yaml disabled 列表 |
| `hub` | 从 skills.sh 等 Hub 源安装 | `hermes skills uninstall` |
| `local` | 本地安装的技能 | 直接删除目录（先备份） |
| `external` | 外部共享技能（`~/.agents/skills/`） | 删除需谨慎，影响所有 Agent |

## 备份恢复

```bash
# 查看备份
ls -la ~/.hermes/skills/.audit-backups/

# 恢复单个技能
tar -xzf ~/.hermes/skills/.audit-backups/cleanup-<timestamp>/<skill-name>.tar.gz -C ~/.hermes/skills/
```

## 注意事项

- `--apply` 必须用户输入 y 确认，不会自动执行
- 执行前自动备份 config.yaml 和目标技能目录
- config.yaml 修改会合并现有 disabled 列表而非覆盖
- 已禁用的零调用技能不会重复建议
