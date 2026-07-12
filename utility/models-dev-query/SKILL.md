---
name: models-dev-query
description: >
  Query AI model specs (pricing, context limits, capabilities, modalities) and
  provider API endpoints from models.dev. Use when the user asks about model
  pricing/specs, needs a provider's API/base-URL/env config, or wants to
  list/filter/compare models across providers. 触发例：「gpt-5 的定价」
  「查 XXX 支持哪些模型」「配置 Trae 用 deepseek」。
---

# Models.dev Query

Query [models.dev](https://github.com/anomalyco/models.dev) - a comprehensive database of AI model specs. All data is fetched live from the aggregated JSON endpoint; no local data required.

## AI Agent Protocol

当你收到关于模型规格/定价/提供商的问题时，按以下步骤操作：

### Step 1 - 设置缓存

```bash
CACHE=/tmp/models-dev-catalog.json
```

检查 `$CACHE` 是否存在，不存在则下载（数 MB）：

```bash
[ -f "$CACHE" ] || curl -sL https://models.dev/catalog.json -o "$CACHE"
```

### Step 2 - 选层

确认目标字段属于哪一层，见下方 Data Structure 的「选哪一层」表。

### Step 3 - 构造 jq 查询

参考下方的 Query Guide 例子，按需调整字段和过滤条件。所有查询都从 `$CACHE` 读取。

---

## Data Structure

`catalog.json` 有两层结构，字段分布不同。编写 jq 查询时需根据目标选择正确的路径。

### 1. `models` - 扁平模型索引

Key = `"<provider-id>/<model-id>"`。适合**发现与比较**。

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

### 2. `providers` - 提供商字典

Key = `"<provider-id>"`。每个 provider 包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | Provider ID |
| `name` | string | 显示名称 |
| `api` | string | OpenAI 兼容的 base URL |
| `npm` | string | AI SDK 包名 |
| `env` | array | 环境变量名列表 |
| `doc` | string | 文档链接 |
| `models` | object | **内嵌模型字典（含定价）** |

### 3. `providers[].models[]` - 内嵌模型（含定价）

约 5000+ 条，分布在所有 provider 中。适合**查询定价、API 配置和运营信息**。

| 字段 | 类型 | 说明 |
|------|------|------|
| (所有 `models` 层的字段) | - | 同上层，值可能被 provider 覆盖 |
| `cost` | object | 定价（USD/百万 token）。常见子键：`input`、`output`、`cache_read`、`cache_write`、`reasoning`；多模态模型另有 `input_audio`/`output_audio`；部分模型有 `context_over_200k`、`tiers`。实际子键用 `jq '.providers[].models[].cost \| keys'` 探查 |
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
| 评测成绩 (benchmarks) | `models["<provider-id>/<model-id>"].benchmarks` |
| 模型状态 (status) | `providers["<provider-id>"].models["<model-id>"].status` |
| 提供商 API 信息 | `providers["<provider-id>"] \| {name, api, env, doc}` |

---

## Query Guide

前提：`CACHE=/tmp/models-dev-catalog.json` 已设置且文件已缓存。

### 1. 列出某 provider 的模型

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

### 2. 查模型完整画像（定价 + 能力 + 评测，一次调用）

`models` 层无 `cost`、`providers[].models[]` 层无 `benchmarks/weights`，跨层一次取齐：

```bash
# 替换 <PROVIDER> 和 <MODEL> 即可
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

只需 benchmarks/weights 时：`jq '.models["<provider-id>/<model-id>"] | {benchmarks, weights, open_weights}' "$CACHE"`。

### 3. 配置某 provider 的 API

```bash
# 提供商信息（base URL、env、文档）
jq '.providers["<provider-id>"] | {name, api, doc, env}' "$CACHE"

# 模型 ID 和能力
jq '.providers["<provider-id>"].models["<model-id>"] | {id, name, reasoning, tool_call, structured_output}' "$CACHE"
```

Key fields:

- `api` - OpenAI-compatible base URL
- `npm` - AI SDK package name (`@ai-sdk/openai-compatible` for generic OpenAI-compatible)
- `env[]` - environment variable names for auth

Combine into a configuration snippet for the user's target tool (Trae, OpenCode, Cursor, Continue, etc.).

### 4. 按条件筛选模型

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

### 5. 最近发布模型

```bash
# 最近 30 天发布的模型（相对日期，自动按当下计算）
jq --arg d "$(date -d '30 days ago' +%F 2>/dev/null || date -v-30d +%F)" '
  [.models[] | select(.release_date > $d)]
  | sort_by(.release_date) | reverse
  | .[] | {id, name, release_date, family}
' "$CACHE"
```

### 6. 列出所有 provider / 列出某能力的模型

```bash
# 所有 provider
jq -r '.providers | keys | sort | .[]' "$CACHE"

# 所有支持 reasoning 的模型（从扁平索引扫描；换 .tool_call / .structured_output 等同理）
jq -r '[.models[] | select(.reasoning == true) | .id] | sort | .[]' "$CACHE"
```

---

## Output Format

Present results clearly:

- **Provider query**: name, API endpoint, env vars, doc link
- **Model list**: table with Model ID, Name, Context, Input/M, Output/M, Capabilities
- **Model detail**: sectioned - Capabilities (reasoning/tool_call/structured_output/attachment/modalities), Limits (context/output), Pricing (input/output/cache_read), Benchmarks (if available)
- **For reasoning models**: also note interleaved field name (from `providers[].models[].interleaved`)
