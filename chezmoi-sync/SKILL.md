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

One-command chezmoi dotfiles synchronization: fetch remote → pull → detect
local changes → ask user → commit → push → verify consistency.

## Prerequisites (confirmed before executing)

- chezmoi installed: `which chezmoi`
- Source state exists and is a git repo: `chezmoi source-path` and `git rev-parse --git-dir` inside it
- Remote `origin` configured: `git remote get-url origin`
- Remote HEAD branch: `main` (assumed; verify with `git symbolic-ref refs/remotes/origin/HEAD`)

## Skill Parameters

The workflow can be customized via these parameters in the skill invocation:

- `commit_msg`: Optional. Custom commit message. If omitted, auto-generated from changed file list.
- `skip_confirm`: Optional. If `true`, skip the confirmation prompt for local changes (auto-commit). Default: `false`.

## Workflow

### Step 0: Enter chezmoi source directory

```bash
chezmoi_source="$(chezmoi source-path)"
cd "$chezmoi_source" || exit 1
echo "🔧 同步 chezmoi dotfiles — $(pwd)"
```

### Step 1: Check local state

Check for uncommitted changes and record the current state.

```bash
# Record current HEAD for final verification
head_before=$(git rev-parse HEAD)

# Check for local changes
local_changes=$(git status --porcelain)
if [ -n "$local_changes" ]; then
  echo "📝 检测到本地变更:"
  git status --short
  echo "---"
  git diff --stat
else
  echo "✅ 本地没有未提交变更"
fi

# Check for unpushed commits
behind_remote=$(git log --oneline HEAD..origin/main 2>/dev/null)
ahead_remote=$(git log --oneline origin/main..HEAD 2>/dev/null)

if [ -n "$behind_remote" ]; then
  echo "⬇️  远程有 $({ echo "$behind_remote" | wc -l; }) 个新提交待拉取"
fi
if [ -n "$ahead_remote" ]; then
  echo "⬆️  本地有 $({ echo "$ahead_remote" | wc -l; }) 个提交待推送"
fi

# Show branch overview
echo "---"
echo "当前状态一览:"
echo "  本地 HEAD: $(git rev-parse --short HEAD)"
echo "  远程:      $(git rev-parse --short origin/main 2>/dev/null || echo 'N/A')"
```

### Step 2: Pull remote changes

```bash
# Fetch first to get latest remote state
echo "🔄 获取远程变更..."
git fetch origin

# Check if remote has new commits
remote_new=$(git log --oneline HEAD..origin/main)
if [ -z "$remote_new" ]; then
  echo "✅ 远程没有新变更，跳过拉取"
else
  echo "⬇️  拉取远程变更..."
  echo "$remote_new"

  # Try pull with rebase + autostash (cleanest for dotfiles repos)
  # --autostash: temporarily stash local uncommitted changes
  # --rebase: keep history linear, avoid merge commits
  if git pull --autostash --rebase; then
    echo "✅ 拉取成功"
  else
    echo "⚠️  拉取产生冲突，进入冲突分析..."
    # Conflict analysis is handled below
  fi
fi
```

#### Conflict Analysis (Smart Auto-resolve)

If `git pull --autostash --rebase` fails due to conflicts, perform a
per-file analysis to determine whether the agent can auto-resolve:

```bash
# Find conflicted files (from rebase or stash pop)
conflicted_files=$(git diff --name-only --diff-filter=U)

echo "🔍 分析冲突文件..."

# Collect analysis for each conflicted file
analysis_log=""
auto_resolve=""
needs_user=""

for file in $conflicted_files; do
  echo "---"
  echo "📄 文件: $file"

  # --- Analysis ---

  # 1. Local file modification time (mtime) from filesystem
  if [ -f "$file" ]; then
    local_mtime=$(stat -c %Y "$file" 2>/dev/null || echo "0")
    local_mtime_hr=$(date -d @"$local_mtime" '+%Y-%m-%d %H:%M' 2>/dev/null || echo "unknown")
  else
    local_mtime="0"
    local_mtime_hr="(deleted)"
  fi

  # 2. Last commit date on local branch
  local_commit_date=$(git log -1 --format=%ct HEAD -- "$file" 2>/dev/null || echo "0")
  if [ "$local_commit_date" != "0" ]; then
    local_commit_hr=$(date -d @"$local_commit_date" '+%Y-%m-%d %H:%M' 2>/dev/null || echo "unknown")
  else
    local_commit_hr="(never)"
  fi

  # 3. Last commit date on remote branch
  remote_commit_date=$(git log -1 --format=%ct origin/main -- "$file" 2>/dev/null || echo "0")
  if [ "$remote_commit_date" != "0" ]; then
    remote_commit_hr=$(date -d @"$remote_commit_date" '+%Y-%m-%d %H:%M' 2>/dev/null || echo "unknown")
  else
    remote_commit_hr="(never)"
  fi

  # 4. Show conflict markers (side-by-side not possible, show snippets)
  conflict_lines=$(grep -c '^<<<<<<<' "$file" 2>/dev/null || echo "0")

  echo "  本地修改时间: $local_mtime_hr"
  echo "  本地最近提交: $local_commit_hr"
  echo "  远程最近提交: $remote_commit_hr"
  echo "  冲突块数: $conflict_lines"
  echo ""
  echo "  冲突内容预览:"
  grep -A2 '^<<<<<<<' "$file" 2>/dev/null | head -20
  echo "  ---"
  grep -A2 '^=======' "$file" 2>/dev/null | head -10
  echo "  ---"
  grep -A2 '^>>>>>>>' "$file" 2>/dev/null | head -10

  # --- Decision ---

  # If file was deleted on one side
  if [ ! -f "$file" ]; then
    analysis_entry="$file | 已删除 | 本地删除，远程保留（或反之）"
    echo "  ⏭️  文件已在工作树外，跳过"
    needs_user="$needs_user $file"
    continue
  fi

  # Compare timestamps to determine which side is newer
  # If local hasn't been touched for a while and remote is newer
  now=$(date +%s)
  days_since_local_commit=$(( (now - local_commit_date) / 86400 ))

  if [ "$remote_commit_date" -gt "$local_commit_date" ] && [ "$days_since_local_commit" -gt 7 ]; then
    # Remote changes are significantly newer → auto-resolve with theirs
    echo "  ✅ 自动解决: 远程变更较新（本地最近提交 ${days_since_local_commit} 天前），采用远程版本"
    git checkout --theirs -- "$file"
    git add "$file"
    auto_resolve="$auto_resolve ✅ $file (采用远程)"
  elif [ "$local_commit_date" -ge "$remote_commit_date" ] && [ "$days_since_local_commit" -lt 1 ]; then
    # Local changes are very recent → auto-resolve with ours
    echo "  ✅ 自动解决: 本地有最近变更，采用本地版本"
    git checkout --ours -- "$file"
    git add "$file"
    auto_resolve="$auto_resolve ✅ $file (采用本地)"
  else
    # Ambiguous — ask the user
    echo "  🤔 无法自动判断，需要用户确认"
    needs_user="$needs_user $file"
  fi
done

echo ""
echo "--- 冲突分析报告 ---"
if [ -n "$auto_resolve" ]; then
  echo "🟢 自动解决:"
  echo "$auto_resolve" | while read -r line; do echo "  $line"; done
fi
if [ -n "$needs_user" ]; then
  echo "🟡 需要用户裁决:"
  for f in $needs_user; do echo "  - $f"; done
fi

if [ -n "$needs_user" ]; then
  # Present the unresolved conflicts to the user with analysis
  echo ""
  echo "以下文件无法自动解决，请确认处理方式："
  echo "  1) 采用本地版本 (git checkout --ours)"
  echo "  2) 采用远程版本 (git checkout --theirs)"
  echo "  3) 手动编辑后告诉我继续"
  echo ""
  echo "→ 请告诉我每个文件的处理方式。"
  # Agent: wait for user response, then apply per-file
fi

# If all conflicts resolved, continue rebase
if [ -z "$(git diff --name-only --diff-filter=U)" ]; then
  git rebase --continue
  echo "✅ 冲突已全部解决，拉取完成"
fi

# Handle post-rebase stash pop conflict (rare, but possible)
stash_conflicts=$(git diff --name-only --diff-filter=U)
if [ -n "$stash_conflicts" ]; then
  echo "⚠️  自动存储弹出产生冲突，这些是本地修改与拉取后的版本冲突:"
  for f in $stash_conflicts; do
    echo "  - $f (自动采用拉取后版本)"
    git checkout --theirs -- "$f" 2>/dev/null && git add "$f"
  done
  echo "✅ 存储冲突已解决"
fi
```

### Step 3: Check for local changes (after pull)

After pulling, check if there are remaining local uncommitted changes:

```bash
# Check for local changes (including any that were stashed and popped)
final_changes=$(git status --porcelain)
if [ -z "$final_changes" ]; then
  echo "✅ 同步完成，本地没有未提交变更"
  echo "  本地:  $(git rev-parse --short HEAD)"
  echo "  远程:  $(git rev-parse --short origin/main)"
  echo ""
  echo "最近提交:"
  git log --oneline -3
  return 0
fi

echo "📝 同步后有 $(echo "$final_changes" | wc -l | tr -d ' ') 个文件待提交:"
if [ -n "$final_changes" ]; then
  git status --short
  echo "---"
  echo "变更摘要:"
  git diff --stat
fi
```

### Step 4: Confirm and commit

Ask the user whether to commit and push. If user declines, skip to Step 5 to show current state (changes remain local).

```bash
# Ask user whether to commit and push
echo ""
echo "是否提交并推送这些变更到远程？(y/n)"
# Agent: wait for user response

# If user says yes:
git add -A

# Auto-generate commit message
changed_files=$(git diff --cached --name-only | head -20)
if [ $(git diff --cached --name-only | wc -l) -gt 20 ]; then
  commit_msg="sync: 同步 $(git diff --cached --name-only | wc -l) 个 dotfiles 变更"
else
  commit_msg="sync: $(echo "$changed_files" | tr '\n' ' ')"
fi

echo "提交信息: $commit_msg"
git commit -m "$commit_msg"
echo "✅ 提交成功: $(git rev-parse --short HEAD)"

git push origin main
echo "✅ 推送成功"
```

### Step 5: Final state verification

```bash
echo ""
echo "=== 同步完成 ==="
echo "  本地:  $(git rev-parse --short HEAD)"
echo "  远程:  $(git rev-parse --short origin/main)"
if [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ]; then
  echo "  ✅ 本地 ↔ 远程 一致"
else
  echo "  ⚠️  本地和远程不同步，可能还有其他设备未推送的变更"
fi

echo ""
echo "最近提交:"
git log --oneline -5
```

## Error Handling

| Situation | Behavior |
|-----------|----------|
| chezmoi not installed | Stop, tell user to install chezmoi |
| Source state not a git repo | Stop, tell user to init: `chezmoi init` |
| No remote `origin` | Stop, tell user to configure remote |
| Git network error | Stop, show error, suggest retry later |
| Conflict auto-resolve fails | Show analysis, ask user for direction |
| Push rejected (remote ahead) | Stop, tell user to re-run (pull will catch new commits) |

## Usage Examples

### Basic sync

```text
@agent use chezmoi-sync
```

### Sync with custom commit message

```text
@agent use chezmoi-sync
        commit_msg: "feat: 更新 git 和 zsh 配置"
```

### Unattended sync (auto-commit, no confirm)

```text
@agent use chezmoi-sync
        skip_confirm: true
```

## Safety Rules

1. **Never force push** — if push is rejected, something else changed remote → pull first
2. **Never delete files** without user confirmation
3. **All git operations** go through `chezmoi git` — never operate on the raw directory path
4. **Autostash is safe** for dotfiles — local changes are reapplied after pull
5. **Conflict auto-resolve** only applies when one side is clearly dominant (>7 day gap or <1 day recent); ambiguous conflicts always go to user
