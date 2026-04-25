# 工作日志变体规则

## Vault 路径

- 根目录：由配置文件 `~/.config/cnife-skills/obsidian-diary.json` 中的 `vaults.work.base` 决定
- 日志目录：`工作日志/YYYY/MM/`
- 文件命名：`YYYY年M月D日星期X.md`（如 `2026年4月17日星期五.md`）
- 模板文件：`工作日志/日志模板.md`

## 模板内容

新日志文件从模板复制，模板仅包含一个 `# 待办事项` 标题和 tasks 查询块。

## 格式规则

### 标题结构

- `# 子系统名` → 一级标题，粒度到具体子系统（如 `# OneReason MCP` 而非 `# OneReason`）
- `## 具体任务` → 二级标题，按独立交付物拆分（两个功能 = 两条，框架搭建 ≠ 工具实现）

### 任务状态 Emoji

- ✅ 已完成
- 🔄 进行中
- 🐛 Bug修复
- 🔍 调研
- 🚀 已部署
- 🤝 会议/协作

### 内容规则

每个交付物 1-2 行。参考风格：简洁、只写结果、以子系统为维度。

**好的写法：**
- `✅ execute_cypher：只读查询 + 权限管控 + 结果序列化，经真实数据库验证`
- `✅ 单阶段 Dockerfile（256MB），MCP 端点响应符合预期`
- `✅ 确认 taplo-pre-commit 为 tamasfe/taplo 官方镜像仓库，非 fork`

**应避免的写法：**
- `❌ 完成 Wave 2-4：权限管控、序列化、工具实现`
- `❌ 4 轮最终验证全部 APPROVE，18 个测试用例全部通过`
- `❌ 创建 .dockerignore：排除 .git/.venv/__pycache__/.env/tests 等 12 项`
- `❌ 已提交并推送到 dev 分支`
- `❌ 沉淀 5 条项目规则到 AGENTS.md`

## 待办更新规则

1. **新增待办放到今天**：不修改历史日志中的待办列表，新任务记录在当天日志
2. **Obsidian 链接引用之前的待办**：用 `[[日期#标题]]` 格式链接到历史待办（文件名不带路径和 `.md`）
3. **之前的待办也要更新**：历史待办状态变化时，同步更新原日志中的 `[ ]` → `[x]`，并添加完成日期和链接

## 示例结构

文件开头固定为 `# 待办事项` + tasks 查询块，之后按子系统分组：

````text
# 待办事项
```tasks
not done
```

# Genos Reg Server

## 正式环境部署

🚀 完成 prod 后端部署（10.200.50.22，Debian 11，NVIDIA A40 46GB）：
- 清理冗余数据 128GB，磁盘使用率 95% → 27%
- Git 远程切换为 SSH 方式，切换到 dev-caitao 分支
- uv sync 安装 Python 3.12.12 + torch 2.5.1+cu124 + 82 个依赖包
- flash-attn whl GLIBC 不兼容，降级到 v2.7.4.post1
- 后端启动成功，health check 通过，8 个 API 端点就绪

## 文档整理

- 新增 docs/prod-server-maintenance.md：生产服务器维护手册
- 部署计划归档：plans/prod-backend-deployment.md → docs/finished-plans/
- 创建 MR !16（dev-caitao → main），指派 @caitao，评审 @吴雯
````
