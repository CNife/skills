---
name: models-dev-query
description: >
  Query AI model specifications from the models.dev database. Use when the user
  asks about model specs (pricing, context limits, capabilities: reasoning,
  tool_call, modalities), needs API endpoint information for a provider, wants to
  list what models a provider supports, or compare models across providers.
  Triggers for questions like "查一下 XXX 支持哪些模型"、"gpt-5 的定价"、
  "配置 Trae 用 deepseek 的配置"。
---

# Models.dev Query

Query [models.dev](https://github.com/anomalyco/models.dev) — a comprehensive database of AI model specs. All data is fetched live from the aggregated JSON endpoint; no local data required.

## AI Agent Protocol

当你收到关于模型规格/定价/提供商的问题时，按以下步骤操作：

### Step 1 — 设置缓存

```bash
CACHE=/tmp/models-dev-catalog.json
```

检查 `$CACHE` 是否存在，不存在则下载（约 2.3MB）：

```bash
[ -f "$CACHE" ] || curl -sL https://models.dev/catalog.json -o "$CACHE"
```

### Step 2 — 查 Data Structure 表

确认要用哪一层：

- 查定价 / 提供商 API 配置 → `providers["<id>"].models["<id>"]`
- 查 benchmarks / 开源权重 → `models["<provider-id>/<model-id>"]`

### Step 3 — 构造 jq 查询

参考下方的例子但按需调整字段和过滤条件。所有查询都从 `$CACHE` 读取。

> 不要重复下载。文件存在就直接用 `jq '...' "$CACHE"` 查询。

---

## Data Structure

`catalog.json` 有两层结构，字段分布不同。编写 jq 查询时需根据目标选择正确的路径。

### 1. `models` — 扁平模型索引

Key = `"<provider-id>/<model-id>"`，共 205 条。适合**发现与比较**。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 完整模型 ID |
| `name` | string | 显示名称 |
| `family` | string | 模型系列 |
| `attachment` | bool | 是否支持文件附件 |
| `reasoning` | bool | 是否支持推理/思维链 |
| `tool_call` | bool | 是否支持工具调用 |
| `structured_output` | bool | 是否支持结构化输出 |
| `temperature` | bool | 是否支持温度控制 |
| `knowledge` | string | 知识截止日期 |
| `release_date` | string | 发布日期 |
| `last_updated` | string | 最后更新日期 |
| `modalities` | object | `{input: [...], output: [...]}` 模态 |
| `open_weights` | bool | 是否开源权重 |
| `limit` | object | `{context, output}` 上下文/输出上限 |
| `benchmarks` | array | 评测成绩 |
| `weights` | array | 权重下载链接 |

> 此层 **没有** `cost` 定价字段。

### 2. `providers` — 提供商字典

Key = `"<provider-id>"`，共 140 个。每个 provider 包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | Provider ID |
| `name` | string | 显示名称 |
| `api` | string | OpenAI 兼容的 base URL |
| `npm` | string | AI SDK 包名 |
| `env` | array | 环境变量名列表 |
| `doc` | string | 文档链接 |
| `models` | object | **内嵌模型字典（含定价）** |

### 3. `providers[].models[]` — 内嵌模型（含定价）

约 5000+ 条，分布在所有 provider 中。适合**查询定价、API 配置和运营信息**。

| 字段 | 类型 | 说明 |
|------|------|------|
| (所有 `models` 层的字段) | — | 同上层，值可能被 provider 覆盖 |
| `cost` | object | `{input, output, cache_read, reasoning, cache_write}` 定价（USD/百万 token） |
| `status` | string | 生命周期：`"alpha"` / `"beta"` / `"deprecated"` |
| `interleaved` | object | 推理模型的交叉字段配置 |
| `reasoning_options` | object | 推理选项配置 |
| `experimental` | bool | 是否实验性功能 |

> 此层 **没有** `benchmarks` 和 `weights`。

### 快速参考：选哪一层

| 查什么 | 路径 |
|--------|------|
| 模型名、能力（reasoning/tool_call/modalities）、上下文窗口 | `models["<provider/model-id>"]` **或** `providers["<provider-id>"].models["<model-id>"]` |
| 定价 (cost) | `providers["<provider-id>"].models["<model-id>"].cost` |
| 评测成绩 (benchmarks) | `models["<provider/model-id>"].benchmarks` |
| 模型状态 (status) | `providers["<provider-id>"].models["<model-id>"].status` |
| 提供商 API 信息 | `providers["<provider-id>"] \| {name, api, env, doc}` |

---

## Quick Reference Commands

前提：`CACHE=/tmp/models-dev-catalog.json` 已设置且文件已缓存。

### List all providers

```bash
jq -r '.providers | keys | sort | .[]' "$CACHE"
```

### Get provider info (API endpoint, env vars)

```bash
jq '.providers["<provider-id>"] | {name, api, doc, env}' "$CACHE"
```

### List models for a provider

```bash
jq -r '.providers["<provider-id>"].models | keys | .[]' "$CACHE"
```

### Get model specs + pricing

```bash
jq '.providers["<provider-id>"].models["<model-id>"]' "$CACHE"
```

### Get model benchmarks / weights

```bash
jq '.models["<provider-id>/<model-id>"] | {benchmarks, weights}' "$CACHE"
```

### List all models with a capability

```bash
# 列出所有支持 reasoning 的模型（从扁平索引快速扫描）
jq -r '[.models[] | select(.reasoning == true) | .id] | sort | .[]' "$CACHE"
```

---

## Query Guide

### 1. "查一下 X 提供商支持哪些模型"

```bash
jq -r '
  .providers["<provider-id>"] as $p |
  "Provider: \($p.name // "<provider-id>")",
  "API: \($p.api // "N/A")",
  "Models:",
  ($p.models | to_entries[] |
    "  - \(.key): \(.value.name)  (ctx: \(.value.limit.context // "?"), $\(.value.cost.input)/M in, $\(.value.cost.output)/M out)")
' "$CACHE"
```

### 2. "查某模型的详细参数"

```bash
# Specs + pricing（来自 provider 内嵌模型）
jq '.providers["<provider-id>"].models["<model-id>"]' "$CACHE"

# Benchmarks + open_weights（来自扁平索引）
jq '.models["<provider-id>/<model-id>"] | {benchmarks, weights, open_weights}' "$CACHE"
```

### 3. "配置 XXX 用某提供商的 API"

```bash
# 提供商信息
jq '.providers["<provider-id>"] | {name, api, doc, env}' "$CACHE"

# 模型 ID 和能力
jq '.providers["<provider-id>"].models["<model-id>"] | {id, name, reasoning, tool_call, structured_output}' "$CACHE"
```

Key fields:

- `api` — OpenAI-compatible base URL
- `npm` — AI SDK package name (`@ai-sdk/openai-compatible` for generic OpenAI-compatible)
- `env[]` — environment variable names for auth

Combine into a configuration snippet for the user's target tool (Trae, OpenCode, Cursor, Continue, etc.).

### 4. "按条件筛选模型"

```bash
# 找定价 < $1/M input 且支持 reasoning + tool_call 的模型
jq '
  [.providers[] | .models[] | select(
    .cost.input != null and .cost.input < 1 and
    .reasoning == true and
    .tool_call == true
  )] | sort_by(.cost.input)
  | .[] | {id, name, cost: .cost.input, context: .limit.context, reasoning}
' "$CACHE"

# 找开源模型，按上下文窗口排序
jq '
  [.models[] | select(.open_weights == true)] | sort_by(.limit.context) | reverse
  | .[] | {id, name, context: .limit.context, release_date}
' "$CACHE"
```

### 5. "有什么新模型"

```bash
# 最近 30 天发布的模型
jq '
  [.models[] | select(.release_date > "2026-05-09")]
  | sort_by(.release_date) | reverse
  | .[] | {id, name, release_date, family}
' "$CACHE"
```

### 6. 跨层联合查询（定价 + benchmarks 一次获取）

需要同时取定价（`providers[].models[]`）和评测（`models[]`）时，用一次性 jq 避免两次 bash 调用：

```bash
# 例子：查 google gemini-2.5-flash 的定价 + benchmarks
jq '
  .providers["google"] as $p |
  .models["google/gemini-2.5-flash"] as $m |
  {name: $p.models["gemini-2.5-flash"].name,
   cost: $p.models["gemini-2.5-flash"].cost,
   benchmarks: $m.benchmarks}
' "$CACHE"
```

```bash
# 通用模式：查任意 provider/model 的定价 + 评测
# 替换 PROVIDER 和 MODEL 即可
jq '
  .providers["<PROVIDER>"] as $p |
  .models["<PROVIDER>/<MODEL>"] as $m |
  {name: $p.models["<MODEL>"].name,
   cost: $p.models["<MODEL>"].cost,
   limit: $p.models["<MODEL>"].limit,
   capabilities: {reasoning: $p.models["<MODEL>"].reasoning,
                 tool_call: $p.models["<MODEL>"].tool_call,
                 structured_output: $p.models["<MODEL>"].structured_output},
   benchmarks: ($m.benchmarks // []),
   weights: ($m.weights // [])}
' "$CACHE"
```

---

## Output Format

Present results clearly:

- **Provider query**: name, API endpoint, env vars, doc link
- **Model list**: table with Model ID, Name, Context, Input/M, Output/M, Capabilities
- **Model detail**: sectioned — Capabilities (reasoning/tool_call/structured_output/attachment/modalities), Limits (context/output), Pricing (input/output/cache_read), Benchmarks (if available)
- **For reasoning models**: also note interleaved field name (from `providers[].models[].interleaved`)

For Chinese-language queries, respond in Chinese. For English queries, respond in English — match the user's language.
