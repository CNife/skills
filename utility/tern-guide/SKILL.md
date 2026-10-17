---
name: tern-guide
description: Tern 终端编排、配置或排查时加载。
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

命令语法以 `tern COMMAND --help` 为准，全量词汇见 `tern help dev`（开发/脚本用，非稳定 API）。

## 功能

| 要做 | 命令 |
| --- | --- |
| 看现状 | `tern ls [--json]`、`tern process BLOCK`、`tern whoami --json` |
| 开 session / 新块 | `tern new session`、`tern split`、`tern new tab` |
| 跑命令 | `tern run BLOCK COMMAND...` |
| 取证据 | `tern capture BLOCK`（`--ansi` 留色、`--scrollback` 取历史、`--html` 给片段） |
| 等结果 | `tern wait BLOCK --until exit\|idle=MS` |
| 注入输入 | `tern send BLOCK text TEXT`、`keys COMBO`、`paste TEXT` |
| 搬运与聚焦 | `tern move`、`tern focus` |
| 保活 | `tern keep-open BLOCK on`（程序成功退出时默认关块） |
| 事件流 | `tern events [--filter KIND,...]`，JSON lines 持续输出 |
| 开文件 | `tern open [--split right\|down\|--tab\|--preview] PATH[:LINE[:COL]]` |

要点：

- **`idle=MS` 只等输出安静，不等于任务结束。** 实测：`wait --until idle=800` 在 `sleep 4` 跑到一半时就返回 rc=0，后续输出还没出现。构建、下载、训练这类间歇性输出的任务尤其会误判。
- **`--until exit` 才等程序退出**，并透传状态码（`124` 是超时）。它只在 block 由那条命令自己创建时才有意义（`tern split ... -- COMMAND`）。
- **判断「已完成」用哨兵**：让命令末尾写一个只有它能产生的东西，再轮询它。每次任务换全新路径（`mktemp`）—— 固定名字或 `$$` 都会撞上上一轮的残留。

  ```sh
  D=$(mktemp /tmp/task.XXXXXX)
  tern run "$B" "cargo test 2>&1; printf 'RC=%s\n' \$? > $D"
  until [ -s "$D" ]; do sleep 1; done; cat "$D"
  ```

  写文件比在屏幕里 grep 字符串可靠 —— 命令行本身也会出现在 capture 里，会自己匹配自己。
- **`send text` 只打字，不回车**；要执行再发 `keys Enter`。这正好用来先让人看见、再决定执行。
- 长任务的托管模型（`proc://`、远端、子代理）见 `long-running-tasks`；要人看得见、能接管、能跨设备看，就把命令开在 Tern 的 block 里。

**动窗口先认准目标**：`tern close BLOCK` 关单个 block，`tern kill session SESSION` 终止整个 session —— 两者层级不同，别把 block id 套进 `kill`。承载自己的 block 是 `$TERN_PANE`，读它、别动它。

## 配置

`~/.config/tern/settings.json`（`TERN_CONFIG_DIR` 可覆盖），手改后要重载；`tern ctl` 改的是运行中的窗口，并写回同一个文件。

| 要改 | 命令 |
| --- | --- |
| 字号 / 行高 | `tern ctl font 16`、`tern ctl adjust-cell-height 20%` |
| 字体（网格 / 界面 / 代码） | `tern ctl font-family`、`ui-font`、`code-font` |
| 主题 / 布局 / 密度 | `tern ctl theme`、`layout`、`style` |
| 透明度 / 窗口控件 | `tern ctl glass 60`、`decorations` |
| CSS | `tern ctl css reload [DIR]` 重读样式表 |
| 读当前值 | `tern ctl state` |

含空格的字体名要把引号**字面**传进去（`tern ctl font-family '"JetBrains Maple Mono"'`），否则被拆成多个参数报 `expected font-family`。默认值不必记，`tern ctl state` 会报当前生效值。

## 排查

| 症状 | 查 |
| --- | --- |
| `tern: command not found` | PATH；`tern --version` |
| `ctl` 报参数错或无响应 | 命令拼错（`tern help dev` 是全量词汇）、或窗口没有 control endpoint |
| 窗口命令落在错的窗口 | 显式 `--window KEY`，或看 `$TERN_WINDOW_KEY` |
| 关窗口后程序没了 | daemon 没起：`tern daemon --login` |
| `wait` 提前返回、结果不全 | `idle` 只看安静；改用哨兵或 `--until exit` |
| 远端连不上 | `tern remote doctor HOST` 逐项看 spec、relay、pkarr、host key、auth |
| 其他 | `~/.local/state/tern/logs/{tern,tern-daemon,tern-remote}.log` |
