---
name: opencode-permission
description: >
  Manage OpenCode's permission rules in opencode.jsonc — add, remove, or list
  auto-approval rules for Bash commands and tool invocations so the agent stops
  asking for confirmation on every single command. Use whenever the user wants
  to auto-approve, deny, or require confirmation for a shell command, even if
  they don't mention "permission" or "opencode.jsonc" directly. Triggers on
  "允许 kubectl get *", "拒绝 rm -rf", "auto-approve npm run build", "总是执行
  git status", "add permission rule", "list my permissions", "查看权限",
  "添加权限", "移除权限", "把 X 加到允许列表", "skip confirmation for", and
  similar — even if the user doesn't explicitly mention OpenCode's config.
compatibility: Requires `uv` (auto-manages Python runtime). Uses `json-five` for JSONC round-trip comment preservation.
---

# OpenCode Permission Manager

Manage `permission.bash` rules in `~/.config/opencode/opencode.jsonc`. Add, remove, or list auto-approval rules for shell commands and tool invocations.

## Workflow

1. Identify the rule string and action from the user's request (e.g., `"kubectl get *"` → `allow`)
2. Determine the subcommand: `add` (default) / `remove` / `list` / `list-all`
3. Run the bundled script:
   ```bash
   uv run --script <skill-path>/scripts/manage_permission.py add "kubectl get *" --action allow
   ```
4. Confirm the change was written to the config file
5. Remind the user: **修改配置后需要重启 OpenCode 才能生效**

## Command Reference

### Add a rule

```bash
# Allow (default action)
uv run --script manage_permission.py add "kubectl get *"

# Explicit action
uv run --script manage_permission.py add "kubectl get *" --action allow
uv run --script manage_permission.py add "git commit *" --action ask
uv run --script manage_permission.py add "rm -rf *" --action deny

# Custom config path
uv run --script manage_permission.py add "kubectl get *" --config /path/to/opencode.jsonc
```

### Remove a rule

```bash
uv run --script manage_permission.py remove "kubectl get *"
```

### List rules

```bash
# List permission.bash only
uv run --script manage_permission.py list

# List all permission categories (bash, read, edit, etc.)
uv run --script manage_permission.py list-all
```

## Rule Format Reference

### Permission actions

| Value | Meaning |
|-------|---------|
| `allow` | Auto-execute, no confirmation needed |
| `ask` | Prompt for confirmation each time |
| `deny` | Block the command entirely |

### Wildcard syntax

| Symbol | Meaning | Example |
|--------|---------|---------|
| `*` | Matches zero or more characters | `"git *"` matches `git status`, `git diff --staged` |
| `?` | Matches exactly one character | `"ls ?"` matches `ls -l` but not `ls -la` |

**Important**: `"git status"` only matches `git status` with no arguments. To match with arguments, use `"git status *"`.

### Available permission keys

| Key | Matches | Description |
|-----|---------|-------------|
| `bash` | Shell command pattern | Command execution (e.g., `"kubectl get *"`) |
| `read` | File path | File reading operations |
| `edit` | File path | File modifications (edit/write/patch) |
| `glob` | Glob pattern | File wildcard search |
| `grep` | Regex pattern | Content search |
| `list` | Directory path | Directory listing |
| `task` | Subagent type | Subagent spawning |
| `lsp` | LSP query | Language server queries |
| `skill` | Skill name | Skill loading |
| `external_directory` | File path | Access outside working directory |
| `todowrite` | — | Todo writing (simple, no pattern matching) |
| `question` | — | Asking user questions (simple) |
| `webfetch` | URL | Web fetching (simple) |
| `websearch` / `codesearch` | Search query | Web/code search (simple) |
| `doom_loop` | — | Repeated tool call detection (simple) |

Simple keys (no pattern matching) accept only `"allow"`, `"ask"`, or `"deny"` as a string value.

### Rule matching logic

- **Last matching rule wins** — more specific rules override `"*"` defaults
- Common pattern: set `"*": "ask"` as fallback, then add specific `allow` rules
- Supports `~` and `$HOME` path expansion for file-related keys

### Configuration file format

- **Location**: `~/.config/opencode/opencode.jsonc` (global) or `<project>/.opencode/opencode.jsonc` (project-level)
- **Format**: JSONC (JSON with Comments) — supports `//` and `/* */` comments
- **Structure**:
  ```jsonc
  {
    "permission": {
      "edit": "ask",
      "bash": {
        "*": "ask",
        "kubectl get *": "allow",
        "git status *": "allow"
      }
    }
  }
  ```
- **Agent-level override**: Rules can also be set per-agent in the `agent` section, which take precedence over global rules

## Examples

### Allow all kubectl read operations

```bash
uv run --script manage_permission.py add "kubectl get *" --action allow
uv run --script manage_permission.py add "kubectl describe *" --action allow
```

### Allow git commit but require confirmation for push

```bash
uv run --script manage_permission.py add "git commit *" --action allow
uv run --script manage_permission.py add "git push *" --action ask
```

### Block dangerous commands

```bash
uv run --script manage_permission.py add "rm -rf *" --action deny
```

### View current rules

```bash
uv run --script manage_permission.py list
```

## Notes

- This script uses `json-five` (ModelLoader/ModelDumper) to preserve all existing comments in the config file during read-modify-write cycles
- New rules are appended to the end of the `permission.bash` object
- The script automatically creates the `permission` and `bash` sections if they don't exist (with `"*": "ask"` as the default bash rule)
