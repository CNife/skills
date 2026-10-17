---
name: tern-guide
description: 操作 Tern（pane/block/host 编排、把命令开在可见窗格、配置与排查）时加载。
---

# Tern

原生终端：程序按 Tern Surface Protocol 描述界面，Tern 原生绘制 Mermaid、LaTeX、diff 和网页。程序跑在 daemon 里，窗口关掉也活着。

## 先在 Tern 里

```sh
tern --version                              # 装没装、哪个版本
echo "${TERM_PROGRAM:-} ${TERN_PANE:-}"     # 是不是 Tern 的 pane
tern whoami --json                          # 身份链：谁、在哪个 host 上
```

`TERM_PROGRAM=tern` 且 `TERN_PANE` 有值，说明当前 shell 就在 Tern 的 pane 里。窗口级命令按 `$TERN_WINDOW_KEY` 找窗口；这个变量可能为空，此时落到第一个窗口 —— 多窗口时显式 `--window KEY` 才可靠。

## 核心概念

**层级**：`host → session → tab → block`。host 是跑程序的那台机器；session 归 daemon 所有、跨窗口存活；tab 是一组并排的 block；block 既可以是跑程序的面板，也可以是原生界面块（file、git、sqlite、notebook、browser、board）。

**寻址**：`BLOCK` 接受 id、`@focused`、标题或程序名；`SESSION/BLOCK` 跨 session 定位。id 稳定、可复现，名字会重名。

**两套入口**：窗口命令（`ls`/`new`/`split`/`run`/`send`/`capture`/`wait`/`move`）经 daemon 作用于 session；`tern ctl` 经 control endpoint 面向窗口 UI（设置、布局、主题、状态）。前者在装了 Tern 的任何 shell 里可用，后者需要窗口在跑。

## 功能

| 要做 | 命令 |
| --- | --- |
| 看现状 | `tern ls`、`tern ls --json`、`tern process BLOCK`、`tern whoami --json` |
| 开 session | `tern new session NAME --cwd DIR [--keep-open] [-- COMMAND...]` |
| 开新块 | `tern split BLOCK right\|down [--cwd DIR] [--keep-open] [-- COMMAND...]`、`tern new tab [SESSION]` |
| 跑命令 | `tern run BLOCK COMMAND...`（打字加回车） |
| 取证据 | `tern capture BLOCK [--html\|--ansi] [--scrollback] [--surfaces]` |
| 等结果 | `tern wait BLOCK --until idle=MS\|exit --timeout SECONDS` |
| 注入输入 | `tern send BLOCK text TEXT`、`keys COMBO`、`paste TEXT` |
| 搬运与聚焦 | `tern move BLOCK left-of\|right-of\|above\|below BLOCK`、`move BLOCK tab N\|new-tab`、`tern focus BLOCK` |
| 保活 | `tern keep-open BLOCK on\|off`（程序成功退出时默认关块） |
| 事件流 | `tern events [--filter KIND,...]`，JSON lines 持续输出 |
| 开文件 | `tern open --split right\|--tab\|--preview PATH[:LINE[:COL]]` |

要点：

- **`--until exit` 用程序状态码返回**，`124` 表示超时。`--until prompt` 在 0.9.2 上实测稳定超时，等命令结束用 `idle=<ms>` 或 `exit`。
- **`send text` 只打字，不回车**；要执行再发 `keys Enter`。这正好用来先让人看见、再决定执行。
- **`capture` 是交证据的正路**：`--ansi` 保留颜色，`--scrollback` 取历史，`--html` 给可渲染片段。
- 长任务的托管模型（`proc://`、远端、子代理）见 `long-running-tasks`；要人看得见、能接管、能跨设备看，就把命令开在 Tern 的 block 里。

改窗口前先认准目标：`tern ls` 拿 id 再动手，`kill` 与 `close` 都按 id 走。自己所在的 block 是 `$TERN_PANE`，操作别的 block 时把它留着。

## 配置

`~/.config/tern/settings.json`（`TERN_CONFIG_DIR` 可覆盖），手改后要重载；`tern ctl` 改的是运行中的窗口，并写回同一个文件。

| 要改 | 命令 |
| --- | --- |
| 字号 | `tern ctl font 16` |
| 字体 | `tern ctl font-family '"Family Name"'`（含空格时引号要字面传入）、`ui-font`、`code-font` |
| 行高 | `tern ctl adjust-cell-height 20%` |
| 主题 | `tern ctl theme dark <name>` |
| 布局 | `tern ctl layout rail\|float\|tiles\|studio` |
| 透明度 | `tern ctl glass 60` |
| 窗口控件 | `tern ctl decorations system\|lights\|buttons` |
| CSS | `tern ctl css reload [DIR]` 重读样式表 |
| 读当前值 | `tern ctl state`（`font`、`font_family`、`theme`、`layout`、`hosts`…） |

## 排查

| 症状 | 查 |
| --- | --- |
| `tern: command not found` | PATH；`tern --version` |
| `ctl` 报参数错或无响应 | 命令拼错（`tern help dev` 是全量词汇）、或窗口没有 control endpoint |
| 窗口命令落在错的窗口 | 显式 `--window KEY`，或看 `$TERN_WINDOW_KEY` |
| 关窗口后程序没了 | daemon 没起：`tern daemon --login` |
| `wait --until prompt` 一直超时 | 换 `--until idle=<ms>` 或 `--until exit` |
| 远端连不上 | `tern remote doctor HOST` 逐项看 spec、relay、pkarr、host key、auth |
| 其他 | `~/.local/state/tern/logs/{tern,tern-daemon,tern-remote}.log` |
