---
date: 2026-06-08T11:41:21+0800
author: 蔡涛
commit: 827671a
branch: main
repository: skills
topic: "chezmoi-sync 技能改进：modify_ 模板处理、非交互式提交、验证增强"
tags: [research, chezmoi, dotfiles, modify-template, automation]
status: complete
last_updated: 2026-06-08T13:00:00+0800
last_updated_by: 蔡涛
last_updated_note: "架构修正：脚本纯工具化，移除 typer.confirm 和 --yes，用户确认放在技能流程中"
---

# Research: chezmoi-sync 技能改进

## Research Question

查看会话 `/home/cnife/.pi/agent/sessions/--home-cnife-code-deploy-k3s--/2026-06-08T03-35-25-958Z_019ea54c-ac06-7307-8e81-b70a6a8cf35f.jsonl`，分析 chezmoi-sync 技能该如何改进。

## Summary

会话揭示了 chezmoi-sync 技能的四个核心问题：

1. **modify_ 模板处理不当**：当前模板遍历所有键并覆盖，导致 home 文件本地修改被抹掉。正确做法是只管理需要同步的字段。
2. **re-add 不兼容 modify_**：`chezmoi re-add` 对 modify_ 条目返回 "not managed"。正确路径是直接对比 home JSON 与 `.chezmoidata.yaml` 的管理字段，而非依赖 `chezmoi status`。
3. **脚本与技能职责混淆**：`typer.confirm` 放在脚本中，导致非交互模式阻塞。正确做法是脚本纯工具化，用户确认放在技能流程中。
4. **验证范围不足**：`verify()` 仅检查 git HEAD 一致性，不验证 dotfiles 状态。

**关键架构原则**：

- **脚本是纯工具**：确定性、无交互、输出结构化标记
- **技能流程负责用户交互**：展示信息、询问决策、调用脚本

## Detailed Findings

### 0. 核心架构：管理字段映射与直接对比（新增）

**问题**：`chezmoi status` 对 modify_ 条目不可靠 — 模板覆盖所有字段时，home 侧编辑被抹掉，status 报告无差异。

**解决方案**：引入管理字段映射，直接对比 home JSON 与 `.chezmoidata.yaml`，不依赖 `chezmoi status`。

**映射配置**（放在 `.chezmoidata.yaml` 中）：

```yaml
# .chezmoidata.yaml
pi:
  modify_entries:
    - target: .pi/agent/settings.json
      data_root: pi.settings
      managed_paths:
        - compaction
        - doubleEscapeAction
        - enabledModels
        - followUpMode
        - hideThinkingBlock
        - images
        - lastChangelogVersion
        - packages
        - session
        - steeringMode
        - terminal
        - theme
        - transport
        - treeFilterMode
        - warnings
      ignored_paths:
        - defaultModel
        - defaultProvider
        - defaultThinkingLevel
```

**新增 Layer 3：managed-data-diff**：

```python
def managed_data_diff(entry: dict) -> list[dict]:
    """对比 home JSON 与 .chezmoidata.yaml 的管理字段"""
    target = entry["target"]
    data_root = entry["data_root"]
    managed_paths = entry["managed_paths"]

    home_path = Path.home() / target
    home_json = json.loads(home_path.read_text())

    # 读取 .chezmoidata.yaml
    data_yaml = yaml.safe_load(data_path.read_text())
    data_values = get_nested(data_yaml, data_root)

    diffs = []n    for path in managed_paths:
        home_val = get_nested(home_json, path)
        data_val = get_nested(data_values, path)
        if home_val != data_val:
            diffs.append({"path": path, "home": home_val, "data": data_val})

    return diffs
```

**工作流变化**：

```text
Step 3: 状态检测
  ├── Layer 1: git status（不变）
  ├── Layer 2: chezmoi status（不变，用于普通文件）
  └── Layer 3: managed-data-diff（新增，用于 modify_ 文件）
      ├── 读取 home JSON
      ├── 读取 .chezmoidata.yaml
      ├── 只对比 managed_paths
      └── 有差异 → 展示 path-level diff → 问用户是否同步
```

### 1. modify_ 模板状态检测盲区

**问题**：当前模板使用 `range` 遍历 `.pi.settings` 的所有键并调用 `setValueAtPath`，这会**覆盖** home 文件的本地值。

**当前模板** (`modify_dot_pi/agent/settings.json`):

```text
{{- /* chezmoi:modify-template */ -}}
{{- $s := fromJson (or .chezmoi.stdin "{}") -}}
{{- range $key, $value := .pi.settings -}}
{{-   $s = setValueAtPath $key $value $s -}}
{{- end -}}
{{ toPrettyJson $s }}
```

**问题场景**：

- 用户在 home 文件中修改 `defaultModel` 为 `deepseek`
- `.chezmoidata.yaml` 中仍然是 `mimo-v2.5-pro`
- `chezmoi status` 报告无差异（因为 `setValueAtPath` 用数据源值覆盖了 home 值）

**解决方案**（chezmoi 官方推荐 + 直接对比）：

1. **修改模板**：只对需要同步的字段调用 `setValueAtPath`
2. **技能检测**：直接对比 home JSON 与 `.chezmoidata.yaml`，不依赖 `chezmoi status`

```text
// chezmoi:modify-template
{{- $stdin := .chezmoi.stdin -}}
{{- $result := $stdin | default "{}" | fromJson }}

{{- /* 管理的字段（从 chezmoi data 同步） */}}
{{- $result = $result | setValueAtPath "compaction" .pi.settings.compaction }}
{{- $result = $result | setValueAtPath "packages" .pi.settings.packages }}
{{- /* ... 其他管理字段 ... */}}

{{- /* 机器专属字段不覆盖，保留本地值 */}}
{{- /* defaultModel, defaultProvider, defaultThinkingLevel */}}

{{- /* 首次运行：初始化机器专属字段 */}}
{{- if not $stdin -}}
  {{- $result = $result | setValueAtPath "defaultModel" .pi.settings.defaultModel }}
{{- end }}

{{- $result | toPrettyJson }}
```

### 2. chezmoi re-add 不兼容 modify_ 模板

**问题**：`chezmoi re-add` 对 modify_ 模板返回 "not managed"，因为源是模板脚本而非普通文件。

**位置**：`scripts/chezmoi-sync.py:417, 433, 441`

**影响**：当 re-add 失败时，文件被静默丢弃 — 不加入 `auto_re_add`、`needs_decision` 或任何跟踪列表。

**关键洞察**：即使采用部分 modify_ 模板，`chezmoi re-add` 仍会拒绝 modify_ 条目 — 源条目是模板脚本，不是普通文件。正确路径是**编辑 `.chezmoidata.yaml`**，而非 re-add。

**技能需要的改进**：

- 不依赖 `chezmoi status` 检测 modify_ 差异
- 使用 Layer 3（managed-data-diff）直接对比 home JSON 与 `.chezmoidata.yaml`
- 检测到管理字段差异时，展示 diff 并询问用户是否同步到 `.chezmoidata.yaml`
- 确认后自动更新 `.chezmoidata.yaml`，然后 commit + push

### 3. mtime 启发式比较错误文件

**问题**：`re_add()` 比较 `home_mtime` 与 modify_ 脚本的 git 提交时间，而非 `.chezmoidata.yaml` 的提交时间。

**位置**：`scripts/chezmoi-sync.py:398-404`

**影响**：时间戳比较对 modify_ 模板无意义 — 脚本文件可能数月未改，但数据源频繁更新。

**解决方案**：对 modify_ 条目跳过 mtime 启发式，直接进入数据源更新引导流程。

### 4. typer.confirm 阻塞非交互执行

**问题**：`commit()` 函数无条件调用 `typer.confirm`，当 stdin 不是 TTY 时抛出 `typer.Abort`。

**位置**：`scripts/chezmoi-sync.py`

**根本原因**：脚本与技能职责混淆 — 用户确认不应放在脚本内部。

**解决方案**：

- **移除 `typer.confirm`**：脚本打印摘要后直接执行
- **移除 `--yes/-y` 标志**：脚本不需要这个标志
- **用户确认放在技能流程中**：agent 展示 diff → 问用户 → 确认后调用脚本

```python
@app.command()
def commit(msg: str | None = typer.Option(None, "--message", "-m", help="自定义提交信息")) -> None:
    """📝 add + commit（非交互，打印摘要后直接执行）"""
    # ... 打印摘要 ...
    # 直接提交，无 typer.confirm
    r = _chz_git("commit", "-m", commit_msg)
```

### 5. verify() 仅检查 git 一致性

**问题**：`verify()` 只比较 `HEAD` 和 `origin/main` 的 SHA，不验证 dotfiles 状态。

**位置**：`scripts/chezmoi-sync.py:548-565`

**影响**：git 同步成功但 home 文件可能过时（如 modify_ 模板数据源已更新但未 apply）。

**修复方案**：增加 `chezmoi diff` 检查：

```python
@app.command()
def verify() -> None:
    # ... 现有 git 检查 ...

    # 新增：chezmoi diff 检查
    diff_r = _chz("diff")
    if diff_r.stdout.strip():
        print(_entry("⚠️", "chezmoi diff 非空 — home 与源不一致"))
        print("__chezmoi_dirty=1")
    else:
        print(_entry("✅", "chezmoi diff 空 — home 与源一致"))
        print("__chezmoi_dirty=0")
```

### 6. 条目类型无差别解析

**问题**：`status()` 和 `re_add()` 解析 chezmoi status 输出时丢弃两字母状态前缀，无法区分 modify_、`.chezmoiremove`、`run_` 等条目类型。

**位置**：`scripts/chezmoi-sync.py:370`

**影响**：`.chezmoiremove` 条目可能触发错误的 re-add 尝试。

**修复方案**：解析状态前缀，过滤不支持的条目类型：

```python
status_prefix = parts[0]
if status_prefix.strip() == "D":  # 删除条目
    continue
```

### 7. 数据源变更无专用信号

**问题**：`.chezmoidata.yaml` 编辑被折叠进 `__has_git_changes`，无语义区分。

**位置**：`scripts/chezmoi-sync.py:260-263`

**影响**：工作流无法区分「源文件变更」和「数据源变更」。

**解决方案**：Layer 3（managed-data-diff）独立于 `chezmoi status`，直接对比 home JSON 与 `.chezmoidata.yaml`，输出 `__has_data_changes=1` 标志。

## Code References

- `modify_dot_pi/agent/settings.json:1-5` — modify_ 模板定义
- `.chezmoidata.yaml:1-48` — 模板数据源
- `.chezmoidata.yaml` (新增) — `pi.modify_entries` 管理字段映射
- `scripts/chezmoi-sync.py:235-275` — `status()` 双层级检测
- `scripts/chezmoi-sync.py` (新增) — `managed_data_diff()` Layer 3 检测
- `scripts/chezmoi-sync.py:341-469` — `re_add()` 智能 re-add
- `scripts/chezmoi-sync.py:483-520` — `commit()` 提交逻辑
- `scripts/chezmoi-sync.py:548-570` — `verify()` 验证逻辑
- `SKILL.md:59-61` — `skip_confirm` 参数文档（未实现）
- `SKILL.md:66-72` — 工作流阶段定义

## Integration Points

### Inbound References

- `SKILL.md:149-179` — Step 5 工作流描述，假设所有条目支持 re-add
- `SKILL.md:185-188` — Step 6 提交工作流，依赖 `typer.confirm`

### Outbound Dependencies

- `chezmoi status` — 状态检测依赖
- `chezmoi re-add` — re-add 操作依赖
- `chezmoi diff` — diff 展示依赖
- `chezmoi git --` — git 操作封装

### Infrastructure Wiring

- `.chezmoidata.yaml` — 模板数据源
- `~/.config/chezmoi/chezmoi.yaml` — 机器专属数据（可选）

## Architecture Insights

1. **modify_ 模板数据流反转**：值从 `.chezmoidata.yaml` → home 文件，而非 home → 源。`chezmoi re-add` 对 modify_ 条目无效（返回 "not managed"），正确路径是编辑 `.chezmoidata.yaml`。

2. **三层状态模型**：
   - Layer 1: git status — 检测源目录文件变更
   - Layer 2: chezmoi status — 检测普通文件的 home↔源差异
   - Layer 3: managed-data-diff — 直接对比 home JSON 与 `.chezmoidata.yaml` 的管理字段（新增）

3. **脚本与技能职责分离**：

   ```text
   ┌─────────────────────────────────────────────────────────┐
   │  技能流程 (SKILL.md)                                      │
   │  - 调用脚本获取信息                                        │
   │  - 向用户展示摘要                                          │
   │  - 询问用户决策                                            │
   │  - 调用脚本执行操作                                        │
   └─────────────────────────────────────────────────────────┘
                           │
                           ▼
   ┌─────────────────────────────────────────────────────────┐
   │  辅助脚本 (chezmoi-sync.py)                               │
   │  - 纯工具，确定性                                          │
   │  - 无交互，无确认                                          │
   │  - 输出结构化标记供解析                                    │
   └─────────────────────────────────────────────────────────┘
   ```

4. **不依赖 chezmoi status 检测 modify_ 差异**：如果模板覆盖所有字段，`chezmoi status` 看不到 home 侧编辑。必须直接对比。

5. **条目类型应分流处理**：不同 chezmoi 条目类型（普通文件、modify_、remove、run_）需要不同的处理逻辑。modify_ 条目使用 Layer 3 检测 + 数据源更新引导。

## Precedents & Lessons

无类似变更历史（git history unavailable for this skill）。

### Composite Lessons

- **chezmoi 官方推荐**：`modify_` 模板应只管理需要同步的字段，不碰机器专属字段（[官方文档](https://chezmoi.io/user-guide/manage-different-types-of-file/#manage-part-but-not-all-of-a-file)）
- **deepEqual 模式**：使用 `deepEqual` 比较前后状态，无变化时输出原始 stdin 保留格式（[讨论 #2864](https://github.com/twpayne/chezmoi/discussions/2864)）
- **数据分层**：共享数据放 `.chezmoidata.yaml`，机器专属数据放 `~/.config/chezmoi/chezmoi.yaml`（[讨论 #2114](https://github.com/twpayne/chezmoi/discussions/2114)）

## Developer Context

**Q (`modify_dot_pi/agent/settings.json:1-5`): 当前模板遍历所有键并覆盖，导致 home 文件本地修改被抹掉。应采用哪种策略？**
A: 采用「部分 modify_ 模板」策略 — 只管理需要同步的字段，不碰机器专属字段（`defaultModel`, `defaultProvider`, `defaultThinkingLevel`）。

**Q: home 中的 settings.json 有更新时，应该怎么更新到 chezmoi 库中？**
A: 采用方案 C（混合方式）— 检测到 modify_ 条目管理字段有差异时，展示 diff 并询问用户是否同步到 `.chezmoidata.yaml`，确认后自动更新。本地专属字段忽略不处理。

## Decisions（已确认）

1. **modify_ 检测方式**：不依赖 `chezmoi status`，使用 Layer 3（managed-data-diff）直接对比 home JSON 与 `.chezmoidata.yaml`
2. **home→源同步**：检测到管理字段差异时，展示 diff 并询问用户是否同步到 `.chezmoidata.yaml`，确认后自动更新
3. **脚本与技能职责分离**：
   - **脚本**：纯工具，确定性，无交互，打印摘要后直接执行
   - **技能流程**：负责用户交互（展示信息、询问决策、调用脚本）
   - 移除 `typer.confirm` 和 `--yes/-y` 标志
4. **verify() 增强**：增加 `chezmoi diff` 检查，输出 `__chezmoi_dirty=1` 单独标志（不改变 `__synced` 含义）

## Open Questions

1. **映射配置位置**：管理字段映射放在 `.chezmoidata.yaml` 中还是技能内部硬编码？
2. **其他条目类型的处理**：`.chezmoiremove` 和潜在的 `run_`/`create_` 条目是否需要特殊处理？
3. **首次运行边界条件**：当本地文件为空 `{}` 时，`if not $stdin` 会重新应用首次运行默认值 — 是否需要更精确的检测？
4. **key 排序问题**：`toPrettyJson` 会按字母顺序重排键 — 是否需要使用 `deepEqual` 模式保留原始格式？
5. **YAML 格式保留**：使用 `ruamel.yaml` 替代 `PyYAML` 以保留注释和格式

## Related Research

无相关研究文档。

## Follow-up Research

（待后续补充）
