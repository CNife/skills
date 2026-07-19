# OMP 会话 JSONL 格式

当需要手工解析 OMP 的 JSONL 会话文件时参考。`scripts/extract_today.py` 已自动处理此格式，仅在调试或核对时查阅。

## 文件位置与目录树

OMP 一个会话由两部分组成：

- **主文件**：`~/.omp/agent/sessions/<项目路径>/<UTC时间戳>_<UUID>.jsonl`
- **同名目录**：`~/.omp/agent/sessions/<项目路径>/<UTC时间戳>_<UUID>/`，内含子代理会话文件（`__advisor.jsonl`、`Verify*.jsonl` 等）

`extract_today.py` 用**文件名 UTC 日期前缀**粗筛（工作日窗口 ±1 天的多前缀），只处理主文件。目录内的子会话文件名不以日期开头，被**有意排除**--它们是 advisor 咨询、verify 校验等辅助任务，不改变"这个会话做了什么"的结论，纳入只会让候选表膨胀。

## 文件内树形结构

主文件内部与 Pi 一致（`id`/`parentId` 树、脚本线性读取、`msg_count` 跨分支计数、`last_assistant_summary` 取物理末行、对 `--min-msgs` 可接受）。详见 `pi-session-format.md` 的“树形结构”段。

## 关键行类型

| 行类型 | 识别 | 提取字段 |
|--------|------|----------|
| `session` | `"type":"session"` | `id`(UUID)、`timestamp`(UTC)、`cwd`(工作目录) |
| `title` | `"type":"title"` | `title`（会话标题，文件第一行） |
| `message` | `"type":"message"` | `message.role`(user/assistant/toolResult)、`message.content[]`（数组，需过滤非文本块） |

## 与 Pi 的关键差异

- **目录树**：OMP 会话是"主文件 + 子会话目录"，Pi 是单个扁平文件
- **标题来源**：OMP 的标题在文件第一行的 `{"type":"title","title":"主题名"}` 中，而非 `session_info` 行
- **额外条目类型**：可能包含 `model_change`、`thinking_level_change`、`compaction`、`branch_summary`、`custom_message`、`session_init`、`mode_change`、`custom` 等类型--**计数和提取时跳过这些行**，只处理 `type:"message"`
- **`message.content[]` 过滤**：OMP 消息的 content 数组中包含 `{type:"thinking"}`、`{type:"toolCall"}`、`{type:"toolResult"}` 等非文本类型，提取文本时**只取 `type:"text"` 元素**的 `text` 字段

## 提取字段

与 Pi 一致：标题、消息量、首条用户消息、产出摘要、工作目录
