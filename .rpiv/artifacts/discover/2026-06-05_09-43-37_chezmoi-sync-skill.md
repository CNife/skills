---
date: 2026-06-05T09:43:37+0800
author: 蔡涛
commit: b81bd8daa
branch: master
repository: chezmoi
topic: "Chezmoi Sync Skill"
tags: [intent, frd, chezmoi, skill, git]
status: complete
last_updated: 2026-06-05T09:43:37+0800
last_updated_by: 蔡涛
---

# FRD: Chezmoi Sync Skill

## Summary

一个 AI agent skill，自动化 chezmoi dotfiles 的同步流程：拉取远程变更 → 检查本地变更 → 展示差异并询问用户 → 提交推送 → 展示最终状态一致性。用户只需一次命令即可完成原本需要多步手动操作的 git 同步流程。

## Problem & Intent

"手动流程繁琐"——每次修改 dotfiles 后需要手动 git add/commit/push，换机器后手动 pull，流程固定但重复。想做一个可发布的通用技能，让所有使用 chezmoi 的用户都能一键完成同步，避免手动操作的同时保留关键决策点的确认能力。

## Goals

- 一次命令完成 chezmoi 同步全流程（pull → commit → push）
- 拉取远程在前，避免覆盖远程变更
- 只在关键步骤询问用户确认（有冲突时、有本地变更要推送时）
- 自动生成简洁的提交信息（变更文件列表）
- 同步完成后展示最终状态（本地=仓库=远程）
- 发布为通用 skill，按 cnife-skills-repo 规范管理

## Non-Goals

- 完全自动执行不经过用户确认
- 自动解决 git 冲突（遇到冲突立即停止并提示）
- 定时/监控式同步（用户主动触发）
- 管理 chezmoi 以外的 git 仓库
- 提供 GUI/TUI 交互界面

## Functional Requirements

1. **状态检查** — 技能启动时，检查 chezmoi source state（`~/.local/share/chezmoi/`）的本地未提交变更和远程是否有新提交
2. **拉取远程** — 先执行 `git pull`（通过 `chezmoi git pull`），获取远程最新变更；如果产生冲突，立即停止并展示冲突信息，等待用户手动解决
3. **本地变更展示** — 如果本地有未提交变更，以结构化方式展示（文件列表 + diff 摘要），并询问用户是否提交推送
4. **提交推送** — 用户确认后，执行 git add → commit（自动生成提交信息）→ push
5. **最终状态验证** — 同步完成后展示 git log 摘要，确认本地=chezmoi仓库=远程仓库一致

## Non-Functional Requirements

- **Performance**: 只执行 git 操作，应在秒级完成（网络延迟除外）
- **Security**: 不存储凭据，依赖用户已有的 git 远程配置（SSH/https）
- **UX**: 输出清晰的中文提示，用结构化方式展示变更和最终状态
- **Reliability**: 任何 git 操作失败（网络、冲突、权限）都应明确报错并停止，不静默跳过
- **Dependencies**: 纯 shell 指令，不引入 Python 或外部依赖

## Constraints & Assumptions

- 用户已安装 chezmoi
- chezmoi source state 已初始化为 git 仓库
- 已配置 git 远程 remote（`origin`）
- 遵循 cnife-skills-repo 规范：SKILL.md 位于 `~/personal_code/skills/chezmoi-sync/SKILL.md`
- 使用 chezmoi 内置命令（`chezmoi git <args>`）而非硬编码路径
- 提交信息采用简洁格式，列出变更的文件名

## Acceptance Criteria

- [ ] `bunx skills add CNife/skills@chezmoi-sync -g -y` 安装成功
- [ ] 在 chezmoi source state 有未提交变更时，技能展示差异并询问用户
- [ ] 用户确认后，变更被正确 commit 并 push 到远程
- [ ] 远程有新变更时，技能先 pull 再继续
- [ ] pull 产生冲突时，技能停止并展示冲突信息
- [ ] 同步完成后，输出状态确认三者一致

## Recommended Approach

纯 shell 指令型 SKILL.md（无 Python 辅助脚本），通过 `chezmoi git` 命令操作 chezmoi 源码仓库。SKILL.md 按流程分步骤组织，每步包含具体命令和用户交互说明。提交信息用 `git diff --name-only` 生成简洁的文件列表。放在 `~/personal_code/skills/chezmoi-sync/` 下，按 cnife-skills-repo 规范发布。

## Decisions

### 核心痛点

**Question**: 你为什么要做这个 chezmoi 同步技能？遇到了什么具体痛点？
**Recommended**: 手动流程繁琐
**Chosen**: 手动流程繁琐 — 每次修改后要手动 git 操作，固定但重复
**Rationale**: 用户确认，这是最核心的驱动因素

### 使用场景

**Question**: 技能的用户是谁？
**Recommended**: 可分享的通用作品
**Chosen**: 可分享的通用作品 — 通过 cnife-skills-repo 发布，别人也能安装使用
**Rationale**: 用户确认，需遵循通用技能规范

### 目标范围

**Question**: 技能覆盖哪些操作？
**Recommended**: 完整同步流程（检查 → pull → commit → push → 确认状态）
**Chosen**: 完整同步流程，只在关键步骤需要用户确认（远程有变更覆盖本地时、本地有变更要同步到远程时）
**Rationale**: 用户定制的方案，介于「半自动」和「全自动」之间

### 工作起点

**Question**: 同步从哪个目录开始？
**Recommended**: 当前 chezmoi 目录自动检测
**Chosen**: 使用 `chezmoi git` 命令操作，不硬编码路径
**Rationale**: 用户提出使用 chezmoi 内置命令（`evidence: chezmoi git` 文档 + 用户确认）

### 技能结构

**Question**: SKILL.md 用什么方式组织？
**Recommended**: 纯 shell 指令
**Chosen**: 纯 shell 指令，不搭配 Python 辅助脚本
**Rationale**: 简单直接，零依赖，易于维护和被 AI agent 执行

### 提交方式

**Question**: 提交信息如何生成？
**Recommended**: 自动生成提交信息
**Chosen**: 自动生成简洁式提交信息（列出变更文件），用户确认后提交
**Rationale**: 用户确认，简洁格式优于详细格式

### 异常处理

**Question**: 冲突或异常如何处理？
**Recommended**: 遇到冲突立即停止并提示
**Chosen**: 遇到冲突立即停止并提示，让用户手动解决后重试
**Rationale**: 用户确认，自动解决冲突风险过高

### 工作流顺序

**Question**: pull 和 push 的顺序？
**Recommended**: 先拉取、再推送
**Chosen**: 先 git pull 拉取远程变更，再处理本地变更的提交推送
**Rationale**: 用户确认，先拉避免覆盖远程

### 结果展示

**Question**: 同步完成后如何展示？
**Recommended**: 展示最终状态对比
**Chosen**: 展示最终状态对比（git log 摘要），确认三者一致
**Rationale**: 让用户对同步结果有清晰的确认感

### 前提条件

**Question**: 技能需要说明哪些前提？
**Recommended**: 列出最小前提
**Chosen**: 列出最小前提（已安装 chezmoi、source state 已初始化为 git 仓库、已配置远程 remote）
**Rationale**: 确保通用性的同时避免用户踩坑

## Open Questions

（无 — 所有决策点均已明确）

## Suggested Follow-ups

（无 — 未发现超出范围的建议项）

## References

- [cnife-skills-repo 规范](../../../../.pi/agent/skills/cnife-skills-repo/SKILL.md) — 技能创建/发布规范
- [chezmoi git 命令源码](../../../../github_code/chezmoi/internal/cmd/gitcmd.go) — `chezmoi git <args>` 实现
- [chezmoi update 命令源码](../../../../github_code/chezmoi/internal/cmd/updatecmd.go) — 内置 git pull 逻辑
- [skills 仓库结构](../../../../personal_code/skills/README.md) — 现有技能参考
