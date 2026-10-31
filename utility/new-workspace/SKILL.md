---
name: new-workspace
description: 新建本地工作区：问明目标与位置，搭好 Git、README/AGENTS 与工程技能配置。
disable-model-invocation: true
---

# New Workspace

把一个新任务落到独立本地仓库。技能只定决策、顺序和完成标准。

## 访谈

一次问清，调用里已有的不重复问：

| 问题 | 规则 |
|---|---|
| 目标 + 目录名 | 一句话目标；没给目录名就按目标生成 kebab-case |
| 位置 | 无默认值；没给就问，接受 `~/...`，展开成绝对路径 |
| LICENSE | 问要不要和类型；只有明确类型才写 |

## 流程

1. 建目录、初始化 `main`；目标必须不存在或为空。
2. 写 `README.md`（标题 + 一句话用途）、`AGENTS.md`（标题 + 用途 + `## 工作区`，放本工作区特有约定）、`.gitignore`（OS/编辑器 + `.env`，语言定了再加）；选了 LICENSE 就写。
3. 初始提交：`初始化工作区`。
4. 读 `skill://setup-matt-pocock-skills`，按它的流程配置；本地仓库的 issue tracker 选 local markdown。
5. 提交 setup 产物。

## 验收

- 三个文件非空；选了 LICENSE 时 `LICENSE` 非空。
- `AGENTS.md` 有 `## Agent skills`。
- `docs/agents/issue-tracker.md` 和 `domain.md` 存在且非空。
- 工作区干净，当前分支 `main`，有初始提交和 setup 提交。

## 边界

- 不建远端、不加钩子、不预置语言脚手架。
- 目标非空或已有 `.git`：停下，重新问位置。
- setup 技能读不到：停在已初始化状态，告诉用户先安装。
