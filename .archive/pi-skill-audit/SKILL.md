---
name: pi-skill-audit
description: >
  Audit pi agent skills usage frequency, identify unused skills, and clean up
  safely. Queries pi session logs for skill invocation records (skill tags +
  read SKILL.md calls), cross-references against globally installed skills,
  categorizes by usage into high/medium/low/unused tiers, and drives cleanup
  via bunx skills remove. Use whenever the user mentions skill management,
  cleanup, or usage analysis — including "技能使用频率", "哪些技能用的多",
  "整理技能", "删掉不用的技能", "技能审计", "skill audit", "看看技能",
  "用哪些技能", "used skills", "unused skills", "清理", "clean up skills".
  Also use when the user has many installed skills and you suspect some are
  unused, or when reviewing what skills are worth keeping. This is the
  go-to skill for any pi skill management task. Not for Hermes agent skills
  — use audit-hermes-agent-skills instead.
---

# Pi Agent Skill Audit

审计 pi agent 全局安装的技能（`~/.agents/skills/`），找出哪些高频使用、哪些从未用过，帮助用户做清理决策。

## 为什么需要这个技能

Pi agent 的技能是逐步累积的。新的实验性技能装上去后可能只用一两次、同类技能可能互相覆盖（比如 smart-search 替代了 tavily 全家桶）、有些技能装完就忘了。如果不定期清理：

- 系统 prompt 被大量不相关技能的 description 占满，影响模型对真正有用技能的判断
- 用户花精力维护的技能库实际只有一半在用
- 新装技能被淹没在长尾列表里

这个技能帮你把"凭感觉删"变成"看数据删"。

## 工作流

```text
统计调用 → 交叉分析 → 报告展示 → 用户决策 → 删除 → 验证
```

### 第一步：运行审计脚本

```bash
uv run --script scripts/audit.py
```

脚本自动扫描 `~/.pi/agent/sessions/` 下的全部会话日志，统计每个技能被调用的次数。输出包含：

- **总览**：已安装技能数、有调用记录的技能数、总调用次数
- **四档分类**：高频 / 中频 / 低频 / 未使用
- **可视化柱状图**：直观对比各技能使用量
- **删除命令**：直接给出可 copy-paste 的 `bunx skills remove` 命令

统计原理：pi 的会话日志里记录了两类 skill 调用痕迹——用户主动加载的 `<skill name="...">` 标签，以及 agent 自己通过 read 工具读取的 `skills/*/SKILL.md`。两者合一才能反映真实使用情况。

### 第二步：分析报告，给建议

对照脚本输出，分析每个未使用或低频技能的清理价值：

| 类别 | 判定 | 建议 |
|:---|:---|:---|
| 🔥 高频 (≥10 次) | 硬需求 | 无条件保留 |
| ✅ 中频 (3-9 次) | 稳定使用 | 保留 |
| ⚠️ 低频 (1-2 次) | 偶尔用到 | 读 SKILL.md 了解用途，让用户判断 |
| ❌ 未使用 (0 次) | 从未调过 | 建议删除，附理由 |

分析未使用技能时，重点关注这几类：

1. **被同类覆盖** — 比如 tavily 系列已被 smart-search 取代
2. **场景已不存在** — 之前某个项目需要，项目结束了技能也闲置了
3. **装完就没用过** — 安装时觉得将来会用，实际上再没碰过
4. **面向不同的 agent** — 某些技能是为 Hermes/Claude Code 设计的，pi 用不上

对每个建议删除的技能，先读它的 SKILL.md 了解功能（1 分钟），然后在报告中给出清理理由。这样用户不是盲目删除。

### 第三步：执行删除

用户确认后，用 bunx skills 删除：

```bash
# 单个删除
bunx skills remove <skill-name> -g -y

# 批量删除（同系列场景）
bunx skills remove tavily-cli tavily-crawl tavily-search -g -y
```

参数：

- `-g` — 全局安装（`~/.agents/skills/`）
- `-y` — 跳过交互确认

### 第四步：验证

```bash
ls ~/.agents/skills/ | grep <skill-name>
# 无输出 = 已删除
```

## 分析技巧

### 如何判断技能是否被同类覆盖

这是最常见的无用技能场景。当发现多个技能面向同一个需求领域时：

1. **检查各自调用次数** — 调用次数多的那个是用户实际在用的
2. **对比 description** — 覆盖面更广的通常胜出（如 smart-search 替代多个专用搜索源）
3. **向用户确认** — "这个技能看起来被 X 替代了，要删吗？"

### 如何评估技能价值

高调用次数不直接等于高价值：

- **think 调用最多**（40+）— 因为每做一次方案规划就用一次，这是高频短流程
- **obsidian-diary 调用很多**（30+）— 因为每次会话结束都触发，这是高频常规流程
- **git-master 调用 10 次**— 虽然次数少，但每次都是关键时刻（提交/推送/回滚），价值很高

所以真正该删的是：**调用次数为 0，且没有明确理由保留的技能**。

## 注意事项

- 先展示报告再删除，不要跳过用户确认步骤
- 删除前读一遍 SKILL.md，解释该技能是干什么的，用户记不清时有用
- 同系列技能（如 tavily-\*、tavily-\*）一次列出供用户批量决策
- bunx skills remove 会同时清理全局和所有 agent 的引用，不需要额外步骤
- 本技能只负责 pi agent 技能，Hermes 技能请用 `audit-hermes-agent-skills`

## 脚本参考

审计脚本在 `scripts/audit.py`，使用 PEP 723 内联依赖，`uv run --script` 直接执行。

支持自定义路径：

```bash
uv run --script scripts/audit.py --sessions /custom/sessions/dir --skills /custom/skills/dir
```

如果脚本输出为空，检查：

1. `~/.pi/agent/sessions/` 是否存在且有 `.jsonl` 文件
2. `~/.agents/skills/` 是否存在且有技能目录
