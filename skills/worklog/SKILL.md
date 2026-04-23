# Worklog: 工作总结

从 OpenCode 数据库提取今日会话数据，生成结构化工作总结并写入 Obsidian 工作日志。

## 流程

### 步骤 1：提取会话数据

```bash
uv run {skill_dir}/extract.py --since today
```

可选参数：
- `--since today|yesterday|<ISO datetime>` — 时间范围
- `--directory <path>` — 限定项目目录
- `--limit N` — 最大会话数

脚本输出结构化纯文本，包含每个会话的用户提问、工具调用和 AI 回复摘要。

### 步骤 2：生成总结并写入

加载 `/obsidian-diary` skill，按其规则提取关键事件、生成总结并写入工作日志。
