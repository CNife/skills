# Tern 文档

文档站 <https://docs.stencil.so/tern/>，`toc.html` 是完整目录（82 页）。每页有 markdown 原文，把 `.html` 换成 `.md` 就能 grep；整本合并版 `print.html`（1.88 MB）。下文的路径相对文档站根。

站上 `scripts/` 各章讲的是**场景脚本**：经 `ctl` 逐条发送的动作，语法与 CLI 动词只是同名 —— `run "git status"` 是场景命令，`tern run BLOCK 'git status'` 才是窗口命令。两套词汇不要混查。

## 按需求跳转

| 要知道 | 章节 |
| --- | --- |
| 分层模型：window、daemon、host 各管什么 | `concepts/architecture` |
| 插件包结构、manifest 字段 | `concepts/packages`、`reference/manifest` |
| 插件何时加载/重载，host 半与 window 半各在哪跑 | `concepts/lifecycle` |
| 预算、JIT、日志级别、失败 toast | `concepts/runtime` |
| 插件能做什么、信任边界、哪些设置能关掉它 | `concepts/security` |
| 各平台能力差异 | `concepts/support-matrix` |
| 场景脚本语法（`ctl` 发的就是这套） | `scripts/index`、`scripts/harness` |
| 控制命令全表：`dump`/`tree`/`state`/`css`/`perf`/`trace`/`a11y` | `scripts/control` |
| 终端编排：Shell、`run`、`expect`、`ready`、字体与窗口控件 | `scripts/terminal` |
| tab、焦点、路径选择器、移动 pane | `scripts/navigation` |
| session 与 block：关闭策略、shell/agent block | `scripts/sessions` |
| 各 block 类型 | `scripts/browser`、`scripts/file`、`scripts/files`、`scripts/git`、`scripts/sqlite`、`scripts/notebook`、`scripts/board`、`scripts/screen`、`scripts/pip`、`scripts/procs`、`scripts/profile` |
| 远端 host、SSH、链接条件 | `scripts/remote` |
| 设置面板各页、预览主题、pinned host key | `scripts/prefs` |
| 设置项 | 无全表章节。`tern ctl state` 报当前值；插件里 `cx.settings:describe(key)` 给默认值与说明，读写见 `reference/api-window#settings-cx` |
| Surface Protocol | `protocol/index`，逐章 `transport`、`handshake`、`surfaces`、`documents`、`input`、`theme`、`operations` |
| 写自定义块与视图 | `guides/blocks`、`guides/views`、`elements/index`、`reference/ui` |
| 命令透镜 | `guides/lenses` |
| 键位、命令覆盖、内置动作、事件 | `guides/commands`、`reference/actions`、`reference/events` |
| 主题、CSS 变量、支持的 CSS | `guides/chrome`、`styles/index`、`styles/variables`、`styles/css` |
| 布局与工作区 | `guides/layout` |
| `tern.fs`/`tern.process` 的机器边界与存储 | `guides/io` |
| 文件与链接路由 | `guides/routing` |
| host hooks、spawn filter | `guides/hooks` |
| 插件 API | `reference/api-host`、`reference/api-window`、`reference/api-shared` |
| 上限（尺寸、条目数、超时） | `reference/limits` |
| 示例插件（含完整源码） | `examples/index` 及子页 |

## 排错

| 要知道 | 章节 |
| --- | --- |
| 失败显示在哪（toast、`tern plugin list`、日志） | `guides/debugging` 的 Where failures show |
| 日志路径与日志里每条消息的含义 | `guides/debugging#log-files` |
| 从脚本驱动一个窗口复现问题 | `guides/debugging` 的 Driving a window from a script |
| 错误消息与成因 | `reference/errors` |
| `tern plugin` 全家 | `reference/cli` |
| 术语 | `reference/glossary` |
