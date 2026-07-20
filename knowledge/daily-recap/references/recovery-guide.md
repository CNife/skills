# daily-recap 恢复指南

常见故障情景与处理方式。daily-recap 全程使用 pi-nmem 插件工具（`nmem_list_threads`/`nmem_read_thread`），不调用裸 `nmem` CLI。插件工具抛 `NmemError` 时 pi 标记 `isError:true`（会话继续）；`isRetryable` 错误（`timeout`/`backend_unreachable`/`server_error`）插件已内部重试 2 次，到本层说明真不可达。

## 后端不可达（Hard stop）

| 症状 | NmemError code | 操作 |
|------|------|------|
| `nmem_list_threads` 连接失败/超时 | `backend_unreachable` / `timeout` | Hard stop--询问用户是否仅看本机会话（用 `extract_today.py`）|
| 鉴权失败 | `unauthorized` | 配置错误：检查 `~/.nowledge-mem/config.json` 或 `NMEM_API_KEY`，修复后重试 |

## 远程列举与读取（单条容错）

| 症状 | 原因 | 操作 |
|------|------|------|
| `nmem_list_threads` 返回空但本机有数据 | 远程无同步或当日未用 nmem | 正常，走纯本机路径（非失败）|
| `nmem_list_threads` `has_more=true` | 候选多于 `limit` | 分页续取（`offset` 递增），非失败 |
| `nmem_read_thread` `not_found`/`bad_request` | 线程 id 无效或参数错误 | 该会话标记"内容待补充"，不阻塞整体 |
| `nmem_read_thread` 返回 `total_messages=0` | 空线程 | 标记"内容待补充" |
| `nmem_read_thread` `timeout`/`server_error` | 服务端问题（已内部重试）| 该会话标记"内容待补充"，不阻塞整体 |
| nmem 有线程但本地无对应文件 | 正常--其他机器的会话 | 按远程会话流程，用 `nmem_read_thread` 获取 |

## 本机与写入

| 症状 | 原因 | 操作 |
|------|------|------|
| 会话 jsonl 文件不可读 | 权限问题或路径变更 | 该会话标记 error，内容降级为通过 `nmem_read_thread` 获取摘要 |
| `extract_today.py` `total:0` 但当前会话应在窗口 | 窗口/路径/日期配置可疑 | 反证排查（见 SKILL.md Step 0），不直接终止 |
| `obsidian-helper.py` 失败/配置缺失 | 脚本未找到或 `CONFIG_MISSING=true` | 询问用户 vault 路径，创建 `~/.config/cnife-skills/obsidian-diary.json` 后重试；写入降级为直接 Edit 文件 |
