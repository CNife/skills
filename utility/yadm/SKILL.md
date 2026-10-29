---
name: yadm
description: 管理我的 yadm dotfiles：按个人约定处理仓库、alternates、transcrypt、bootstrap，并直接提交推送 main。
disable-model-invocation: true
---

# Yadm

这是 CNife 的 yadm 操作入口。yadm 是以 `$HOME` 为工作树的 Git 前端，并在 Git 之上提供 alternates、templates、权限、加密和 bootstrap；不要把它当成位于普通项目目录中的 Git 仓库。

## 操作约定

- 只在用户手动调用本技能时使用。
- 用户明确要求修改，即授权完成修改、验证、提交并推送 `main`；仅要求检查或解释时保持只读。
- 超出原请求，或涉及下文的高危操作时，单独说明影响并等待确认。
- 正常过程保持简洁，只报告结果；发现风险、歧义或需要决策时再解释原理。
- yadm dotfiles 仓库直接推送 `main`，这是对全局“远程仓库走 PR”规则的明确例外。

## 先认清现场

每次修改前先从环境取得事实，不缓存当前机器的路径和身份：

1. 用 `yadm introspect repo` 取得实际仓库，用 `yadm gitconfig --get core.worktree` 取得实际工作树。
2. 后续 yadm Git 命令以实际工作树为 `cwd`；Git pathspec 相对调用目录，而不是自动相对 `$HOME`。
3. 用 `yadm branch --show-current`、`yadm status --short` 和 `yadm list -a` 确认分支、改动及受管理文件。默认状态隐藏未跟踪文件，不能据此声称整个工作树干净。
4. 只查询明确且非敏感的单个配置键。禁止任何枚举完整仓库 config 的命令，包括 `yadm gitconfig --list`、带 `--show-origin` 的全量枚举和 yadm 环境中的 `git config -l`；这些命令可能输出 transcrypt 凭据。
5. 操作 yadm 仓库使用 `yadm <git-command>` 或 `yadm enter`，不用裸 `git`。

先把目标分为普通受管文件、alternate 源、alternate/template 生成目标、transcrypt 文件、yadm 配置或 bootstrap，再选择操作路径。已有无关改动属于用户现场，保留并避开。

## Alternates

生成目标不是配置的单一来源。目标为指向 `##` 变体的符号链接时修改其源；目标由模板生成时，从 `yadm list -a` 中找到对应的 `##template.*` 源。不要直接修改生成目标。

新增或调整变体时采用“最宽泛且足够准确”的条件：

1. `##default`：其余条件均不匹配时的共享回退。
2. `os`、`distro`、`distro_family`：可由系统稳定探测的平台差异，优先使用。
3. `class`：系统无法探测、且确实会复用的人工角色；按机器以 `yadm config local.class <role>` 设置。
4. `hostname`：真正绑定单台机器的差异，最后使用。

`local.*` 是本机覆盖值，不是自动探测结果；键未设置时仍要按 yadm 规则检查实际环境。yadm 将 WSL 识别为 `os.WSL`，普通 OS/架构来自 `uname`，发行版来自 `/etc/os-release` 等系统事实。

不维护固定主机清单，不为未来假想场景预建 class。先复用现有属性和值；需要新增 class、组合条件或重新划分现有变体时，说明最小方案并询问。发行版名称属于 `distro`，不把它重复建模成 class。

条件越多越容易改变候选得分；只添加表达真实差异所需的条件。模板优先于符号链接候选，`yadm.alt-copy=true` 和模板处理都可能覆盖普通目标；执行 `yadm alt` 或触发自动 alt 前检查目标及相关配置。

## 移出追踪与忽略本机变更

“本机不跟随某条受管路径”有三种互不等价的表达，先按目标选：

1. `yadm update-index --skip-worktree -- <path>`：保留追踪与本机内容，本机忽略后续改动；pull 不覆盖该文件，也不需要 `.gitignore`。这是“本机暂时不跟随”的默认手段。
2. `yadm rm --cached -- <path>`，并在仓库 `.gitignore` 登记该路径：彻底脱离追踪并保留本机文件。工作树是 `$HOME`，未跟踪文件数量巨大且默认状态看不见；不登记 `.gitignore` 时，防止重新纳入只能靠限定 add 范围（`yadm add -u` 或显式路径），不用 `add .`、`add -A`。
3. `##default` 与 `##hostname.*`/`##distro.*` alternates：本来就该按机器分裂的配置，用变体表达，不停止追踪。

`rm --cached` 生成的是删除提交，推送后对其他机器的后果是确定的：没有本地改动的机器 pull 时同名文件被删除，有本地改动的机器 pull 直接中止。用户要“先把当前版本同步到所有机器，再忽略变更”时，分两次提交：先提交内容并推送，等各机 pull 到位，再提交移出追踪。

## 配置边界

- `yadm config yadm.*` 管理 yadm 配置文件。
- `yadm config local.{class,arch,os,hostname,user,distro,distro-family}` 操作本机仓库配置，不随远程同步。
- `yadm gitconfig` 管理 yadm 仓库的 Git 配置。
- 即使 `~/.config/yadm/config` 由 yadm 跟踪，也不要把 `local.*` 写进它作为跨机器配置；yadm 会把这些键路由到本机仓库配置。

查询有效值而不是从文件副本推断。若 class 只是重复自动探测到的 OS 或发行版，视为冗余并在相关任务中提出清理，不主动批量重构现有 hostname 变体。

## 机密文件

本仓库唯一支持的加密方案是 transcrypt；不混用 `yadm encrypt`/`archive` 或 git-crypt。

默认只检查路径和结构，不读取或复述机密内容：

1. 用 `yadm check-attr filter diff merge -- <path>` 检查 `.gitattributes` 规则。
2. 用 `yadm gitconfig --get filter.crypt.required` 检查过滤器已启用。
3. 用 `yadm transcrypt --list` 对照实际纳入范围；属性声明不代表文件已经受管或已经加密。
4. 新机上的 transcrypt 凭据通过仓库外渠道恢复，不写入受管文件、提交、日志或答复。

只有用户明确要求安全审计时才读取具体内容。机密路径的 diff 可能经 textconv 显示明文；默认仅查看 `--stat`、`--name-status` 和属性状态。把敏感文件加入 Git 前先证明过滤器生效；敏感文件一旦以明文进入历史，事后增加属性不能消除泄漏。

## Bootstrap 与高危操作

新机恢复时先读取实际 yadm bootstrap，说明其依赖和影响，确认 transcrypt 凭据及过滤器已经由仓库外方式恢复；只有明确的新机初始化任务才执行 `yadm bootstrap`。

以下操作必须单独确认，不能因为用户已授权普通修改而直接执行：

- `yadm init -f`、`yadm clone -f`：会删除现有仓库，并可能强制解除子模块。
- `yadm decrypt`：会覆盖工作树中的同名文件；先运行 `yadm decrypt -l` 查看清单。
- `reset --hard`、可能覆盖文件的 `checkout`/`restore`，以及任何作用于整个工作树的恢复操作。
- 把受管文件移出追踪，或删除受管文件：推送后其他机器 pull 时会删掉本地同名文件，本地有改动时 pull 中止；先按「移出追踪与忽略本机变更」确认顺序。
- 重设 transcrypt、迁移加密体系、读取或输出机密内容。
- 未检查的 bootstrap、template 或 `alt-copy` 覆盖。

不要通过附加 `-f` 绕过报错。pre hook 可以主动中止命令；失败时先检查 yadm hooks 和原始退出状态，不把短路误判为 Git 故障。

## 修改与交付

1. 确认当前分支是 `main`。若不是，报告现场，不自动切换或覆盖工作树。
2. 修改正确的单一来源；对新文件先判定是否需要 alternate 或 transcrypt。
3. 用目标路径限定 `yadm status`、`yadm diff --stat`、`yadm diff --name-status` 和 `yadm add`，不卷入无关改动。
4. 暂存后用 `yadm diff --cached --stat` 和 `yadm diff --cached --name-status` 再次核对范围；机密文件按上节验证属性和 transcrypt 状态，不输出内容 diff。
5. 运行能直接覆盖配置行为的检查或实际命令。没有适合的运行验证时，说明限制，不用“看起来正确”代替证据。
6. 使用简短的一行中文提交信息提交：普通修改用 `yadm commit -m "<msg>" -- <paths>`；用 `rm --cached` 移出追踪后该路径已不在索引，pathspec 会退化成空提交，改用不带 pathspec 的 `yadm commit -m "<msg>"`（范围已由第 4 步的 `--cached` 核对保证）。提交为 0 条改动即说明 pathspec 或暂存状态有问题，先查 `yadm status`，不要重试同一条命令。随后 `yadm push origin main`。
7. 推送因远端分歧失败时保留现场并报告；不要自行 pull、rebase、reset 或强推。

行为无法解释时，以当前安装的 yadm、`yadm help` 和 [yadm 官方源码](https://github.com/yadm-dev/yadm) 为准。
