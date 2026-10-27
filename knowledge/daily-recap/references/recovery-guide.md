# daily-recap 恢复指南

常见故障情景与处理方式。daily-recap 用 **nmem CLI**（`nmem threads list/show/search`）作为会话唯一来源；CLI 失败以退出码非 0 + stderr 报错体现。时间过滤优先用线程 id 里的 UUID v7（前 48 位 = 会话开始时间毫秒戳），其次 id 内嵌日期时刻，不用 REST。

## 后端不可达（Hard stop）

| 症状 | 判断 | 操作 |
|------|------|------|
| `nmem threads list` 连接失败/超时 | 退出码 ≠ 0，stderr 报 `connecting to ...`/timeout | Hard stop--nmem 是唯一来源，无降级路径；询问用户排查 nmem 后重试 |

## 列举与读取（单条容错）

| 症状 | 原因 | 操作 |
|------|------|------|
| `nmem threads list` 无窗口内线程 | 当日未用 nmem 或确实无会话 | 正常终止，告知用户"目标工作日没有会话记录" |
| 翻页后仍担心漏线程 | 列表排序既非会话时间序也非严格导入序（实测旧会话出现在几十页后） | `--scan` 扫全库到底（约 44 页 / 20 秒），不提前停页；手工翻页时别按页码推断，至少翻到全部页 |
| `--scan` 探针阶段很慢或成片「读取失败」 | 每条候选一次 `nmem threads show`（已内置 1 次重试），服务端偶发超时时成片失败 | 等它跑完；`--scan` 里整片失败通常不是真故障，重跑一次多半就恢复；nmem 持续不可用则加 `--no-probe` 只按标题族分类 |
| `nmem threads show` 只返回 10 条消息 | 默认 `--limit 10` | 显式传 `--limit`，按消息数选读法（见 `agents/recap-collector.md`「读写纪律」） |
| `nmem threads show` 超时（约 30s） | 并发过载或大响应 | 同一时刻最多 2 个并发调用；超时最多重试 1 次；再失败记「读取失败」继续，不阻塞 |
| `nmem threads show` 404/not found | 线程 id 前缀漂移（同一会话 `pi-`/`omp-` 都可能出现）或 id 无效 | 用 `nmem threads search <关键词>` 语义检索定位；仍失败则标记「内容待补充」，不阻塞整体（批准条目需回头告知用户，见 SKILL.md 3a） |
| 线程读取失败/空线程 | 服务端问题 | 标记「内容待补充」，不阻塞整体 |

## 写入

| 症状 | 原因 | 操作 |
|------|------|------|
| `obsidian-helper.py` 失败/配置缺失 | 脚本未找到或 `CONFIG_MISSING=true` | 询问用户 vault 路径，创建 `~/.config/cnife-skills/obsidian-diary.json` 后重试；写入降级为直接 Edit 文件 |

## 时间口径备忘

- **时间过滤的判定顺序**：id 里的 UUID v7（毫秒戳，前缀任意）→ id 内嵌日期时刻（`import-YYYYMMDDhhmmss-`、`YYYYMMDD_hhmmss_`、`cron_…_YYYYMMDD_hhmmss`，按 CST）→ 消息级 `timestamp` → 都判不出时用 `created_at` 保守排除。listing 阶段由 `extract_today.py --scan` 自动完成；collector 侧批量复核用 `extract_today.py --check`（从 stdin 读 thread_id）。
- 线程 `created_at` 是**导入批次日级日期**（"Aug 02, 2026"），实测比会话开始最多晚 52 天、最早早 1 天，只作「证明早于窗口」的排除，不作窗口判定。
- 不用 nmem REST 接口取消息级时间戳--id 时间戳精确到毫秒级，REST 被旁路。
