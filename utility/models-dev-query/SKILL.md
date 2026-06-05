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

Query [models.dev](https://github.com/anomalyco/models.dev) — a comprehensive database of AI model specs. All data is fetched live from GitHub API or the aggregated JSON endpoint; no local data required.

## Data Sources

| Source | Command | Best For |
|--------|---------|----------|
| Aggregated JSON API | `curl -sL https://models.dev/api.json \| jq '...'` | Fast queries: list providers, get pricing/limits/capabilities |
| GitHub API (TOML files) | `gh api repos/anomalyco/models.dev/contents/...` | Detailed specs: reasoning mode, interleaved field, modalities, family |

> Default branch is `dev` (the GitHub repo's default). The `main` branch does not exist.

## Quick Reference Commands

### List all providers

```bash
curl -sL https://models.dev/api.json | jq -r 'keys | .[]' | sort
```

### List models for a provider

```bash
# From api.json (fast)
curl -sL https://models.dev/api.json | jq -r '.["<provider-id>"].models | keys | .[]'

# From GitHub (detailed)
gh api repos/anomalyco/models.dev/contents/providers/<provider-id>/models \
  --jq '.[].name' | sed 's/\.toml$//'
```

### Get model specs (fast — api.json)

```bash
curl -sL https://models.dev/api.json | jq '.["<provider-id>"].models["<model-id>"]'
```

### Get model specs (detailed — GitHub TOML)

```bash
gh api repos/anomalyco/models.dev/contents/providers/<provider-id>/models/<model-id>.toml \
  --jq '.download_url' | xargs curl -sL
```

### Get provider info

```bash
curl -sL https://models.dev/api.json | jq '.["<provider-id>"] | {name: .name, api: .api, doc: .doc, env: .env}'
```

## Query Guide

### 1. "查一下 X 提供商支持哪些模型"

Use api.json to get the provider's model list + basic info in one shot:

```bash
curl -sL https://models.dev/api.json | jq -r '
  .["<provider-id>"] as $p |
  "Provider: \($p.name // "<provider-id>")",
  "API: \($p.api // "N/A")",
  "Models:",
  ($p.models | to_entries[] | "  - \(.key): \(.value.name)  (ctx: \(.value.limit.context // "?"), $\(.value.cost.input)/M in, $\(.value.cost.output)/M out)")
'
```

Format the output as a readable table.

### 2. "查某模型的详细参数"

Always fetch both sources for completeness:

```bash
# 1. Fast check from api.json
curl -sL https://models.dev/api.json | jq '.["<provider-id>"].models["<model-id>"]'

# 2. Detailed TOML for fields api.json doesn't have (family, reasoning, modalities, family, etc.)
gh api repos/anomalyco/models.dev/contents/providers/<provider-id>/models/<model-id>.toml \
  --jq '.download_url' | xargs curl -sL
```

If the model ID contains `/` (e.g. `nvidia/llama-3.1`), the TOML file is in a subdirectory:

```text
providers/<provider-id>/models/<slash-prefix>/<rest-of-id>.toml
```

### 3. "配置 XXX 用某提供商的 API"

Read the provider's `provider.toml` for API endpoint:

```bash
gh api repos/anomalyco/models.dev/contents/providers/<provider-id>/provider.toml \
  --jq '.download_url' | xargs curl -sL
```

Key fields:

- `api` — OpenAI-compatible base URL
- `npm` — AI SDK package name (`@ai-sdk/openai-compatible` for generic OpenAI-compatible)
- `env[]` — environment variable names for auth

Then read the model TOML for model ID and capabilities. Combine into a configuration snippet for the user's target tool (Trae, OpenCode, Cursor, Continue, etc.).

### 4. "按条件筛选模型"

Use api.json with jq filtering:

```bash
# Find models under $X/M input that support reasoning + tool_call
curl -sL https://models.dev/api.json | jq '
  .[].models[] | select(.cost.input < 1 and .reasoning == true and .tool_call == true)
  | {id: .id, name, cost: .cost.input, context: .limit.context, reasoning}
'
```

## Output Format

Present results clearly:

- **Provider query**: name, API endpoint, env vars, doc link
- **Model list**: table with Model ID, Name, Context, Input/M, Output/M, Capabilities
- **Model detail**: sectioned — Capabilities (reasoning/tool_call/structured_output/attachment/modalities), Limits (context/output), Pricing (input/output/cache_read), Interleaved (if reasoning model)

For Chinese-language queries, respond in Chinese. For English queries, respond in English — match the user's language.
