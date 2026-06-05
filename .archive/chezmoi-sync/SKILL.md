---
name: chezmoi-sync
description: >-
  Automate chezmoi dotfiles sync — fetch remote, pull changes with smart
  conflict resolution, commit local changes with auto-generated messages,
  and push. Use whenever the user wants to sync dotfiles, says "同步",
  "chezmoi sync", "提交 dotfiles", "备份配置", or is about to run
  chezmoi git commands manually.
---

# Chezmoi Sync Skill

One-command chezmoi dotfiles synchronization: validate → fetch + summarize →
fast-path on clean state → pull remote → commit local → push → verify.

## Prerequisites

| Dependency | Required | Notes |
|-----------|----------|-------|
| `chezmoi` | ✅ | Source state must be a git repo with remote `origin` |
| `git` | ✅ | Bundled with chezmoi — commands go through `chezmoi git --` |
| `stat` / `date` / `grep` | ✅ | Used in conflict analysis |

## Skill Parameters

- `commit_msg`: Custom commit message. Auto-generated from changed file list if omitted.
- `skip_confirm`: If `true`, skip the confirmation prompt for local changes (auto-commit). Default: `false`.

## Workflow

### Step 0: Validate Prerequisites & Capture Source Path

Use a single bash block to verify everything works and store the source path.
This path is used in every subsequent step — each bash block starts with `cd "$CHZ_SRC"`.

**IMPORTANT**: Shell variables do NOT persist between tool calls. Each bash block
must re-enter the source directory via `cd "$CHZ_SRC"` at its start.

```bash
# Validate all prerequisites in one pass
CHZ_SRC="$(chezmoi source-path)" || { echo "❌ chezmoi not found"; exit 1; }

cd "$CHZ_SRC" || exit 1
echo "🔧 chezmoi 源目录: $CHZ_SRC"

# Verify it's a git repo with remote origin
chezmoi git -- rev-parse --git-dir >/dev/null 2>&1 || { echo "❌ 不是 git 仓库"; exit 1; }
chezmoi git -- remote get-url origin >/dev/null 2>&1 || { echo "❌ 未配置 remote origin"; exit 1; }
remote_branch=$(chezmoi git -- symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/heads/||')
if [ "$remote_branch" != "main" ]; then
  echo "⚠️  远程 HEAD 分支: ${remote_branch:-未设置}，期望 main"
fi

echo "  远程: $(chezmoi git -- remote get-url origin)"
echo "  HEAD: $(chezmoi git -- rev-parse --short HEAD)"
```

> ⚠️ Agent: allow failure for `remote_branch` check — a missing `origin/HEAD` symref
> is non-fatal; continue if it fails.

### Step 1: Fetch & Summarize State

Check local uncommitted changes, fetch remote, and detect divergence.
All in one block to minimize round-trips.

```bash
cd "$(chezmoi source-path)"

# Local changes
local_changes=$(chezmoi git -- status --porcelain)
if [ -n "$local_changes" ]; then
  echo "📝 本地待提交 ($(echo "$local_changes" | wc -l | tr -d ' ') 个文件):"
  echo "$local_changes"
  echo "---"
  chezmoi git -- diff --stat
else
  echo "✅ 本地无未提交变更"
fi

# Fetch remote
echo "🔄 获取远程..."
chezmoi git -- fetch origin

# Remote / ahead counts
remote_new=$(chezmoi git -- log --oneline HEAD..origin/main 2>/dev/null)
ahead_local=$(chezmoi git -- log --oneline origin/main..HEAD 2>/dev/null)

if [ -n "$remote_new" ]; then
  echo "⬇️  远程有 $(echo "$remote_new" | wc -l | tr -d ' ') 个新提交"
  echo "$remote_new"
fi
if [ -n "$ahead_local" ]; then
  echo "⬆️  本地有 $(echo "$ahead_local" | wc -l | tr -d ' ') 个待推送提交"
fi

echo "---"
echo "  HEAD:      $(chezmoi git -- rev-parse --short HEAD)"
echo "  origin/main: $(chezmoi git -- rev-parse --short origin/main 2>/dev/null || echo N/A)"
```

#### Fast Path (Early Exit)

**Agent decision**: if BOTH of these are true, jump directly to **Step 4 (Final Verification)**:

1. `local_changes` is empty (no uncommitted changes), AND
2. `remote_new` is empty (HEAD equals origin/main), AND
3. `ahead_local` is empty (no unpushed commits)

The clean-state sync is a no-op — no fetch, no pull, no commit needed.
Skip Steps 2 and 3 entirely.

### Step 2: Pull Remote Changes

Only executed when `remote_new` detected in Step 1.

```bash
cd "$(chezmoi source-path)"

echo "⬇️  拉取远程变更..."
if chezmoi git -- pull --autostash --rebase; then
  echo "✅ 拉取成功"
else
  echo "⚠️  拉取冲突，进入分析..."
  # → fall through to conflict analysis below
fi
```

#### Conflict Analysis (Smart Auto-resolve)

When `pull --autostash --rebase` fails, find conflicted files and analyze each.

```bash
cd "$(chezmoi source-path)"

conflicted_files=$(chezmoi git -- diff --name-only --diff-filter=U)

echo "🔍 分析 $(echo "$conflicted_files" | wc -l | tr -d ' ') 个冲突文件..."
auto_resolve=""
needs_user=""

for file in $conflicted_files; do
  echo "---"
  echo "📄 $file"

  if [ ! -f "$file" ]; then
    echo "  ⏭️  文件已删除，需要用户确认"
    needs_user="$needs_user $file"
    continue
  fi

  # Gather timestamps
  local_mtime=$(stat -c %Y "$file" 2>/dev/null || echo "0")
  local_mtime_hr=$(date -d @"$local_mtime" '+%Y-%m-%d %H:%M' 2>/dev/null || echo "?")
  local_commit_date=$(chezmoi git -- log -1 --format=%ct HEAD -- "$file" 2>/dev/null || echo "0")
  remote_commit_date=$(chezmoi git -- log -1 --format=%ct origin/main -- "$file" 2>/dev/null || echo "0")

  local_commit_hr=$(date -d @"$local_commit_date" '+%Y-%m-%d %H:%M' 2>/dev/null || echo "?")
  remote_commit_hr=$(date -d @"$remote_commit_date" '+%Y-%m-%d %H:%M' 2>/dev/null || echo "?")

  now=$(date +%s)
  days_since_local=$(( (now - local_commit_date) / 86400 ))

  echo "  mtime: $local_mtime_hr | 本地提交: $local_commit_hr | 远程提交: $remote_commit_hr"
  echo "  冲突块:"
  grep -A2 '^<<<<<<<' "$file" 2>/dev/null | head -20
  echo "  ---"
  grep -A2 '^>>>>>>>' "$file" 2>/dev/null | head -10

  # Decision heuristic
  if [ "$remote_commit_date" -gt "$local_commit_date" ] && [ "$days_since_local" -gt 7 ]; then
    echo "  ✅ 远程变更显著更新，采用远程"
    chezmoi git -- checkout --theirs -- "$file" && chezmoi git -- add "$file"
    auto_resolve="$auto_resolve ✅ $file (远程)"
  elif [ "$local_commit_date" -ge "$remote_commit_date" ] && [ "$days_since_local" -lt 1 ]; then
    echo "  ✅ 本地刚刚变更，采用本地"
    chezmoi git -- checkout --ours -- "$file" && chezmoi git -- add "$file"
    auto_resolve="$auto_resolve ✅ $file (本地)"
  else
    echo "  🤔 需要用户裁决"
    needs_user="$needs_user $file"
  fi
done

# Report
[ -n "$auto_resolve" ] && echo "🟢 自动解决:" && echo "$auto_resolve"
if [ -n "$needs_user" ]; then
  echo "🟡 需用户裁决: $needs_user"
  echo "  选项: 1) 采用本地 (ours)  2) 采用远程 (theirs)  3) 手动编辑"
  # Agent: wait for user instruction, then apply per file
fi

# Continue rebase if all resolved
if [ -z "$(chezmoi git -- diff --name-only --diff-filter=U)" ]; then
  chezmoi git -- rebase --continue && echo "✅ 冲突解决，拉取完成"
fi
```

#### Post-Rebase Stash Pop Conflicts

Rare but possible — autostash pop can conflict if local changes touch the same
lines as pulled changes. Apply the same heuristic rather than blindly adopting theirs.

```bash
cd "$(chezmoi source-path)"

stash_conflicts=$(chezmoi git -- diff --name-only --diff-filter=U)
if [ -z "$stash_conflicts" ]; then exit 0; fi

echo "⚠️  存储弹出冲突 ($(echo "$stash_conflicts" | wc -l | tr -d ' ') 个文件):"
# Same heuristic as above — re-run the analysis loop if stash conflicts exist
# Agent: re-run the conflict analysis block for these files
```

**Agent note**: if stash conflicts occur, re-run the conflict analysis loop above
on `stash_conflicts`. Never silently take theirs for local dotfile changes.

### Step 3: Commit & Push Local Changes

Only executed when `status --porcelain` is non-empty after Step 2 (or when the
user had local changes from the start and opted to commit).

```bash
cd "$(chezmoi source-path)"

changes=$(chezmoi git -- status --porcelain)
if [ -z "$changes" ]; then
  echo "✅ 无变更需提交"
  exit 0
fi

echo "📝 待提交 ($(echo "$changes" | wc -l | tr -d ' ') 个文件):"
chezmoi git -- status --short
```

#### Confirmation

- If `skip_confirm=true` → auto-commit, skip prompt.
- Otherwise → ask user: "提交并推送这些变更到远程？(y/n)"
  - User says "n" → skip to Step 4.

#### Commit

```bash
cd "$(chezmoi source-path)"

chezmoi git -- add -A

if [ -n "$commit_msg" ]; then
  msg="$commit_msg"
else
  count=$(chezmoi git -- diff --cached --name-only | wc -l)
  if [ "$count" -gt 20 ]; then
    msg="sync: 更新 $count 个 dotfiles"
  else
    files=$(chezmoi git -- diff --cached --name-only | tr '\n' ' ')
    msg="sync: $files"
  fi
fi

echo "📝 提交: $msg"
chezmoi git -- commit -m "$msg"

echo "⬆️  推送..."
chezmoi git -- push origin main
echo "✅ 推送成功"
```

### Step 4: Final Verification

```bash
cd "$(chezmoi source-path)"

echo "=== 同步完成 ==="
echo "  HEAD:      $(chezmoi git -- rev-parse --short HEAD)"
echo "  origin/main: $(chezmoi git -- rev-parse --short origin/main)"
if [ "$(chezmoi git -- rev-parse HEAD)" = "$(chezmoi git -- rev-parse origin/main)" ]; then
  echo "  ✅ 本地 ↔ 远程 一致"
else
  echo "  ⚠️  本地与远程不同步"
fi

echo ""
echo "最近提交:"
chezmoi git -- log --oneline -5
```

## Error Handling

| Situation | Behavior |
|-----------|----------|
| chezmoi not installed | Stop, tell user to install chezmoi |
| Source state not a git repo | Stop, tell user: `chezmoi init` |
| No remote `origin` | Stop, tell user to configure remote |
| Git network error | Stop, show error, suggest retry later |
| Conflict auto-resolve fails | Show analysis, ask user for direction |
| Push rejected (remote ahead) | Stop, tell user to re-run (pull catches new commits) |

## Usage Examples

```text
@agent use chezmoi-sync                                           # basic sync
@agent use chezmoi-sync commit_msg: "feat: 更新 git 和 zsh 配置" # custom message
@agent use chezmoi-sync skip_confirm: true                        # unattended
```

## Safety Rules

1. **Never force push** — if push is rejected, remote changed → pull first
2. **Never delete files** without user confirmation
3. **All git operations** use `chezmoi git -- <cmd>`
4. **Autostash is safe** for dotfiles — local changes are reapplied after pull
5. **Conflict auto-resolve** requires clear dominance (>7 day gap or <1 day);
   ambiguous conflicts always go to user
6. **Stash pop conflicts** use same heuristic as main conflicts — never silently
   discard local changes
