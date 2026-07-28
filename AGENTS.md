# 本仓库

个人 AI agent 技能集合。目录和可用技能见 [README.md](./README.md)。

## 修改技能

所有编辑落在 `<category>/<name>/` 仓库源码；`~/.agents/skills/<name>/` 仅是运行时副本。

1. 用 `fd <name>` 定位源码。
2. 修改并验证：脚本在技能目录运行 `uv run --script scripts/<file>.py`；执行 `uv run ruff check --fix <category>/<name>/`。
3. 推送到 main 后，运行 `skill-manager --global source update && skill-manager --global sync` 同步安装副本（GitHub 仓库为唯一源）。
4. 完成前确认 `name:` 与目录名一致、`description:` 完整；目录结构变动时更新 README.md。

## 存档技能

不再维护的技能移入 `.archive/<name>/`，并在 `SKILL.md` frontmatter 加 `metadata.internal: true`。重新安装存档技能用 `skill-manager --global enable --all CNife/skills <name>`。

## 按需参考

- 创建、读取或分流 GitHub issue 时，读 `docs/agents/issue-tracker.md` 和 `docs/agents/triage-labels.md`。
- 使用 wayfinder（map/child ticket 工作流）时，读 `docs/agents/wayfinder.md`。
- 使用 domain-modeling、CONTEXT 或 ADR 时，读 `docs/agents/domain.md`。
