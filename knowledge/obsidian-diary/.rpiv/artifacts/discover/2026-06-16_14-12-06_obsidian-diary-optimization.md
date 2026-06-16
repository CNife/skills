---
date: 2026-06-16T14:12:06+0800
author: 蔡涛
commit: cceedf5
branch: main
repository: skills
topic: "obsidian-diary 技能优化"
tags: [intent, frd, obsidian-diary, skill-optimization]
status: ready
last_updated: 2026-06-16T14:12:06+0800
last_updated_by: 蔡涛
---

# FRD: obsidian-diary 技能优化

## Summary

对 obsidian-diary 技能做结构性优化：新增「事实边界」约束（禁止 AI 杜撰会话中不存在的信息），将分散在 SKILL.md 和两个 reference 文件中的重复内容压缩到合并后的 `references/diary-rules.md`，将冗长的三段落自检（语气/结构/噪音）重构为一张不可跳过的 3-blocker 硬闸门表格，同步修复脚本 `personal-diary.md` 的 fallback 命名不对称，并补充「禁止杜撰」和「混合内容拆分」两个 eval 用例。

## Problem & Intent

AI Agent 在写日记时存在两个核心问题：

1. **需要多轮修正**：AI 写完日记后用户经常要改两三版才符合要求 — 路径格式不对、风格不像人写的、混入了 agent 操作日志。用户希望一次过。
2. **日记质量不够**：输出内容像是 agent 工作流水账，而不是人看的结论式记录。AI 还会杜撰会话中不存在的细节（如"根据习惯""随手翻了翻"），这是用户明确不能接受的。

优化目标：**减少修正轮次 + 提升日记质量** — 让 AI 第一次写就对。

## Goals

- 新增「事实边界」规范，从源头阻止 AI 杜撰虚构内容
- 将 SKILL.md 从 ~320 行精简到更紧凑的状态，消除三重复
- 将自检步骤从三段式自问改为不可跳过的 3-blocker 硬闸门
- 统一 reference 文件命名，修复脚本的 fallback 不对称
- 补充 eval 用例覆盖新规则和混合内容场景

## Non-Goals

- 不改变技能的核心工作流（五步流程保持不变）
- 不重写 `scripts/obsidian-helper.py`，只修命名引用
- 不改变主动询问策略（6月11日已优化过）
- 变体选择规则中存在覆盖漏洞：用户明确说了「记到个人日记」时 AI 仍按自己的判断选 work — 需强化规则：**用户明确指定的变体优先于 AI 的自动判断**

## Functional Requirements

1. **用户明确指定的变体优先**：当用户明确说出「记工作日志」「写个人日记」等变体指示时，AI 必须直接遵从，不得用自动判断规则覆盖用户的显式指令。变体判断表只在用户未指定时生效。
2. SKILL.md 头部新增一个「不可违反的约束」段落，包含事实边界规则：每条写入日记的 bullet 必须有会话/工具输出中的证据支撑，禁止添加"根据习惯""随手"等 AI 填充语
3. SKILL.md 中的自检步骤（步骤 3d）从三段式自问重构为一张 3-blocker 硬闸门表格（事实虚构 / 结构散乱 / 流程噪音），每行一个 blocker，未通过则阻止确认
4. `references/work-log.md` 和 `references/personal-diary.md` 合并为 `references/diary-rules.md`，用变体标记区分 work/personal 规则
5. SKILL.md 中路径规则的精简：只保留一句话指针指向 `references/diary-rules.md`，详细格式和对照表只留在 reference 中
6. `scripts/obsidian-helper.py` 中引用 `personal-diary.md` 的 fallback 逻辑改为直接引用合并后的 `diary-rules.md`
7. AI 噪音过滤表（当前独立 5 行表）合并到 blocker 表格的「流程噪音」行
8. 在 `evals/evals.json` 中新增 2 个 eval 用例：禁止杜撰、混合内容拆分

## Non-Functional Requirements

- **性能**: 无特定约束 — SKILL.md 指令精简不会影响运行时性能
- **可维护性**: 消除三重复后，路径规则、噪音过滤、自检指南各只有一处维护入口
- **兼容性**: 合并 reference 文件后，旧的 `references/work-log.md` 和 `references/personal-diary.md` 需暂时保留（指向新文件）或直接删除
- **可靠性**: blocker 闸门比自问自答更可靠 — 硬性条件触发修正而非依赖 AI 自觉

## Constraints & Assumptions

- SKILL.md 行数应控制在合理范围内（技能创建指南建议 <500 行），当前 ~320 行仍有精简空间
- 脚本 `obsidian-helper.py` 的 reference 文件路径解析使用相对路径 `../references/`，合并后需更新
- 安装副本（`~/.pi/agent/skills/obsidian-diary/`）通过 `cp` 同步，不涉及 bunx/npm 重装
- 假设用户希望保留现有 evals/evals.json 结构（5 个现有用例不动，只追加）

## Acceptance Criteria

- [ ] 运行 `uv run ruff check --fix knowledge/obsidian-diary/` 通过
- [ ] SKILL.md 中不出现"杜撰"、"fabricat"以外的虚构内容 — 已新增事实边界约束
- [ ] `references/diary-rules.md` 同时包含 work 和 personal 变体规则，格式正确
- [ ] 旧的 `references/work-log.md` 和 `references/personal-diary.md` 已删除或仅留指向新文件的指针
- [ ] `scripts/obsidian-helper.py` 中不再引用 `personal-diary.md` 或 `work-log.md` 文件名
- [ ] `evals/evals.json` 中至少有 6 个用例（5 个原有 + 1 个新增「禁止杜撰」）
- [ ] 安装副本与源码同步：`diff` 无差异

## Recommended Approach

对 SKILL.md 做结构性精简：顶部新增 Invariant 区（事实边界），中间去掉重复的路径规则和噪音过滤表改为指针引用，步骤 3d 的重写为 3-blocker 表格。两个 reference 文件合并为 `diary-rules.md` 并更新脚本引用。eval 追加 2 个用例。修改后按 cnife-skills-repo 流程：ruff 检查 → cp 到安装副本 → git 提交。

## Decisions

### 用户指定变体优先

**Question**: 用户说了「个人日记」时 AI 应该听从还是按规则判断？
**Recommended**: 用户指定优先于自动判断
**Chosen**: 用户指定优先
**Rationale**: AI 覆盖用户的显式指令是反直觉的，且用户在实际使用中被纠正过

### 优化范围

**Question**: 这次优化的范围到哪？
**Recommended**: SKILL.md + references + evals + 脚本
**Chosen**: 全量范围 — SKILL.md + references + evals + 脚本
**Rationale**: 要修复脚本的命名不对称必须动脚本，要统一 reference 必须合并文件

### 事实边界位置

**Question**: 「禁止杜撰」规则放在哪？
**Recommended**: 作为独立 Invariant 段落放在 SKILL.md 开头
**Chosen**: 独立 Invariant 段落
**Rationale**: 这是不可违反的约束，需要显眼，不能埋在工作流步骤中

### 自检方案

**Question**: 自检步骤如何重构？
**Recommended**: 3-blocker 硬闸门表格，统一放在 SKILL.md
**Chosen**: 3-blocker 硬闸门表格
**Rationale**: 表格比三段自问更紧凑、更可执行、更难跳过

### 路径精简

**Question**: 路径规则的三重复如何精简？
**Recommended**: 仅在 references 详述，SKILL.md 只留指针
**Chosen**: 仅在 references 详述
**Rationale**: 路径格式已在 references 中有完整对照表和 ASCII 图，无需在 SKILL.md 中重复

### 参考文件合并

**Question**: 两个 reference 文件如何处理？
**Recommended**: 合并为 references/diary-rules.md
**Chosen**: 合并为 references/diary-rules.md
**Rationale**: 减少文件数量，统一命名，同步修复脚本 fallback 不对称

### AI 噪音过滤表位置

**Question**: AI 噪音过滤表如何处理？
**Recommended**: 合并到 3-blocker 的「流程噪音」行
**Chosen**: 合并到 3-blocker 的「流程噪音」行
**Rationale**: 噪音过滤本质是自检的一环，独立成章增加重复

### Eval 补充

**Question**: Eval 如何补充？
**Recommended**: 新增 2 个 eval
**Chosen**: 新增 2 个 eval —「禁止杜撰」和「混合内容拆分」
**Rationale**: 两个都是用户明确面对的痛点，需要有可验证的测试覆盖

## Open Questions

无 — 所有决策已在面试中完成。

## Suggested Follow-ups

- 脚本 `obsidian-helper.py` 中 `CONFIG_PATH` 硬编码 `~/.config/cnife-skills/obsidian-diary.json`，无 CLI 覆盖选项 — 如后续需要多配置切换可加 `--config` 参数
- reference 文件引用使用相对路径 `../references/diary-rules.md`，在安装副本中通过 symlink 或 cp 部署时需确保目录结构一致

## References

- `knowledge/obsidian-diary/SKILL.md` — 当前 SKILL.md（~320 行）
- `knowledge/obsidian-diary/references/work-log.md` — 工作日志变体规则（78 行）
- `knowledge/obsidian-diary/references/personal-diary.md` — 个人日记变体规则（194 行）
- `knowledge/obsidian-diary/evals/evals.json` — 现有 5 个 eval 用例
- `knowledge/obsidian-diary/scripts/obsidian-helper.py` — 脚本（418 行）
