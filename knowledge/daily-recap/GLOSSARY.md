# Daily Recap 领域模型

## 术语表

### Daily Recap（日报）

每天从 AI Agent 会话中提取「做了什么 + 为什么做 + 能学到/总结什么」，写入 Obsidian 日记。不是会话的压缩传输，而是从会话中提取理解。

### AI Agent Session（会话）

用户大部分工作通过 AI Agent（Pi / OMP）完成。会话蕴含工作和个人项目的丰富细节。Pi 和 OMP 均配了插件，自动同步会话到 nmem。nmem 是会话的 source of truth。

### 机器会话（Machine Session）

由 agent 工具链自动产生、不代表人的直接工作产出的会话：advisor 镜像（标题以 `### Session update` 开头）、子代理任务会话、no-mistakes 流水线的阶段子代、上一次 recap 自身及其收集/核验子代。整理日报时默认跳过；**跳过必须留痕**--归类审查消息里注明数量，用户可点名捞回。

判族两条路：标题族（脚本 `MACHINE_TITLE_FAMILIES`）与首条消息族（脚本 `MACHINE_MESSAGE_FAMILIES`）。父会话派发的子代理、流水线阶段与 recap 子代常带友好标题（如「为 18 个 UP 主打标并生成 out/tags/part07.json」），标题族认不出，只能取首条 user 消息判族。

### nmem

会话的 source of truth。存储两类数据：

- **会话 transcript**（`threads`）--完整对话记录，`threads list` 返回 `created_at`（日级 UTC）
- **自动蒸馏记忆**（`memories`）--从会话中自动提取的语义事实

### 线程 ID 时间戳（UUID v7）

Pi 和 OMP 的线程 ID 多为 UUID v7（如 `omp-019fd628-514d-7000-88be-e0591fac251c`）。前 48 位编码会话开始时间的毫秒级 Unix 时间戳，可从 `threads list` 的 `id` 字段直接解析，无需 REST 调用。

- 编码的是**会话开始时间**（会话 UUID 生成时刻），不是 nmem 导入时间
- 毫秒精度，可直接判断 04:00 CST 窗口边界
- 对 `nmem t sync` 导入的旧会话同样准确（UUID 不因导入而改变）
- 已用 OMP 磁盘文件名时间戳交叉验证：毫秒级完全一致
- 前缀不固定（`pi-`/`omp-`/`grok-`…），按 UUID v7 形状在 id 里查找，不能只剥 `pi-`/`omp-` 再取前 12 位

**id 判不出时**：先看消息级 `timestamp`（毫秒精度，如 deepseek-harness 线程的 id 完全不带时间，只有消息带），再退到 `created_at` 保守排除。

**非 UUID v7 的 id**：nmem 里还有自带日期时刻的 id--`import-YYYYMMDDhhmmss-<hex>`（历史导入）、`YYYYMMDD_hhmmss_<hex>`（pi 早期）、`cron_<hex>_YYYYMMDD_hhmmss`（定时任务），按 CST 解析后同样能精确判窗口。两者都判不出时，用 `created_at` 做保守排除：`created_at` 是导入批次日级日期，实测比会话开始最多晚 52 天、最早早 1 天，所以只有 `created_at + 1 天` 仍早于窗口当日才算证明在窗口外，其余的进候选留痕而不是丢弃。

### 自动蒸馏记忆（Auto-distilled Memory）

nmem 从会话中自动提取的语义事实。局限性：

- 按**语义**检索（`memories search`），不按时间排序
- **无 source_thread 关联**--不能查"某会话产出了哪些记忆"
- **无 event_start**--不能按日期过滤
- `created_at` 是蒸馏时间，不是事件发生时间
- 因此**不能直接用于日报**（无法按日期/会话过滤）

### Obsidian Diary（Obsidian 日记）

日报载体。优势：方便阅读、方便手动编辑、按时间排序。nmem 记忆不可替代，因为记忆琐碎、不按时间排序、不方便手动编辑。

变体：

- **工作日志**（work）：公司项目/部署运维/团队协作，可分享给团队
- **个人日记**（personal）：个人技术探索/学习/投资/生活，保留个人观点和感受

### 时间窗口

CST [工作日 04:00, 次日 04:00)。凌晨 00:00-04:00 的会话归前一工作日。窗口归属由线程开始时间判断，判定顺序见「线程 ID 时间戳」，全程不用 REST。

### 事件（Event）

从会话中提取的语义单位，也是 subagent 收集与主 agent 写作（3b）的容器。一个事件选型 6 种形态之一（决策/调研/部署/修复/功能/验证）并填对应骨架字段。**会话是事件来源，事件是理解单位**--输入单位（会话）≠ 输出单位（事件）。每个事件带 `来源` 指针（线程 + 消息/行号）供追溯。「学到什么」不在收集阶段填（合成=3b）；「放弃的替代方案」会话显式讨论才填。

### 主题域（Theme Domain）

日报的组织单位。将语义相关的会话聚合到一个主题下，按重要性排序（部署/功能交付在前，基础设施/配置在后，探索/学习最后）。

### 归类审查（唯一人工门）

daily-recap 全程唯一的人工环节：用户审阅候选会话的主题域归类与去向（工作日志/个人日记/不记录）并作最终裁定；收集、核验、写入均静默完成。
