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

脚本通过 **三种数据源** 确定技能属性和健康度：

| 数据源 | 用途 | 优先级 |
|--------|------|--------|
| Hermes 内部 API（`_find_all_skills`、`_read_manifest`、`HubLockFile`） | 基础来源分类：builtin / hub / local / external | 主分类 |
| **Hermes Curator**（`hermes curator status` + `run.json`） | **交叉验证来源分类**，补充 Curator 活跃度指标（activity/use/view/patches）和 consolidation/archive 关系 | 权威覆盖（高于 API） |
| 文件系统扫描 + `state.db` tool_calls 解析 | 定位物理目录路径、统计调用频次 | 基础覆盖 |

## Hermes Curator 集成点：

- **来源分类权责**：如果 Curator 认定某技能为 `agent-created`，覆盖 API 返回的 `local` 分类（agent-created 是 local 的真子集）
- **Consolidation 感知**：从 Curator 的 `run.json` 读取技能合并关系（如 `dida365-openapi → platform-integration`），告知用户该技能已被 umbrella 替代
- **归档感知**：curator 归档的技能在建议中标记为「已归档」，防止用户重新启用
- **活跃度指标**：`activity` = 总操作次数，`use` = skill_view 调用，`patches` = 修改次数，`last_activity` = 最近活动

来源分类映射：

| 来源 | 识别方式 | 含义 | 清理方式 |
|------|---------|------|---------|
| `builtin` | Hermes `.bundled_manifest` | Hermes 内置技能 | 添加到 config.yaml disabled 列表 |
| `skills.sh` | `~/.agents/.skill-lock.json` | 通过 skills.sh 安装的社区技能 | `bunx skills add` / `hermes skills uninstall` |
| `skillhub` | `~/.hermes/skills/.hub/lock.json` | 通过 SkillHub 安装的技能 | `skillhub remove` |
| `agent-created` | Curator `agent-created` 列表 | Agent 在用户监督下创建的技能（首次方） | 直接删除目录（先备份），低优先级清理 |
| `local` | 不在以上任何来源 | 其他本地安装的技能 | 直接删除目录（先备份） |
| `external` | `~/.agents/skills/` 路径 | 外部共享技能，影响所有 Agent | 删除需谨慎，确认不影响其他 Agent |

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
