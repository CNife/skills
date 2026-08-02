# CNife's Agent Skills

个人收集和开发的 AI Agent Skills，按类别组织。

## 目录结构

```text
knowledge/           个人知识系统
├── nmem-maintenance/  Nowledge Mem 知识库巡检与事件处理
└── daily-recap/       今日会话聚合成日报，写入 Obsidian 工作日志/日记

utility/             通用工具（与代理无关）
├── models-dev-query/    AI 模型规格查询
└── plain-speak/         对话中冒出自造黑话时去掉、用平实的话重新解释

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

> pi-agent 分类的 6 个技能已于 2026-08-02 迁入 [CNife/pi-extensions](https://github.com/CNife/pi-extensions) 的 `personal/skills/`，随 pi git 包分发；本仓库不再维护。

### knowledge/

| Skill | 描述 |
|-------|------|
| [nmem-maintenance](./knowledge/nmem-maintenance) | Nowledge Mem 知识库巡检--检查服务状态、审查待处理事件、分类处理陈旧结晶/重复记忆/矛盾 |
| [daily-recap](./knowledge/daily-recap) | 整理所有机器上的 Pi/OMP 会话，按主题聚合成结构化日报，写入 Obsidian 工作日志或个人日记 |

### utility/

| Skill | 描述 |
|-------|------|
| [models-dev-query](./utility/models-dev-query) | 查询 models.dev 数据库 - 模型规格、定价、上下文限制、提供商 API 端点 |
| [plain-speak](./utility/plain-speak) | 对话中 AI 冒出自造黑话、用户跟不上时调用--把自造词去掉，用平实的话重新解释一遍 |

## 开发

```bash
git clone https://github.com/CNife/skills.git && cd skills
uv run pre-commit install   # 安装 git hooks
uv run pre-commit run --all-files   # 运行全部检查
```

## License

MIT
