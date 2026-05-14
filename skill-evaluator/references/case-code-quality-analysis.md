# Case: Code Quality Analysis Skills Evaluation

**Date:** 2026-05-07
**Source session:** User asked for skills to find "屎山代码" (spaghetti code) and optimize code structure.
**Methodology:** skill-evaluator flow — multi-source search, SKILL.md review, security audit, comparison.

## Search Terms Used

- `code smell`, `refactoring`, `code quality`, `技术债务`, `代码质量`, `重构`

## Platforms Searched

- **skills.sh** (bunx skills find)
- **SkillHub** (skillhub search)

## Candidates Found

### From skills.sh

| Skill | Source | Installs | Stars (parent) | Last Commit |
|-------|--------|----------|----------------|-------------|
| rysweet/amplihack@code-smell-detector | skills.sh | 207 | 58 | 2026-04-25 (active) |
| nishilbhave/codeprobe@codeprobe-code-smells | skills.sh | 34 | 4 | 2026-04-23 (low) |
| jackjin1997/clawforge@clean-code-zh | skills.sh | 44 | — | — |
| addyosmani/agent-skills@code-review-and-quality | skills.sh | 2.7K | 31.7K | 2026-05-07 (very active) |
| decebals/claude-code-java@performance-smell-detection | skills.sh | 48 | — | — |

### From SkillHub

| Skill | Slug | Version |
|-------|------|---------|
| bookforge-code-smell-diagnosis | bookforge-code-smell-diagnosis | 1.0.0 |
| code-smell-analyzer | code-smell-analyzer | 1.0.0 |
| hefestoai-auditor | hefestoai-auditor | 2.2.0 |
| code-quality-guardian | code-quality-guardian | 1.0.0 |
| yuyonghao-code-refactor | yuyonghao-code-refactor | 0.1.0 |
| clean-code-review | clean-code-review | 2.0 |
| refactoring | refactoring | 1.0.0 |
| code-refactoring | code-refactoring | 1.0.0 |

## Top Candidates Detail

### 1. bookforge-code-smell-diagnosis (SkillHub)

**Type:** Pure AI agent skill (no external tools)
**Language:** Universal
**Detects:** All 22 named code smells from Fowler's Refactoring catalog:
- Duplicated Code, Long Method, Large Class, Long Parameter List, Divergent Change
- Shotgun Surgery, Feature Envy, Data Clumps, Primitive Obsession, Switch Statements
- Parallel Inheritance Hierarchies, Lazy Class, Speculative Generality, Temporary Field
- Message Chains, Middle Man, Inappropriate Intimacy, Alternative Classes with Different Interfaces
- Incomplete Library Class, Data Class, Refused Bequest, Comments

**Each smell maps to its Fowler-prescribed refactoring** with conditional branches (e.g., Duplicated Code branches by same-class / sibling-subclasses / unrelated-classes).

**Safety: 9/10** — Pure SKILL.md (552 lines), no scripts, no network calls, read-only.
**Install:** `skillhub --dir ~/.hermes/skills/ install bookforge-code-smell-diagnosis`
**Sibling skills:** bookforge-method-decomposition-refactoring, bookforge-big-refactoring-planner, bookforge-data-organization-refactoring

### 2. code-smell-detector (amplihack, skills.sh)

**Type:** Pure AI agent skill
**Language:** Universal (with Python emphasis)
**Detects:** 5 anti-patterns from amplihack philosophy:
1. Over-abstraction (unnecessary ABCs, deep inheritance)
2. Complex inheritance (>2 levels)
3. Large functions (>50 lines)
4. Tight coupling (hardcoded instantiation)
5. Missing `__all__` exports (Python)

**Output:** Before/after code examples, detection checklists, fix strategies
**Safety: 9/10** — Pure SKILL.md + README, no scripts, read-only.
**Install:** `bunx skills add rysweet/amplihack@code-smell-detector -g -y`
**⚠️ Note:** Heavily tied to amplihack philosophy; some rules (__all__) are Python-specific.

### 3. codeprobe (skills.sh)

**Type:** Multi-agent audit orchestrator (9 sub-skills)
**Language:** Universal (PHP/Python/JS/TS with language-specific references)
**Detects:**
- Security vulnerabilities
- SOLID violations
- Architecture issues + dependency cycles
- Code smells
- Performance problems
- Error handling gaps
- Test quality
- Framework best practices

**Output:** Score 0-100 per category, severity P0-P3 findings, copy-paste fix prompts, full HTML/markdown report
**Scripts:** dependency_mapper.py (cycle detection), complexity_scorer.py, file_stats.py
**Safety: 8/10** — Has Python scripts but read-only. Report written to `./codeprobe-reports/`.
**Install:** `bunx skills add nishilbhave/codeprobe@codeprobe -g -y`
**⚠️ Caveat:** 34 installs, 4 stars — low community validation. Codebase may be immature.

### 4. code-quality-guardian (SkillHub)

**Type:** Local CLI tool with Python package
**Languages:** Python, JavaScript/TypeScript, Go
**Tools integrated:** flake8, pylint, bandit, radon, mypy, eslint, go vet
**Detects:** Code smells, complexity, security, style violations
**Output:** Console / JSON / HTML report
**Safety: 8/10** — Local tools, no network. Requires pip install dependencies.
**Install:** `skillhub --dir ~/.hermes/skills/ install code-quality-guardian` + `pip install radon flake8 pylint bandit`
**Chinese docs supported.** Configurable via `.quality.yml`.

### 5. hefestoai-auditor (SkillHub)

**Type:** Standalone CLI tool (hefesto-ai)
**Languages:** 17 languages including Python/TS/JS/Java/Go/Rust/C# + DevOps configs
**Detects:** SQL injection, hardcoded secrets, deep nesting, high cyclomatic complexity, long functions, semantic drift in AI code
**Output:** JSON/HTML/Text reports
**Safety: 8/10** — "All analysis runs locally. No code leaves your machine." Claims no network calls during analysis.
**Install:** `pip install hefesto-ai` then `hefesto analyze /path --severity HIGH`
**Pricing:** Free tier sufficient for basic analysis. Pro $8/mo for ML features.

## Security Comparison Matrix

| Skill | Scripts? | Network Calls? | Read-Only? | Risk Level |
|-------|----------|---------------|------------|------------|
| bookforge-code-smell-diagnosis | ❌ | ❌ | ✅ AI-only | 🔒 Low |
| code-smell-detector | ❌ | ❌ | ✅ AI-only | 🔒 Low |
| codeprobe | ✅ (3 Python scripts) | ❌ | ✅ (writes report only) | 🔒 Low-Med |
| code-quality-guardian | ✅ (full Python pkg) | ❌ | ✅ | 🔒 Low-Med |
| hefestoai-auditor | ✅ (pip install) | ❌ (claimed) | ✅ | 🔒 Low-Med |

## Recommendation Strategy

- **AI analysis only** (no dependencies, no install, no network): bookforge-code-smell-diagnosis (most comprehensive on code smells)
- **Hard data** (real tool output): code-quality-guardian (radon/flake8/bandit) or hefestoai-auditor (17 languages)
- **Full audit pipeline** (score + severity + fix prompts): codeprobe
- **Mix recommended**: bookforge for quick smell diagnosis + code-quality-guardian for hard metrics
