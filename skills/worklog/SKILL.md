# Worklog: 工作总结

从 OpenCode 数据库和 Qwen Code 日志中提取今日会话数据，生成结构化工作总结并写入 Obsidian 工作日志。

## 流程

### 步骤 1：提取会话数据

```bash
uv run {skill_dir}/extract.py --since today
```

可选参数：
- `--since today|yesterday|<ISO datetime>` — 时间范围
- `--directory <path>` — 限定项目目录
- `--limit N` — 最大会话数

脚本自动合并两个数据源：
1. **OpenCode**: `~/.local/share/opencode/opencode.db` (SQLite)
2. **Qwen Code**: `~/.qwen/tmp/*/logs.json`（NDJSON） + `~/.qwen/projects/*/chats/*.jsonl`（NDJSON）

输出格式统一，Qwen Code 会话标记为 `(Qwen Code)` 前缀。

### 注意事项

- Qwen Code 使用 `.jsonl` 扩展名（每行一个 JSON 对象），非 `.json`
- Qwen Code 用户消息格式：`{"role":"user","parts":[{"text":"..."}]}`，需从 `parts` 数组提取文本
- 项目路径通过 SHA256 哈希映射，`.hermes` 等含 `.` 的路径需点分解析（如 `.hermes` 编码为 `home-cnife-.hermes`）

### 步骤 2：生成总结并写入

加载 `/obsidian-diary` skill，按其规则提取关键事件、生成总结并写入工作日志。
