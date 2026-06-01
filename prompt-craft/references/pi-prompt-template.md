# Pi Prompt Template 格式参考

来源：<https://pi.dev/docs/latest/prompt-templates>

## 概述

Prompt template 是 Markdown 片段，可展开为完整提示词。在 pi 编辑器输入 `/名称` 即可调用，`名称` 即文件名（不含 `.md`）。

## 存放位置

| 位置 | 路径 | 作用域 |
|------|------|--------|
| 全局 | `~/.pi/agent/prompts/*.md` | 所有项目 |
| 项目 | `.pi/prompts/*.md` | 当前项目 |
| 包 | `prompts/` 目录或 `package.json` 中的 `pi.prompts` | 包内 |
| CLI | `--prompt-template <path>` | 临时 |

## 格式

```markdown
---
description: 简短描述模板用途
argument-hint: "[可选参数提示]"
---

提示词正文内容。
```

- 文件名即命令名。`review.md` → `/review`
- `description` 可选。缺省时取文件第一个非空行
- `argument-hint` 可选。在自动补全下拉中显示预期参数

### argument-hint 写法

- `<尖括号>` 表示必选参数
- `[方括号]` 表示可选参数

示例：

```markdown
---
description: 从 URL 审查 PR，含结构化 issue 和代码分析
argument-hint: "<PR-URL>"
---
```

补全下拉显示效果：

```text
→ pr   <PR-URL>     — 从 URL 审查 PR，含结构化 issue 和代码分析
```

## 参数

模板中可使用位置参数：

| 写法 | 含义 |
|------|------|
| `$1`, `$2`, ... | 第 N 个参数 |
| `$@` 或 `$ARGUMENTS` | 所有参数（空格连接） |
| `${@:N}` | 从第 N 个起所有参数 |
| `${@:N:L}` | 从第 N 个起的 L 个参数 |

示例：

```markdown
---
description: 创建组件
---

创建名为 $1 的 React 组件，功能：$@
```

使用：`/component Button "onClick 处理" "支持 disabled"`

## 加载规则

- `prompts/` 目录下的模板发现是非递归的
- 如需子目录模板，需通过 `prompts` 设置或包清单显式添加
