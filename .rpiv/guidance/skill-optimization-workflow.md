---
title: "Skill Optimization Workflow"
description: "Workflow patterns and traps learned from optimizing utility/models-dev-query. Apply to future skill work."
---

## Skill Optimization Workflow

This document captures the process and concrete lessons from optimizing the `utility/models-dev-query` skill, from initial requirement through testing, review, and commit.

### Flow

```text
discover → implement → subagent test → review → advisor → commit
```

| Phase | What | Why |
|-------|------|-----|
| `discover` | 2-3 intent questions → lightweight probe → interview loop → FRD | Intent before code; lazy tree, not full pre-build |
| implement | Write SKILL.md (or edit). Sync install copies. | Source under `<category>/<name>/`, copy to both `~/.agents/skills/<name>/` and `~/.pi/agent/skills/<name>/` |
| subagent test | Spawn worker subagent in clean context | Isolated execution, no context bleed from main chat |
| review | reviewer subagent with targeted scope | Narrower = faster (78s vs 373s for full sweep) |
| advisor | Call advisor for sign-off | Catches what reviewer missed and validates verification rigour |
| commit | `git add -A && git commit` | Let pre-commit hooks auto-fix MD/ruff issues |

### Subagent Testing Patterns

#### Worker Type (Fast, Self-Contained)

Worker subagents work best when the prompt is fully self-contained — include exact steps and commands, so the worker doesn't need to read SKILL.md as a first step (which wastes ~5-8s and tokens).

**Good prompt shape:**

```text
1. Set CACHE=...
2. [ -f "$CACHE" ] || curl -sL ... -o "$CACHE"
3. jq '...' "$CACHE"
4. Return results
```

#### Reviewer Type (Narrow vs Broad)

- **Broad sweep** (test every command): ~373s, 28 tool uses — use only on final sign-off
- **Targeted review** (verify specific fixes): ~78s, 9 tool uses — use after each fix iteration

Always scope the reviewer prompt to specific items to review, not "review everything".

### Common jq Traps in catalog.json Queries

#### Trap 1: `null < N` is `true`

```jq
# BAD — includes models with .cost.input == null
select(.cost.input < 1 and ...)

# GOOD — guard null first
select(.cost.input != null and .cost.input < 1 and ...)
```

#### Trap 2: `as $var` then jq shorthand pulls from root `.`, not `$var`

```jq
# BAD — {reasoning, tool_call} reads from root ., not $p.models[...]
.providers["P"] as $p | {reasoning, tool_call}

# GOOD — explicit path
.providers["P"] as $p | {reasoning: $p.models["M"].reasoning}
```

#### Trap 3: Pipeline order

```jq
# BAD — sort after enumerate (sorts individual strings, no-op)
keys | .[] | sort

# GOOD — sort array before enumerate
keys | sort | .[]
```

#### Trap 4: Stale hardcoded counts

```markdown
# BAD — 4806 条 (goes stale as catalog grows)

## GOOD — 约 5000+ 条
```

### SKILL.md Quality Gates (for this repo)

Per `utility/cnife-skills-repo/SKILL.md`:

| Check | Command |
|-------|---------|
| Frontmatter: name + description | `grep -E '^name:|^description:' SKILL.md` |
| Name matches directory | `echo "dir: $(basename $(dirname SKILL.md))"` vs `grep '^name:' SKILL.md` |
| No hardcoded paths | `rg '~/|/home/|/mnt/' SKILL.md` |
| File size < 500 lines | `wc -l SKILL.md` |
| Ruff compliance | `uv run ruff check <category>/<name>/` |
| README.md lists skill | `grep -c '<name>' README.md` |
| Sync install copies | `cp SKILL.md ~/.agents/skills/<name>/SKILL.md && cp SKILL.md ~/.pi/agent/skills/<name>/SKILL.md` |
| Pre-commit passes | `git commit` triggers hooks; common fix: rumdl auto-fixes MD031/MD032 |

### Pi Agent Skills Installation Paths

Two install locations on this machine — both must be synced after SKILL.md changes:

| Location | Purpose |
|----------|---------|
| `~/.agents/skills/<name>/SKILL.md` | Old skill registry |
| `~/.pi/agent/skills/<name>/SKILL.md` | Pi agent skills directory |

### Session Logs

Session logs live under `~/.pi/agent/sessions/--<sanitized-cwd>--/`. They record the main conversation but **do not persist subagent internal tool calls** — only the final summary text is recoverable. This means:

- Subagent verification must be done via result output review, not session log analysis
- To capture subagent tool calls for debugging, include explicit logging instructions in the subagent prompt

### Before Committing

1. [ ] `uv run ruff check --fix .` — Python compliance
2. [ ] SKILL.md `name:` matches directory name
3. [ ] SKILL.md `description:` has trigger phrases
4. [ ] Changed SKILL.md → synced to both install copies
5. [ ] README.md updated if new skill or renamed
6. [ ] `git add -A && git commit` — hooks auto-fix rumdl issues (run again if hooks modify files)
