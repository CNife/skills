---
date: 2026-06-09T14:20:26+0800
author: 蔡涛
commit: 99755db
branch: main
repository: skills
topic: "models-dev-query catalog migration"
tags: [intent, frd, models-dev-query]
status: complete
last_updated: 2026-06-09T14:20:26+0800
last_updated_by: 蔡涛
---

# FRD: models-dev-query catalog migration

## Summary

将 `utility/models-dev-query/` 技能的数据源从 `api.json` 迁移到 `catalog.json`，在 SKILL.md 中描述 catalog.json 的完整字段结构，并提供针对 `/tmp` 缓存文件的 jq 查询示例。不引入独立脚本，保持 curl + jq 的轻量模式。

## Problem & Intent

技能使用者（自己和公开用户）需要查询 AI 模型规格（提供商、定价、上下文窗口、能力）。当前 SKILL.md 使用 `api.json` 作为主要数据源，但 models.dev 已推出 `catalog.json` 统一端点，合并了 provider 数据和 model 元数据（benchmarks/weights），且增加了 `models.json` 提供模型独立元数据。同时旧版 SKILL.md 的内联 jq 示例结构没有反映 catalog.json 的双层结构（扁平 `models` 索引 + provider 内嵌 `models`），导致 AI 写的 jq 查询容易踩错字段路径。目标是用最轻的方式更新技能：不写脚本，只更新文档和示例，让 AI 理解新结构后自动构造正确的 jq 查询。

## Goals

- 默认数据源从 `api.json` 切换为 `catalog.json`
- 将 `catalog.json` 下载到 `/tmp/models-dev-catalog.json`，按需缓存
- 在 SKILL.md 中完整描述 catalog.json 的双层结构（`models` 和 `providers` 各自的字段）
- 提供针对缓存文件的 jq 查询示例
- 减少外部依赖（不再需要 `gh` CLI）

## Non-Goals

- 不编写 Python 或 Shell 脚本
- 不实现 TTL 缓存或复杂缓存策略（仅检查文件是否存在）
- 不保留 `api.json` 作为 fallback 数据源
- 不添加配置生成功能（如自动生成 Cursor/Continue 配置片段）
- 不保留 `gh` CLI 查询 TOML 的能力

## Functional Requirements

1. SKILL.md 的快速查询命令中，默认使用 `catalog.json` 替代 `api.json`
2. SKILL.md 必须说明缓存位置：`/tmp/models-dev-catalog.json`，以及按需下载 + 检查缓存的策略
3. SKILL.md 必须完整记录 `catalog.json` 的双层结构表：
   - 顶层 `models` — 扁平索引（key = `provider/model-id`），字段列表及说明
   - 顶层 `providers` — provider 元信息（api, npm, env, doc）
   - provider 内嵌 `models` — 含 `cost` 定价数据，字段列表及说明
   - 标明两个层的差异：`models` 有 `benchmarks`/`weights`，providers 内嵌 `models` 有 `cost`/`status`
4. SKILL.md 必须提供针对 `/tmp/models-dev-catalog.json` 的 jq 查询示例，覆盖：
   - 列出所有提供商
   - 列出某提供商的所有模型及定价
   - 查某模型的详细参数（包括 pricing）
   - 按条件筛选模型
   - 获取提供商 API 端点信息
5. 示例中的 jq 过滤器必须能覆盖两种情况：扁平 `models` 索引 vs provider 内嵌 `models`

## Non-Functional Requirements

- **Performance**: `curl -sL https://models.dev/catalog.json -o /tmp/models-dev-catalog.json` 约 2.3MB，应在合理时间内完成
- **Reliability**: 下载失败时有 fallback 提示（如提示用户检查网络或重试）
- **UX**: 保持"用户一句话 → AI 写出 jq 查询 → 返回结果"的交互模式

## Constraints & Assumptions

- 数据源仅依赖 `https://models.dev/catalog.json` 端点
- 假设运行环境有 `curl` 和 `jq`（SKILL.md 已假设）
- 假设 `/tmp` 目录可写
- 不对 `catalog.json` 的 schema 做版本兼容（跟随 upstream 变化更新 SKILL.md）
- `api.json` 仍可用但不再是默认数据源

## Acceptance Criteria

- [ ] SKILL.md 中所有 `curl` 示例的 URL 从 `api.json` 改为 `catalog.json`
- [ ] SKILL.md 中 `jq` 过滤器的字段路径与 catalog.json 的实际结构匹配
- [ ] SKILL.md 包含完整的字段结构参考表（`models` + `providers` 双层）
- [ ] SKILL.md 包含 `curl -sL ... -o /tmp/models-dev-catalog.json` + 缓存检查的说明
- [ ] 运行 `curl -sL https://models.dev/catalog.json | jq '.models | keys'` 能正确列出所有 model ID
- [ ] 运行 `curl -sL https://models.dev/catalog.json | jq '.providers["openai"].models["gpt-4o"].cost'` 能返回定价数据

## Recommended Approach

纯文档更新：只修改 `utility/models-dev-query/SKILL.md` — 更新数据源 URL、增加 catalog.json 字段结构文档、调整 jq 示例以匹配双层结构、增加缓存策略说明。不新增任何文件。

## Decisions

### Data Source: catalog.json

**Question**: 默认使用哪个端点作为数据源？
**Recommended**: catalog.json — 它合并 api.json 的 provider 数据和 models.json 的模型元数据
**Chosen**: catalog.json
**Rationale**: 统一端点，减少 API 调用次数，同时包含 benchmarks/weights/cost 等完整数据

### Script Extraction

**Question**: 内联命令是否提取为独立的 Python 脚本？
**Recommended**: Python 脚本 + uv run --script
**Chosen**: 不提取脚本，保持 curl + jq 的轻量模式
**Rationale**: 用户提出的新思路更简洁 — 只需要下载 + 描述结构 + 让 AI 写 jq，不需要脚本抽象层

### Download Strategy

**Question**: 如何下载和缓存 catalog.json？
**Recommended**: 按需下载 + 检查 /tmp 缓存
**Chosen**: curl 下载到 /tmp/models-dev-catalog.json，查询前检查文件是否存在
**Rationale**: 简单可靠，2.3MB 数据量小，CDN 命中率高

### gh CLI Dependency

**Question**: 是否保留 gh CLI 查询 GitHub TOML 的能力？
**Recommended**: 去掉 gh 依赖 — catalog.json 已有 cost/pricing/status 等完整数据
**Chosen**: 去掉 gh 依赖
**Rationale**: catalog.json 的 providers[].models[] 已包含 cost、status、interleaved、reasoning_options 等字段，不再需要单独查 TOML

### Output Format

**Question**: 查询结果应该用什么格式输出？
**Recommended**: 纯 JSON — 方便 AI parse
**Chosen**: 纯 JSON
**Rationale**: AI 直接构造 jq 命令，jq 默认输出 JSON，AI 可以自由加工

## Open Questions

（无）

## Suggested Follow-ups

- 如果将来 models.dev 修改 catalog.json schema，SKILL.md 需要同步更新字段结构表

## References

- `utility/models-dev-query/SKILL.md` — 当前技能文件
- `https://models.dev/catalog.json` — 新数据源
- `https://models.dev/api.json` — 旧数据源（仍可用）
- `https://models.dev/models.json` — 模型独立元数据端点
