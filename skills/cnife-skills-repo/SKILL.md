---
name: cnife-skills-repo
description: Guide to the CNife/skills repository structure, Python project standards, pre-commit hooks, and PEP 723 single-script mode. Use when creating or modifying skills in ~/personal_code/skills/, setting up Python scripts for skills, configuring ruff/pre-commit, or when the user mentions their skills repository, adding a new skill to CNife/skills, or asks about the skill creation workflow. Also load when working with Python scripts inside any skill's scripts/ directory.
---

# CNife Skills Repository

Personal skill repository at `~/personal_code/skills/`, published to `github.com/CNife/skills`.

## Repository Structure

```
~/personal_code/skills/
├── .gitignore              # Python project ignores (pyc, cache, venv, uv.lock)
├── .pre-commit-config.yaml # pre-commit hooks
├── LICENSE
├── README.md               # Skill table with links
├── pyproject.toml          # Root Python project config
├── uv.lock                 # Dependency lock file
└── skills/
    ├── <skill-name>/
    │   ├── SKILL.md
    │   ├── scripts/
    │   │   └── <script>.py    # PEP 723 single-script mode
    │   └── references/
    ...
```

## Python Project Standards

### Root pyproject.toml

```toml
[project]
  name = "cnife-skills"
  version = "0.1.0"
  requires-python = ">=3.11"
  dependencies = ["pyyaml>=6.0"]

[tool.ruff]
  line-length = 100
  target-version = "py311"

  [tool.ruff.lint]
    extend-select = ["I", "B", "UP", "C4", "PIE", "RUF", "W"]
    # 允许中文全角标点
    allowed-confusables = ["，", "。", "：", "；", "！", "？", "（", "）", "【", "】", "《", "》"]

    [tool.ruff.lint.isort]
      split-on-trailing-comma = false

  [tool.ruff.format]
    skip-magic-trailing-comma = true
```

### PEP 723 Single-Script Mode

Every Python script in `scripts/` MUST use PEP 723 inline metadata:

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]  # or [] if stdlib-only
# ///
"""Script docstring..."""
```

Run with `uv run scripts/<script>.py`. uv auto-creates isolated env and installs deps.

### Ruff Compliance

Before committing:
```bash
cd ~/personal_code/skills
uv run ruff check --fix skills/
uv run ruff format skills/
uv lock
```

Common fixes: `Dict/List/Tuple/Set` → `dict/list/tuple/set`, import sorting, unused imports, bare `except` → specific exceptions, `raise ... from err`, unnecessary `mode="r"`.

### Pre-commit Hooks

- **pre-commit-hooks**: large files, merge conflicts, yaml/toml/json validation, debug statements, private keys, EOF fixer, line endings, trailing whitespace
- **uv-pre-commit**: `uv lock`
- **ruff-pre-commit**: `ruff check --fix` + `ruff format`
- **rumdl-pre-commit**: Markdown linting and formatting

## Skill Creation Workflow

1. Create/modify in `~/personal_code/skills/skills/<skill-name>/`
2. Add PEP 723 header to Python scripts
3. Run ruff check/format + uv lock
4. Update README.md skill table
5. `git add -A && git commit -m "简短中文描述" && git push`
6. `bunx skills add CNife/skills@<skill-name> -g -y`
7. Hermes discovers via `skills.external_dirs: [~/.agents/skills/]`

## Quality Gates

- All Python scripts pass `ruff check` and `ruff format`
- All scripts have PEP 723 inline metadata
- No `__pycache__/` or `.pyc` committed
- No `uv.lock` committed (in .gitignore)
- Git commit: short Chinese, one line, no prefix
- `uv lock` runs via pre-commit

## Audit: Identifying Unused Skills

The `audit-hermes-agent-skills` skill analyzes usage from `~/.hermes/state.db`:
- **standalone** (only in `~/.hermes/skills/`): safe to delete
- **external** (in `~/.agents/skills/`): shared across ALL agents — confirm before deleting
- **builtin** (Hermes built-in): disable via `config.yaml` `skills.disabled`
