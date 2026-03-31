---
name: Report Generator
description: Use this skill when the user asks to "create a report", "save this as a report", "make a nice report", "export to HTML", "generate an artifact", "build a dashboard", or when a substantial analysis has been completed and the user wants a polished, shareable output. Also trigger when the user says "save this", "export this", "make this pretty", "I need to share this with my team", "share this report", "get a link", or "send this to my client". Generates branded reports in the SegmentStream dark theme style — as self-contained HTML files (Claude Code), JSX artifacts (Cowork), or shared artifacts via shareable URL.
---

# Report Generator

Create polished reports styled after the segmentstream.ai website. Supports three output modes:

- **Claude Code** → Self-contained HTML file saved to `.artifacts/`, opened in browser
- **Cowork** → JSX artifact rendered inline with React, Tailwind, and Recharts
- **Shared artifact** → Content-only HTML uploaded via `share_artifact`, returns a shareable URL

The design system, content structure, and components are identical across all formats.

## When to Use

Generate an HTML report when:
- A substantial analysis has been completed and the user wants a shareable artifact
- The user explicitly asks for a report, export, or dashboard
- The conversation has produced data tables, insights, and recommendations that deserve a polished format

Do not auto-generate reports without the user asking — this is an explicit output format, not a default.

## Design System

The template at `assets/template.html` implements the segmentstream.ai visual identity:

- **Self-contained**: No external references — no CDN links, no @import URLs, no external fonts or scripts. System fonts only. All SVGs inlined. Reports must work fully offline.
- **Dark theme**: Black background (#000), card backgrounds (#111), subtle borders (white at 8% opacity)
- **Accent**: Indigo (#6366F1) for highlights, tags, and emphasis
- **Typography**: System sans-serif for body text, system monospace for data/tables/labels
- **Components**: KPI cards, data tables with channel icons, callout boxes, tags, inline SVG charts, bar indicators, two-column layouts
- **Channel icons**: Read `references/channel-icons.md` for inline SVG icons of ad platforms. Only ad platforms get icons; organic channels render as plain text.

Read `assets/template.html` to understand the full CSS class vocabulary before generating any report.

## Output Format

Detect the environment and choose the appropriate format:

**Claude Code** (local terminal, has filesystem + `open` command):
- Read `assets/template.html` and `assets/logo.svg`
- Generate a self-contained HTML file (no external references, system fonts, inline SVGs)
- Save to `.artifacts/{name}.html` and open in browser

**Cowork** (no browser, artifacts render inline):
- Read `references/jsx-format.md` for JSX component patterns and Tailwind token mapping
- Generate a single-file React component using Tailwind + Recharts for charts
- Write as a `.jsx` file — Cowork renders it as an artifact automatically

The user can also explicitly request a format: "save as HTML" or "make a JSX artifact."

## Workflow (HTML — Claude Code)

### Step 1 — Read the template and logo

Read `assets/template.html` to load the complete HTML template with all CSS styles and component patterns. Also read `assets/logo.svg` for the SegmentStream logo SVG. Both are essential — the template contains the full design system and the logo provides brand identity.

### Step 2 — Assemble the report

Replace the template placeholders:

- `{{LOGO_SVG}}` — The contents of `assets/logo.svg` (inline SVG, not a file reference)
- `{{REPORT_TITLE}}` — Main headline (e.g., "March 2026 Performance Report")
- `{{REPORT_SUBTITLE}}` — One-line summary (e.g., "Channel performance, maturation analysis, and intent signals for Ribble Cycles")
- `{{REPORT_DATE}}` — Current date in human-readable format (e.g., "16 March 2026")
- `{{REPORT_META}}` — Meta tags as `<span>` elements, use `class="accent"` for emphasis. Example: `<span>Ribble Cycles</span><span>Conversion: <span class="accent">CRM + Online Orders</span></span><span>Attribution: <span class="accent">First Click 90d</span></span>`
- `{{REPORT_BODY}}` — The main content, built from components below

### Step 3 — Build the body from components

Use these HTML patterns to construct `{{REPORT_BODY}}`. Each major section wraps in `<section>`:

**KPI cards** — Use for top-level metrics:
```html
<div class="kpi-grid">
  <div class="kpi-card">
    <div class="kpi-label">Spend</div>
    <div class="kpi-value">£38.8k</div>
    <div class="kpi-change positive">+2% YoY</div>
  </div>
</div>
```
KPI change classes: `positive`, `negative`, `neutral`. If including a comparison label like "vs Jan 2026", keep it in a separate `neutral` element so it doesn't inherit the color:
```html
<div class="kpi-change negative">-45%</div><div class="kpi-change neutral">vs Jan 2026</div>
```

**KPI grid layout:** Default 3 columns. Add `kpi-grid-2` or `kpi-grid-4` for 2 or 4 columns. Avoid single orphan cards — 7 KPIs → use 4-column (4+3), not 3-column (3+3+1).

**Data tables** — Use for channel breakdowns, comparisons:
```html
<div class="data-table-wrapper">
  <table class="data-table">
    <thead><tr><th>Channel</th><th class="num">Cost</th></tr></thead>
    <tbody><tr><td>Google Ads</td><td class="num">£24,090</td></tr></tbody>
    <tfoot><tr><td>Total</td><td class="num">£38,800</td></tr></tfoot>
  </table>
</div>
```
Use `class="num"` for right-aligned numeric columns. Use `class="positive"`, `class="negative"`, or `class="accent"` on `<td>` for colored values.

**Inline bars** — Use inside table cells for visual proportions. Only use when there is no separate percentage column already showing the same data — avoid redundancy.
```html
<td class="num">39%<div class="bar-container"><div class="bar-fill" style="width: 39%"></div></div></td>
```

**Callout boxes** — Use for key insights or warnings. Wrap inline numbers (currencies, percentages, ROAS multipliers) in `<span class="num">` and entity names (channels, campaigns, products) in `<strong>` so they stand out from the surrounding text.
```html
<div class="callout">
  <div class="callout-title">Key Insight</div>
  <div class="callout-body">At <span class="num">2.1x</span> ROAS and <span class="num">£129</span> CPA, Generic Broad sits 50% below the account average.</div>
</div>
```
Variants: default (cyan), `callout warning`, `callout positive`, `callout negative`.

**Tags** — Use inline for status labels:
```html
<span class="tag positive">+79%</span>
<span class="tag negative">-48%</span>
<span class="tag">First Click</span>
```

**Insight lists** — Use for bullet-point findings and recommendations. Wrap inline numbers in `<span class="num">` so they pop visually:
```html
<ul class="insight-list">
  <li><strong>Shopping is the standout:</strong> <span class="num">50</span> conversions at half the 2025 spend, delivering <span class="num">4.8x</span> ROAS.</li>
</ul>
```

**Timeseries chart** — Use inline SVG for daily/weekly trends (no external libraries). Draw inside a `.chart-wrapper` div with `<svg viewBox="0 0 800 220">`. Use polylines for data series, circles for data points, and text elements for axis labels.

Chart color palette — every line on a chart must be a **distinct color**. Never use the same color for two series, even with different dash patterns:
- `#6366F1` (indigo) — primary metric (e.g., sessions, spend)
- `#10B981` (green) — positive/actual values (e.g., observed conversions)
- `#F59E0B` (amber) — projected/estimated values
- `#EF4444` (red) — negative/declining metrics
- `#888888` (gray, dashed) — comparison/previous period

Grid lines: `rgba(255,255,255,0.04)`. Axis labels: font-size 10, fill `#555`, font-family `var(--font-mono)`. Data point dots: r=3 for primary, r=2 for secondary. Add a legend row above the chart using small colored swatches.

**Two-column layout** — Use for side-by-side content:
```html
<div class="two-col">
  <div><!-- left content --></div>
  <div><!-- right content --></div>
</div>
```

**Drill-down (expandable rows)** — Use CSS grid (not table+flexbox) so parent and child columns align. Wrap in `.data-table-wrapper` for consistent card styling:
```html
<div class="data-table-wrapper">
  <div class="drill-down">
    <div class="drill-head">
      <span>Channel / Campaign</span>
      <span class="num">Cost</span>
      <span class="num">Conv.</span>
      <span class="num">CPA</span>
      <span class="num">ROAS</span>
    </div>
    <details open>
      <summary>
        <span class="drill-name"><span class="chevron"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="4,2 8,6 4,10"/></svg></span> ICON_SVG Channel Name <span class="tag">58% of spend</span></span>
        <span class="num">£18,420</span>
        <span class="num">198</span>
        <span class="num">£93</span>
        <span class="num">4.6x</span>
      </summary>
      <div class="drill-child">
        <span>Campaign Name <span class="tag">Best</span></span>
        <span class="num">£6,200</span>
        <span class="num">82</span>
        <span class="num">£76</span>
        <span class="num">5.2x</span>
      </div>
    </details>
    <div class="drill-total">
      <span>Total</span>
      <span class="num">£31,060</span>
      <span class="num">326</span>
      <span class="num">£95</span>
      <span class="num">4.3x</span>
    </div>
  </div>
</div>
```
Place status tags ("Best", "Review") next to the campaign name in the first column, not after the last metric. Use `<details open>` on the first channel so it's expanded by default.

### Inline number highlighting
Wrap numbers (currencies, percentages, ROAS, counts) in `<span class="num">` for monospace + indigo styling. Wrap entity names (channels, campaigns, products) in `<strong>`.

### Channel icons everywhere
Use inline SVG channel icons (from `references/channel-icons.md`) in any component showing channel names. Wrap with `.ch` pattern: `<div class="ch">ICON_SVG <span>Channel Name</span></div>`.

### Step 4 — Write the file

Save to `.artifacts/` with a descriptive kebab-case filename:
```
.artifacts/ribble-march-2026-performance.html
```

Create the `.artifacts/` directory if it does not exist.

### Step 5 — Open in browser

```bash
open .artifacts/ribble-march-2026-performance.html
```

Tell the user the file path and that it's been opened.

## Workflow (JSX — Cowork)

### Step 1 — Read the brand constraints and logo

Read `references/jsx-format.md` for the SegmentStream brand colors, typography rules, chart color palette, and Cowork constraints. Also read `references/logo-component.jsx` and copy the logo component verbatim into your report (do not truncate or simplify the SVG). This is intentionally minimal — it defines the brand identity and lets you design the layout.

### Step 2 — Design and build the component

Create a single `export default function ReportName()` component. Use your design judgment with shadcn/ui, Tailwind, and Recharts. The reference file gives you the color palette and a few hard rules (distinct chart colors, mono for numbers, dark theme). Everything else — layout, spacing, component choice, how to structure the data — use your best instincts. The goal is a polished, professional report that feels like it belongs on segmentstream.ai.

Also read `references/channel-icons.md` for ad platform SVG icons to inline in channel tables.

### Step 3 — Write and confirm

Save as `.artifacts/{name}.jsx`. Tell the user it should render in Cowork's artifact panel.

## Sharing Reports

When the user says "share this report", "get a link", "send this to my client", or similar — generate the report as a shared artifact with a shareable URL.

### How it works

The segmentstream.ai artifact viewer wraps shared content in its own chrome (logo, title bar, "Content generated by..." attribution). So the uploaded HTML must **not** include the report's own branding frame — only the report content.

### Workflow

1. **Generate the full HTML** — follow the normal Claude Code HTML workflow (Steps 1-3) to build the complete report
2. **Strip the outer chrome** before uploading:
   - Remove the `<div class="artifact-topbar">...</div>` element (contains the logo and action buttons)
   - Remove the `<div class="artifact-bottombar">...</div>` element (contains the "Generated via SegmentStream MCP" footer)
   - Keep `<div class="report-content">` and everything inside it: report-header (title, subtitle, meta), all sections, KPI cards, tables, charts
   - Keep the `<head>` with all CSS styles intact
3. **Upload** the stripped HTML via `share_artifact` MCP tool
4. **Return the URL** to the user — format: `https://segmentstream.ai/artifacts/{uuid}`

### What to strip vs keep

| Element | Action |
|---------|--------|
| `<div class="artifact-topbar">` (logo + buttons) | **Remove** |
| `<div class="artifact-bottombar">` (footer attribution) | **Remove** |
| `<div class="report-content">` (header + body) | **Keep** |
| `<head>` with all `<style>` blocks | **Keep** |
| All CSS classes and styles | **Keep** — the viewer does not provide its own report styles |

### When to share vs save locally

- User asks to "share", "get a link", "send to someone" → **shared artifact**
- User asks to "save", "export", "download" → **local HTML file** (full branding)
- If unclear, ask the user

## Content Guidelines

- **Lead with KPIs** — put the 4-6 most important numbers in a KPI grid at the top
- **Tables are the backbone** — the SegmentStream aesthetic is data-forward; use tables generously for channel breakdowns, comparisons, maturation data
- **Callouts for insights** — pull out the 2-3 key takeaways as callout boxes between tables
- **Keep text tight** — section descriptions should be 1-2 sentences max; let the data speak
- **Use tags for change indicators** — colored tags make YoY changes and status immediately scannable
- **Format numbers cleanly** — use £, %, x for ROAS, k/M for large numbers, consistent decimal places
- **Include a "What This Means" or "Recommendations" section** at the end with an insight list

## Naming Convention

Files should follow: `{client}-{topic}-{period}.{html|jsx}`

Examples:
- `ribble-march-2026-performance.html` (Claude Code)
- `ribble-march-2026-performance.jsx` (Cowork)
- `ribble-channel-maturation-q1-2026.html`

## Error Handling

| Issue | Response |
|-------|----------|
| No analysis data in conversation | Ask the user what data to include; do not generate an empty report |
| Template file missing | Reconstruct from the component patterns documented in this file — all CSS classes and HTML structure are documented above |
| `.artifacts/` doesn't exist | Create it with `mkdir -p .artifacts/` |
| `open` command fails | Provide the file path for manual opening |
