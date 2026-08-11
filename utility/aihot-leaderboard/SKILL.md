---
name: aihot-leaderboard
description: 查询 AIHOT 大模型排行榜（aihot.virxact.com/leaderboard）的实时数据——总榜前 30 名、单个模型在各家来源榜单的明细成绩、或全部来源（12 张评测榜单）的完整排名与分数。用户询问当前大模型排行榜、某模型排名/共识分、某模型在某评测榜单的名次分数、或需要对比多家榜单数据时使用。必须通过 xd://browser 访问站点实时抓取，不凭训练记忆回答榜单数据。
---

# AIHOT Leaderboard

查询 [AIHOT 大模型排行榜](https://aihot.virxact.com/leaderboard) 的实时数据。站点由「数字生命卡兹克」维护，用 LatentRank 算法（Bradley-Terry 成对比较 + 先验 + 锚点归一化）聚合 10 家独立来源、12 张评测榜单，产出 0–100 分的「AIHOT 共识分」。

## 安全与访问边界

- **反爬**：站点有 EO_Bot_Ssid 反爬（curl / 无头浏览器被拦，code 567），**必须用真实浏览器会话**。在 omp 环境通过 `xd://browser` 执行；浏览器已打开站点时直接复用 tab。
- **只读**：只读取公开页面数据，不提交表单、不登录、不改动站点任何状态。
- **许可**：数据仅限个人非商业 / 组织内部使用；面向外部的商业用途须先取得 AIHOT 书面授权（见站点 `https://aihot.virxact.com/agent?tab=api` 的用途许可边界）。
- 榜单每天约 08:17（北京时间）更新一次；抓取到的即当前快照，回答时说明数据时间（页面「更新于」）。

## 数据层与触发路由

| 用户意图 | 数据层 | 来源页 | 脚本 |
|---|---|---|---|
| 榜单整体（谁第一、前十、某模型总排名） | 总榜前 30 | `/leaderboard` | `scripts/aihot-leaderboard.js` |
| 单个模型在各家榜单的成绩（某模型排名/共识分/在某榜的名次） | 模型明细 | `/leaderboard/<slug>` | `scripts/aihot-model.js` |
| 某家来源榜单的完整排名（AA Index / Epoch / LiveBench / llm2014 等全量） | 来源榜单 12 张 | `/leaderboard/methodology` | `scripts/aihot-sources.js` |

**路由示例**：问「Claude Opus 5 现在排第几」→ 模型明细层（slug 取自总榜 `a.lb-row` href，如 `claude-opus-5`）；问「AA Index 上谁第一」→ 来源榜单层；问「现在榜首是谁 / 前五名」→ 总榜层。

## 工作流

### Step 0：定位 slug（模型明细层需要）

用户问单个模型时，先用总榜页把模型名映射到 slug：

1. 用 `xd://browser` 打开 `https://aihot.virxact.com/leaderboard`（已打开则复用 tab）。
2. 运行下面的**总榜驱动代码**，返回的 `rows` 里每行含 `url`（如 `/leaderboard/claude-opus-5`），取末段即 slug；模型名可能在总榜里没有（30 名以外），此时按用户给的模型名从 URL 猜测（小写、连字符），抓不到就在回答中说明该模型不在总榜 30 名内。

### Step 1：抓取（驱动代码，不粘贴脚本全文）

脚本是 CommonJS 模块，从磁盘加载；把**对应数据层**的驱动代码粘贴进 `xd://browser`（`action: run`，`name: main`）的 `code` 字段执行即可。脚本自带导航：当前 tab 已在目标页则直接抓取，否则自动跳转。

**先定位 `<SCRIPTS_DIR>`（每次使用前都做，勿假设安装位置）**：用 `read skill://aihot-leaderboard` 读本技能 SKILL.md，从返回的路径得知其磁盘位置（形如 `<...>/aihot-leaderboard/SKILL.md`）；scripts 目录即**同目录下的 `scripts/`**（`dirname(SKILL.md)/scripts`）。若 `skill://` 不可解析（注册表为会话启动时快照），改用 find_files / glob 搜索 `aihot-leaderboard/SKILL.md` 定位同一文件。把下面驱动代码里的 `<SCRIPTS_DIR>` 替换为该绝对路径——无论技能装在哪个目录、或只在仓库源码里，这个推导都成立。

**总榜层**（返回含 30 行 `rows`，每行带 `url` 可作 slug 来源）：

```js
const file = '<SCRIPTS_DIR>/aihot-leaderboard.js';
delete require.cache[require.resolve(file)];
const { extractLeaderboard } = require(file);
return extractLeaderboard(page);
```

**模型明细层**（把 slug 换成目标模型的 slug，见 Step 0）：

```js
const file = '<SCRIPTS_DIR>/aihot-model.js';
delete require.cache[require.resolve(file)];
const { extractModel } = require(file);
return extractModel(page, { slug: 'claude-opus-5' });
```

**来源榜单层**（数据量大，返回仅各榜行数摘要；完整 JSON 在返回的 `output` 指出的文件里，用 read 读取）：

```js
const file = '<SCRIPTS_DIR>/aihot-sources.js';
delete require.cache[require.resolve(file)];
const { extractSources } = require(file);
return extractSources(page);
```

- `delete require.cache[...]` 确保加载最新版脚本（技能更新后立即生效），保留此行不要删。
- 总榜/模型明细的 `rows` 直接出现在工具返回里；来源榜单的完整数据在 `output` 指出的 JSON 文件。

### Step 2：呈现

读 JSON 文件，按 Output Format 输出。回答先说结论（排名、分数、升降、亮点），再给表格；数据时间以页面「更新于」为准。

## Output Format

- **总榜**：Markdown 表格 —— 排名、模型、厂商、共识分（+ 可选：上线日期、评测完整度、输入/输出价格）。前 30 全列，或按用户问的范围（前 5/前 10）截取并注明。
- **模型明细**：先一句总述（共识分、当前第几名），再表格 —— 榜单（含运营方分组，如 `llm2014 Agent` 下的子任务）、原榜名次、原始分数、原榜型号；缺失项（`missing: true`，即「暂无评估」）标 `—`。表后可加 1–2 行观察（该模型在哪些榜领先/落后）。
- **来源榜单**：表格 —— 名次、模型、厂商、原榜分数（+ 置信区间若有）；含子 tab 的来源（如 llm2014）按子榜分组呈现。
- 所有数字直接引用抓取结果，不四舍五入改写；「暂无评估」和真实 0 分区分（0 分是评估了得 0，`—` 是没评估）。

## 注意事项

- **价格字段差异**：总榜多数模型有 `price.input` / `price.output`（美元/百万 tokens）；订阅制模型（如 Qwen3.8 Max）无按量价，脚本里落在 `price.note`（如 `$6/月起`）。
- **运行时机**：站点一天只更新一次，重复抓取结果不变；回答即可，无需缓存或历史对比。
- 脚本失败时（tab 被关闭、导航失败）重新 `xd://browser open` 后再执行对应驱动代码；不要用 curl / fetch 直连代替，必被反爬拦截。
