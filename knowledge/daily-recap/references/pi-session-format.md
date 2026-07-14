# Pi Agent 会话 JSONL 格式

当需要手工解析 Pi Agent 的 JSONL 会话文件时参考。`scripts/extract_today.py` 已自动处理此格式，仅在调试或核对时查阅。

## 文件位置

`~/.pi/agent/sessions/<项目路径>/<UTC时间戳>_<UUID>.jsonl`

通过 `/fork`、`/clone` 创建的会话，首行 `session` 还带 `parentSession` 字段指向源会话文件路径（跨文件的父子关系，脚本不还原）。

## 树形结构

会话条目通过 `id` / `parentId` 形成**树**（Version 2+）：首条 `parentId: null`，其后每条指向父条目，`/tree` 可原地分支而不产生新文件。当前叶子（leaf）是树中的活动位置。权威定义见 `~/github_code/pi/packages/coding-agent/docs/session-format.md`。

`extract_today.py` **线性读取**整个文件，不还原树：

- `msg_count` 统计所有分支的 message（含被放弃的分支）
- `last_assistant_summary` 取物理最后一行 assistant

这对 `--min-msgs` 过滤可接受--stub 会话不会分支，不会因虚高漏网；append-only 分支也使物理最后一行接近当前 leaf。是有意设计，非 bug。

## 关键行类型

| 行类型 | 识别 | 提取字段 |
|--------|------|----------|
| `session` | `"type":"session"` | `id`(UUID)、`timestamp`(UTC)、`cwd`(工作目录)、可选 `parentSession` |
| `session_info` | `"type":"session_info"` | `name`（会话标题） |
| `message` | `"type":"message"` | `message.role`(user/assistant/toolResult)、`message.content[]`（数组，元素 `{type:"text", text:"..."}`） |
| `branch_summary` | `"type":"branch_summary"` | `summary`、`fromId`--`/tree` 切走分支时的摘要，不计入 msg_count |
| `compaction` | `"type":"compaction"` | `summary`、`firstKeptEntryId`--上下文压缩摘要，不计入 msg_count |

其余类型（`model_change`、`thinking_level_change`、`label`、`custom`、`custom_message` 等）不匹配提取分支，自然跳过。

## 提取规则

- `message.content` 是**数组**，用户/助手消息文本在 `message.content[].text` 中，需遍历拼接
- 工具执行结果(`toolResult`) 的 `content[]` 同样为数组结构
- 消息量计数：`type == "message"` 的行数（跨所有分支）
- 标题来源：`session_info` 行的 `name` 字段
- 产出摘要：物理最后一个 `role == "assistant"` 的 message 行提取关键结论/产出
