---
name: nmem-maintenance
description: 巡检 Nowledge Mem 知识库——检查服务状态、审查待处理事件、分类处理（陈旧结晶/重复记忆/矛盾裁定），输出清理报告。调用 ask_user_question 批量获取裁定，不做任何自动化决策。
disable-model-invocation: true
---

# nmem-maintenance — Nowledge Mem 知识库巡检

周期性巡检 nmem 知识库，处理后台积累的待办事件。核心是**先分类再处理，关键裁定交给用户，不做自动化决策**。

## 前置条件

- `nmem` CLI 可用且已登录

## 流程

### Step 1：服务健康检查

确认 nmem 服务在线，记录版本和模式：

```bash
nmem --json status
```

**健康响应**：`status: ok`，有 `server_version`，`database: true`。

**完成标记**：服务在线，或已报告故障。

### Step 2：拉取近期事件

```bash
nmem feed --days 7 -j
```

筛选出 `severity: action_required` 且 `resolved: false` 的事件。

> ⚠️ feed 事件的 `resolved` 字段是**只读标记**——即使底层记忆已修复，该字段也不会自动变为 true。后续核查必须直接用 `nmem memories show` 验证记忆状态，不能依赖事件状态。

**完成标记**：列出所有待处理事件及其 ID。若无待处理事件，结束巡检。

### Step 3：分类事件

将每个 `action_required` 事件归入以下三类之一：

| 事件类型 | 分类 | 特征 |
|---------|------|------|
| `flag_stale` | **陈旧结晶** | 结晶有新源记忆，建议补充更新 |
| `flag_merge_candidate` | **重复记忆** | 多条记忆标题/内容高度重复 |
| `flag_contradiction` | **矛盾裁定** | 两条记忆给出相反指引，需用户裁定 |
| `insight_generated` | info | 后台自动洞察，无需处理 |
| `crystal_created` | info | 新结晶生成，无需处理 |
| `pattern_detected` | info | 模式发现，非紧急，可后续讨论 |

**注意**：事件类型和分类并不总是 1:1。`info` 级别的 `insight_generated` 可能包含需要关注的建议，但不需要立即处理。按 `action_required` 筛选是安全的起点。

**完成标记**：全部待处理事件已打上分类标签。

### Step 4：分类处理

#### 4a. 陈旧结晶（flag_stale）

1. 读出结晶内容：`nmem memories show <crystal_id> -j`
2. 读出新源记忆：`nmem memories show <new_memory_id> -j`
3. 对比差异：
   - 新源记忆是否**增加了结晶未覆盖的信息**？
   - 新信息是**补充性**（结晶的核心内容仍然准确）还是**替代性**（结晶的核心结论已过时）？
4. 如果是补充性的，**执行更新**：`nmem memories update <crystal_id> -c '<new_content>'`
   - 保持原有结构，在末尾新增章节
5. 如果是替代性的，标记为 `deprecate`：`nmem memories deprecate <crystal_id> --supersede <new_memory_id>`

**完成标记**：每个陈旧结晶已处理——要么更新，要么标记废弃，要么向用户报告"无需处理"。

#### 4b. 重复记忆（flag_merge_candidate）

1. **读取全部候选记忆的完整内容**，不得只看标题就做决定：
   ```bash
   nmem memories show <id1> -j
   nmem memories show <id2> -j
   ```
2. 比较内容**完整度**（长度、覆盖的细节数量、是否包含验证方法等独有信息）
3. 保留最完整的一条
4. 删除其余：
   ```bash
   nmem memories delete <id_to_delete1> <id_to_delete2>
   ```

> **安全规则**：先读全文再删。标题相同的记忆可能内容略有差异，合并时取内容最完整的。不要盲目删除第一条。

**完成标记**：每组重复记忆只保留一条，其余已删除。

#### 4c. 矛盾裁定（flag_contradiction）

1. 读出两条矛盾记忆的完整内容
2. 识别两条记忆各自的核心论断——**矛盾的具体位置是什么**？
3. 通过 `ask_user_question` 向用户呈现：
   - 两条记忆的各自立场
   - 矛盾的具体位置
   - 你分析后的建议（如果有倾向性）
4. 获取用户裁定后，更新**被推翻的那条记忆**（用 `update` 修改内容使其与正确结论一致），或删除/标记废弃
5. **不要自行裁定矛盾**——涉及领域知识和设计决策，必须交给用户

**完成标记**：每组矛盾已获用户裁定，被推翻的记忆已更新或标记。

### Step 5：呈现清理报告

输出结构化摘要：

```markdown
## nmem 巡检报告

**服务状态**: ✅ xxx

### ✅ 已处理
- 陈旧结晶 × N — 已更新/已废弃
- 重复记忆 × N — 已合并
- 矛盾裁定 × N — 已裁定+更新

### ⏸️ 仍需用户裁定
- ...

### ℹ️ info 仅参考
- ...
```

### Step 6：可选 — 写入工作日志

询问用户是否需要将本次巡检记录写入 Obsidian 工作日志。

---

## 参考：分类决策树

```
action_required 事件
    │
    ├─ flag_stale ──────→ 读出结晶 + 新源记忆
    │                        ├─ 补充性信息 → update
    │                        └─ 替代性信息 → deprecate
    │
    ├─ flag_merge_candidate → 读全部全文
    │                        ├─ 保留最完整 → delete 其余
    │
    └─ flag_contradiction ──→ 读两条全文 → ask_user_question
                              └─ 依裁定 update 被推翻方
```

## 参考：命令速查

| 操作 | 命令 |
|------|------|
| 服务状态 | `nmem --json status` |
| 近期事件 | `nmem feed --days 7 -j` |
| 读取记忆 | `nmem memories show <id> -j` |
| 创建记忆 | `nmem memories add -t '<title>' -c '<content>'` |
| 更新记忆 | `nmem memories update <id> -t '<title>' -c '<content>'` |
| 删除记忆 | `nmem memories delete <id1> <id2>` |
| 废弃记忆 | `nmem memories deprecate <id>` |

## 参考：安全规则

1. **feed resolved=false 不可信**：feed 事件的 `resolved` 字段不会随底层记忆更新而自动翻转。核查时直接用 `memories show` 确认记忆当前状态。
2. **删重复前必须读全文**：标题相同不代表内容相同。读取全部候选记忆后保留最完整的一条。
3. **矛盾不自动删**：矛盾标记的两条记忆可能各有所据。`ask_user_question` 获取用户裁定后，更新被推翻方。
4. **结晶更新保持原结构**：在旧结晶末尾新增章节，不破坏原有结构。除非用户明确要求重建。
5. **使用 ask_user_question 批量呈现**：同类事件（如多个矛盾）合并到一次问卷中，不要逐条追问。
6. **区分调度器与数据处理工具**：知识库的记忆中可能出现关于 _BIN 路径原则的矛盾——注意确认矛盾双方讨论的是同一类工具。
