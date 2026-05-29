# `ast_grep_helper.py` — full subcommand reference

A single-file Python 3 stdlib wrapper. Same on every OS.

## `search` — find all matches of a pattern

```bash
python3 scripts/ast_grep_helper.py search 'console.log($MSG)' --lang ts src/
```

Validates the pattern offline first. If the pattern looks like regex (`\w`, `.*`, `|`, etc.) the helper exits with a hint and never calls `sg` — saves a round-trip. Pass `--force` to skip validation.

Flags:
- `--lang ts` (or any of the 25 languages; aliases like `js`, `py`, `rs`, `kt` accepted)
- `--globs '!**/*.test.ts'` (repeatable; prefix `!` to exclude)
- `-C 3` (context lines)
- `--json-out` (raw JSON instead of human format)

## `replace` — rewrite by pattern, dry-run by default

```bash
# Dry-run preview (default — no files mutated)
python3 scripts/ast_grep_helper.py replace 'console.log($MSG)' 'logger.info($MSG)' --lang ts src/

# Actually apply
python3 scripts/ast_grep_helper.py replace 'console.log($MSG)' 'logger.info($MSG)' --lang ts src/ --apply
```

The helper:
1. Validates both `pattern` and `rewrite` for hint-detectable mistakes.
2. Runs pass 1 with `--json=compact` to collect matches and show a preview.
3. If `--apply` is set, runs pass 2 with `--update-all` to mutate files.

## `scan` — run YAML rules

```bash
# Discover sgconfig.yml from cwd and run all rules
python3 scripts/ast_grep_helper.py scan src/

# Run a single rule file
python3 scripts/ast_grep_helper.py scan -r rules/no-console.yml src/

# Apply auto-fixes
python3 scripts/ast_grep_helper.py scan -U src/

# CI-friendly GitHub annotations
python3 scripts/ast_grep_helper.py scan --report-style short src/
```

## `validate` — offline pattern check (no `sg` call)

Useful for CI lints, pre-commit hooks, and quick sanity checks:

```bash
python3 scripts/ast_grep_helper.py validate '\w+' --lang ts
# → exit 2: regex \w not supported. Use $VAR for identifiers.

python3 scripts/ast_grep_helper.py validate 'console.log($MSG)' --lang ts
# → exit 0: pattern looks plausible for ast-grep.
```

## `langs` / `doctor` / `install`

```bash
python3 scripts/ast_grep_helper.py langs       # list 25 supported languages and aliases
python3 scripts/ast_grep_helper.py doctor      # check ast-grep binary availability
python3 scripts/ast_grep_helper.py install     # delegate to install.sh / install.ps1
```

`new` and `test` subcommands proxy directly to `sg new` and `sg test`.
