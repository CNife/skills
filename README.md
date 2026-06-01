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

### 目录结构

每个技能独立一个目录，放在仓库根目录下：

```text
<skill-name>/
├── SKILL.md              # Required — 技能定义
├── scripts/              # Python 脚本（PEP 723）
└── references/           # 参考文件
```

### 依赖

- **Python 工具** — 使用 [uv](https://docs.astral.sh/uv/) 管理，无需手动安装
- **pre-commit** — 代码提交前自动检查

### 质量门禁

提交前运行所有检查：

```bash
# 安装 pre-commit 钩子（首次）
uv run pre-commit install

# 手动运行全部检查
uv run pre-commit run --all-files
```

已配置的 hooks：

- **pre-commit-hooks** — 基础格式检查（YAML/TOML/JSON 校验、尾随空格、EOF 空行等）
- **uv-pre-commit** — `uv lock` 锁定依赖
- **ruff-pre-commit** — Python 代码检查（`ruff check --fix`）+ 格式化（`ruff format`）
- **rumdl** — Markdown 格式化（lint + 自动修复），配置见 `.rumdl.toml`

### 新建技能

```bash
# 1. 创建技能目录和 SKILL.md
mkdir -p <name>/scripts

# 2. 运行检查
uv run ruff check --fix <name>/
uv run ruff format <name>/

# 3. 更新 README.md 中的技能表格
# 在可用 Skills 表格中新增一行

# 4. 提交并推送
git add -A
git commit -m "<name>: <简要描述>"
git push
```

### GitHub 发布

安装到全局：

```bash
bunx skills add CNife/skills@<name> -g -y
```

## License

MIT
