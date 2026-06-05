---
date: 2026-06-05T21:43:11+0800
author: CNife
commit: c31aa0f
branch: main
repository: skills
topic: "Chezmoi Sync Skill Enhancement"
tags: [intent, frd, chezmoi, skill, enhancement]
status: complete
last_updated: 2026-06-05T21:43:11+0800
last_updated_by: CNife
---

# FRD: Chezmoi Sync Skill Enhancement

## Summary

增强现有的 chezmoi-sync 技能，修复「只检查 git 状态而漏掉 chezmoi 层级变更」的核心盲点，加入智能 re-add 流程和更好的输出可读性。保持纯 bash 主体，容许轻量辅助脚本。工作流改为「先拉远程 → 检测 chezmoi 状态 → re-add → 提交推送」，按阶段独立快走。

核心安全模型：将 home ←→ 源仓库 ←→ 远程仓库三者的同步操作按安全性分层——git 内操作（pull/push/re-add）全程可回滚，自动执行；apply（源→home）为唯一危险操作，必须人工确认。

## Problem & Intent

"刚才同步 session 暴露了一个盲点：skill 只查了 `chezmoi git -- status`（源目录 git 状态），没查 `chezmoi status`（源 vs home 的差异），导致明明 home 目录有改动，却走了快速路径说「全部同步」。而且 re-add 后的文件重命名（`private_` 前缀）需要手动确认，流程可以更顺滑。"

## Goals

- 修复核心盲点：Step 1 加入 `chezmoi status` / `chezmoi diff` 检测，不再漏同步
- 智能 re-add：用时间戳判断变更方向（home 新 → re-add，源新 → 询问用户）
- 按阶段快走：远程状态、chezmoi 状态、git 状态各自独立判断，减少不必要的提示
- 输出可读性：结构化中文提示 + emoji 标记，让 agent 和用户都能快速理解状态
- 安全性三层模型：git 内操作自动执行，apply（源→home）为唯一红线，必须人工确认
- 安全优先：源比 home 新时必须询问用户，禁止自动 apply

## Non-Goals

- 完全自动化无需用户确认（保留关键决策点的交互）
- 冲突处理增强（现有启发式规则保持不变）
- 定时/监控式同步（用户主动触发）
- 管理 chezmoi 以外的 git 仓库
- 提供 GUI/TUI 交互界面

## Functional Requirements

1. **双层级状态检测** — 技能启动时同时检查：
   - git 状态：`chezmoi git -- status --porcelain`（源目录 git 变更）
   - chezmoi 状态：`chezmoi status` / `chezmoi diff`（源 vs home 差异）
   两者任一有变更，即不走该阶段的快速路径

2. **智能 re-add 方向判断** — 当 `chezmoi status` 显示有差异时：
   - 比较 home 文件 mtime 与源仓库中该文件的最近提交时间
   - home 更新 → 自动执行 `chezmoi re-add <path>` 收录到源
   - 源更新 → 展示差异并询问用户：apply（源覆盖 home）还是 re-add（home 覆盖源）
   - 时间戳不可比时（如新增文件），默认走 re-add（安全方向）

3. **阶段式工作流** — 按顺序执行：
   - 阶段 A：拉取远程（git fetch + pull）
   - 阶段 B：检测 chezmoi 状态 + 智能 re-add
   - 阶段 C：提交推送本地 git 变更
   - 各阶段独立快速路径判断

4. **先拉再推** — 先拉远程，再处理本地变更，避免覆盖远程

5. **自动提交信息** — 生成简洁提交信息，列出变更文件名；用户可自定义

6. **最终验证** — 同步完成后展示三者状态（本地 HEAD / origin/main），确认一致

## Non-Functional Requirements

- **Performance**: 纯 git/chezmoi 操作，秒级完成（网络延迟除外）
- **Security**: 参照安全性三层模型——
  - 🟢 远程 ↔ 源仓库：全 git 操作（pull/push），双向安全，自动执行
  - 🟢 home → 源仓库：`chezmoi re-add` 写入 git，`git checkout` 可还原，安全，可自动
  - 🔴 源仓库 → home：`chezmoi apply` 覆盖 home 文件，**无撤销机制**，必须人工确认
  - 不存储凭据，依赖用户已有配置
  - 永不 force push
- **UX**: 结构化中文输出 + emoji 状态标记；关键决策点清晰展示差异后再提问
- **Reliability**: 任何 git 操作失败（网络、冲突、权限）明确报错并停止；re-add 失败不阻塞后续流程
- **Dependencies**: 纯 shell 主体，容许轻量脚本（如 Python）但需在 SKILL.md 中声明

## Constraints & Assumptions

- 用户已安装 chezmoi，source state 已初始化为 git 仓库
- 已配置 git 远程 remote（`origin`）
- 所有 git 操作通过 `chezmoi git -- <cmd>` 执行
- 遵循 cnife-skills-repo 规范：SKILL.md 位于 `utility/chezmoi-sync/SKILL.md`
- 引入外部脚本时需在 Prerequisites 表中列出，并确保跨平台兼容
- `private_` 前缀重命名是 chezmoi 的标准行为，skill 需正确处理（git rm 旧文件 + git add 新文件）
- 安全性三层模型是技能的核心设计原则，所有自动化决策以此为依据

## Acceptance Criteria

- [ ] **复现漏同步场景**：home 有未记录变更（如 `~/.config/rpiv-pi/models.json` 权限变化），远程干净 → skill 不走快速路径，正确检测 chezmoi 状态并走 re-add 流程
- [ ] 远程有新提交时 → skill 先 pull，再继续处理本地
- [ ] pull 冲突 → skill 展示冲突信息按现有启发式自动解决，无法自动解决时询问用户
- [ ] 智能 re-add：home 文件更新 → 自动 re-add；源更新 → 询问用户 apply 或 re-add
- [ ] 按阶段快走：无远程变更跳过 pull，无 chezmoi 差异跳过 re-add，无 git 变更跳过 commit-push
- [ ] **安全性验证**：skill 在任何路径下都不会自动执行 apply（源→home）；方向不确定时默认走 re-add（home→源）
- [ ] 同步完成输出三者状态一致确认

## Recommended Approach

扩展现有纯 shell SKILL.md，在 Step 1 的 git 状态检测之后加入 `chezmoi status` / `chezmoi diff` 检测分支。工作流重排为三阶段：拉取远程 → 检测+re-add → 提交推送，每阶段独立快走。智能 re-add 逻辑用 bash 脚本实现时间戳比较。输出格式统一用 emoji 前缀 + 结构化分段。

将安全性三层模型作为技能的核心设计原则，显式写入 SKILL.md 的 Safety Rules：
- 🟢 **自动执行**：pull/push/re-add — 均在 git 安全边界内，全程可回滚
- 🟡 **可自动但展示**：commit（生成提交信息后展示再提交）
- 🔴 **必须人工确认**：apply（源→home），唯一覆盖 home 文件的操作，无撤销机制

## Decisions

### 增强方向

**Question**: 你想解决什么问题？改进后的 skill 对谁最有价值？
**Recommended**: (三类选项) 修复核心盲点 / 整体增强 / agent 体验优化
**Chosen**: 整体增强 — 不只是修复盲点，还加入 re-add 流程自动化和输出可读性改进
**Rationale**: 用户明确选择「整体增强」

### 增强子项

**Question**: 整体增强的话，你最关心的改进方向有哪些？
**Recommended**: (四选多) 检测 chezmoi 层级变更 / re-add 流程自动化 / 冲突处理升级 / 输出可读性
**Chosen**: 检测 chezmoi 层级变更 + re-add 流程自动化 + 输出可读性
**Rationale**: 用户多选确认，冲突处理明确排除在外

### 脚本策略

**Question**: 现有约定「纯 shell，不引入外部依赖」，是否保持？
**Recommended**: 全部保持
**Chosen**: 容许引入轻量脚本（如果显著改善体验）
**Rationale**: 用户确认可以引入，但保持最小化

### re-add 方向判断

**Question**: 检测到 home 目录有 chezmoi 未记录的变更后，re-add 流程怎么做？
**Recommended**: 智能 re-add，按时间戳判断方向
**Chosen**: 比较 home 文件 mtime 与源仓库该文件的最近提交时间，home 更新则 re-add，源更新则询问用户
**Rationale**: 用户提出的方案，解决了「哪边是权威变更」的核心问题

### 安全性三层模型

**Question**: home ←→ 源仓库 ←→ 远程仓库三者同步，哪些操作可以自动执行，哪些必须确认？
**Recommended**: （无推荐——由用户从安全分析推导）
**Chosen**: 三层安全性模型——
  - 🟢 远程 ↔ 源仓库：git pull/push，双向安全，全量历史可回滚，自动执行
  - 🟢 home → 源仓库：chezmoi re-add，写入 git 仓库，git checkout 可还原，自动执行
  - 🔴 源仓库 → home：chezmoi apply，覆盖 home 文件，无撤销机制，**必须人工确认**
**Rationale**: 用户从实践中总结——「远程仓库与源仓库之间的同步比较好搞，全程 git 仓库可回滚；从 home 到源仓库也是 git 操作比较安全；但从源仓库到 home 就是不安全的操作」。《——该观察直接成为技能的核心安全设计原则

### 源更新时的行为

**Question**: 当 chezmoi 检测到「源比 home 新」时，怎么处理？
**Recommended**: 每次询问
**Chosen**: 必须询问，禁止自动 apply
**Rationale**: 用户强调「apply 覆盖 home 不可逆，re-add 错了有 git 兜底」— 安全优先。这与安全性三层模型一致：apply 跨过了 git 安全边界

### 工作流形状

**Question**: 工作流应该怎么调整？
**Recommended**: 先拉再处理本地
**Chosen**: 先拉取远程变更，再检测 chezmoi 状态 + re-add，最后提交推送
**Rationale**: 用户确认，匹配原有「先拉再推」决策

### 快速路径

**Question**: 快速路径的策略？
**Recommended**: 按阶段快走
**Chosen**: 每阶段独立判断——无远程变更跳过 pull，无 chezmoi 差异跳过 re-add，无 git 变更跳过 commit-push
**Rationale**: 用户确认，比「三者都干净才快走」更灵活

### 输出形式

**Question**: 输出可读性做到什么程度？
**Recommended**: 改进纯 bash 输出
**Chosen**: 结构化中文提示 + emoji 标记，保持纯 bash
**Rationale**: 用户确认，无需引入 Python 脚本

### 验收标准

**Question**: 怎么判断改好了？
**Recommended**: 复现漏同步场景
**Chosen**: 复现漏同步场景 — home 有未记录变更 + 远程干净 → skill 正确检测并走 re-add 流程
**Rationale**: 用户选择，这是最有说服力的验收场景

## Open Questions

（无 — 所有决策点均已在访谈中明确）

## Suggested Follow-ups

（无）

## References

- `utility/chezmoi-sync/SKILL.md` — 当前技能实现
- `.rpiv/artifacts/discover/2026-06-05_09-43-37_chezmoi-sync-skill.md` — 原始 FRD（设计决策基线）
