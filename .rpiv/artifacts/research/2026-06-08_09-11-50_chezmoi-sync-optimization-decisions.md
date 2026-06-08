---
date: 2026-06-08T09:11:50+0800
author: 蔡涛
commit: 546f004
branch: main
repository: skills
topic: "根据 /home/cnife/.pi/agent/sessions/--home-cnife--/2026-06-08T01-04-22-809Z_019ea4c2-6119-7cfd-98df-6d4e2822d85c.jsonl 会话文件和 /home/cnife/.rpiv/artifacts/handoffs/2026-06-08_09-08-10_chezmoi-sync-skill-review.md 文档，决策优化 @utility/chezmoi-sync/ 技能的要点"
tags: [research, codebase, chezmoi-sync, dotfiles, skill-optimization]
status: complete
last_updated: 2026-06-08T09:44:17+0800
last_updated_by: 蔡涛
last_updated_note: "Added follow-up correction for chezmoi diff direction vs refresh claim"
---

# Research: chezmoi-sync 优化决策要点

## Research Question

根据 `/home/cnife/.pi/agent/sessions/--home-cnife--/2026-06-08T01-04-22-809Z_019ea4c2-6119-7cfd-98df-6d4e2822d85c.jsonl` 会话文件和 `/home/cnife/.rpiv/artifacts/handoffs/2026-06-08_09-08-10_chezmoi-sync-skill-review.md` 文档，决策优化 `utility/chezmoi-sync/` 技能的要点。

## Summary

优化顺序应以安全红线为第一约束：先解决“用户授权单文件 `apply`，脚本实际执行全量 `chezmoi apply`”的问题。`SKILL.md` 将 `chezmoi apply` 定义为覆盖 home 且不可撤销的危险方向，但 `re_add()` 在 `--direction source` 分支调用无路径 `_chz("apply")`，与 `SKILL.md` 中单文件命令示例不一致。

第二优先级是 pull 后状态正确性：`pull()` 在 git pull 成功后直接返回，没有任何显式 chezmoi 层面的状态刷新；实战会话证明后续 `status/diff` 可能与实际 git HEAD 文件内容不对齐。第三优先级是降低误判概率：修正源路径时间戳查找、标注 UTC、在 `__needs_decision` 中一次性提供足够决策上下文。`private_` 场景和提交信息主要是文档/可读性问题，发布同步路径则是后续落地风险。

## Detailed Findings

### Safety Redline: 单文件授权被扩大为全量 apply

- `utility/chezmoi-sync/SKILL.md:31-40` 定义安全三层模型：`git pull/push` 和 `re-add` 自动执行，`apply` 是源到 home 的危险覆盖操作，必须人工确认。
- `utility/chezmoi-sync/SKILL.md:153-159` 在 `__needs_decision` 非空时展示单文件命令：`re-add .config/xxx --direction source`。用户心智是“对这个文件做源到 home”。
- `utility/chezmoi-sync/scripts/chezmoi-sync.py:346-357` 会按 `paths` 参数筛出 `targets`，因此外层循环看起来确实是按文件处理。
- `utility/chezmoi-sync/scripts/chezmoi-sync.py:416-418` 在 `direction == "source"` 时调用 `_chz("apply")`，没有传 `fp` 或 `home_path`。脚本随后只把当前 `fp` 加进 `applied` 列表，输出也只报告当前文件。
- 这个不一致不是普通 UX 问题，而是授权边界问题：用户确认的是单个文件，实际命令可能覆盖所有 chezmoi 差异文件。它应作为第一优先级。

### Pull 后状态不对齐会诱导错误决策

- `utility/chezmoi-sync/scripts/chezmoi-sync.py:131-141` 的成功路径执行 `_chz_git("pull", "--autostash", "--rebase")` 后打印 `__pull_ok=1` 并直接 `return`。
- `utility/chezmoi-sync/scripts/chezmoi-sync.py:137-141` 成功路径没有显式调用任何 chezmoi 层面的刷新命令；冲突路径 `utility/chezmoi-sync/scripts/chezmoi-sync.py:147-220` 也只在 git/rebase 层处理冲突。
- 后续状态检测走 `utility/chezmoi-sync/scripts/chezmoi-sync.py:246-248` 的 `_chz("status")`，diff 展示走 `utility/chezmoi-sync/scripts/chezmoi-sync.py:270-276` 的 `_chz("diff")`。
- 会话文件中 `re-add` 输出 `__needs_decision=.config/rpiv-pi/models.json` 后，agent 多次检查实际 home、`chezmoi cat`、git HEAD，最终在会话行 35 的 reasoning 中判断 chezmoi source state 可能与磁盘 git 文件不一致。
- 这里的研究结论只确认“当前脚本没有显式刷新且实战出现不对齐”；具体应使用哪个 chezmoi 命令刷新仍需单独验证。

### Diff 方向标注不足放大 stale 状态的影响

- `utility/chezmoi-sync/scripts/chezmoi-sync.py:276` 只在标题中输出一次 `chezmoi diff（源 → home）`。
- `utility/chezmoi-sync/scripts/chezmoi-sync.py:281-285` 从 `diff --git a/... b/...` 提取文件名，但不把 `a/`、`b/` 的语义输出给 agent。
- `utility/chezmoi-sync/scripts/chezmoi-sync.py:300-308` 的逐文件摘要和 diff 详情只显示 `+/-` 行数与彩色 diff，不再提示 `-` 属于源还是 home。
- `utility/chezmoi-sync/SKILL.md:128-133` 只要求执行 diff，没有给 agent 解析方向的规则。
- 会话行 23、27、31、35 展示了 agent 在 diff、真实文件、git HEAD 之间多轮自我校正，说明方向标注和状态不对齐组合后会显著增加误判成本。

### 源路径时间戳查找依赖脆弱 fallback

- `utility/chezmoi-sync/scripts/chezmoi-sync.py:381-384` 为 chezmoi 目标路径构造了标准和 `private_` 两个源路径变体。
- `utility/chezmoi-sync/scripts/chezmoi-sync.py:387` 只遍历 `src_path_variants[:1]`，第二个变体永远不会执行。
- 当前构造还把 `dot_` 简单前缀到整个路径上，例如 `.config/...` 会被构造成 `dot_.config/...`，而 chezmoi 源路径通常是 `dot_config/...`。
- `utility/chezmoi-sync/scripts/chezmoi-sync.py:393-398` 通过 `git ls-files -- *<basename>` 模糊匹配兜底；会话中 `models.json` 存在多个同名候选时，这种 `matched[0]` 行为可能取到错误文件。
- `utility/chezmoi-sync/scripts/chezmoi-sync.py:402-442` 用该 `source_commit_ts` 决策自动 re-add 或进入 `__needs_decision`。错误时间戳会直接改变安全方向判断。

### 时间戳算法正确，展示缺少时区

- `utility/chezmoi-sync/scripts/chezmoi-sync.py:68-70` 使用 `datetime.fromtimestamp(ts, tz=timezone.utc)`，但格式化字符串不包含 `UTC` 或 offset。
- `utility/chezmoi-sync/scripts/chezmoi-sync.py:402-406` 输出 `home mtime` 和 `源仓库提交` 时没有时区标注。
- `utility/chezmoi-sync/scripts/chezmoi-sync.py:432` 的比较基于 Unix epoch，算法本身不受时区影响。
- 会话行 22-23 中 agent 明确对 `2026-06-05 01:54` 和 `2026-06-05 13:42` 的本地/UTC 含义发生推理分叉；这是展示层误导，而不是比较算法错误。

### `__needs_decision` 的上下文不足造成多轮交互

- `utility/chezmoi-sync/scripts/chezmoi-sync.py:457-465` 在需要人工决策时只输出文件列表和 `__needs_decision` 标记。
- `utility/chezmoi-sync/SKILL.md:153-160` 让 agent 展示差异并询问方向，但没有要求一次性展示双方实际内容、时间戳、推荐方向和红线说明。
- 会话行 22-38 中出现了 `re-add` 输出、第一次询问、用户要求“先看看内容”、agent 额外 cat/ls/git show、多轮校正、第二次询问、最终执行 `--direction source` 的完整链路。
- 体验优化应服务于安全决策：减少来回不是为了快，而是为了让用户在确认 apply 前看到足够完整且不冲突的上下文。

### `private_` 场景：提交正确，解释不足

- `utility/chezmoi-sync/SKILL.md:151` 说明 re-add 后 chezmoi 可能根据权限自动添加 `private_` 前缀，commit 会包含旧文件删除和新文件添加。
- `utility/chezmoi-sync/SKILL.md:221` 把 `private_` 重命名列为安全规则中的正常处理。
- `utility/chezmoi-sync/scripts/chezmoi-sync.py:286-291` 会把 `old mode/new mode` 显示为权限变化，但不能区分这是 re-add 引入还是 pull 引入。
- `utility/chezmoi-sync/scripts/chezmoi-sync.py:480` 的 `git add -A` 会覆盖删除和新增，因此提交正确性已有保障。
- handoff 在 `/home/cnife/.rpiv/artifacts/handoffs/2026-06-08_09-08-10_chezmoi-sync-skill-review.md:48-49` 记录了此次是 pull 进来的 `dot_` 到 `private_` 场景；当前 SKILL.md 对这一方向缺少说明。

### Exit Code 契约需要更精确

- `utility/chezmoi-sync/scripts/chezmoi-sync.py:37-39` 定义 `EXIT_HAS_CHANGES = 2`，注释说明它不是错误。
- `utility/chezmoi-sync/scripts/chezmoi-sync.py:263-264` 在 `status()` 有变更时退出 2；`utility/chezmoi-sync/scripts/chezmoi-sync.py:467-468` 在 `re_add()` 需决策时退出 2。
- `utility/chezmoi-sync/SKILL.md:117` 对 status 使用 `|| true`，会同时吞掉退出码 2 和真实错误退出码。
- `utility/chezmoi-sync/SKILL.md:142-143` 的默认 `re-add` 示例没有 `|| true`，所以 `__needs_decision` 可能被执行环境标为工具错误。
- 结构化 stdout 标记已经表达了细粒度状态，但当前 shell 契约没有精确区分“需处理”和“真失败”。

### 发布同步路径是落地风险

- `/home/cnife/personal_code/skills/AGENTS.md:14-17` 规定改仓库源码，不碰安装副本，但把安装副本写成 `.agents/skills/<name>/`。
- `/home/cnife/personal_code/skills/AGENTS.md:43-49` 的同步示例也指向 `~/.agents/skills/<name>/SKILL.md`。
- 当前技能实际加载路径来自 handoff：`/home/cnife/.rpiv/artifacts/handoffs/2026-06-08_09-08-10_chezmoi-sync-skill-review.md:59-62` 指向 `/home/cnife/.pi/agent/skills/chezmoi-sync/`。
- 本次只读比较显示 `utility/chezmoi-sync/` 与 `/home/cnife/.pi/agent/skills/chezmoi-sync/` 当前无差异；后续修改仍应先改源码，再同步安装副本。
- `AGENTS.md` 按仓库规则只能读不能改；如果要修同步路径，应另行提议或在技能本地文档中补足。

## Code References

- `utility/chezmoi-sync/SKILL.md:31-40` — 安全三层模型，定义 apply 为危险且需人工确认。
- `utility/chezmoi-sync/SKILL.md:128-133` — Step 4 只执行 diff，没有 diff 方向解析说明。
- `utility/chezmoi-sync/SKILL.md:138-160` — Step 5 智能 re-add 与 `--direction home/source` 单文件示例。
- `utility/chezmoi-sync/SKILL.md:163-176` — commit 阶段和提交信息规则。
- `utility/chezmoi-sync/SKILL.md:212-221` — 安全规则，包含永不自动 apply、默认 re-add、`private_` 正常处理。
- `utility/chezmoi-sync/scripts/chezmoi-sync.py:44-58` — `_chz` 和 `_chz_git` 命令封装。
- `utility/chezmoi-sync/scripts/chezmoi-sync.py:68-70` — UTC 时间格式化但无时区输出。
- `utility/chezmoi-sync/scripts/chezmoi-sync.py:131-141` — pull 成功路径，git pull 后直接返回。
- `utility/chezmoi-sync/scripts/chezmoi-sync.py:226-264` — status 双层级检测与退出码 2。
- `utility/chezmoi-sync/scripts/chezmoi-sync.py:268-321` — diff 摘要、权限模式和前 60 行详情输出。
- `utility/chezmoi-sync/scripts/chezmoi-sync.py:322-468` — re_add 目标解析、路径查找、方向分支、结构化输出。
- `utility/chezmoi-sync/scripts/chezmoi-sync.py:381-398` — `src_path_variants[:1]` 与 `git ls-files` basename fallback。
- `utility/chezmoi-sync/scripts/chezmoi-sync.py:416-418` — `--direction source` 无路径 apply。
- `utility/chezmoi-sync/scripts/chezmoi-sync.py:472-518` — commit 使用 `git add -A` 和自动提交消息。
- `/home/cnife/.pi/agent/sessions/--home-cnife--/2026-06-08T01-04-22-809Z_019ea4c2-6119-7cfd-98df-6d4e2822d85c.jsonl:22` — `re-add` 输出 `__needs_decision`、UTC 风格时间戳和退出码 2。
- `/home/cnife/.pi/agent/sessions/--home-cnife--/2026-06-08T01-04-22-809Z_019ea4c2-6119-7cfd-98df-6d4e2822d85c.jsonl:23` — agent 第一次解释时间戳与方向，并询问用户。
- `/home/cnife/.pi/agent/sessions/--home-cnife--/2026-06-08T01-04-22-809Z_019ea4c2-6119-7cfd-98df-6d4e2822d85c.jsonl:35` — agent 通过实际文件/git HEAD 检查后识别 source state 不对齐。
- `/home/cnife/.pi/agent/sessions/--home-cnife--/2026-06-08T01-04-22-809Z_019ea4c2-6119-7cfd-98df-6d4e2822d85c.jsonl:37-38` — 用户确认 `apply` 后执行 `--direction source`，脚本输出只显示 1 个文件。
- `/home/cnife/.rpiv/artifacts/handoffs/2026-06-08_09-08-10_chezmoi-sync-skill-review.md:30-49` — handoff 记录 7 个不完善点。
- `/home/cnife/personal_code/skills/AGENTS.md:14-17` — 仓库源码/安装副本双身份规则。
- `/home/cnife/personal_code/skills/AGENTS.md:43-49` — 当前同步路径示例指向 `~/.agents/skills`。

## Integration Points

### Inbound References

- `utility/chezmoi-sync/SKILL.md:92-107` — agent 先 fetch，再根据 `__new_remote` 决定是否 pull。
- `utility/chezmoi-sync/SKILL.md:114-124` — agent 读取 `status` 的结构化标记决定是否进入 diff/re-add。
- `utility/chezmoi-sync/SKILL.md:128-160` — agent 调用 diff/re-add，并在 `__needs_decision` 时向用户询问方向。
- `utility/chezmoi-sync/SKILL.md:163-193` — agent 调用 commit/push/verify 完成同步。
- `/home/cnife/.rpiv/artifacts/handoffs/2026-06-08_09-08-10_chezmoi-sync-skill-review.md:18-23` — 实战审查引用安装副本中的 SKILL 和脚本。

### Outbound Dependencies

- `utility/chezmoi-sync/scripts/chezmoi-sync.py:44-49` — 所有 chezmoi 子命令通过 `subprocess.run(["chezmoi", *args])` 调用。
- `utility/chezmoi-sync/scripts/chezmoi-sync.py:53-58` — 所有 git 操作通过 `chezmoi git --` 调用。
- `utility/chezmoi-sync/scripts/chezmoi-sync.py:68-70` — 时间展示依赖 Python `datetime` 和 `timezone.utc`。
- `utility/chezmoi-sync/scripts/chezmoi-sync.py:507` — commit 阶段依赖 Typer 的交互确认。
- `utility/chezmoi-sync/SKILL.md:50-56` — 运行依赖包括 chezmoi、git、uv、stat/date/grep。

### Infrastructure Wiring

- `utility/chezmoi-sync/SKILL.md:84-87` — Step 0 用 `$SKILL_DIR/scripts/chezmoi-sync.py` 检查运行时脚本存在。
- `utility/chezmoi-sync/SKILL.md:94-193` — 所有命令通过 `uv run --script "$SKILL_DIR/scripts/chezmoi-sync.py"` 执行。
- `/home/cnife/personal_code/skills/AGENTS.md:31-49` — 仓库源码测试和安装副本同步流程。
- `/home/cnife/.rpiv/artifacts/handoffs/2026-06-08_09-08-10_chezmoi-sync-skill-review.md:59-62` — 当前实战运行路径是 `/home/cnife/.pi/agent/skills/chezmoi-sync/`。

## Architecture Insights

- 技能的核心架构是“SKILL.md 编排 + Typer 单脚本执行 + stdout 结构化标记反馈给 agent”。脚本不是独立 CLI 产品，而是 agent 工作流的执行内核。
- 安全模型已经写在 SKILL.md 和 FRD 里，但脚本实现没有完全维护“人工确认的授权范围”。因此优化时应优先验证每条危险命令的实际作用域是否等于用户确认的作用域。
- `pull()` 和 `status/diff` 分别处在 git 层与 chezmoi 层。当前流程把 git 层成功等同于 chezmoi 层可读状态，这正是会话中 stale diff 的来源。
- 方向判断链条跨越 4 个输入：home mtime、源文件 commit time、chezmoi diff、用户确认。任一输入展示错误或映射错误，都会把压力传导到 apply 红线上。
- `private_` 权限重命名是 chezmoi 正常行为，`git add -A` 能保证提交完整；真正的问题是路径时间戳查找和文档没有覆盖 pull 引入的 rename 场景。
- 退出码 2 与 stdout 标记是同一语义的两种表达。当前 `|| true` 让 agent 易用性上升，但错误隔离下降。
- 仓库源码和安装副本双身份是技能仓库的系统性风险；本技能有脚本文件，不能只同步 SKILL.md。

## Precedents & Lessons

3 similar past changes analyzed.

### Precedent: 一键同步 chezmoi dotfiles

**Commit(s)**: `bc69683` — "feat(chezmoi-sync): 一键同步 chezmoi dotfiles" (2026-06-05)
**Blast radius**: 4 files across 2 layers
  `chezmoi-sync/SKILL.md` — initial skill doc
  `.rpiv/artifacts/discover/2026-06-05_09-43-37_chezmoi-sync-skill.md` — initial FRD
  `README.md` — skill table update
  `.rumdl.toml` — lint config

**Follow-up fixes**:

- `d14a171` — "fix(chezmoi-sync): 用 chezmoi git -- 替代裸 git 命令" (2026-06-05) — direct git invocation needed alignment with chezmoi conventions.
- `940c81d` — "feat(chezmoi-sync): 加 compatibility 和 skip_confirm/commit_msg 参数" (2026-06-05) — configuration surface followed initial creation.
- `5b3b433` — "feat(chezmoi-sync): 重构为 agent-friendly 流程，添加 fast-path 和 stash 冲突处理" (2026-06-05) — agent workflow ergonomics required follow-up.
- `085e4f5` — "增强 chezmoi-sync：双层级检测、智能 re-add、安全性三层模型" (2026-06-05) — original git-only detection missed chezmoi layer changes.

**Lessons from docs**:

- `.rpiv/artifacts/discover/2026-06-05_09-43-37_chezmoi-sync-skill.md` — initial scope emphasized full sync, pull before local commit/push, and source state as git repository.

**Takeaway**: First versions under-modeled chezmoi-specific state; later fixes added structure but also increased the need for safety-contract verification.

### Precedent: 双层级检测 + 智能 re-add + 安全三层模型

**Commit(s)**: `085e4f5` — "增强 chezmoi-sync：双层级检测、智能 re-add、安全性三层模型" (2026-06-05)
**Blast radius**: 3 files across 2 layers
  `utility/chezmoi-sync/SKILL.md` — workflow and safety model rewrite
  `utility/chezmoi-sync/scripts/chezmoi-sync.py` — new 569-line Typer script
  `.rpiv/artifacts/discover/2026-06-05_21-43-11_chezmoi-sync-skill-enhancement.md` — enhancement FRD

**Follow-up fixes**:

- No committed fix yet for the 2026-06-08 handoff findings.

**Lessons from docs**:

- `.rpiv/artifacts/discover/2026-06-05_21-43-11_chezmoi-sync-skill-enhancement.md` — apply is the only red direction, must be manually confirmed; direction uncertainty defaults to re-add.

**Takeaway**: The safety model is already the canonical design constraint; implementation should be checked against it before UX polish.

### Precedent: AGENTS.md 修改技能流程

**Commit(s)**: `546f004` — "添加 AGENTS.md，指导 AI 修改技能的流程" (2026-06-05)
**Blast radius**: 1 file across 1 layer
  `AGENTS.md` — repository rules for source vs installed skill copies

**Follow-up fixes**:

- None found.

**Lessons from docs**:

- `/home/cnife/personal_code/skills/AGENTS.md` — must edit repository source, then sync installed copy.

**Takeaway**: The repository process recognizes dual copies, but its install path example does not match the current pi runtime path observed in the handoff.

### Composite Lessons

- Prioritize safety contracts over flow smoothness. The redline is not “ask before apply” in the abstract; it is “execute exactly the scope the user confirmed”.
- Treat git-layer and chezmoi-layer state as separate integration points. A git pull success marker is insufficient evidence that later `chezmoi status/diff` is aligned.
- Keep stdout markers, exit codes, and SKILL.md command snippets in sync. Agent workflows depend on all three.
- Use real execution transcripts as regression seeds. The 2026-06-08 session exposed stale diff, timezone ambiguity, `private_` rename, and full-apply scope in one path.

## Historical Context (from `.rpiv/artifacts/`)

- `.rpiv/artifacts/discover/2026-06-05_09-43-37_chezmoi-sync-skill.md` — original chezmoi-sync FRD.
- `.rpiv/artifacts/discover/2026-06-05_21-43-11_chezmoi-sync-skill-enhancement.md` — enhancement FRD for dual-layer detection and smart re-add.
- `/home/cnife/.rpiv/artifacts/handoffs/2026-06-08_09-08-10_chezmoi-sync-skill-review.md` — execution handoff recording 7 observed issues.

## Developer Context

**Q (`utility/chezmoi-sync/scripts/chezmoi-sync.py:416-418`, `utility/chezmoi-sync/SKILL.md:153-159`, `utility/chezmoi-sync/SKILL.md:35`): `--direction source` currently calls pathless `_chz("apply")`, while the SKILL.md command shape implies a single-file apply and the safety model marks apply as the red direction. Which optimization priority should lead?**
A: 先解决单文件授权却全量 apply 的问题。

**Q (`.rpiv/artifacts/research/2026-06-08_09-11-50_chezmoi-sync-optimization-decisions.md`): Scan complete — write the doc, or adjust first?**
A: Write the doc (Recommended).

## Related Research

- None found.

## Open Questions

- What exact chezmoi-level command should refresh state after a successful git pull? The current code gap is verified, but the correct refresh primitive requires separate validation.
- Should the repository-level `AGENTS.md` install-copy path be updated from `~/.agents/skills/` to the observed `/home/cnife/.pi/agent/skills/` path? The file is read-only under current repository instructions, so this needs explicit approval.
- Should `EXIT_HAS_CHANGES` remain a non-zero exit code, or should scripts rely only on stdout markers for non-error state? The research identifies the contract mismatch but does not choose the implementation strategy.
- What regression fixture should represent the full-apply risk: multiple pending chezmoi differences, then user confirms apply for only one path.

## Follow-up Research 2026-06-08T09:44:17+0800

### User Feedback

Reviewer feedback on the original line 38 asked: `chezmoi diff` already compares the source repository and home; why would there be a refresh problem?

### Correction

The feedback is valid. The earlier explanation that `git pull` caused an established chezmoi source-state refresh problem is not sufficiently supported by the transcript. It should be treated as superseded by this follow-up.

`chezmoi diff --help` says the command prints the difference between the target state and the destination state. Its default diff arguments are `{{ .Destination }}` then `{{ .Target }}`. In practical unified diff terms, the observed `-` lines correspond to the destination/home side and the `+` lines correspond to the target/source-derived side.

This matches the session transcript rather than contradicting it: session line 26 shows home had `alibaba-cn/qwen3.7-max` and `chezmoi cat` showed source-derived content had `deepseek/deepseek-v4-pro`; session line 30 shows diff as `- alibaba-cn/qwen3.7-max` and `+ deepseek/deepseek-v4-pro`. Those two facts are consistent if `chezmoi diff` is read as destination/home to target/source, not as source to home.

### Revised Implication

The confirmed issue is not “pull 后必须刷新 chezmoi source state”. The confirmed issue is that the script and research interpreted diff direction too loosely:

- `utility/chezmoi-sync/scripts/chezmoi-sync.py:276` labels the section `chezmoi diff（源 → home）`, which is ambiguous for `+/-` semantics.
- The handoff at `/home/cnife/.rpiv/artifacts/handoffs/2026-06-08_09-08-10_chezmoi-sync-skill-review.md:31` asserted `a/ = 源仓库、b/ = home 目录`; the live command help and transcript do not support using that as the decision rule.
- Any future change should prioritize clearer diff labeling: `-` is current destination/home, `+` is target/source-derived content, unless `--reverse` is used.

### Superseded Finding

The original “Pull 后状态不对齐会诱导错误决策” section should no longer be used as a confirmed finding. It may remain as an open reproduction question only: if someone can produce a minimal transcript where `chezmoi diff`, `chezmoi cat`, actual home content, and source file content disagree after accounting for Destination vs Target semantics, then the refresh hypothesis can be reopened.
