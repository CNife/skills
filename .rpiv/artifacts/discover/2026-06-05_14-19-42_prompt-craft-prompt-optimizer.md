---
date: 2026-06-05T14:19:42+0800
author: 潭渊
commit: 6d7a6a2
branch: reorg/restructure-by-category
repository: skills
topic: "Prompt Craft 通用提示词优化"
tags: [intent, frd, prompt-craft, pi-agent]
status: complete
last_updated: 2026-06-05T14:19:42+0800
last_updated_by: 潭渊
---

# FRD: Prompt Craft 通用提示词优化

## Summary
`prompt-craft` should be simplified from a pi prompt template creation/writing skill into a general LLM prompt optimization skill for improving existing prompts. It should serve both skill users and skill maintainers: users get a shorter flow with diagnosis plus an improved prompt, while maintainers get a single principles source, README consistency, and a minimal `evals/evals.json` regression reference.

## Problem & Intent
The developer identified the audience as "1，2": skill users and skill maintainers. During the interview, the scope was narrowed in the developer's own words to "只优化改进", "简化功能，只要优化提示词，不写文件", and storage choices should "都去掉".

The desired behavior is also explicit: "同意，缺信息时需要追问用户". For maintenance, the developer wants this to follow `skill-creator` expectations, but only at the selected lightweight level: "只加 evals 文件".

## Goals
- Turn `prompt-craft` into a general LLM prompt optimization skill for existing prompts, not a pi prompt template generator.
- Give users a concise but explainable result: relevant diagnosis, brief rationale, and a complete improved prompt.
- Ask follow-up questions only when missing information would materially affect the rewrite.
- Preserve the original prompt's language and style unless the user explicitly asks otherwise.
- Keep `references/principles.md` as the single source for OpenAI prompt engineering principles.
- Add a minimal `evals/evals.json` file for regular prompt rewrite examples, following the skill-creator file convention.
- Update the repository README so the discovery/index description matches the new behavior.

## Non-Goals
- Creating new pi prompt template files from scratch.
- Writing prompt templates to `.pi/prompts/`, `~/.pi/agent/prompts/`, package prompt directories, or CLI paths.
- Asking the user where to store generated files.
- Running the full `skill-creator` evaluation loop, generating benchmark reports, launching `generate_review.py`, or optimizing the skill description in this phase.
- Building a broad eval suite for edge cases, negative cases, or all 9 principles in this phase.

## Functional Requirements
1. The system SHALL redefine `pi-agent/prompt-craft/SKILL.md` around optimizing existing LLM prompts, not creating or saving pi prompt templates.
2. The system SHALL remove the prompt template formatting, prompt template file writing, and storage-location workflow from the skill instructions.
3. The system SHALL instruct the agent to request the original prompt when the user asks for optimization but does not provide prompt text.
4. The system SHALL instruct the agent to ask targeted follow-up questions only when task goal, audience, output format, or constraints are missing and would materially affect the rewrite.
5. The system SHALL read and use `references/principles.md` as the single principles source, applying only relevant principles rather than forcing a complete 9-point checklist.
6. The system SHALL output a concise diagnosis, the improvement rationale tied to relevant principles, and a complete improved prompt.
7. The system SHALL preserve the original prompt's language and style unless the user asks for translation or style conversion.
8. The system SHALL remove or collapse the duplicated 9-principle quick-reference content currently maintained in `SKILL.md`.
9. The system SHALL add `pi-agent/prompt-craft/evals/evals.json` using the `skill-creator` evals shape, with regular prompt rewrite examples only.
10. The system SHALL update README entries for `prompt-craft` so they describe general prompt optimization rather than pi prompt template creation.

## Non-Functional Requirements
- **Performance**: No specific runtime constraint. The interaction should avoid unnecessary fixed questionnaires and avoid forcing a full 9-item audit for simple prompts.
- **Security**: The optimized skill should not write files during normal prompt optimization and should not ask for storage paths.
- **UX / Accessibility**: The default flow should be low-friction: accept pasted prompt text, ask only necessary clarifying questions, and return directly usable improved text.
- **Reliability**: Single-source principles and minimal evals should reduce drift when the skill is later edited.

## Constraints & Assumptions
- The target skill currently lives at `pi-agent/prompt-craft/` and consists of `SKILL.md` plus reference files.
- The current README describes `prompt-craft` as creating and improving pi prompt templates; this must be updated if the skill behavior changes.
- `skill-creator` is used as the maintenance convention source, but this phase intentionally adopts only the `evals/evals.json` file requirement.
- The downstream implementation should verify whether `references/pi-prompt-template.md` remains referenced before deciding whether to delete or leave it unused.

## Acceptance Criteria
- [ ] Running `rg -n "\.pi/prompts|~/.pi/agent/prompts|存放位置|第六步|prompt template 文件" pi-agent/prompt-craft/SKILL.md` returns no matches for an active file-writing or storage-location workflow.
- [ ] Running `rg -n "references/principles.md" pi-agent/prompt-craft/SKILL.md` shows that the skill loads the principles reference, and running `rg -n "原则速查|最新模型|分隔符|参数合理" pi-agent/prompt-craft/SKILL.md` shows no duplicated 9-principle quick-reference block.
- [ ] Running `python -m json.tool pi-agent/prompt-craft/evals/evals.json` exits 0, and the file contains `skill_name: "prompt-craft"` plus regular rewrite eval prompts.
- [ ] Running `rg -n "创建和改进 pi prompt template" README.md` returns no matches, and `README.md` contains a `prompt-craft` entry describing general prompt optimization.
- [ ] Invoking the skill with a pasted ordinary LLM prompt visibly returns a concise diagnosis, rationale, and complete improved prompt without asking whether to create or save a file.
- [ ] Invoking the skill with "帮我优化提示词" and no prompt text visibly asks the user to provide the original prompt before attempting a rewrite.

## Recommended Approach
Rewrite `pi-agent/prompt-craft/SKILL.md` as a lean prompt-optimization workflow: gather missing context only when needed, load `references/principles.md`, apply relevant principles, and return diagnosis plus improved prompt. Add a lightweight `evals/evals.json` for regular rewrite cases and update README descriptions to match the new general LLM prompt optimization scope.

## Decisions

### Target Audience
**Question**: 你想优化 `@pi-agent/prompt-craft/` 技能，是为了解决谁在什么场景下遇到的具体问题？
**Recommended**: n/a — intent question
**Chosen**: "1，2" — skill users and skill maintainers.
**Rationale**: The feature must improve both invocation/output experience and maintainability, not just one side.

### Scope Narrowed To Improvement
**Question**: 从探针我推断：`prompt-craft` 目前公开承诺同时覆盖“创建”和“改进”prompt template（`pi-agent/prompt-craft/SKILL.md:8`，`README.md:56`）。这次优化要保留这个双模式，还是改变范围？
**Recommended**: 保留但拆清
**Chosen**: 只优化改进
**Rationale**: The developer explicitly narrowed the feature away from creation and toward existing-prompt optimization.

### Remove File Writing
**Question**: 从探针我推断：生成正文后，技能会先询问是否产出文件，用户确认才进入写入（`pi-agent/prompt-craft/SKILL.md:35`）。这条确认门要保留吗？
**Recommended**: 保留确认门
**Chosen**: 简化功能，只要优化提示词，不写文件
**Rationale**: File writing is no longer part of the simplified skill concept.

### Remove Storage Choices
**Question**: 从探针我推断：技能当前只暴露项目/全局两个位置（`pi-agent/prompt-craft/SKILL.md:54-55`），但参考文档列出全局/项目/包/CLI 四种（`pi-agent/prompt-craft/references/pi-prompt-template.md:13-16`）。这次要怎么处理？
**Recommended**: 补齐四种
**Chosen**: 都去掉
**Rationale**: Storage choices belong to file generation, which the developer removed from scope.

### Single Principles Source
**Question**: 从探针我推断：`SKILL.md` 既要求读取 `references/principles.md`，又在本文件内维护一份 9 条原则速查（`pi-agent/prompt-craft/SKILL.md:25`，`pi-agent/prompt-craft/SKILL.md:59`）。这次要消除这个双源吗？
**Recommended**: 单一原则源
**Chosen**: 单一原则源
**Rationale**: evidence: `pi-agent/prompt-craft/SKILL.md:25` + `pi-agent/prompt-craft/SKILL.md:59` + confirmed.

### Output Shape
**Question**: 只做提示词优化时，技能每次应该给用户什么形态的结果？这里的张力是“可解释”对“简洁速度”。
**Recommended**: 诊断加改进版
**Chosen**: 诊断加改进版
**Rationale**: This preserves explainability without requiring a complete audit report.

### Missing Information Follow-Up
**Question**: 优化已有提示词时，技能应该怎么收集上下文？这里的张力是“少打断”对“少误改”。
**Recommended**: 缺信息才追问
**Chosen**: 同意，缺信息时需要追问用户
**Rationale**: The flow should avoid fixed questionnaires while still preventing low-quality rewrites caused by missing context.

### Prompt Type
**Question**: 去掉文件写入后，`prompt-craft` 应该主要优化哪类提示词？这里的张力是“贴合 pi agent”对“通用可用”。
**Recommended**: pi agent 提示词
**Chosen**: 通用 LLM 提示词
**Rationale**: The new scope is general prompt optimization, with pi no longer constraining the output format.

### Language And Style Preservation
**Question**: 优化提示词时，输出语言和风格应该怎么处理？这里的张力是“忠实保留”对“主动增强”。
**Recommended**: 保留原语言风格
**Chosen**: 保留原语言风格
**Rationale**: Preserving language and style lets users directly replace their original prompt unless they ask for translation or style conversion.

### Optimization Basis
**Question**: 这个技能优化提示词时应该采用什么判断依据？这里的张力是“原则可追溯”对“灵活发挥”。
**Recommended**: 沿用相关原则
**Chosen**: 沿用相关原则
**Rationale**: evidence: `pi-agent/prompt-craft/references/principles.md:1` + `pi-agent/prompt-craft/SKILL.md:25` + confirmed.

### Skill-Creator Maintenance Level
**Question**: 维护者体验这部分要做到什么程度？这里的张力是“改动轻”对“可防回归”。
**Recommended**: 文档加示例用例
**Chosen**: 按照 skill-creator 规范来
**Rationale**: The developer redirected maintenance requirements to the existing skill improvement convention.

### Skill-Creator Scope
**Question**: “按照 skill-creator 规范”这条，这次 FRD 应该要求做到哪一层？这里的张力是“完整闭环”对“实施成本”。
**Recommended**: 可评测迭代
**Chosen**: 只加 evals 文件
**Rationale**: The feature adopts `evals/evals.json` as a regression reference while deferring the full review/benchmark loop.

### README Synchronization
**Question**: 技能范围改成通用提示词优化后，要不要同步更新仓库 README 里的描述？这里的张力是“口径一致”对“改动范围小”。
**Recommended**: 同步 README
**Chosen**: 同步 README
**Rationale**: evidence: `README.md:56` currently advertises pi prompt template creation; synchronizing the index prevents stale discovery text.

### Eval Coverage
**Question**: 初始 `evals/evals.json` 应该覆盖哪组真实场景？这里的张力是“核心行为覆盖”对“样例数量少”。
**Recommended**: 三类核心场景
**Chosen**: 只测常规改写
**Rationale**: The developer wants the first eval file lightweight and focused on common rewrite behavior.

## Open Questions
- 无。

## Suggested Follow-ups
- After the simplified skill is stable, consider running the full `skill-creator` review and benchmark flow with `generate_review.py` (`/Users/cnife/.agents/skills/skill-creator/SKILL.md:238`, `/Users/cnife/.agents/skills/skill-creator/SKILL.md:478`).
- Consider description-trigger optimization after the behavioral rewrite lands; `skill-creator` documents this as a later step (`/Users/cnife/.agents/skills/skill-creator/SKILL.md:333`).

## References
- `pi-agent/prompt-craft/SKILL.md`
- `pi-agent/prompt-craft/references/principles.md`
- `pi-agent/prompt-craft/references/pi-prompt-template.md`
- `README.md`
- `/Users/cnife/.agents/skills/skill-creator/SKILL.md`
