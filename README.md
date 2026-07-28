# CNife's Agent Skills

个人收集和开发的 AI Agent Skills，按类别组织。

## 目录结构

```text
pi-agent/            Pi Agent 生态专用技能
├── pi-trending/                Pi 生态热门包发现
├── search-pi-extensions/       按需求检索 pi 扩展/包
├── add-provider-models-to-pi/  从 provider 拉模型适配进 pi
├── pi-session-query/           Pi 会话树形查询原语库
└── fabric-best-practices/      fabric_exec 判断力/避坑手册

knowledge/           个人知识系统
├── nmem-maintenance/  Nowledge Mem 知识库巡检与事件处理
└── daily-recap/       今日会话聚合成日报，写入 Obsidian 工作日志/日记

utility/             通用工具（与代理无关）
└── models-dev-query/    AI 模型规格查询

.archive/            不再维护的历史技能
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
| [pi-trending](./pi-agent/pi-trending) | Pi 生态热门包发现 - 从 npm registry 计算趋势分 |
| [search-pi-extensions](./pi-agent/search-pi-extensions) | 按需求检索 pi 扩展/包 - npm 关键词检索 + GitHub 信号质量评估 |
| [add-provider-models-to-pi](./pi-agent/add-provider-models-to-pi) | 从源 provider（models.dev/官方文档）拉取参数并适配进 pi 的 models.json |
| [pi-session-query](./pi-agent/pi-session-query) | Pi 会话树形查询原语库 - 还原主路径/分支/压缩/工具配对，供 AI 写查询脚本做复杂分析 |
| [fabric-best-practices](./pi-agent/fabric-best-practices) | fabric_exec 判断力/避坑手册 - 何时用哪个机制 + 常见陷阱 + 纠错口诀；fabric-exec 与 fabric-guide 之间的判断力层 |

### knowledge/

| Skill | 描述 |
|-------|------|
| [nmem-maintenance](./knowledge/nmem-maintenance) | Nowledge Mem 知识库巡检--检查服务状态、审查待处理事件、分类处理陈旧结晶/重复记忆/矛盾 |
| [daily-recap](./knowledge/daily-recap) | 整理所有机器上的 Pi/OMP 会话，按主题聚合成结构化日报，写入 Obsidian 工作日志或个人日记 |

### utility/

| Skill | 描述 |
|-------|------|
| [models-dev-query](./utility/models-dev-query) | 查询 models.dev 数据库 - 模型规格、定价、上下文限制、提供商 API 端点 |

## 开发

```bash
git clone https://github.com/CNife/skills.git && cd skills
uv run pre-commit install   # 安装 git hooks
uv run pre-commit run --all-files   # 运行全部检查
```

## License

MIT
