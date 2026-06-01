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
| [ast-grep](./ast-grep) | AST 结构搜索与代码重写 — 基于 ast-grep 的 25 语言结构化代码搜索和跨文件重构 |
| [audit-hermes-agent-skills](./audit-hermes-agent-skills) | 审计 Hermes Agent 技能使用频率，生成带中文描述和下拉决策的 XLSX，支持清理执行 |
| [models-dev-query](./models-dev-query) | 查询 models.dev 数据库 — 模型规格、定价、上下文限制、提供商 API 端点、能力标记 |
| [cnife-skills-repo](./cnife-skills-repo) | 本仓库结构说明、Python 项目规范、PEP 723 单脚本模式和 pre-commit 钩子配置 |
| [git-master](./git-master) | Git 操作专家：原子提交、rebase/squash、历史搜索（blame/bisect/log -S） |
| [obsidian-diary](./obsidian-diary) | 将会话内容总结到 Obsidian 工作日志/日记中，管理待办事项 |
| [opencode-permission](./opencode-permission) | 自动化管理 OpenCode 权限规则（allow/ask/deny），支持 JSONC 注释保留，一键添加/删除/查看命令 |
| [optimize-agents-md](./optimize-agents-md) | AGENTS.md 编写与优化指南，遵循渐进式披露原则 |
| [pi-trending](./pi-trending) | 发现 Pi Agent 生态最新热门包 — 从 npm registry 计算趋势分，按 extension/skill/theme/prompt 分类展示 |
| [prompt-craft](./prompt-craft) | 基于 OpenAI 提示词工程最佳实践，创建和改进 pi prompt template |
| [qwen-code-permission](./qwen-code-permission) | 自动化管理 Qwen Code 权限规则（allow/ask/deny），一键添加命令到允许列表 |
| [search-router](./search-router) | 基于 opencli 的智能搜索路由器，根据话题路由到最佳搜索源，带搜索理由软约束 |
| [reminder-review-session](./reminder-review-session) | 会话问题解决后提醒我将知识整理到 Obsidian（日记或独立文章） |
| [skill-evaluator](./skill-evaluator) | 评估、比较、推荐、发现和安装 AI Agent 技能 |
| [worklog](./worklog) | 多数据源收集活动轨迹 → 分析工作与个人 → Kami 排版 PDF → 邮件投递 |

## 开发

```bash
git clone https://github.com/CNife/skills.git && cd skills
uv run pre-commit install   # 安装 git hooks
uv run pre-commit run --all-files   # 运行全部检查
```

## License

MIT
