---
name: ast-grep
description: "Search and rewrite code by AST structure across 25 languages with ast-grep (sg). Use when the task is structural - find function calls shaped like X, rewrite console.log to logger.info, find all `as any`, migrate require() to import, find empty catch blocks, missing await, codemod a class hierarchy, scan project against YAML rules. Preferred over grep when the user mentions code SHAPE or needs deterministic refactoring across many files. Triggers: 'ast-grep', 'sg', 'ast grep', 'astgrep', 'find all functions that', 'find every call to', 'codemod', 'structural search', 'pattern match code', 'replace pattern across files', 'rename function everywhere', 'find usages of pattern', 'apply this transformation to all', 'migrate X to Y'."
---

# ast-grep

`sg` (also installed as `ast-grep`) is an **AST-aware search and rewrite tool** across 25 languages. It treats your pattern as code, parses it the same way it parses your project, and matches structurally. It is the right tool whenever your question depends on **code shape** rather than text bytes.

This skill ships a Python wrapper at `scripts/ast_grep_helper.py` and platform install scripts at `install.sh` (POSIX) and `install.ps1` (Windows). The helper adds offline pattern validation, the two-pass write trick, and binary auto-resolution. Use it as your default entry point.

---

## When to use this skill

Use it whenever the user's question is about **code structure**, not bytes:

- "Find every function that takes a `Request` parameter."
- "Rewrite every `console.log(x)` to `logger.info(x)`."
- "Strip every `as any` cast."
- "Replace `require(...)` with `import` across the repo."
- "Find empty catch blocks."
- "Migrate `Optional[X]` to `X | None`."
- "Apply this codemod across these 200 files."
- "Run our YAML lint rules and surface violations."

Switch to plain `grep` / `rg` when the question is text-shaped (string literal contents, comments, license headers, file names, cross-language regex). When in doubt, ask: "does the answer depend on the language's syntax tree, or just on the file's bytes?" If the former, ast-grep. If the latter, grep.

---

## Three things the agent must internalize

### 1. ast-grep is NOT regex

The wildcards are `$VAR` (one AST node) and `$$$` (zero or more nodes). Regex syntax fails silently:

| You wrote | What ast-grep saw | What you wanted |
|---|---|---|
| `foo\|bar` | bitwise-or of `foo` and `bar` | run two separate searches |
| `.*foo` | not parseable | `$$$ foo` (if `$$$` is a list of nodes) or use `rg` |
| `\w+` | not parseable | `$VAR` to capture any identifier |
| `[a-z]` | character class, not parseable | switch to `rg` |

The full anti-pattern table is in `references/pitfalls.md` §1. The helper's `validate` subcommand catches these mechanically — call it before debugging "no matches" by hand.

### 2. Patterns must be valid code

The pattern itself must parse. `def $FN($$$):` fails because the trailing `:` makes it incomplete; use `def $FN($$$)`. `function $NAME` without params/body fails; use `function $NAME($$$) { $$$ }`. Full table per language in `references/pitfalls.md` §2.

### 3. `--update-all` and `--json` are mutually exclusive (silently)

This is the single biggest gotcha when scripting. `sg run -p P -r R --json --update-all` returns the JSON but **does not mutate files**. To both preview AND apply, run **two passes**:

```bash
sg run -p P -r R --json=compact .   # pass 1: see what would change
sg run -p P -r R --update-all .     # pass 2: actually apply
```

The helper does this automatically when you call `replace --apply`. Read `references/pitfalls.md` §9.

---

## The helper script — `scripts/ast_grep_helper.py`

A single-file Python 3 stdlib wrapper. Same on every OS. The agent's default entry point.

### `search` — find all matches
```bash
python3 scripts/ast_grep_helper.py search 'console.log($MSG)' --lang ts src/
```
Validates pattern offline; flags: `--lang`, `--globs`, `-C`, `--json-out`.

### `replace` — rewrite by pattern, dry-run by default
```bash
python3 scripts/ast_grep_helper.py replace 'console.log($MSG)' 'logger.info($MSG)' --lang ts src/
python3 scripts/ast_grep_helper.py replace 'console.log($MSG)' 'logger.info($MSG)' --lang ts src/ --apply
```
Validates both pattern and rewrite. Two-pass automatically (preview then mutate).

### `scan` — run YAML rules
```bash
python3 scripts/ast_grep_helper.py scan src/                          # auto-discover sgconfig.yml
python3 scripts/ast_grep_helper.py scan -U src/                       # apply auto-fixes
python3 scripts/ast_grep_helper.py scan --report-style short src/     # CI annotations
```

### `validate` — offline pattern check
```bash
python3 scripts/ast_grep_helper.py validate 'console.log($MSG)' --lang ts
python3 scripts/ast_grep_helper.py validate '\\w+' --lang ts         # catches regex misuse
```

### `langs` / `doctor` / `install`
```bash
python3 scripts/ast_grep_helper.py langs      # list 25 supported languages
python3 scripts/ast_grep_helper.py doctor     # check binary availability
python3 scripts/ast_grep_helper.py install    # auto-install sg binary
```

> Full subcommand reference in `references/helper.md`.

---

## Direct `sg` use (when the helper isn't enough)

The helper is opinionated. For full control, drop to `sg`. The skill ships a CLI cheat sheet in `references/cli.md`. The minimal idioms:

```bash
sg run -p 'console.log($MSG)' --lang ts src/                          # search
sg run -p 'console.log($MSG)' --lang ts --json=compact src/ | jq .    # search → JSON
sg run -p 'console.log($MSG)' -r 'logger.info($MSG)' --lang ts src/   # dry-run rewrite
sg run -p 'console.log($MSG)' -r 'logger.info($MSG)' --update-all .   # apply rewrite
echo 'console.log("hi")' | sg run -p 'console.log($MSG)' --lang js --stdin  # stdin pattern
sg run -p '$_' --lang ts --debug-query=cst src/file.ts | head -40     # inspect file AST
```

**Always single-quote patterns** in shell — `'$VAR'` not `"$VAR"`.

---

## Decision tree — what to use, when

```
USER asks for "find/rewrite/codemod"
│
├─ structural pattern (function shape, call, class, import, control flow)
│  └→ ast-grep (this skill)
│
├─ text pattern (regex, alternation, character classes, file names)
│  └→ rg / grep
│
├─ semantic question (what variable does this refer to? does this throw?)
│  └→ LSP tools, TypeScript compiler, Pyright, Semgrep with type inference
│
└─ multiple repos / federated search
   └→ a search engine + then ast-grep / rg / LSP per-repo
```

If the user says "find all" or "every", default to ast-grep when the target is shaped (function, class, call, import, statement). Default to rg when the target is text (string content, comment, license header, file name, identifier substring).

---



---

## When `sg` returns 0 matches but you know the code is there

In priority order:

1. **Run `helper validate '<pattern>' --lang <lang>`** — catches regex misuse, missing function bodies, Python trailing colons.
2. **Check `--lang`** — `sg` infers from extension; if you pass a `.tsx` file with `--lang ts` (not `tsx`), JSX won't parse.
3. **Inspect the parsed pattern**: `sg run -p '<pattern>' --lang <lang> --debug-query=ast --stdin <<< '<sample>'`. If it shows `ERROR` nodes, the pattern is malformed.
4. **Check the AST of the target file**: `sg run -p '$_' --lang <lang> --debug-query=cst path/to/file | head -40` — find the `kind` you're trying to match.
5. **Try the playground**: <https://ast-grep.github.io/playground.html> — paste code + pattern, see what's happening.

Do not blindly retry with variations. Each failure has a reason; surface it.

---

## When to use YAML rules vs inline `-p` patterns

**Use inline `-p`** when:
- One-off ad-hoc query.
- The pattern is simple (no constraints, no fix template).
- You're exploring.

**Use YAML rules** (file under `rules/`, run via `sg scan`) when:
- The pattern is reused (lint rule, codemod that runs in CI).
- You need `constraints`, `transform`, complex `inside`/`has`, or composite logic.
- You want auto-fix (`fix:` field).
- You want to test the rule (snapshot tests via `sg test`).

The full YAML rule schema is in `references/yaml-rules.md`. Project setup (`sgconfig.yml`, `ruleDirs`, `utilDirs`) is in `references/sgconfig.md`.

---



---

## Required reading (in order of priority)

| File | Read when | What it covers |
|------|----------|----------------|
| `references/patterns.md` | Pattern doesn't match as expected | Meta-variables, naming rules, strictness levels |
| `references/pitfalls.md` | 0 matches surprises you | Failure-mode field guide (regex misuse, trailing colons, --lang mismatch) |
| `references/recipes.md` | Starting a new task | Copy-paste patterns by language |
| `references/cli.md` | Helper isn't enough | `sg run`, `sg scan`, `sg test`, `sg new`, `sg lsp` full reference |
| `references/helper.md` | Need full subcommand docs | Every `ast_grep_helper.py` subcommand with flags and examples |
| `references/yaml-rules.md` | Outgrowing inline patterns | YAML rule schema, constraints, transforms, fix templates |
| `references/sgconfig.md` | Setting up `sg scan` for a project | Project-level configuration (`ruleDirs`, `utilDirs`) |
| `references/install.md` | `install.sh` / `install.ps1` fail | Per-OS install methods and troubleshooting |

---

## Invariants (do not break)

### Safety
- **Validate before searching.** Call `helper validate` on every new pattern. Catches ~70% of "0 matches" cases (regex misuse).
- **Dry-run before applying.** Never apply what you haven't inspected. Flow: `helper search` → `helper replace` (dry-run) → inspect → `helper replace --apply`.
- **Two-pass writes.** When using `sg` directly, `--json` silently disables `--update-all`. Run preview and apply as separate invocations.

### Correctness
- **Pattern is code, not regex.** `$VAR` = one AST node, `$$$` = many. Need `|`, `.*`, or `[a-z]`? Switch to `rg`.
- **Single-quote patterns in shell.** `'$VAR'` not `"$VAR"` — shell expands the latter to empty string.
- **`--lang` is required for stdin.** `sg` can't infer language from a pipe.
- **Linux: alias `sg` → `ast-grep`** — `sg` collides with `setgroups`. The helper handles this automatically.

### Output discipline
- `sg run --json=compact` → match objects `{ file, range, text, replacement?, lines, language }`. Pipe through `jq` for scripting.
- Helper defaults to `file:line:column + preview`; pass `--json-out` for raw JSON.
- **Always report file count**, not just match count. Users care about blast radius.
