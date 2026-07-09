# Pi Agent 会话 JSONL 格式

当需要手工解析 Pi Agent 的 JSONL 会话文件时参考。`scripts/extract_today.py` 已自动处理此格式，仅在调试或核对时查阅。

## 文件位置

`~/.pi/agent/sessions/<项目路径>/<UTC时间戳>_<UUID>.jsonl`

## 关键行类型

| 行类型 | 识别 | 提取字段 |
|--------|------|----------|
| `session` | `"type":"session"` | `id`(UUID)、`timestamp`(UTC)、`cwd`(工作目录) |
| `session_info` | `"type":"session_info"` | `name`（会话标题） |
| `message` | `"type":"message"` | `message.role`(user/assistant/toolResult)、`message.content[]`（数组，元素 `{type:"text", text:"..."}`） |

## 提取规则

- `message.content` 是**数组**，用户/助手消息文本在 `message.content[].text` 中，需遍历拼接
- 工具执行结果(`toolResult`) 的 `content[]` 同样为数组结构
- 消息量计数：`type == "message"` 的行数
- 标题来源：`session_info` 行的 `name` 字段
- 产出摘要：最后一个 `role == "assistant"` 的 message 行提取关键结论/产出
