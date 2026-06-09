---
name: cnife-skills-repo
description: Guide to managing and optimizing skills in the CNife/skills repository — quality gates, creation/publishing workflow, and the sub-agent verification loop for automated skill auditing and repair. Use when working with this repository, adding or modifying skills, running bulk operations across skills, or when the user mentions skill quality, verification, or repo maintenance.
---

# CNife Skills Repository

Personal skills repository published to `github.com/CNife/skills`. Skills are organized by category under `<category>/<name>/` and are installed via `bunx skills add CNife/skills@<name>`.

```text
<skill-name>/
├── SKILL.md              # Required — skill definition
├── scripts/              # Python scripts (PEP 723)
└── references/           # Reference files
```

## Quality Gates

Every skill in the repository MUST pass these checks before publishing.

### Python Scripts (scripts/)

All Python scripts use PEP 723 inline metadata:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = []  # or ["package>=ver"]
# ///
```

Run before commit:

```bash
cd <repo-root>
uv run ruff check --fix .
uv run ruff format .
```

### SKILL.md Frontmatter

Required fields:

```yaml
---
name: <skill-name>          # lowercase, hyphens
description: >              # single-line trigger description
  What this skill does and when to load it. Be specific about triggers.
---
```

Verify frontmatter across all skills:

```bash
python3 -c "
import yaml, glob
for f in sorted(glob.glob('*/SKILL.md')):
    with open(f) as fh:
        meta = yaml.safe_load(fh.read().split('---')[1])
    name = f.split('/')[0]
    errors = []
    if not meta.get('name'): errors.append('missing name')
    if not meta.get('description'): errors.append('missing description')
    status = '❌ ' + ', '.join(errors) if errors else '✅'
    print(f'{status} {name}')
"
```

### Pre-commit Hooks

Configured in `.pre-commit-config.yaml`:

- pre-commit-hooks (format/validate)
- uv-pre-commit (`uv lock`)
- ruff-pre-commit (check + format)
- rumdl (markdown linting)

## Skill Creation / Publishing Workflow

```bash
# 1. Create skill directory and SKILL.md
mkdir -p <name>/scripts
# Write SKILL.md with frontmatter

# 2. Quality checks
uv run ruff check --fix <name>/
uv run ruff format <name>/

# 3. Update README.md skill table
# Add row in README.md

# 4. Publish
git add -A
git commit -m "feat(<name>): brief description"
git push

# 5. Install globally (skills.sh)
bunx skills add CNife/skills@<name> -g -y
```

## Sub-Agent Verification Loop

Use `delegate_task` to run a closed-loop audit-fix-verify cycle when bulk-maintaining skills. This prevents the main agent from declaring work done when issues remain.

### Workflow

```text
Phase 1: Sub-agent scans + reports issues
         ↓
Phase 2: Main agent fixes each issue
         ↓
Phase 3: Sub-agent re-verifies → issues remain? → back to Phase 2
                             → all clear?  → done
```

### Phase 1: Scan (sub-agent)

Spawn a sub-agent with **read-only tools only** (`toolsets=["file"]`) to scan all skills and produce a structured issue report:

```markdown
## Issues Report

### Missing PEP 723 header

- foo/scripts/run.py
- bar/scripts/deploy.py

### SKILL.md missing frontmatter `description`

- baz/SKILL.md

### Ruff compliance failures

- qux/scripts/analyze.py:15: unused import

### Stale README.md (skill listed but directory missing)

- archived-skill (in README but no directory)
```

Pass a clear context to the sub-agent listing what to check:

```python
from hermes_tools import delegate_task

result = delegate_task(
    goal="Scan all skills in the repository and report issues",
    context="""Check each skill for:
1. SKILL.md has valid frontmatter (name + description)
2. Python scripts in scripts/ have PEP 723 headers
3. ruff compliance (run ruff check --fix dry-run)
4. README.md matches actual skill directories""",
    toolsets=["file", "terminal"],
)
```

The sub-agent returns a structured markdown report. **Do not skip this step — always verify the report exists with actual findings before proceeding.**

### Phase 2: Fix (main agent)

Work through each issue category from the report:

1. **Bulk fixes first** — use `execute_code` or `patch` for repeated patterns (same fix across N files)
2. **Manual fixes second** — unique per-skill issues
3. **Commit strategically** — group related fixes into atomic commits; do NOT lump unrelated changes (README update + code fix + new skill) into one commit

### Phase 3: Re-verify (sub-agent)

Spawn the same sub-agent again with the same scan criteria. Compare against Phase 1's report:

- **If new issue count == 0** → verification passed, proceed to final commit + push
- **If new issue count < previous count** → progress made, loop back to Phase 2
- **If new issue count >= previous count** → the fix approach is wrong, pause and reassess strategy

Use a fresh sub-agent instance to avoid stale context biasing the verification.

### Loop Termination

| Condition | Action |
|-----------|--------|
| 3 consecutive rounds without reduction | Abort loop, report blockers to user |
| All issues resolved | Final commit, push, done |
| Partial resolution + user decides remaining are acceptable | Commit partial, note remaining as known issues |

## Single-Skill Optimization Loop

对单个技能做迭代优化时，使用测试→审查→反思→优化的循环，而非一次性改完。

### The Loop

```text
  ┌─ 1. 在干净上下文中启动 subagent 测试技能
  │
  ├─ 2. 审查 subagent 的工作路径
  │      ├── 消息：prompt 是否够自包含？
  │      ├── 思考：subagent 是否理解了任务？
  │      ├── 工具调用：有没有冗余或报错？
  │      └── 错误：哪一步出问题了？
  │
  ├─ 3. 评估技能效果，确定改进方向
  │      ├── 结果正确吗？
  │      ├── 路径直接简洁吗？
  │      └── 还有没有可优化的？
  │
  ├─ 4. 优化技能（改 SKILL.md / 加脚本）
  │
  └─ 回到 1，直到路径足够直接简洁
```

### Prompt 设计原则

Worker subagent 的 prompt 必须**自包含**——给全执行步骤和命令，不要让它第一手读 SKILL.md。

```text
# 好的 prompt：步骤写死，不需要额外读文件
操作步骤：
1. 检查缓存是否存在，不存在则下载
2. 运行查询命令
3. 返回结果

# 差的 prompt：只给意图，subagent 得自己读 SKILL.md 找命令
查一下 openai 的模型
```

### 审查关注点

| 关注点 | 怎么看 |
|--------|--------|
| **消息** | subagent 的 prompt 完整吗？还是需要额外追问？ |
| **思考** | subagent 理解了任务意图吗？还是理解偏了？ |
| **工具调用** | 有没有冗余的读文件？能不能合并 bash 调用？ |
| **错误** | 命令报错过吗？字段路径对不对？ |
| **路径长度** | 能否用更少的 tool calls 完成同样的事？ |

### 停止条件

循环终止于 **路径足够直接简洁**。标志：

- subagent 的 tool calls 无明显冗余
- prompt 自包含，subagent 不需要额外读 SKILL.md
- 结果正确，不需要二次修正
- 审查时找不到明显可优化的点
