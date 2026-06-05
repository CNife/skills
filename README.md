# CNife's Agent Skills

个人收集和开发的 AI Agent Skills，按类别组织。

## 目录结构

```text
pi-agent/            Pi Agent 生态专用技能
├── pi-skill-audit/  Pi 技能使用频率审计与清理
├── pi-trending/     Pi 生态热门包发现
└── prompt-craft/    提示词工程 — 创建和改进 pi prompt template

hermes-agent/        Hermes Agent 专用技能
└── worklog/         活动轨迹收集 → PDF → 邮件投递

knowledge/           知识管理
└── obsidian-diary/  会话总结 → Obsidian 工作日志/日记

utility/             通用工具（与代理无关）
├── chezmoi-sync/        一键同步 chezmoi dotfiles
├── cnife-skills-repo/   本仓库元技能和质量门禁
├── models-dev-query/    AI 模型规格查询
└── search-router/       智能搜索路由器

.archive/            不再维护的历史技能（仅作参考）
├── arch-wsl-cleanup/
├── arch-wsl-cleanup/
├── ast-grep/
├── audit-hermes-agent-skills/
├── git-master/
├── opencode-permission/
├── optimize-agents-md/
├── qwen-code-permission/
├── reminder-review-session/
└── skill-evaluator/
```

## 安装

```bash
# 从 GitHub 仓库安装
bunx skills add CNife/skills --full-depth

# 或安装单个技能（指定子目录路径）
bunx skills add CNife/skills@pi-agent/pi-skill-audit --full-depth
```

## 可用 Skills

### pi-agent/

| Skill | 描述 |
|-------|------|
| [pi-skill-audit](./pi-agent/pi-skill-audit) | Pi 技能使用频率审计 — 统计调用次数，四档分类，可视化报告，一键清理 |
| [pi-trending](./pi-agent/pi-trending) | Pi 生态热门包发现 — 从 npm registry 计算趋势分 |
| [prompt-craft](./pi-agent/prompt-craft) | 基于 OpenAI 提示词工程最佳实践，创建和改进 pi prompt template |

### hermes-agent/

| Skill | 描述 |
|-------|------|
| [worklog](./hermes-agent/worklog) | 多数据源收集活动轨迹 → 分析工作与个人 → Kami 排版 PDF → 邮件投递 |

### knowledge/

| Skill | 描述 |
|-------|------|
| [obsidian-diary](./knowledge/obsidian-diary) | 将会话内容总结到 Obsidian 工作日志/日记中，管理待办事项 |

### utility/

| Skill | 描述 |
|-------|------|
| [chezmoi-sync](./utility/chezmoi-sync) | 一键同步 chezmoi dotfiles — 拉取远程 → 智能冲突处理 → 提交推送 |
| [cnife-skills-repo](./utility/cnife-skills-repo) | 本仓库结构说明、Python 项目规范、PEP 723 单脚本模式和 pre-commit 钩子配置 |
| [models-dev-query](./utility/models-dev-query) | 查询 models.dev 数据库 — 模型规格、定价、上下文限制、提供商 API 端点 |
| [search-router](./utility/search-router) | 基于 opencli 的智能搜索路由器，根据话题路由到最佳搜索源 |

### .archive/

仅作参考，不再维护。完整列表见目录结构。

## 开发

```bash
git clone https://github.com/CNife/skills.git && cd skills
uv run pre-commit install   # 安装 git hooks
uv run pre-commit run --all-files   # 运行全部检查
```

## License

MIT
