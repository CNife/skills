# CNife's Agent Skills

个人收集和开发的 AI Agent Skills，按类别组织。

## 目录结构

```text
knowledge/           个人知识系统
└── daily-recap/       今日会话聚合成日报，写入 Obsidian 工作日志/日记

utility/               通用工具（与代理无关）
├── local-github/        ~/github 参考库：克隆、同步与本地路径查询
├── models-dev-query/    AI 模型规格查询
├── new-workspace/       新建本地工作区：问明目标与位置，搭好 Git、README/AGENTS、工程技能配置并验收
├── plain-speak/         重讲一遍：把整件事重新讲清楚，并把自造黑话换成项目术语、行业标准术语或日常词汇
├── treehouse/           Git worktree 池管理
├── tern-guide/          Tern 终端：pane/block 编排、配置与文档导航
└── yadm/                个人 dotfiles 管理

methodology/         方法论（组合并强化 agent 工作方式的技能）
├── grill-for-unknowns/  用拷问的方式对齐未知
└── skill-design/        写或改技能：判 agent 缺什么，定每类技能的正文重点

.archive/            不再维护的历史技能
```

## 安装

使用 skill-manager 声明式管理：

```bash
skill-manager --global source add CNife/skills       # 添加本仓库为源
skill-manager --global enable CNife/skills <skill>   # 启用所需技能
skill-manager --global sync                          # 同步到 ~/.agents/skills/
```

## 可用 Skills

### knowledge/

| Skill | 描述 |
|-------|------|
| [daily-recap](./knowledge/daily-recap) | 整理所有机器上的 Pi/OMP 会话，按主题聚合成结构化日报，写入 Obsidian 工作日志或个人日记 |

### utility/

| Skill | 描述 |
|-------|------|
| [local-github](./utility/local-github) | 查 GitHub 代码时先克隆到 ~/github 参考库再本地读，不用 curl 抓远端文件；并管理该参考库（clone / sync / ensure / path / list / rename） |
| [models-dev-query](./utility/models-dev-query) | 查询 models.dev 数据库 - 模型规格、定价、上下文限制、提供商 API 端点 |
| [new-workspace](./utility/new-workspace) | 新建本地工作区：问明目标与位置，搭好 Git、README/AGENTS、工程技能配置并验收 |
| [plain-speak](./utility/plain-speak) | 对话中 Agent 冒出自造黑话、或用户表示没看懂时调用——把整件事重新讲清楚，并把自造黑话换成项目术语、行业标准术语或日常词汇 |
| [treehouse](./utility/treehouse) | 教 Agent 使用 Treehouse CLI 获取、租用和归还 worktree |
| [tern-guide](./utility/tern-guide) | 教 Agent 操作 Tern 终端：pane/block/host 编排、把命令开在可见窗格、配置与按需查文档 |
| [yadm](./utility/yadm) | 按个人约定管理 yadm dotfiles、alternates、transcrypt 与 bootstrap，并直接提交推送 main |

### methodology/

| Skill | 描述 |
|-------|------|
| [grill-for-unknowns](./methodology/grill-for-unknowns) | 用户主动调用的 `grill-with-docs` 强化版：核对领土，用四类未知事项探索战争迷雾，并按需调用 `prototype` 或 `research` |
| [skill-design](./methodology/skill-design) | 写或改技能：按 agent 缺什么判类型，按每类重点定正文该写什么；写作规范交给 writing-for-agents |

## 开发

```bash
git clone https://github.com/CNife/skills.git && cd skills
uv tool install pre-commit       # 全局工具，不依赖项目环境
pre-commit install               # 安装 git hooks
pre-commit run --all-files       # 跑一遍全部检查
```

检查项见 `.pre-commit-config.yaml`，ruff 规则与取舍理由见 `.ruff.toml`；`.archive/` 是冻结的历史技能，不参与检查。

## License

MIT
