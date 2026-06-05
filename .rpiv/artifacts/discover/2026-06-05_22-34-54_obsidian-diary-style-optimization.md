---
date: 2026-06-05T22:34:54+0800
author: CNife
commit: 085e4f5
branch: main
repository: skills
topic: "obsidian-diary 写作风格优化"
tags: [intent, frd, obsidian-diary, style-check]
status: complete
last_updated: 2026-06-05T22:34:54+0800
last_updated_by: CNife
---

# FRD: obsidian-diary 写作风格优化

## Summary

在 obsidian-diary 技能的工作流中增加「写作风格自检」步骤，防止 agent 将日记写成流水账或工作周报风格。通过修改 SKILL.md 工作流、补充 references/personal-diary.md 自检章节、新增 evals 测试用例来实现。不改动 obsidian-helper.py 脚本，最小改动范围。

## Problem & Intent

"基于刚才对 obsidian-diary 的评估发现，先调研技能的脚本、eval、references 等内部结构，再制定具体的优化方案并实施。"

核心问题：会话日志分析发现，agent 在写个人日记时默认输出工作周报风格（分节列清单、按时间顺序平铺），用户明确反馈"太流水账了，语言风格也不对"。当前技能完全依赖 LLM 指令引导来防止流水账，没有任何程序化验证或自检机制。

## Goals

- SKILL.md 工作流增加一个显式的「写作风格自检」步骤（在步骤 3 写入之后、步骤 4 确认之前）
- references/personal-diary.md 增加结构化的自检清单章节
- evals/evals.json 新增 1 个风格质量检测用例
- agent 输出不再是流水账风格（按主题聚合、有个人感受、无 AI 噪音）

## Non-Goals

- 不改动 obsidian-helper.py 脚本（纯文件系统辅助，不做内容验证）
- 不增加程序化内容验证或后处理过滤逻辑
- 不改动 references/work-log.md（工作日志的格式规则已经完备）
- 不改动变体选择逻辑（work vs personal 的判断现有机制足够）

## Functional Requirements

1. SKILL.md 的工作流步骤 3（提取并写入）和步骤 4（确认）之间，新增「写作风格自检」副步骤
2. 自检覆盖三个维度：语气（是否像工作周报）、结构（是否按主题聚合）、噪音（是否包含禁止项）
3. references/personal-diary.md 增加结构化自检清单章节，含具体检查问题和修正指引
4. evals/evals.json 新增风格质量检测用例，验证 agent 输出是否符合良好风格标准

## Non-Functional Requirements

- **Performance**: 无额外性能要求 — 自检在 LLM 输出阶段完成，不增加工具调用
- **Security**: 无影响
- **UX / Accessibility**: 自检步骤的输出以文本形式呈现给用户，不改变确认流程的交互方式
- **Reliability**: 自检是建议性而非强制阻断 — agent 发现问题后应重写，但如果用户仍要求写入则尊重用户指令

## Constraints & Assumptions

- 不修改 obsidian-helper.py — 脚本只做文件系统操作，保持零内容验证
- 两个位置的 SKILL.md 完全相同（`.agents/skills/` 活跃位置 ↔ `code/skills/knowledge/` 源位置），修改时需同步到两个位置
- 假设当前 LLM 能理解并遵守自检指令（与评估中 agent 正确修正"太流水账"问题的表现一致）

## Acceptance Criteria

- [ ] SKILL.md 的工作流章节包含 `## 写作风格自检` 副步骤，明确列出语气、结构、噪音三项检查
- [ ] references/personal-diary.md 包含 `# 写好之后自检` 章节，含至少 4 个具体自检问题
- [ ] evals/evals.json 新增的测试用例可通过 `skill-evaluator` 运行验证
- [ ] 用评估期间发现的实际会话样本（小说项目规范建设）手动测试，agent 输出为叙事风格而非列表风格

## Recommended Approach

在 SKILL.md 工作流的步骤 3b（写入方式）和步骤 4（确认）之间插入「写作风格自检」副步骤。同时更新 references/personal-diary.md 增加自检清单章节，更新 evals/evals.json 新增风格质量用例。修改涉及 3 个文件、4 处改动。

## Decisions

### 优化目标
**Question**: 这次优化的目标粒度是什么？
**Recommended**: 仅加「自检」步骤 — 在 SKILL.md 工作流中加自检 + 更新 references + 加 eval 用例。不改脚本。
**Chosen**: 仅加「自检」步骤
**Rationale**: 最小改动最大效果 — 用户评估已确认「弱点是可修复的，不是价值问题」，不需要重写架构

### 自检覆盖维度
**Question**: 自检步骤应该覆盖哪些维度？
**Recommended**: 三重自检 — 语气是否自然 + 结构是否按主题聚合 + 是否包含禁止项
**Chosen**: 三重自检（语气、结构、噪音）
**Rationale**: 覆盖了"太流水账"的三个根源：语气像周报、结构按时间平铺、内容含 AI 噪音

### Eval 方案
**Question**: 新的 eval 用例应该检测什么？
**Recommended**: 风格质量检测 — 给定会话样本 + 标准输出，验证 agent 输出是否接近标准
**Chosen**: 风格质量检测
**Rationale**: 直接对齐用户反馈的"太流水账了"问题，比间接检测自我修正能力更可靠

### 不改脚本
**Question**: Pre-resolved from codebase evidence
**Recommended**: 不修改 obsidian-helper.py
**Chosen**: 不修改 obsidian-helper.py
**Rationale**: `evidence: scripts/obsidian-helper.py (217 lines)` — 脚本是纯文件系统辅助，不做任何内容验证，改动方向不对

### 两个位置同步
**Question**: Pre-resolved from codebase evidence
**Recommended**: 修改时同步更新 `.agents/skills/` 和 `code/skills/knowledge/` 两个位置
**Chosen**: 同步更新两个位置
**Rationale**: `evidence: codebase-analyzer probe` — 两位置完全一致，不同步会导致运行时版本与源码版本脱节

### SKILL.md 缺少自检环节
**Question**: Pre-resolved from codebase evidence
**Recommended**: 在步骤 3b 与步骤 4 之间插入自检副步骤
**Chosen**: 在步骤 3b 与步骤 4 之间插入自检副步骤
**Rationale**: `evidence: SKILL.md lines 176-222` — 工作流从提取写入直接跳到确认，中间没有任何风格检查

### Evals 缺少风格用例
**Question**: Pre-resolved from codebase evidence
**Recommended**: 新增风格质量检测用例
**Chosen**: 新增风格质量检测用例
**Rationale**: `evidence: evals/evals.json (4 test cases)` — 现有用例覆盖变体选择、主动询问、R18 处理，但无风格质量检测

### Personal-diary.md 缺少自检步骤
**Question**: Pre-resolved from codebase evidence
**Recommended**: 增加结构化自检清单章节
**Chosen**: 增加结构化自检清单章节
**Rationale**: `evidence: references/personal-diary.md lines 89-101` — 已有语气对比示例但只是参考，不是流程约束

### 验收标准
**Question**: 怎么算优化完成？
**Recommended**: 可运行 + 可验证 — 文档更新到位 + evals 能跑通 + 手动测试通过
**Chosen**: 可运行 + 可验证
**Rationale**: 文档更新是基础，evals 防止回归，手动测试确认效果

## Open Questions

（无 — 所有问题在访谈中已解决）

## Suggested Follow-ups

- 日记中已记录「流水账」问题：`个人日记/2026/05/2026年5月4日星期一.md:84` — "SKILL.md 工作流缺少「主题识别→聚合」步骤——这是流水账的根因"。本次优化已覆盖此问题。
- 评估期间发现的远程机器（cnife.work-pc）104 次调用中有少量纠正模式，但未深入分析具体内容 — 可能揭示额外边缘情况，建议后续调研。

## References

- 评估报告（本会话前序内容）
- `~/.agents/skills/obsidian-diary/SKILL.md`
- `~/.agents/skills/obsidian-diary/scripts/obsidian-helper.py`
- `~/.agents/skills/obsidian-diary/evals/evals.json`
- `~/.agents/skills/obsidian-diary/references/personal-diary.md`
- `~/.agents/skills/obsidian-diary/references/work-log.md`
