---
name: models-dev-query
description: 查询 models.dev 开源 AI 模型数据库（GitHub 源码仓库 anomalyco/models.dev）中的模型规格（定价、上下文、能力、模态）与提供商 API 配置。
disable-model-invocation: true
---

# Models.dev Query

查询 [models.dev](https://github.com/anomalyco/models.dev) 的 GitHub 源码仓库，默认分支 `dev`。站点直发的 `catalog.json` 是构建产物、直连常超时，改读仓库内按 provider 分目录维护的 TOML 源文件。

## 货架

所有数据是按 provider 分目录的 TOML 文件。查询 = 先选货架，再读取：

| 货架 | 内容 | 用途 |
|------|------|------|
| `providers/` | 目录列表，子目录名 = provider-id | 列出所有提供商 |
| `providers/<id>/provider.toml` | `name` / `api` / `env[]` / `npm` / `doc` | 提供商 API 配置 |
| `providers/<id>/models/` | 目录列表，可能含一层按厂商分组的子目录 | 列出某提供商的模型 |
| `providers/<id>/models/<model>.toml` | `cost`（USD/M）、`status`、`reasoning_options`、`interleaved`、能力字段 | 该提供商视角的模型 |
| `models/<provider>/<model>.toml` | 能力、`limit`、`modalities`、`benchmarks`、`weights`、`knowledge` | 模型规格（canonical） |

**子目录**：`providers/<id>/models/` 下常有一层按模型厂商分组的子目录（如 `anyapi` 的 `models/openai/o4-mini.toml`、`togetherai` 的 `models/zai-org/GLM-5.toml`），少数还有更深层级；确切路径以目录列表为准。

**base_model 继承**：provider 层 TOML 含 `base_model = "<provider>/<model>"` 时，能力字段（attachment / reasoning / limit / modalities 等）不重写，继承自 canonical 文件 `models/<provider>/<model>.toml`。无 `base_model` 的 provider 层 TOML 字段自足。

**读取方式**（离线优先）：镜像 = 仓库 tarball（gzip 后仅 ~1MB），一次解压；需要最新数据时设 `MODELS_DEV_REFRESH=1` 重下。

```bash
MODELS_DEV=${MODELS_DEV:-$HOME/.cache/models-dev}
if [ ! -f "$MODELS_DEV/.complete" ] || [ "$MODELS_DEV_REFRESH" = 1 ]; then
  mkdir -p "${MODELS_DEV%/*}"
  tmp=$(mktemp -d)   # 解压到临时目录，成功才整体替换，失败不污染旧镜像
  if curl -sfL https://github.com/anomalyco/models.dev/archive/refs/heads/dev.tar.gz \
      | tar -xz --strip-components=1 -C "$tmp"; then
    rm -rf "$MODELS_DEV"
    mv "$tmp" "$MODELS_DEV"
    touch "$MODELS_DEV/.complete"
  else
    rm -rf "$tmp"   # 解压失败：丢弃临时目录，.complete 不写入
    exit 1          # 显式失败，改用下方 gh api 备选
  fi
fi
```

之后所有查询直接读本地文件：TOML 在 `<镜像>/<path>`，目录即本地目录列表，全程离线。上游个别模型读不到（断链 symlink 全仓约 32 个，或 `base_model` 指向的 canonical 文件不存在），该字段标注 `N/A`。备选（无 curl/tar 环境）：gh api 单文件拉取，文件取原文、目录取 JSON 数组（取 `type`/`name`）：

```bash
gh api "repos/anomalyco/models.dev/contents/<path>?ref=dev" -H "Accept: application/vnd.github.raw+json"
```

## 查询协议

### Step 1 — 选货架

按查询目标在上表确定每个数据的确切路径（文件或目录）。
**完成标准**：所有待查数据都有唯一路径，无歧义。

### Step 2 — 读取

按「读取方式」逐个读取目标路径；目录一次读回全部条目。捕获每条 `base_model` 字段。
**完成标准**：每个目标都已读到，内容在手。

### Step 3 — 呈现

按下方 Output Format 输出，字段缺失时标注 `N/A`。
**完成标准**：能力、limit、定价、评测各节齐全；存在 `base_model` 时其 canonical 已补读（评测与权重只在 canonical 层）。

## 查询指南

### 单模型画像（能力 + 定价 + 评测）

1. 读 provider 层模型 TOML（`providers/<id>/models/` 下，有子目录时路径含中间层）——定价、推理选项、该提供商的能力覆盖。
2. 含 `base_model`，或文件缺能力字段 → 读 `models/<provider>/<model>.toml` 补齐能力、limit、benchmarks、weights。
3. 两层合并呈现。

### 提供商 API 配置

读 `providers/<id>/provider.toml`：`api`（base URL）、`env[]`（认证变量）、`npm`（AI SDK 包）、`doc`。可组合为目标工具（Trae / OpenCode / Cursor / Continue 等）的配置片段。

### 列出提供商 / 模型

- 所有提供商：`providers/` 下的目录名即 provider-id。
- 某提供商的模型：`providers/<id>/models/` 下的模型 TOML 文件名（有子目录时含中间层）。

### 批量筛选 / 比较（开源、低价、最近发布）

在镜像内本地遍历全部模型 TOML（离线）：

```bash
find "$MODELS_DEV/models" "$MODELS_DEV/providers" -name '*.toml' -type f
```

逐个读取汇总比较。筛选依据：canonical 的 `open_weights` / `release_date` / `benchmarks`，provider 层的 `cost.input`。

## Output Format

- **Provider query**: name、API endpoint、env vars、doc link
- **Model list**: 表格 —— Model ID、Name、Context、$/M in、$/M out、Capabilities
- **Model detail**: 分节 —— Capabilities（reasoning / tool_call / structured_output / attachment / modalities）、Limits（context / output）、Pricing（input / output / cache_read）、Benchmarks（如有）
- **Reasoning 模型**: 另附 provider 层 `reasoning_options`（toggle / effort / budget_tokens）与 `interleaved.field`（如 `reasoning_content`）
