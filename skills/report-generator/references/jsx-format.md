# JSX Report Format (Cowork)

Generate a single-file React component. Cowork renders it inline with React 18, Tailwind CSS, shadcn/ui, Lucide, and charting libraries pre-loaded.

## Critical: Tailwind Class Restrictions

Cowork does NOT have a Tailwind JIT compiler — only core utility classes from Tailwind's pre-built stylesheet are available. **Any class containing square brackets `[...]` will be silently ignored**, breaking your layout with no error message. This includes:
- Colors: `bg-[#0A0A0A]`, `text-[#EDEDED]`, `border-[#333]` — use named classes like `bg-neutral-900`, `text-gray-100`
- Grid templates: `grid-cols-[2fr,1fr,1fr]` — use `grid-cols-3`, `grid-cols-4`, `grid-cols-5` or `<table>` elements
- Spacing: `w-[200px]`, `h-[calc(100vh-4rem)]`, `min-h-[calc(100vh-8rem)]` — use standard utilities like `w-48`, `min-h-screen`
- Opacity: `border-white/[0.08]` — use `border-neutral-800`

When you need unequal column widths, use `<table>` elements instead of CSS grid with arbitrary values.

## Brand Identity

Apply these constraints. Everything else — layout, spacing, component choice — use your best design judgment with the available libraries.

**Color palette (dark theme) — core Tailwind classes only:**
- Background: `bg-black` (page), `bg-neutral-950` (content area), `bg-neutral-900` (cards/headers)
- Text: `text-gray-100` (primary), `text-gray-400` (secondary), `text-gray-500` (muted)
- Accent: `text-indigo-500` / `bg-indigo-500` — used sparingly for interactive elements and key highlights
- Borders: `border-neutral-800` (default), `border-neutral-700` (hover)
- Status: `text-emerald-400` (positive), `text-red-400` (negative), `text-amber-400` (warning)

**Typography:**
- Body text: default sans-serif (Tailwind's `font-sans`)
- Data values, KPI numbers, table headers: `font-mono`
- Table body: first column (labels/names) stays sans-serif, numeric columns use `font-mono`

**SegmentStream logo:**
Read `references/logo-component.jsx` and copy the `SegmentStreamLogo` component **verbatim** into your report file. Do not modify, truncate, or simplify the SVG — it must be copied in full. The component renders at `h-8 w-auto` and includes both the icon mark and the full "segmentstream" wordmark.

**Frame layout:**
- Top bar: `bg-neutral-900`, `border-b border-neutral-800` — contains only the SegmentStream logo (left) and the date (right). The report title does NOT go in the top bar.
- Report title: rendered as a large `text-3xl font-bold` heading inside the content area, at the top before any other content. This is the main h1 of the report.
- Bottom bar: `bg-neutral-900` with "Generated via SegmentStream MCP" in small mono uppercase, `border-t border-neutral-800`
- Content area: `bg-neutral-950`, `max-w-5xl` centered

## Component Patterns

### KPI cards
Use a 4-column grid (`grid grid-cols-4 gap-4`) for the top-level metrics. Each card uses `flex flex-col` to stack: label → value → change indicator. Use **short single-word labels** that won't wrap (e.g., "Cost" not "Total Cost", "Conversions" not "Total Conversions", "CPA", "ROAS"). If context is needed, put it in the change line (e.g., "vs Jan"). Label: `text-gray-500 text-xs font-mono uppercase tracking-wider`. Value: `text-2xl font-bold font-mono text-gray-100 mt-2`. Change: status color + `text-sm font-mono mt-1`. For cost metrics, a decrease is favorable (emerald); for revenue/ROAS, an increase is favorable.

### Comparison tables (period-over-period)
When data includes both current and previous period values, use a **stacked cell layout** — each numeric cell shows the current value on top (`text-gray-100`) and the previous value below (`text-gray-500 text-xs`), with a change badge. This is the SegmentStream signature table style and should be used whenever comparison data is available. Structure:

```jsx
<td className="text-right px-4 py-3 font-mono">
  <div className="text-gray-100">£30,891</div>
  <div className="text-gray-500 text-xs">prev: £44,142</div>
  <span className="text-emerald-400 text-xs">-30.0%</span>
</td>
```

Always show both current and previous values in the table — don't drop previous-period data even when there's a separate "Change" column.

### Tags
Inline status badges for change values, labels, and categories. Use `font-mono text-xs px-2 py-0.5 rounded` as the base, then add background and text color:
- Positive: `bg-emerald-400/10 text-emerald-400` → `+79%`
- Negative: `bg-red-400/10 text-red-400` → `-48%`
- Warning: `bg-amber-400/10 text-amber-400`
- Neutral/info: `bg-indigo-500/10 text-indigo-400` → `First Click`

Use tags generously inside table cells, KPI cards, and next to campaign/channel names.

### Executive summary
A narrative block for high-level analysis. Use `bg-neutral-900 border-l-4 border-indigo-500 rounded-r-lg p-6`. Inside, use `text-gray-400 leading-relaxed` for body text. Wrap inline numbers (currencies, percentages, ROAS) in `<span className="font-mono text-indigo-400 font-semibold">` and entity names (channels, campaigns) in `<strong className="text-gray-100">` so they pop from the surrounding text.

### Callout boxes
Use for key insights or warnings. Background: `bg-neutral-900`, left border with status color (`border-l-4 border-red-400` for negative, `border-amber-400` for warning, `border-indigo-500` for info). Title in bold with matching color, body in `text-gray-400`.

### Delta indicators
Compact change display with arrow + colored value. Use Lucide's `ArrowUp`, `ArrowDown`, or `ArrowRight` icons at size 14 alongside the value. Color the entire indicator (icon + text) with status color. Example:

```jsx
<span className="inline-flex items-center gap-1 text-emerald-400 font-mono text-sm">
  <ArrowDown size={14} /> 23.5%
</span>
```

### Insight lists
Styled findings where data values are visually distinct from prose. Use a div-based list (not `<ul>`) with `border-b border-neutral-800` between items. Inside each item, wrap numbers in `<span className="font-mono text-indigo-400 font-semibold">` and entity names in `<strong className="text-gray-100">`. Body text in `text-gray-400 text-sm`.

### Bar list (horizontal bars)
For showing proportional data without a charting library — e.g., share of spend by channel. Structure each row as: label (left), bar track (flex-1), value (right). The track is `h-2 bg-neutral-800 rounded-full overflow-hidden` and the fill is `h-full rounded-full bg-indigo-500` with width set via inline style. Use different fill colors for different items (indigo, emerald, amber, etc.).

### Category bar (stacked segments)
A single horizontal bar showing proportions (e.g., 60% Google / 40% Meta). Use `flex h-3 rounded-full overflow-hidden` for the track. Each segment gets a different background color and width via inline style. Below the bar, render a legend with colored swatches + labels + values.

### Inline bars in table cells
Small progress bars inside table cells to show relative magnitude. After the numeric value, render a `w-20 h-1.5 bg-neutral-800 rounded-full overflow-hidden inline-block ml-2` track with a colored fill. Use sparingly — only when visual proportions add value beyond the raw numbers.

### Row group headers
When grouping table rows by channel or category, insert a header row with `bg-neutral-800/50 text-gray-400 text-xs font-mono uppercase tracking-wider` spanning all columns. Place the channel icon + name in this row, then indent the data rows below it.

### Drill-down (expandable rows)
For parent/child data like channel → campaign breakdowns, use a `<table>` with React state to toggle child row visibility. **Do NOT use CSS grid with arbitrary column widths** like `grid-cols-[2fr,1fr,...]` — these are arbitrary values and will be silently ignored. Use a standard `<table>` instead:

```jsx
const [expanded, setExpanded] = useState(['Google Ads']);
const toggle = (name) => setExpanded(prev =>
  prev.includes(name) ? prev.filter(c => c !== name) : [...prev, name]
);

<div className="bg-neutral-900 rounded-lg border border-neutral-800 overflow-hidden">
  <table className="w-full">
    <thead>
      <tr className="border-b border-neutral-800">
        <th className="text-left px-4 py-3 text-xs font-mono uppercase tracking-wider text-gray-500">Channel / Campaign</th>
        <th className="text-right px-4 py-3 text-xs font-mono uppercase tracking-wider text-gray-500">Cost</th>
        <th className="text-right px-4 py-3 text-xs font-mono uppercase tracking-wider text-gray-500">Conv.</th>
        <th className="text-right px-4 py-3 text-xs font-mono uppercase tracking-wider text-gray-500">CPA</th>
        <th className="text-right px-4 py-3 text-xs font-mono uppercase tracking-wider text-gray-500">ROAS</th>
      </tr>
    </thead>
    <tbody>
      {/* Parent row — clickable */}
      <tr className="border-b border-neutral-800 cursor-pointer hover:bg-neutral-800/50"
          onClick={() => toggle('Google Ads')}>
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            <ChevronDown size={14} className={`text-gray-400 transition-transform ${expanded.includes('Google Ads') ? 'rotate-180' : ''}`} />
            <span className="text-gray-100 font-medium">Google Ads</span>
            <span className="font-mono text-xs px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400">58% of spend</span>
          </div>
        </td>
        <td className="text-right px-4 py-3 font-mono text-gray-100">£18,420</td>
        <td className="text-right px-4 py-3 font-mono text-gray-100">198</td>
        <td className="text-right px-4 py-3 font-mono text-gray-100">£93</td>
        <td className="text-right px-4 py-3 font-mono text-indigo-400 font-semibold">4.6x</td>
      </tr>
      {/* Child rows — shown when expanded */}
      {expanded.includes('Google Ads') && (
        <>
          <tr className="bg-neutral-800/20 border-b border-neutral-800/50">
            <td className="pl-10 pr-4 py-2 text-sm text-gray-400">Brand Exact</td>
            <td className="text-right px-4 py-2 font-mono text-sm text-gray-300">£6,200</td>
            <td className="text-right px-4 py-2 font-mono text-sm text-gray-300">82</td>
            <td className="text-right px-4 py-2 font-mono text-sm text-gray-300">£76</td>
            <td className="text-right px-4 py-2 font-mono text-sm text-emerald-400">5.2x</td>
          </tr>
        </>
      )}
      {/* Total row */}
      <tr className="bg-neutral-800/50 border-t border-neutral-700">
        <td className="px-4 py-3 text-gray-400 font-mono text-sm">Total</td>
        <td className="text-right px-4 py-3 font-mono text-gray-100 font-semibold">£31,060</td>
        <td className="text-right px-4 py-3 font-mono text-gray-100 font-semibold">326</td>
        <td className="text-right px-4 py-3 font-mono text-gray-100 font-semibold">£95</td>
        <td className="text-right px-4 py-3 font-mono text-indigo-400 font-semibold">4.3x</td>
      </tr>
    </tbody>
  </table>
</div>
```

Use `useState` for expand/collapse. Place tags (share of spend, "Best", "Review") next to the name in the first column. Expand the first channel by default.

### Donut / pie charts
Use Recharts `PieChart` + `Pie` with `innerRadius` for donut style. Place a center label using absolute positioning. Render a legend alongside (not below) the chart using flexbox. Use the chart color palette below.

## Charts

Four charting libraries are available. Pick the best fit for each visualization:

| Library | Import | Best For |
|---------|--------|----------|
| **Recharts** (default) | `import { LineChart, XAxis, ... } from "recharts"` | Standard line/bar/area/pie — React-native, declarative |
| **D3** | `import * as d3 from "d3"` | Custom/non-standard visualizations — heatmaps, Sankey, force graphs |
| **Plotly** | `import * as Plotly from "plotly"` | Interactive dashboards — hover, zoom/pan, scatter, 3D |
| **Chart.js** | `import * as Chart from "chart.js"` | Canvas-based — performant for large datasets (1000+ points) |

**Default to Recharts** for most reports. Use D3/Plotly/Chart.js only when the visualization genuinely needs their capabilities.

### Recharts dark theme config

- Grid: `stroke="rgba(255,255,255,0.04)"`
- Axis ticks: `fontSize: 10, fill: '#6b7280'` (gray-500 hex)
- Tooltip: use inline styles for tooltip background (`backgroundColor: '#171717'`, `border: '1px solid #262626'`) since Recharts tooltip uses inline styles, not Tailwind

**Color rule: every line/series must be a distinct color.** Never reuse a color, even with different dash patterns.
- Primary metric: `#6366F1` (indigo)
- Positive/actual: `#10B981` (green)
- Projected/estimated: `#F59E0B` (amber)
- Negative: `#EF4444` (red)
- Comparison/previous: `#9ca3af` (gray-400) dashed
- Additional series: `#06B6D4` (cyan), `#EC4899` (pink), `#8B5CF6` (violet), `#F97316` (orange), `#14B8A6` (teal)

## Channel Icons

Read `references/channel-icons.md` for inline SVG icons of ad platforms. Only ad platforms (Google Ads, Meta, Microsoft, TikTok, LinkedIn, Pinterest, Reddit, X, Snapchat, Awin) get icons. Other channels (Organic Search, Direct, Email, etc.) render as plain text.

## Constraints

- `export default function ComponentName()` — single file, no local imports
- All data hardcoded as arrays/objects inside the component
- No localStorage, no fetch, no external API calls
- Available: React 18, Tailwind, Recharts, D3, Plotly, Chart.js, shadcn/ui, Lucide
- **No arbitrary Tailwind values** — no square-bracket syntax like `bg-[#xxx]`, `text-[#xxx]`, `border-[color]/[opacity]`. Use only named utility classes (e.g., `bg-neutral-900`, `text-gray-100`, `border-neutral-800`).
