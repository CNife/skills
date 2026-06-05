# 本仓库

个人 AI agent 技能集合，发布到 `github.com/CNife/skills`。
目录结构和可用技能一览见 [README.md](./README.md)。

# 修改技能

## ⚠️ 黄金法则

这个仓库的技能**有两种身份**：

| 身份 | 路径 | 作用 |
|------|------|------|
| **仓库源码** | `code/skills/<category>/<name>/` | Git 管理 |
| **安装副本** | `.agents/skills/<name>/` | AI 运行时加载 |

**永远改仓库源码，不要碰安装副本。**

## 修改流程

### 1. 找到源码

仓库路径 `<category>/<name>/`，例如 `pi-agent/pi-trending/`。用 `fd <name>` 定位。

### 2. 改代码

两类文件，验证方式不同：

| 文件 | 怎么测试 |
|------|---------|
| `scripts/xxx.py` | 从仓库路径直接 `uv run --script scripts/xxx.py` |
| `SKILL.md` | 必须同步到安装副本后，AI 才会读到新指令 |

### 3. 测试脚本

从仓库路径运行，不依赖安装副本：

```bash
cd <repo-root>/<category>/<name>
uv run --script scripts/xxx.py
```

### 4. 同步 SKILL.md（改过时必须）

```bash
cp <repo-root>/<category>/<name>/SKILL.md ~/.agents/skills/<name>/SKILL.md
```

如果同时改了 `scripts/` 下的文件，也一并 cp。

### 5. 提交前检查

- [ ] `uv run ruff check --fix <category>/<name>/` 通过
- [ ] SKILL.md 的 `name:` 字段与目录名一致
- [ ] SKILL.md 的 `description:` 完整
- [ ] 改过 SKILL.md 时，已 cp 到安装副本
- [ ] 新技能或改过名时，同步更新了 README.md 技能表
