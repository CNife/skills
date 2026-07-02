---
name: daily-recap
description: 将今天所有机器上的 Pi 会话整理成主题聚合的结构化日报，可选写入 Obsidian 工作日志。用户说"整理今天工作""日报""daily recap""今天做了什么"时使用。
disable-model-invocation: true
---

# Daily Recap — 今日工作整理

将今天所有机器上的 Pi 会话、记忆和 git 提交整理为一份**主题聚合**的日报——合并分散的会话记录，按主题域聚拢，不做时间线平铺。

**nmem 是 source of truth**：多台机器上的会话通过 nmem 同步，nmem 线程列表覆盖全部机器的全部会话。本地 jsonl 文件仅存在于当前机器，是**本机会话的内容增强来源**。

## 流程

### Step 0：前置检查

1. `nmem --version` 必须可用。**nmem 不可用是 hard stop**——无法获取其他机器的会话，日报不完整。仅当用户明确说"只看本机"时可跳过。
2. 检查今天是否有数据：

   ```bash
   nmem --json t list -n 25 2>/dev/null | python3 -c "
   import json,sys
   threads = json.load(sys.stdin)
   today = [t for t in threads if '<今天日期>' in t.get('created_at','')]
   print(f'nmem: {len(today)} 个今日线程')
   "
   find ~/.pi/agent/sessions/ -type f -newermt "$(date -d 'today 00:00' '+%Y-%m-%d %H:%M:%S')" 2>/dev/null | wc -l
   ```

   两个来源至少一个有数据，否则告知用户"今天没有会话记录"并终止。

### Step 1：并行收集证据

三个数据源同时收集：

#### 1a. nmem 线程（全量，跨所有机器）

```bash
nmem --json t list -n 25
```

从 `created_at` 筛选今天的线程。记下线程 ID 集合 **S_nmem**。

nmem 线程涵盖所有同步过的机器——这是日报的**全量会话清单**。

#### 1b. 本机 Pi 会话文件

```bash
find ~/.pi/agent/sessions/ -type f -newermt "$(date -d 'today 00:00' '+%Y-%m-%d %H:%M:%S')"
```

**不限定单个项目目录**——跨所有项目目录查找。记下文件名 UUID 集合 **S_local**。

**文件名时间戳为 UTC**，展示给用户时需用 `date -d` 转 CST(+8)：

```bash
date -d "2026-07-03T06-17-23Z" "+%H:%M"  # → 14:17 (CST)
```

**排除当前日报会话**：当前会话本身不是工作项。从文件名时间戳识别（通常是当天最晚的会话之一），或从标题中匹配"日报/re-cap"关键词排除。

#### 1c. Git 提交记录

对本机会话的 git 仓库逐一查询。先通过会话 jsonl 中的 `cwd` 识别涉及哪些仓库，然后：

```bash
git -C <repo_path> log --oneline --since="YYYY-MM-DD" --all
```

无 git 仓库的会话（如纯 Obsidian 笔记、纯对话探索）跳过此步。

### Step 2：分类会话并提取内容

#### 2a. 分类

对比 S_nmem 和 S_local（用文件名中的 UUID 匹配线程 ID）：

| 分类 | 判定 | 含义 | 提取方式 |
|------|------|------|----------|
| **本机会话** | UUID 同时在 S_nmem 和 S_local 中 | 在当前机器上进行的会话 | 读本地 jsonl（内容完整） |
| **远程会话** | UUID 仅在 S_nmem 中 | 在其他机器上进行的会话 | nmem t show（内容摘要） |
| **仅本地** | UUID 仅在 S_local 中 | nmem 尚未同步（边缘情况） | 同本机会话处理，标注同步延迟 |

#### 2b. 提取 — 本机会话（直接读 jsonl）

Pi 会话文件每行是一个 JSON 对象，关键行类型：

| 行类型 | 识别 | 提取字段 |
|--------|------|----------|
| `session` | `"type":"session"` | `id`(UUID)、`timestamp`(UTC)、`cwd`(工作目录) |
| `session_info` | `"type":"session_info"` | `name`（会话标题） |
| `message` | `"type":"message"` | `message.role`(user/assistant/toolResult)、`message.content[]`（**数组**，元素 `{type:"text", text:"..."}`） |

注意：`message.content` 是数组而非字符串，用户/助手消息文本在 `message.content[].text` 中，需拼接。

对每个本机会话文件提取：

- **标题**：`session_info` 行的 `name` 字段
- **消息量**：`type == "message"` 的行数
- **首条用户消息**：第一个 user role 的 message 行，提取 `message.content[].text` 拼接
- **产出摘要**：最后一个 assistant role 的 message 行，提取关键结论/产出
- **工作目录**：`session` 行的 `cwd`，用于关联 git 仓库

可用临时 Python 脚本批量处理。

#### 2c. 提取 — 远程会话（nmem t show）

远程会话无本地 jsonl，用 nmem 分段加载提取摘要：

```bash
nmem --json t show "<thread_id>" --limit 5 --offset 0 --content-limit 1000
```

按需增加 offset 查看更多消息。每读一段，问：**这段产生了什么可记录的产出？**——提交、决策、Bug 修复、配置变更。提取：

- **标题**：线程 title
- **摘要**：核心事件和产出（无法统计精确消息量，标注"约 N 条"）
- **git 提交**：标注"📡 远程，git 记录不可用"

### Step 3：构建候选表（按主题域分组，用户确认）

将所有证据整理为候选条目表，**直接按主题域分组**：

| # | 会话 | 主题域 | 来源 | 去向 | 理由 |
|:-:|------|--------|:----:|------|------|
| 1 | HPC 巡检 | genome-assembly | 🖥️ | 工作日志 | 之江实验室日常工作 |
| 2 | 双语 HTML 转换 | learn-mattpocock | 📡 | 不记录 | 个人练习，无产出变化 |

去向：`工作日志` · `个人日记` · `不记录`

来源：🖥️ 本机 / 📡 其他机器

状态标准：✅ 有明确产出且已处理 / 🔄 有进展未完成 / ⏭️ 浏览探索无产出

**呈现给用户确认**。用户修正去向或标记跳过后，仅批准的条目进入聚合。

### Step 4：主题聚合并输出日报

对确认的条目进行**主题聚合**——按主题域合并，不做时间线平铺：

1. 语义相近的事件合并到同一个主题域下
2. 同一主题下的多个事件 → 1 个 `## 🔹 标题` + 子 bullet 展开
3. 按重要性排序：部署/功能交付在前，基础设施/配置在后，探索/学习最后
4. 不超过 6 个主题域（理想 3-5 个），无零散单事件段落

事件记录格式：

- **实现了功能**：功能名 + 核心特性 + 决策
- **修复了问题**：问题 + 根因 + 修复方式
- **做了决策**：决策内容 + 理由 + 放弃的方案
- **部署/配置**：环境 + 关键参数 + 验证结果

#### 输出模板

```markdown
# 📋 YYYY-MM-DD 工作日志

> 跨 N 个仓库：`<主项目>` + <其余> 个其他项目

## 会话全景（共 N 个）

| # | 时间 | 主题 | 来源 | 消息量 | 状态 |
|:-:|:---:|------|:----:|:-----:|:----:|
| 1 | hh:mm | 主题 | 🖥️ | N条 | ✅ |
| 2 | hh:mm | 主题 | 📡 | 约N条 | ✅ |

## 🔹 主题域 1（核心工作）

关键事件 bullet...

## 🔹 主题域 2

关键事件 bullet...

## Git 提交汇总（N commits）

| 仓库 | 时间 | Commit | 说明 |
|:-----|:---:|:------:|-------|

> 📡 远程会话的 git 提交不可用

## 关键发现与决策

1. bullet...
```

模板说明：

- **项目行**：跨多个仓库时写「跨 N 个仓库：主项目 + 其余」，单仓库时写「项目：`<repo>` | 当前 commit: `<hash>`」
- **来源列**：本机 🖥️ / 其他机器 📡——远程会话无法展示完整 git 提交和精确消息量
- **会话时间**：统一用 CST（UTC+8），远程会话从 nmem created_at 转
- **无时间段分组**——始终按主题聚合

### Step 5：可选 — 写入 Obsidian 日志

询问用户是否需要写入工作日志/个人日记。如果确认：

1. **先读取**目标日记文件的现有内容——当天日志可能已被其他会话部分写入过
2. **补全式整合**：在现有文件的对应主题段落中追加新内容，已有段落不重写；新增主题域插入合适位置
3. 优先调用 `obsidian-diary` skill（如已安装）
4. 不可用时，直接用 Edit 工具追加或更新对应段落

不主动写入——等待用户确认。

## 恢复指南

| 症状 | 原因 | 操作 |
|------|------|------|
| nmem 不可用 | CLI 未安装/未登录 | **Hard stop**——询问用户是否仅看本机会话（\`find ~/.pi/agent/sessions/\`）|
| nmem t list 无今日线程 | 今天未通过 nmem 同步或未使用 | 仅用本机会话文件 + git，跳过远程部分 |
| jsonl 文件不可读 | 权限问题或路径变更 | 该本机会话降级为 nmem t show（同远程会话处理） |
| 远程会话 nmem t show 超时/空 | nmem 服务端问题 | 标记该会话"内容待补充"，不阻塞整体流程 |
| nmem 有线程但本地无对应目录 | 正常——其他机器的会话 | 按远程会话流程处理 |
| git log --since 无输出 | commit 日期标记不匹配 | 去掉 --since，用 \`git log -20\` 看最近提交 |
| obsidian-diary 不可用 | skill 未安装 | 直接用 Edit 工具追加，见 Step 5 |
