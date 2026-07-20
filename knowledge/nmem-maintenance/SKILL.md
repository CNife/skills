---
name: nmem-maintenance
description: 周期性巡检 Nowledge Mem 知识库，分类处理后台积累的待办事件。
disable-model-invocation: true
---

# nmem-maintenance - Nowledge Mem 知识库巡检

核心是**先分类再处理，关键裁定交给用户**--巡检 nmem 知识库时按此原则处理后台积累的待办事件。

## 前置条件

- `nmem` CLI 可用且已登录

## 流程

### Step 1：服务健康检查

确认 nmem 服务在线，记录版本和模式：

```bash
nmem status -j
```

**健康响应**：`status: ok`，有 `server_version`，`database: true`。

**完成标记**：服务在线，或已报告故障。

### Step 2：拉取近期事件

```bash
nmem feed --days 7 -j
```

筛选出 `severity: action_required` 且 `resolved: false` 的事件。

> ⚠️ feed 事件的 `resolved` 字段是**只读标记**--即使底层记忆已修复，该字段也不会自动变为 true。后续核查必须直接用 `nmem memories show` 验证记忆状态，不能依赖事件状态。

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

**完成标记**：每个陈旧结晶已处理--要么更新，要么标记废弃，要么向用户报告"无需处理"。

#### 4b. 重复记忆（flag_merge_candidate）

1. **读取全部候选记忆的完整内容**，不得只看标题就做决定：

   ```bash
   nmem memories show <id1> -j
   nmem memories show <id2> -j
   ```

2. **列出该主题的要点清单**（候选记忆共同涉及的核心知识点，如关键步骤、触发条件、验证方法、边界条件），逐条标注每条记忆是否覆盖。

3. **判断簇内关系并分支处理**：

   - **完全重复**（内容基本一致）：保留最早或 importance 最高的一条，删其余。

   - **近重复可合并**（同主题、详略互补同一组要点）：选覆盖要点最全的一条作基底，把其余记忆的**独有要点**用 `update` 补入基底，再删其余。不要只按字数留最长--最长者可能漏关键要点，须对照要点清单逐条确认覆盖度。覆盖度相当时优先保留 `review_status=CONFIRMED` 的版本。

     ```bash
     nmem memories update <base_id> -c '<补全后的完整内容>'
     nmem memories delete <id_to_delete1> <id_to_delete2>
     ```

   - **互补保留**（两条各有显著独有核心信息，粒度不同而非详略差异）：各保留，不合并。尝试建 link 记录关系：

     ```bash
     nmem memories link add <id_a> <id_b> --type references   # 可选增强
     ```

     link 失败（如 422 active memories 限制）不阻塞--记录后继续，两条各自保留即达成核心目标。**判断边界**：只有"显著独有核心信息"才算互补，琐碎细节差异不算；拿不准时保守只留一条。

4. **search gate（强制）**：每簇处理完跑主题词搜索，确认无遗漏成员。重复清单常漏标或用约数，必须用 search 兜底：

   ```bash
   nmem memories search '<主题词>' -j --limit 20
   ```

   命中清单外同主题成员时，读全文判断归属：属本簇则纳入上面分支处理（多为补全后删除）；若是独立综合记忆（粒度不同、含大量独有内容）则保留并在报告标注。

> **安全规则**：先读全文再删。标题相同的记忆可能内容略有差异，须读全文确认后再决定合并或删除。

**完成标记**：每组重复记忆已处理（合并补全保留最完整一条 / 互补保留多条 / 确认无需处理），且已跑 search gate 确认无遗漏。

#### 4c. 矛盾裁定（flag_contradiction）

1. 读出两条矛盾记忆的完整内容
2. 识别两条记忆各自的核心论断--**矛盾的具体位置是什么**？
3. 以结构化方式向用户呈现矛盾（同类矛盾合并到一次问卷）：
   - 两条记忆的各自立场
   - 矛盾的具体位置
   - 你分析后的建议（如果有倾向性）
4. 获取用户裁定后，按裁定执行：更新被推翻方、删除/标记废弃、或保留双方（裁定同成立）
5. 矛盾裁定必须交给用户--涉及领域知识和设计决策

> 注意：矛盾裁定前先确认双方讨论的是同一对象或同一类工具，避免范畴不同造成的伪矛盾。

**完成标记**：每组矛盾已获用户裁定并按裁定执行--更新被推翻方、删除/废弃、或保留双方（裁定同成立）。

### Step 5：呈现清理报告

输出结构化摘要：

```markdown
## nmem 巡检报告

**服务状态**: ✅ xxx

### ✅ 已处理

- 陈旧结晶 × N - 已更新/已废弃
- 重复记忆 × N - 已合并
- 矛盾裁定 × N - 已裁定（含保留双方）

### ⏸️ 仍需用户裁定

- ...

### ℹ️ info 仅参考

- ...
```

**完成标记**：清理报告已呈现，涵盖全部已处理项与待裁定项。
