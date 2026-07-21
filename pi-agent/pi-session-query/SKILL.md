---
name: pi-session-query
description: 把一个 Pi Agent 会话记录（JSONL）交给分析会话时，提供会话查询原语库 + 运行器，正确还原树形结构与完整内容块，供 AI 写查询脚本组合完成轨迹分析、工具调用排查等复杂分析。与 daily-recap 互补（后者线性提取摘要，本技能完整树形解析）。
disable-model-invocation: true
---

# Pi Session Query - 会话查询原语库

把一个 Pi Agent 会话记录文件（JSONL）解析成 `Session` 对象，暴露五组查询原语，供分析会话（AI）写查询脚本组合完成任意复杂分析：还原主路径对话流、查看思考内容、配对工具调用与结果、对比分支差异、定位压缩点、统计 token 消耗等。

## 定位

与 [daily-recap](../../knowledge/daily-recap) 互补：

| | daily-recap | pi-session-query |
|---|---|---|
| 视角 | 线性提取摘要 | 完整树形解析 |
| 范围 | 批量、跨文件、跨机器 | 单文件、全 block 还原 |
| 产出 | 摘要（标题/时间/首末消息） | 原语组合的任意查询 |
| 树还原 | 有意不还原（只要摘要） | 正确还原主路径 + 分支 |

分析方临时手写解析逻辑的典型错误：线性逐行解析，把被放弃的分支与最终主路径混在一起。本技能提供正确的会话操作原语，避免这类错误。

## 调用形态

```bash
uv run --script scripts/query.py <会话 jsonl 路径> <查询脚本路径>
```

运行器解析会话成 `Session` 对象 `s`，注入到查询脚本命名空间并 exec。查询脚本自行 `print` 输出（通常 `print(encode(...))` 用 TOON 省 token）。

## 注入的命名空间

查询脚本 exec 时可用的全局变量：

| 名字 | 说明 |
|------|------|
| `s` | 已载入的 `Session` 对象（会话文件已解析） |
| `Session` | `Session` 类（可重新构造） |
| `encode` | TOON 编码（toon-format 不可用时降级 JSON） |
| `decode` | TOON 解码 |
| `truncate` | 截断长文本，附 size hint |
| `__name__` | `"__main__"`（`if __name__ == "__main__"` 守卫生效） |

查询脚本可用标准库 + 注入的原语 + toon；第三方库 MVP 不支持。

## 原语 API

`Session` 对象的五组原语，均返回最小 schema 的 dict/list（遵循 AXI 输出原则）。

### 会话元数据

| 方法 | 返回 |
|------|------|
| `s.header()` | `{version, id, timestamp, cwd, parent_session}` |
| `s.title()` | 会话标题（最新 `session_info.name`），无则 `None` |

### 树结构

| 方法 | 返回 |
|------|------|
| `s.leaf()` | 末端节点：物理最后一条 entry（与 Pi 源码 `buildSessionPath` 默认一致） |
| `s.entry(id)` | 单个 entry 摘要 |
| `s.parent_chain(id)` | 从 id 回溯到根的链（self-first） |
| `s.children(id)` | id 的直接子节点 |
| `s.branch_leaves()` | 所有叶子节点（分支末端） |
| `s.tree()` | `{total_entries, root_id, leaves, branch_count}` |
| `s.common_ancestor(a, b)` | a、b 的最近公共祖先（LCA） |

### 路径与消息

| 方法 | 返回 |
|------|------|
| `s.path(leaf_id=None)` | root-to-leaf 完整链（含 compaction 等所有 entry）。默认 leaf 为物理最后一条 |
| `s.context_entries(leaf_id=None)` | compaction-aware 活跃 entry 列表（Pi `buildContextEntries` 语义：省略最后一个 compaction 的 `firstKeptEntryId` 之前的条目） |
| `s.messages(leaf_id=None, *, role=None, tool=None, content=None, time=None)` | path 上 message 摘要，可按角色/工具名/正文子串/时间范围过滤（`time=(start, end)` ISO 8601，按字典序） |
| `s.blocks(entry_id)` | 单个 message entry 的 content[] block（thinking/text/toolCall/image；image 只给 mimeType+size，不返回 base64） |
| `s.tool_pairs(leaf_id=None)` | path 上 toolCall ↔ toolResult 按 call id 配对（精确匹配，含复合 id） |

### 分析专用

| 方法 | 返回 |
|------|------|
| `s.diff(a, b)` | 两条分支（leaf id）在公共祖先之后的各自走向：`{common_ancestor, a_only, b_only}`（root-first，从祖先向外） |
| `s.tool_stats(leaf_id=None)` | `{total, by_tool, errors, error_rate}` |
| `s.token_stats(leaf_id=None)` | 累计 token 消耗与成本（来自 assistant `usage`）：`{input, output, cache_read, cache_write, total, cost, assistant_turns, by_model}` |
| `s.compaction_points(leaf_id=None)` | path 上的压缩点：`[{id, timestamp, tokensBefore, firstKeptEntryId, summary}]` |

`leaf_id` 参数缺省时取物理最后一条 entry。path/messages/tool_pairs/token_stats 等都基于"指定 leaf 到根"的路径，可分析任意分支。

## 查询脚本示例

还原主路径对话流：

```python
print(encode([{"role": m["role"], "text": m["text"]} for m in s.messages()]))
```

查看主路径上所有助手思考：

```python
for m in s.messages(role="assistant"):
    for b in s.blocks(m["id"]):
        if b["type"] == "thinking":
            print(m["id"], b["text"])
```

配对工具调用与结果、统计出错率：

```python
print(encode(s.tool_stats()))
print(encode(s.tool_pairs()))
```

对比两条分支差异：

```python
leaves = [e["id"] for e in s.branch_leaves()]
if len(leaves) >= 2:
    print(encode(s.diff(leaves[0], leaves[1])))
```

定位压缩点并查看摘要：

```python
print(encode(s.compaction_points()))
```

查询脚本可写循环、条件、聚合等任意复杂逻辑，不受固定查询能力限制。

## 错误与退出码

| 场景 | exit | stdout |
|------|:----:|--------|
| 用法错误（参数数不对） | 2 | `{"error":true,"type":"usage",...}` |
| 会话/查询脚本文件不存在 | 2 | `{"error":true,"type":"file_not_found",...}` |
| 缺 session header | 1 | `{"error":true,"type":"missing_header",...}` |
| v1/v2 会话（仅支持 v3） | 1 | `{"error":true,"type":"unsupported_version","version":N,...}` |
| 文件无有效条目 | 1 | `{"error":true,"type":"empty",...}` |
| 查询脚本抛异常 | 1 | `{"error":true,"type":"query_error","traceback":...}` |
| 某行 JSON 无法解析 | 0 | 跳过该行，stderr 警告 |

错误输出固定用 JSON（不依赖 toon），确保可解析。查询脚本返回空结果是 `[]`/`{total:0}` 等明确空状态，非报错。

## 设计要点

- **末端节点语义**：物理最后一条 entry（`entries[-1]`），不是"最后一个 assistant text 消息"--后者是次优启发式，会话以 user/toolResult/纯 toolCall 结束时会定位错。与 Pi 源码 `buildSessionPath` 的 `leaf ??= entries[entries.length - 1]` 一致
- **主路径算法**：取末端节点回溯 parentId 到根，按 timestamp 序。正确处理压缩（path 返回完整链含 compaction 标记；context_entries 按 Pi `buildContextEntries` 语义省略被压缩条目）
- **block 类型**：完整支持 thinking/text/toolCall/image（assistant），text/image（toolResult）。image 不返回 base64 data（截断原则）
- **v3 only**：仅支持 v3 会话（树形 id/parentId）；v1（线性、无 id/parentId）与 v2 文件拒绝并结构化错误指出 version，避免静默错误结果
- **TOON fallback**：toon-format 导入失败或编码异常时降级 JSON 输出并 stderr 警告，不崩溃

## 脚本位置

`scripts/query.py` - PEP 723 单文件脚本，依赖 `toon-format>=0.9.0b1,<1.0`（PyPI beta）。原语库 + 运行器自包含于单文件，查询脚本通过 exec 注入的命名空间访问原语，无需 import 本地模块。

## 参考

- Pi 会话格式 -> `~/github_code/pi/packages/coding-agent/docs/session-format.md`（权威格式参考，已覆盖 block/message/entry 类型、树结构、context building）
- AXI 输出原则 -> `~/github_code/axi/`（TOON 输出、最小 schema、截断、聚合、空状态、结构化错误）
- TOON 格式 -> toonformat.dev；Python 库 `toon-format`（PyPI 0.9.0b1，beta，API 可能变）
