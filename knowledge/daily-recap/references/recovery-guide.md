# daily-recap 恢复指南

常见故障情景与处理方式。daily-recap 用 **nmem CLI**（`nmem threads list/show/search`）作为会话唯一来源；CLI 失败以退出码非 0 + stderr 报错体现。时间过滤用 UUID v7（线程 id 前 48 位 = 会话开始时间毫秒戳），不用 REST。

## 后端不可达（Hard stop）

| 症状 | 判断 | 操作 |
|------|------|------|
| `nmem threads list` 连接失败/超时 | 退出码 ≠ 0，stderr 报 `connecting to ...`/timeout | Hard stop--nmem 是唯一来源，无降级路径；询问用户排查 nmem 后重试 |

## 列举与读取（单条容错）

| 症状 | 原因 | 操作 |
|------|------|------|
| `nmem threads list` 无窗口内线程 | 当日未用 nmem 或确实无会话 | 正常终止，告知用户"目标工作日没有会话记录" |
| 翻页后仍担心漏线程 | 列表排序**不是严格日期序**（按导入批次混杂） | 分页停止规则见 SKILL.md Step 0「分页」 |
| `nmem threads show` 只返回 10 条消息 | 默认 `--limit 10` | **必须显式传 `--limit`**（如 300）；消息更多时 `--offset` 续读 |
| `nmem threads show` 404/not found | 线程 id 前缀漂移（同一会话 `pi-`/`omp-` 都可能出现）或 id 无效 | 用 `nmem threads search <关键词>` 语义检索定位；仍失败则标记「内容待补充」，不阻塞整体（批准条目需回头告知用户，见 SKILL.md 2a） |
| 线程读取失败/空线程 | 服务端问题 | 标记「内容待补充」，不阻塞整体 |

## 写入

| 症状 | 原因 | 操作 |
|------|------|------|
| `obsidian-helper.py` 失败/配置缺失 | 脚本未找到或 `CONFIG_MISSING=true` | 询问用户 vault 路径，创建 `~/.config/cnife-skills/obsidian-diary.json` 后重试；写入降级为直接 Edit 文件 |

## 时间口径备忘

- **UUID v7 是时间过滤的唯一口径**：线程 id（去 `pi-`/`omp-` 前缀、去连字符）前 12 位十六进制 = 会话开始时间毫秒级 Unix 时间戳，转 CST 判断 [04:00, 次日 04:00) 窗口。`extract_today.py --filter` 自动完成此计算。
- 线程 `created_at` 是**日级 UTC 日期**（"Aug 02, 2026"），只作粗筛参考，不作窗口判定。
- 不用 nmem REST 接口取消息级时间戳--UUID v7 已精确到毫秒，REST 被 UUID v7 旁路。
