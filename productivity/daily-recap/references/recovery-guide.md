# daily-recap 恢复指南

常见故障情景与处理方式。

| 症状 | 原因 | 操作 |
|------|------|------|
| nmem 不可用 | CLI 未安装/未登录 | **Hard stop**——询问用户是否仅看本机会话（用 `scripts/extract_today.py`） |
| nmem t list 无今日线程 | 今天未通过 nmem 同步或未使用 | 仅用本机会话文件，跳过远程部分——extract_today.py 仍可正常输出 |
| 会话 jsonl 文件不可读 | 权限问题或路径变更 | 该会话标记 error，内容降级为通过 nmem t show 获取摘要 |
| 远程会话 nmem t show 超时/空 | nmem 服务端问题 | 标记该会话"内容待补充"，不阻塞整体流程 |
| nmem 有线程但本地无对应文件 | 正常——其他机器的会话 | 按远程会话流程处理，用 nmem t show 获取 |
| extract_today.py 找不到今天的文件 | 文件名日期格式变更 | 确认目标日期后手动检查 session 目录结构 |
| obsidian-diary 不可用 | skill 未安装在当前 agent | 直接用 Edit 工具追加日记条目，见 Step 5 |
