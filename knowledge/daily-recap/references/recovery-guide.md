# daily-recap 恢复指南

常见故障情景与处理方式。daily-recap 远程线程用 **nmem CLI**（`nmem threads list/show/search`，后端为本地 REST 服务）；CLI 失败以退出码非 0 + stderr 报错体现。

## 后端不可达（Hard stop）

| 症状 | 判断 | 操作 |
|------|------|------|
| `nmem threads list` 连接失败/超时 | 退出码 ≠ 0，stderr 报 `connecting to ...`/timeout | Hard stop——询问用户是否仅看本机会话（用 `extract_today.py`） |

## 远程列举与读取（单条容错）

| 症状 | 原因 | 操作 |
|------|------|------|
| `nmem threads list` 无窗口内线程但本机有数据 | 远程无同步或当日未用 nmem | 正常，走纯本机路径（非失败） |
| 翻页后仍担心漏线程 | 列表排序**不是严格日期序**（按导入批次混杂） | 分页停止规则见 SKILL.md Step 0「分页」 |
| `nmem threads show` 只返回 10 条消息 | 默认 `--limit 10` | **必须显式传 `--limit`**（如 300）；消息更多时 `--offset` 续读 |
| `nmem threads show` 404/not found | 线程 id 前缀漂移（同一会话 `pi-`/`omp-` 都可能出现）或 id 无效 | 用 `nmem threads search <关键词>` 语义检索定位；仍失败则标记「内容待补充」，不阻塞整体（批准条目需回头告知用户，见 SKILL.md 4a） |
| 线程读取失败/空线程 | 服务端问题 | 标记「内容待补充」，不阻塞整体 |
| nmem 有线程但本地无对应文件 | 正常——其他机器的会话 | 按远程会话流程，用 `nmem threads show` 获取 |

## 本机与写入

| 症状 | 原因 | 操作 |
|------|------|------|
| 会话 jsonl 文件不可读 | 权限问题或路径变更 | 该会话标记 error，内容降级为 title + 消息数 |
| `extract_today.py` `total: 0` | 两种可能：真无会话 / 全被过滤 | 看 `total_raw`/`filtered_out` 区分（见 SKILL.md Step 0 空集反证），不直接终止 |
| `find -newermt` 找不到会话文件 | WSL/find 行为差异（疑似） | 勿依赖 mtime 找会话；一律按文件名日期前缀筛（脚本粗筛即此法） |
| `obsidian-helper.py` 失败/配置缺失 | 脚本未找到或 `CONFIG_MISSING=true` | 询问用户 vault 路径，创建 `~/.config/cnife-skills/obsidian-diary.json` 后重试；写入降级为直接 Edit 文件 |

## 时间口径备忘

- 线程 `created_at` 是**日级 UTC 日期**（"Aug 02, 2026"）；±2 天粗筛窗口已覆盖 1 天时区偏移。远程线程无消息级时间戳，日级判定即最终判定（见 SKILL.md Step 0）。
- 会话 jsonl 的 timestamp 是 **UTC**：00:42Z = 08:42 CST，勿误读；核验用「消息不可能早于线程创建」逻辑交叉验证。
- 本机脚本输出 `time_cst` 已换算，无需手算。
