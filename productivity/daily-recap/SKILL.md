---
name: daily-recap
description: 将今天所有机器上的 Pi 和 OMP 会话整理成主题聚合的结构化日报，可选写入 Obsidian 工作日志。用户说"整理今天工作""日报""daily recap""今天做了什么"时使用。
disable-model-invocation: true
---

# Daily Recap — 今日工作整理

将所有机器上的 Agent 会话整理为一份**主题聚合**的日报——合并分散的会话记录按主题域聚拢，不做时间线平铺。最终输出兼容 `obsidian-diary` 格式，可直接写入工作日志或个人日记。

**nmem 是 source of truth**：多台机器上的会话通过 nmem 同步，覆盖全部机器的全部会话。本地 jsonl 文件仅存在于当前机器，是**本机会话的内容增强来源**。

脚本路径前缀：`scripts/` 和 `references/` 相对于本 skill 目录。

## 流程

### Step 0：检查数据来源

先确认今天有可整理的会话：

```bash
cd <skill目录> && uv run --script scripts/extract_today.py --min-msgs 3
```

- nmem 仍应检查：`nmem --json t list -n 25` — 从 `created_at` 筛选今天
- 脚本输出 `total: 0` 且 nmem 也无今日线程 → 告知用户"今天没有会话记录"并终止
- 仅 nmem 有数据 → 纯远程，跳过 Step 1（脚本无本地文件）
- 脚本有输出 → 进入 Step 1

排除当前日报会话：脚本输出的 `sessions[]` 中找标题含"日报/daily-recap"的条目，记下其 `session_id`，在 Step 1a 用 `--exclude` 排除。

### Step 1：收集并提取

两路并行：

#### 1a. 本机会话 — 用提取脚本

脚本已提取所有本地会话的结构化数据（标题、时间 CST、项目、消息量、首条用户消息、产出摘要）。脚本输出即为本机会话的**完整证据集**。

```bash
cd <skill目录> && uv run --script scripts/extract_today.py --min-msgs 3
```

参数备忘：`--min-msgs N` 跳过小于 N 条消息的 stub 会话；`--exclude <uuid>` 排除指定 session（用于排除当前日报会话，从脚本输出中找到对应的 `session_id`）。

#### 1b. 远程会话 — nmem t show

对 nmem 中 UUID **不在**脚本输出 `session_id` 列表中的线程，远程提取：

```bash
nmem --json t show "<thread_id>" --limit 5 --offset 0 --content-limit 1000
```

每读一段，问：**这段产生了什么可记录的产出？** 提取标题和核心事件摘要。

远程会话的 git 提交不可用，标注"📡 远程，git 记录不可用"。

#### 1c. Git 提交（证据校准）

从脚本输出的 `cwd` 字段识别涉及哪些 git 仓库，逐仓库查询今日提交：

```bash
git -C <repo_path> log --oneline --since="YYYY-MM-DD" --all
```

git 提交是**产出真实性的校准源**——agent 自我总结可能 overclaim，commit log 是 ground truth。不产出当日日记正文，仅作为构建候选表时的证据参考。

### Step 2：分类

分类只处理远程会话（本机会话已被脚本结构化）：

| 分类 | 判定 | 内容源 |
|------|------|--------|
| **本机会话** | UUID 在脚本输出中 | 脚本输出的结构化数据 + 原始 jsonl（需要时） |
| **远程会话** | UUID 仅在 nmem 中 | nmem t show 分段提取 |
| **当前日报** | 标题含"日报/daily-recap"关键词 | 标记"当前日报"，不纳入候选 |

### Step 3：构建候选表（用户确认）

将所有证据整理为候选条目表，**直接按主题域分组**：

| # | 会话主题 | 主题域 | 来源 | 去向 | 理由 |
|:-:|----------|--------|:----:|:----:|------|
| 1 | HPC 巡检 | genome-assembly | 🖥️ | 工作日志 | 之江实验室日常工作 |
| 2 | 双语 HTML 转换 | learn-mattpocock | 📡 | 不记录 | 个人练习，无产出变化 |

去向：`工作日志` · `个人日记` · `不记录`
来源：🖥️ 本机 / 📡 其他机器

**呈现给用户确认**。用户修正去向或标记跳过后，仅批准的条目进入下一步。

### Step 4：主题聚合并输出日报

对确认的条目进行**主题聚合**——按主题域合并，输出兼容 obsidian-diary 格式，不做时间线平铺：

1. 语义相近的事件合并到同一个主题域下
2. 同一主题下的多个事件 → 1 个 `## 标题` + 子 bullet 展开
3. 每个子 bullet 1-2 行，只写**结论和决策**，不展开细节、不列出 git 提交、不出现会话编号
4. 按重要性排序：部署/功能交付在前，基础设施/配置在后，探索/学习最后
5. 不超过 6 个主题域（理想 3-5 个），无零散单事件段落

事件记录原则（与 obsidian-diary 一致）：

- **实现了功能**：功能名 + 核心特性 + 决策
- **修复了问题**：问题 + 根因 + 修复方式
- **做了决策**：决策内容 + 理由 + 放弃的方案
- **调研了方案**：调研对象 + 结论 + 选型判断

#### 输出模板

```markdown
# 工作日志 — YYYY-MM-DD

> 项目：`<主项目>`（N 个会话贡献）

## 主题域 1

- 关键事件 bullet...
- 关键事件 bullet...

## 主题域 2

- 关键事件 bullet...
```

#### 写入前门禁

输出模板不含以下元素（obsidian-diary Blocker ③）：会话全景表、Git 提交列表、会话编号、来源标记、消息量、agent 操作日志、验证流程、阶段标记。

### Step 5：可选 — 写入 Obsidian

询问用户是否需要写入工作日志/个人日记。如果确认：

1. **先读取**目标日记文件现有内容——当天日志可能已被其他会话部分写入过
2. **补全式整合**：在现有文件的对应主题段落中追加新内容，已有段落不重写；新增主题域插入合适位置
3. 优先调用 `obsidian-diary` skill（如已安装且可用），按该 skill 的门禁规则执行
4. `obsidian-diary` 不可用时，直接用 Edit 工具补全整合

不主动写入——等待用户确认。

## 参考

- Pi 会话 JSONL 格式 → `references/pi-session-format.md`
- OMP 会话 JSONL 格式 → `references/omp-session-format.md`
- 故障恢复 → `references/recovery-guide.md`
