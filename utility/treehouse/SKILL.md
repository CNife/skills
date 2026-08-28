---
name: treehouse
description: Use when a task needs a Git worktree or mentions Treehouse; follow Treehouse's pooled acquisition, lease, status, and return workflow.
---

# Treehouse

Treehouse 是 Git worktree 的管理入口：需要使用 Git worktree 时，从 Treehouse 获取、使用和回收，不直接手工管理池中的目录。

## 心智模型

- **池**：Treehouse 为每个仓库维护一组可复用的 worktree。`get` 优先复用安全的空闲槽位，不满足条件时再创建槽位。
- **安全复用**：可复用槽位必须空闲、无租约、内容干净且能证明已合并到重置目标；否则保留在池中。
- **占用**：进程正在目录中运行、短生命周期操作保留、以及持久租约是三种不同状态。一个进程消失，不代表租约已经释放。
- **租约**：`get --lease` 把槽位持久标记为当前调用方持有；即使目录里没有进程，后续 `get` 和清理也会避开它，直到 `return`。
- **回收**：`return` 会检查残留进程和脏状态，确认后将槽位重置并放回池中。状态无法证明安全时，目录会留在原处。
- **起点**：新建或复用的槽位按默认分支目标准备，不承接当前目录的未提交改动；复用意味着重置到该目标，而不是保留现场。

## 当前 Agent 的用法

Agent 使用非交互路径：

```sh
worktree="$(treehouse get --lease)"
```

后续工具调用把 `$worktree` 作为工作目录。完成后先把需要保留的改动提交、生成补丁或移出该目录，再执行：

```sh
treehouse return "$worktree"
```

交互式终端才使用不带 `--lease` 的 `treehouse get`；它会打开 subshell。

## 状态不符时

把 `treehouse status` 作为池状态的事实来源：

- 当前目录在默认 `~/.treehouse/`（或配置的池根目录）下时，先确认它确实是本次 Agent 持有的槽位；已持有就继续使用，不重复获取。
- 显示为 `leased` 或 `in-use` 且归属不明时，保留该槽位并换用明确可获取的槽位；路径和进程存在不等于你拥有它。
- 显示为 `dirty`，或归还提示有未提交改动时，先保存交付物，再完成归还。
- `return` 因残留进程或无法验证而失败时，保留 worktree，处理自己启动的进程后重试；状态未确认前不强制清理。

## 排查

遇到无法解释的行为或命令失败时，查阅 [Treehouse 源码](https://github.com/kunchenguid/treehouse)；原作者是 [Kun Chen](https://github.com/kunchenguid)。
