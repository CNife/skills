# CNife's Agent Skills

个人收集的 AI Agent Skills，用于 OpenCode、Claude Code 等 AI 编程助手。

## 安装

```bash
# 安装所有 skills
bunx skills add CNife/skills

# 或单独安装某个 skill
bunx skills add CNife/skills@python
```

## 可用 Skills

| Skill | 描述 |
|-------|------|
| [audit-hermes-agent-skills](./skills/audit-hermes-agent-skills) | 审计 Hermes Agent 技能使用频率，基于指数衰减算法计算热度，安全清理未使用技能 |
| [cnife-skills-repo](./skills/cnife-skills-repo) | 本仓库结构说明、Python 项目规范、PEP 723 单脚本模式和 pre-commit 钩子配置 |
| [git-master](./skills/git-master) | Git 操作专家：原子提交、rebase/squash、历史搜索（blame/bisect/log -S） |
| [obsidian-diary](./skills/obsidian-diary) | 将会话内容总结到 Obsidian 工作日志/日记中，管理待办事项 |
| [optimize-agents-md](./skills/optimize-agents-md) | AGENTS.md 编写与优化指南，遵循渐进式披露原则 |
| [qwen-code-permission](./skills/qwen-code-permission) | 自动化管理 Qwen Code 权限规则（allow/ask/deny），一键添加命令到允许列表 |
| [skill-evaluator](./skills/skill-evaluator) | 评估、比较、推荐、发现和安装 AI Agent 技能 |
| [worklog](./skills/worklog) | 从 OpenCode 和 Qwen Code 提取会话数据，生成结构化工作总结 |

## 开发

```bash
# 克隆仓库
git clone https://github.com/CNife/skills.git
cd skills

# 安装依赖（如果有）
bun install
```

## License

MIT