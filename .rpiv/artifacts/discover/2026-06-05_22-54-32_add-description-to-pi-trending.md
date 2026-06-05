---
date: 2026-06-05T22:54:32+0800
author: CNife
commit: 9837b68
branch: main
repository: skills
topic: "Add one-sentence description to pi-trending output"
tags: [intent, frd, pi-trending, output-format]
status: complete
last_updated: 2026-06-05T22:54:32+0800
last_updated_by: CNife
---

# FRD: pi-trending 增加一句话简介

## Summary

在 pi-trending 输出的 Markdown 趋势表里增加「一句话介绍」列，由 AI 将英文 description 翻译为中文并精简后展示，同时精简表格列布局（去掉类型和周下载），让用户扫一眼就能知道热门包是干什么的。

## Problem & Intent

> "看趋势时快速了解用途"

目前的趋势表有包名、类型、作者、周下载、趋势分五列，但很多包光看名字猜不出功能。npm description 通常是英文的，需要额外理解成本。目标是把已有 description 数据展示在表格里，并由 AI 现场翻译为中文并精简，让中文用户一眼看懂。

## Goals

- 在 Markdown 趋势表中展示每个包的一句话简介，由 AI 翻译为中文并精简
- 精简表格列布局，保留最相关的信息维度
- description 数据复用已有字段，不额外请求 npm API
- 对空 description 友好处理，避免空单元格

## Non-Goals

- 不抓取 README 全文（减少 API 调用和耗时）
- 不改变 JSON 输出格式（JSON 已经包含 description）
- 不改变搜索策略、趋势算法、缓存机制
- 不涉及 CLI 参数变更
- 不在脚本中内置翻译逻辑（由 AI 在展示环节处理）

## Functional Requirements

1. Markdown 趋势表新增「一句话介绍」列，展示每个包的中文功能简介
2. AI 在呈现趋势表时，将原始英文 description 翻译为中文并精简（控制在 20 字以内，保留核心功能信息）
3. 表格列布局改为：`#`、`包名`、`作者`、`趋势分`、`一句话介绍`（移除 `类型` 和 `周下载` 列）
4. 列标题使用「一句话介绍」

## Non-Functional Requirements

- **Performance**: 不新增任何 API 请求，不影响脚本执行时间；AI 翻译在展示环节完成
- **Security**: 无变更（数据源不变）
- **UX**: 表格信息密度更聚焦于「包是什么 + 增长趋势」，中文描述便于一眼筛选
- **Reliability**: 空 description 由 AI 标注「（未提供描述）」

## Constraints & Assumptions

- 不改动 `PiPackage` 数据类模型（description 字段已存在）
- 不改动 `render_json()` 输出（JSON 已包含 description）
- description 数据来源于 npm search API 返回的 `package.description` 字段，通常为 10-30 字的一行简介
- 包的 npm description 可能缺失（空字符串），由 AI 标注「（未提供描述）」
- AI 翻译在展示环节完成，脚本本身不负责翻译

## Acceptance Criteria

- [ ] 运行 `uv run --script scripts/pi_trending.py` 输出的 Markdown 表格包含「一句话介绍」列
- [ ] 表格列标题为 `| # | 包名 | 作者 | 趋势分 | 一句话介绍 |`
- [ ] AI 展示时，description 已翻译为中文并精简至 20 字以内
- [ ] 原始英文 description 为空时，中文显示「（未提供描述）」
- [ ] JSON 输出 (`--json`) 不受影响，格式不变
- [ ] `--type extension` / `--max 10` 等过滤参数依然正常工作
- [ ] `--verbose` 日志不受影响

## Recommended Approach

1. **脚本修改**：修改 `scripts/pi_trending.py` 中的 `render_markdown()` 函数，重新设计 Markdown 表格输出格式——变更表头、调整列顺序（#、包名、作者、趋势分、一句话介绍）、增加 description 列、移除类型和周下载列。原始英文 description 保留在输出中（AI 用作翻译源文）。其他函数（`render_json()`、数据获取逻辑、CLI 解析）无需改动。

2. **AI 展示环节**：更新 SKILL.md，在「快速概览」和「结果解读」工作流中增加步骤——AI 获取脚本输出的 Markdown 后，逐行将英文 description 翻译为中文并精简（≤20 字），然后将翻译结果展示给用户。

## Decisions

### Intent — 快速了解用途
**Question**: 增加一句话简介的目的是什么？使用场景是什么？
**Recommended**: n/a — 意图问题
**Chosen**: 看趋势时快速了解用途
**Rationale**: 开发者想解决"看了名字不知道包干什么用"的问题，扫一眼就能筛选感兴趣的包

### Data source — 复用已有 description
**Question**: Pre-resolved from codebase evidence
**Recommended**: 直接用 npm search API 已有的 description 字段
**Chosen**: 直接用已有 description（确认）
**Rationale**: evidence: `scripts/pi_trending.py:154` — description 已在 `fetch_top_packages()` 中从 search API 提取并存于 `PiPackage.description`，无需额外 API 调用

### Table layout — 精简列布局
**Question**: 描述在 Markdown 表格中怎么展示？
**Recommended**: 表格末尾加列
**Chosen**: 精简版 — #, 包名, 作者, 趋势分, 一句话介绍（去掉类型、周下载）
**Rationale**: 开发者希望表格更紧凑，聚焦于核心信息维度

### Long description handling — 不截断
**Question**: 怎么处理长描述？
**Recommended**: 截断到 40 字加...
**Chosen**: 不截断，自然换行
**Rationale**: 开发者认为完整性比紧凑性更重要

### Column header — 一句话介绍
**Question**: 描述列的标题用什么？
**Recommended**: 一句话介绍
**Chosen**: 一句话介绍
**Rationale**: 与原始需求描述一致

### Translation approach — AI 实时翻译
**Question**: 翻译 description 采用什么方式？
**Recommended**: LibreTranslate 免费 API
**Chosen**: AI 实时翻译（当前 LLM 在展示环节直接翻译）
**Rationale**: 零额外成本，无需在脚本中引入翻译依赖，翻译质量高，且可同时做精简

### Empty description — 显示占位符
**Question**: 如果某个包没有 description，怎么显示？
**Recommended**: 显示"—"
**Chosen**: 显示"—"
**Rationale**: 避免空单元格造成疑惑（AI 翻译时输出「（未提供描述）」）

## Open Questions

无。所有决策已在面试中确定。

## Suggested Follow-ups

无。代码库探索未发现与本次改动相关的其他问题。

## References

- `scripts/pi_trending.py` — 目标脚本，需修改 `render_markdown()` 函数
- `SKILL.md` — 后续可能需要更新文档中的输出示例
