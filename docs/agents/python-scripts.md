# Python 脚本

本仓库脚本的约定：改任何 `scripts/*.py` 前先读这一页。

## 单文件自足

每个脚本用 PEP 723 内联元数据声明依赖（`# /// script` 块），**不依赖仓库级 Python 配置**——本仓库没有 `pyproject.toml`，也不要创建。运行一律 `uv run --script scripts/<file>.py`。

- Python 底线：`requires-python = ">=3.14"`。
- 与 `.ruff.toml` 的 `target-version = "py314"` 绑定：改一处必须改另一处，否则 pyupgrade 类改写会产出旧解释器解析不了的语法。
- 可执行脚本 shebang：`#!/usr/bin/env -S uv run --script`。`-S` 必需——Linux 的 env 把 `uv run` 当成带空格的一个程序名，缺了它 `./script.py` 直接报 127。

## lint / format

统一交给 ruff，配置在 `.ruff.toml`，规则取舍的理由写在那份文件的注释里（默认集 + RUF 全族、全角标点白名单的来历都在那里，不在此复述）。

- 快速自检：`ruff check --fix <category>/<name>/`
- 提交前全量：`pre-commit run --all-files`（pre-commit 经 `uv tool install pre-commit` 安装，不依赖项目环境）
