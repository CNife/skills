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

methodology/         方法论（驱动代理做计划/审查的流程）
└── grill-for-unknowns/  有据盘问：先取证再盘问，一次一个实质性问题，发现未知数并形成共享理解

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
| [aihot-leaderboard](./utility/aihot-leaderboard) | 查询 AIHOT 大模型排行榜 - 总榜前 30、单模型各榜明细、12 张来源榜单全量排名与分数 |
| [plain-speak](./utility/plain-speak) | 对话中 AI 冒出自造黑话、用户跟不上时调用--把自造词去掉，用平实的话重新解释一遍 |

### methodology/

| Skill | 描述 |
|-------|------|
| [grill-for-unknowns](./methodology/grill-for-unknowns) | 有据盘问：先查文档/源码/测试取证，再一次一个实质性问题地盘问计划、规格或 PR，直到发现会改变实现的未知数并形成共享理解 |

## 开发

```bash
git clone https://github.com/CNife/skills.git && cd skills
uv run pre-commit install   # 安装 git hooks
uv run pre-commit run --all-files   # 运行全部检查
```

## License

MIT
