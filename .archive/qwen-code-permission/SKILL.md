---
name: qwen-code-permission
description: Automate adding permission rules to Qwen Code's settings.json. Use whenever the user wants to allow, deny, or require confirmation for a command in Qwen Code. Trigger on phrases like "把 X 加到允许列表"、"添加到允许"、"允许 Bash(X)"、"deny 某命令"、"permission rule"、"auto-approve this command"、"skip confirmation for"、"always allow" — even if the user doesn't explicitly mention Qwen Code's settings.json. Also use when working with Qwen Code permission configuration or troubleshooting auto-approval rules.
compatibility: Requires `uv` (auto-manages Python runtime)
category: qwen code
metadata:
  internal: true
---

# Qwen Code Permission Manager

Manage Qwen Code's `permissions.allow` / `permissions.ask` / `permissions.deny` in `settings.json`.

## Workflow

1. Identify the rule string from user request (e.g., `"Bash(. ~/.x-cmd.root/X)"`)
2. Determine the action: `allow` (default) / `ask` / `deny`
3. Run the bundled script (find it at `scripts/add_permission.py` relative to this skill):

   ```bash
   uv run --script <skill-path>/scripts/add_permission.py "Bash(. ~/.x-cmd.root/X)" --action allow
   ```

4. Confirm the change was written
5. Remind user: **配置更改需要重启 Qwen Code（`/exit` 后重新运行）才能生效**

## Rule Reference

### Tool name aliases

| Alias | Canonical tool |
|-------|---------------|
| `Bash` / `Shell` | `run_shell_command` |
| `Read` / `ReadFile` | `read_file` |
| `Edit` / `EditFile` | `edit` |
| `Write` / `WriteFile` | `write_file` |
| `Grep` / `SearchFiles` | `grep_search` |
| `Glob` / `FindFiles` | `glob` |
| `ListFiles` | `list_directory` |
| `WebFetch` | `web_fetch` |
| `Agent` | `task` |
| `Skill` | `skill` |

### Meta-categories

| Rule name | Tools covered |
|-----------|--------------|
| `Read` | `read_file` + `grep_search` + `glob` + `list_directory` |
| `Edit` | `edit` + `write_file` |

> `Read(/path/**)` matches all four read tools. To restrict only file reading, use `ReadFile(/path/**)` or `read_file(/path/**)`.

### Path pattern prefixes

| Prefix | Meaning | Example |
|--------|---------|---------|
| `//` | Absolute path from filesystem root | `//etc/passwd` |
| `~/` | Relative to home directory | `~/Documents/*.pdf` |
| `/` | Relative to project root | `/src/**/*.ts` |
| `./` | Relative to current working directory | `./secrets/**` |
| (none) | Same as `./` | `secrets/**` |

### Rule examples

| Rule | Meaning |
|------|---------|
| `"Bash"` | All shell commands |
| `"Bash(git *)"` | Commands starting with `git` (word boundary) |
| `"Bash(npm run *)"` | Any `npm run` script |
| `"WebFetch(api.example.com)"` | That domain and all subdomains |
| `"mcp__puppeteer"` | All tools from the puppeteer MCP server |

## Configuration

Qwen Code reads `~/.qwen/settings.json` (user) or `.qwen/settings.json` (project).
The `permissions` section:

```json
{
  "permissions": {
    "allow": ["Bash(git *)"],
    "ask": ["Bash(git push *)"],
    "deny": ["Bash(rm -rf *)"]
  }
}
```

**Decision priority:** `deny` > `ask` > `allow` > default. First matching rule wins.
`allow` rules merge across all scopes (user + project + system).
