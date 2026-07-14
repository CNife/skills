---
name: chezmoi-sync
description: >-
  Automate chezmoi dotfiles sync — fetch remote, pull changes, detect
  chezmoi-level changes (source vs home), smart re-add, commit, and push.
  Use whenever the user wants to sync dotfiles, says "同步", "chezmoi sync",
  "提交 dotfiles", "备份配置", wants to record home changes into the dotfiles
  repo, or is about to run chezmoi git commands manually.
metadata:
  internal: true
---

# Chezmoi Sync Skill

一键同步 home ↔ 源仓库 ↔ 远程仓库。

```text
🏠 Home              📁 源目录 (Git)          ☁️ 远程 (Git)
    │                    │                        │
    │── re-add 🟢 ──────→│                        │
    │←──── apply 🔴 ─────│                        │
    │                    │── push 🟢 ────────────→│
    │                    │←── pull 🟢 ────────────│
```

> **📁 路径约定**：`scripts/` 目录相对于本 SKILL.md 所在目录。
> agent 执行命令时将 `$SKILL_DIR` 解析为实际的技能目录绝对路径。

## 安全性三层模型

这是技能的核心设计原则，所有自动化决策以此为依据：

| 操作 | 方向 | 安全等级 | 策略 |
|------|------|---------|------|
| `git pull / push` | 远程 ↔ 源 | 🟢 安全 | 全 git 操作，全量历史可回滚，**自动执行** |
| `chezmoi re-add` | home → 源 | 🟢 安全 | 写入 git 仓库，`git checkout` 可还原，**自动执行** |
| `chezmoi apply` | 源 → home | 🔴 危险 | 覆盖 home 文件，**无撤销机制，必须人工确认** |

### 需要询问用户的场景

- 源比 home 新时（时间戳分析不确定方向）→ 展示差异，问用户选 apply 还是 re-add
- 提交前展示变更摘要 → 确认后再 commit
- apply（源→home）→ **永不自动执行**，红线

#### 自动执行的场景

- git pull / git fetch — 远程 ↔ 源，全程可回滚
- chezmoi re-add（home 更新时）— 写入 git，可还原
- git push — 推送已提交的变更

## 前置条件

| 依赖 | 必选 | 备注 |
|------|------|------|
| `chezmoi` | ✅ | source state 须为 git 仓库，已配置 `remote origin` |
| `git` | ✅ | 通过 `chezmoi git --` 调用 |
| `uv` | ✅ | 用于运行 PEP 723 辅助脚本 |
| `stat` / `date` / `grep` | ✅ | 冲突分析等场景使用 |

## 技能参数

- `commit_msg`: 自定义提交信息。省略时由脚本自动生成。

## 工作流

```text
阶段 A：拉取远程       阶段 B：检测 + re-add        阶段 C：提交推送
─────────────────     ────────────────────      ──────────────────
Step 1: fetch          Step 3: 状态检测          Step 7: commit
Step 2: pull（可选）    Step 4: diff 展示         Step 8: push
                        Step 5: smart re-add     Step 9: verify
                        Step 6: data-sync
```

每阶段独立快走——无远程变更跳过 A，无差异跳过 B，无 git 变更跳过 C。

---

### Step 0：验证前置条件

检查 chezmoi 和 uv 是否可用、git remote 是否配置、脚本是否存在。

```bash
# 验证依赖
chezmoi source-path >/dev/null 2>&1 || { echo "❌ chezmoi 未安装"; exit 1; }
uv --version >/dev/null 2>&1 || { echo "❌ uv 未安装"; exit 1; }
test -f "$SKILL_DIR/scripts/chezmoi-sync.py" || { echo "❌ 脚本未找到：$SKILL_DIR/scripts/chezmoi-sync.py"; exit 1; }

echo "🔧 chezmoi 源目录：$(chezmoi source-path)"
echo "  远程：$(chezmoi git -- remote get-url origin)"
echo "  HEAD：$(chezmoi git -- rev-parse --short HEAD)"
```

---

### Step 1：Fetch 远程

```bash
uv run --script "$SKILL_DIR/scripts/chezmoi-sync.py" fetch
```

**快速路径 A**：输出中 `__new_remote=0` 且 `__ahead_local=0` → 跳过 Step 2，进入 Step 3。

---

### Step 2：Pull 远程变更（可选）

仅在 Step 1 显示 `__new_remote>0` 时执行。

```bash
uv run --script "$SKILL_DIR/scripts/chezmoi-sync.py" pull
```

**冲突处理**：脚本已内置启发式自动解决（>7 天差距用远程、<1 天用本地）。有 `__needs_user` 输出时，逐文件询问用户。

---

### Step 3：三层状态检测

```bash
# Layer 1 & 2: git status + chezmoi status
uv run --script "$SKILL_DIR/scripts/chezmoi-sync.py" status
rc=$?
if [ "$rc" -ne 0 ] && [ "$rc" -ne 2 ]; then
  exit "$rc"
fi

# Layer 3: modify_ 管理字段对比
uv run --script "$SKILL_DIR/scripts/chezmoi-sync.py" data-diff
data_rc=$?
if [ "$data_rc" -ne 0 ] && [ "$data_rc" -ne 2 ]; then
  exit "$data_rc"
fi
```

`rc=2` 表示有变更需处理，不是真错误；其他非零退出码必须停止。

捕获输出标记：

- `__has_git_changes=1` → 源仓库有未提交变更
- `__has_chezmoi_changes=1` → home 与源有差异（普通文件）
- `__has_data_changes=1` → modify_ 管理字段有差异
- `__data_diff_paths=...` → 有差异的字段名列表

**快速路径 B**：三者都为 0 → 跳过 Step 4–6，进入 Step 7。

---

### Step 4：展示 chezmoi diff

仅当 `__has_chezmoi_changes=1` 时执行。

```bash
uv run --script "$SKILL_DIR/scripts/chezmoi-sync.py" diff
```

阅读 diff 时按 chezmoi 默认方向理解：`-` 是当前 home/destination，`+` 是源生成的 target（apply 后内容）。只有显式使用 `--reverse` 时方向才相反；本脚本不使用 `--reverse`。

---

### Step 5：智能 re-add

仅当 `__has_chezmoi_changes=1` 时执行。

```bash
uv run --script "$SKILL_DIR/scripts/chezmoi-sync.py" re-add
rc=$?
if [ "$rc" -ne 0 ] && [ "$rc" -ne 2 ]; then
  exit "$rc"
fi
```

`rc=2` 表示存在 `__needs_decision`，agent 继续按下方流程询问用户。

#### 脚本自动处理

1. 对每个有差异的文件，比较 home mtime 与源仓库提交时间（以本机时区 + offset 展示）
2. home 更新 → 自动 `chezmoi re-add`（安全方向，有 git 兜底）
3. 源更新或不可比 → 输出 `__needs_decision`，由 agent 询问用户

**`private_` 文件重命名**：chezmoi 会根据文件权限添加 `private_` 前缀。无论这是 re-add 产生的本地变更，还是 pull 引入的远程重命名，git 状态都可能显示旧文件删除 + 新文件添加——这是正常行为，commit 会自动包含。

**当 `__needs_decision` 非空时：**

- 展示差异，问用户：apply（源→home，⚠️ 覆盖）还是 re-add（home→源，✅ 安全）
- `--direction source` 必须带且只带一个目标路径；脚本会拒绝无路径或多路径 apply，避免全量覆盖
- 用户选择后，用 `--direction` 重新执行：

```bash
uv run --script "$SKILL_DIR/scripts/chezmoi-sync.py" re-add .config/xxx --direction home
uv run --script "$SKILL_DIR/scripts/chezmoi-sync.py" re-add .config/xxx --direction source
```

---

### Step 6：Data Sync（modify_ 管理字段同步）

仅当 `__has_data_changes=1` 时执行。

```bash
# Step 6a: 展示差异详情
uv run --script "$SKILL_DIR/scripts/chezmoi-sync.py" data-diff

# Step 6b: 询问用户是否同步（在技能流程中）
# Step 6c: 确认后执行：
uv run --script "$SKILL_DIR/scripts/chezmoi-sync.py" data-sync
```

**工作流程**：

1. 运行 `data-diff` 展示差异字段
2. 询问用户：是否同步到 `.chezmoidata.yaml`？
3. 确认后运行 `data-sync`（脚本直接执行，无二次确认）
4. 忽略的字段（本地专属）不会被同步

---

### Step 7：Commit

仅在 `__has_git_changes=1` 或上一步产生了变更时执行。

```bash
uv run --script "$SKILL_DIR/scripts/chezmoi-sync.py" commit --message "自定义信息"
```

- `--message` 省略时自动生成提交信息
- 脚本直接执行，用户确认在技能流程中

提交信息规则：

- 文件数 ≤20 → 列出文件名
- 文件数 >20 → `sync：更新 N 个 dotfiles`

可通过 `commit_msg` 参数自定义。

---

### Step 8：Push

```bash
uv run --script "$SKILL_DIR/scripts/chezmoi-sync.py" push
```

---

### Step 9：最终验证

```bash
uv run --script "$SKILL_DIR/scripts/chezmoi-sync.py" verify
```

验证输出标记：

- `__synced=1` → 本地 ↔ 远程 git 一致
- `__chezmoi_dirty=0` → chezmoi diff 为空，home 与源一致
- `__chezmoi_dirty=1` → chezmoi diff 非空，home 与源不一致（需关注）

---

## 错误处理

| 情况 | 行为 |
|------|------|
| chezmoi 未安装 | 停止，提示安装 |
| uv 未安装 | 停止，提示安装 |
| 源非 git 仓库 | 停止，提示 `chezmoi init` |
| 无 remote origin | 停止，提示配置远程 |
| 脚本不存在 | 停止，提示路径错误 |
| 网络错误 | 停止，显示错误，建议稍后重试 |
| 冲突自动解决失败 | 输出 `__needs_user`，逐文件询问 |
| push 被拒（远程有更新） | 停止，提示先拉再推 |
| re-add 失败 | 显示错误，不影响后续流程 |
| data-sync 失败 | 显示错误，提示手动编辑 `.chezmoidata.yaml` |

## 安全规则

1. **永不 force push** — push 被拒时先拉再推
2. **永不自动 apply** — apply（源→home）是唯一红线，必须人工确认
3. **方向不确定时默认 re-add** — home→源为安全方向（有 git 兜底）
4. **永不删除文件** — 不经用户确认不删除
5. **所有 git 操作通过 `chezmoi git --`** — 不绕过 chezmoi
6. **autostash 安全** — 本地变更在 pull 后自动恢复
7. **冲突解决偏好本地** — 时间戳不明确时偏向保留本地变更
8. **`private_` 重命名正常处理** — 权限变化导致的前缀变更，commit 自动处理 git rm + git add
9. **data-sync 需确认** — 同步管理字段到 `.chezmoidata.yaml` 前必须展示差异并询问用户
