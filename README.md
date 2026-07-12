# CNife's Agent Skills

个人收集和开发的 AI Agent Skills，按类别组织。

## 目录结构

```text
pi-agent/            Pi Agent 生态专用技能
└── pi-trending/     Pi 生态热门包发现

knowledge/           知识管理
├── nmem-maintenance/  Nowledge Mem 知识库巡检与事件处理
└── obsidian-diary/  会话总结 → Obsidian 工作日志/日记

utility/             通用工具（与代理无关）
├── models-dev-query/    AI 模型规格查询
└── search-router/       智能搜索路由器

.archive/            不再维护的历史技能（仅作参考）
├── arch-wsl-cleanup/
├── ast-grep/
├── audit-hermes-agent-skills/
├── chezmoi-sync/
├── cnife-skills-repo/
├── git-master/
├── opencode-permission/
├── optimize-agents-md/
├── pi-skill-audit/
├── prompt-craft/
├── qwen-code-permission/
├── reminder-review-session/
├── skill-evaluator/
└── worklog/
```

## 安装

```bash
# 从 GitHub 仓库安装
bunx skills add CNife/skills --full-depth
```

## 可用 Skills

### pi-agent/

| Skill | 描述 |
|-------|------|
| [pi-trending](./pi-agent/pi-trending) | Pi 生态热门包发现 — 从 npm registry 计算趋势分 |

### knowledge/

| Skill | 描述 |
|-------|------|
| [nmem-maintenance](./knowledge/nmem-maintenance) | Nowledge Mem 知识库巡检——检查服务状态、审查待处理事件、分类处理陈旧结晶/重复记忆/矛盾 |
| [obsidian-diary](./knowledge/obsidian-diary) | 将会话内容总结到 Obsidian 工作日志/日记中，管理待办事项 |

### productivity/

| Skill | 描述 |
|-------|------|
| [daily-recap](./productivity/daily-recap) | 整理今日工作内容 — 搜索 Nowledge Mem 线程、检查会话文件、查 git 提交，按主题聚合生成结构化日报，可选写入 Obsidian |

### utility/

| Skill | 描述 |
|-------|------|
| [models-dev-query](./utility/models-dev-query) | 查询 models.dev 数据库 - 模型规格、定价、上下文限制、提供商 API 端点 |
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
