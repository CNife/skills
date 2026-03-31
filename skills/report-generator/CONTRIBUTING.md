# Contributing to Report Generator Skill

## Quick Start

1. Clone the repo and install the plugin:
   ```bash
   git clone https://github.com/segmentstream/agent-skills.git
   cd agent-skills
   claude --plugin-dir .
   ```

2. Install the **skill-creator** plugin (required for running evals):
   ```bash
   claude plugin install skill-creator
   ```
   If you get "plugin not found in any installed marketplace", add the official marketplace first:
   ```bash
   claude plugin marketplace add https://github.com/anthropics/claude-plugins-official.git
   ```

3. Verify the skill loads:
   ```
   > /skills
   # Should show "Report Generator" in the list
   ```

4. Test it works:
   ```
   > Generate a channel performance report for Google Ads and Meta
   # Should produce a dark-themed HTML report
   ```

## Development Workflow

### 1. Understand the Architecture

```
skills/report-generator/
├── SKILL.md                          # Main skill (loaded by Claude)
├── assets/
│   ├── template.html                 # CSS design system + HTML shell
│   └── logo.svg                      # SegmentStream logo (inline SVG)
├── references/
│   ├── jsx-format.md                 # JSX/Cowork conventions
│   └── channel-icons.md              # Ad platform SVG icons
├── evals/
│   ├── trigger-eval.json             # Trigger accuracy test set
│   └── evals.json                    # Output quality eval cases with assertions
└── CONTRIBUTING.md                   # This file
```

**What agents load:** SKILL.md tells the agent to read `assets/template.html` + `assets/logo.svg`. Optionally reads `references/jsx-format.md` or `references/channel-icons.md` based on output format.

### 2. Making Changes

All changes are eval-driven. The process:

1. Add or update eval cases in `evals/evals.json` — describe what the output should look like via the prompt and assertions
2. Run evals with the skill-creator plugin and review the outputs visually
3. Leave feedback on what's wrong or missing (e.g., "numbers in callouts aren't highlighted", "drill-down columns are misaligned")
4. The skill-creator iteration loop applies fixes to `SKILL.md` and `assets/template.html` based on your feedback
5. Repeat until outputs match expectations

### 3. Testing Your Changes

Testing uses the **skill-creator** plugin. Ask Claude to run evals:

```
> Run evals for skills/report-generator using skills/report-generator/evals/evals.json
```

This will:
- Run each eval case with and without the skill (baseline comparison)
- Grade outputs against assertions in `evals.json`
- Generate a review viewer for visual inspection

#### Eval file format (`evals/evals.json`)

Each eval case has a prompt, expected output description, and verifiable assertions:

```json
{
  "skill_name": "html-report",
  "evals": [
    {
      "id": 1,
      "prompt": "Generate a channel performance report...",
      "expected_output": "Dark-themed HTML report with KPI cards...",
      "files": [],
      "expectations": [
        "Output is a complete self-contained HTML file",
        "Uses dark theme with --bg-primary: #000000",
        "Has SegmentStream logo SVG in the topbar"
      ]
    }
  ]
}
```

#### Quick manual testing

You can also test individual prompts directly:

```bash
# WITH skill
claude -p "Generate a monthly performance report for Google Ads" --plugin-dir .

# WITHOUT skill (baseline)
claude -p "Generate a monthly performance report for Google Ads" --disable-slash-commands
```

Compare outputs. If the agent:
- Uses wrong colors -- clarify in `assets/template.html` CSS + `SKILL.md`
- Skips components -- make `SKILL.md` more explicit about when to use them
- Misses branding -- check that template placeholders are documented in `SKILL.md`

#### Visual Testing

Open generated HTML files in a browser. Check:
- Dark theme renders correctly
- Fonts load (system fonts, no external dependencies)
- Components match the design system
- Print styles work (Cmd+P)

### 4. Two Output Formats

| Format | Environment | Charts | Template |
|--------|------------|--------|----------|
| **HTML** | Claude Code (local files) | Inline SVG (no external libs) | `assets/template.html` |
| **JSX** | Claude.ai / Cowork | Recharts (pre-loaded) | `references/jsx-format.md` |

When editing, update BOTH formats if the change affects shared design tokens (colors, fonts, spacing).

### 5. Key Constraints

- **`template.html` must stay self-contained** -- no external CSS/font/JS imports
- **`SKILL.md` < 15KB** -- agents read this fully; keep it concise
- **`template.html` < 25KB** -- agents read this as CSS reference
- **Channel icons are inline SVG** -- no external image URLs
- **Dark theme only** -- no light mode toggle (keeps CSS simple)
- **System fonts** -- no Google Fonts or CDN font imports

### 6. Submitting Changes

1. Create a branch: `git checkout -b feat/report-generator-new-component`
2. Make changes to skill files
3. Run evals: ask Claude to `run evals for skills/report-generator`
4. Open PR with:
   - What changed
   - Screenshots of generated reports (before/after)
   - Eval results
