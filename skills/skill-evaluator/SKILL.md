---
name: skill-evaluator
description: >
  Evaluate, compare, and recommend AI agent skills (Claude Code skills, MCP plugins, etc.).
  Use this skill whenever the user wants to find, assess, or choose skills for their AI agent workflow.
  Triggers include: "评估 skill", "找 skill", "对比 skill", "安装 skill", "skill 安全",
  "搜索 skill", "推荐 skill", "skill 哪个好用", "哪个 skill 更好", "safe skill",
  "evaluate skill", "compare skills", or any request involving skill discovery, security assessment,
  or installation decision. Make sure to use this skill whenever the user mentions evaluating,
  comparing, or choosing skills, even if they don't explicitly say "evaluate".
---

# Skill Evaluator

系统性地评估、对比和推荐 AI agent skills 的完整流程指南。

## 核心流程

整个评估流程分为四个阶段，按顺序执行：

```
搜索候选 → 信息收集 → 安全评估 → 对比推荐
```

---

## 阶段 1：搜索候选

### 1.1 关键词搜索

使用 Skills CLI 搜索相关关键词：

```bash
npx skills find [关键词]
```

例如：`npx skills find markitdown`、`npx skills find pdf`

### 1.2 查看 Leaderboard

访问 **https://skills.sh/** 查看热门 skills 排行榜，按安装量排序，了解社区验证程度。

### 1.3 记录候选列表

对每个候选 skill，记录以下信息：
- **skill 名称**（如 `owner/repo@skill-name`）
- **安装量**（反映社区信任度）
- **来源仓库**（GitHub repo）
- **skills.sh 详情页面 URL**

### 1.4 快速过滤

在深入分析前，先过滤掉明显不可靠的候选：

| 过滤条件 | 阈值 | 理由 |
|---------|------|------|
| 安装量 | < 20 | 太低可能不可靠或缺乏社区验证 |
| 最近提交 | > 4 个月 | 大概率已停止维护 |
| Agent Trust Hub | Fail | 明确安全问题，立即拒绝 |

**过滤后保留 2-5 个候选进入深度评估。** 如果过滤后只剩 1 个，同时搜索替代方案对比。

---

## 阶段 2：信息收集

**此阶段所有操作应并行执行**，以提高效率。

### 2.1 功能详情

访问每个 skill 的详情页面获取功能说明：

```
https://skills.sh/{owner}/{repo}/{skill-name}
```

关注点：
- 支持的文件格式/功能范围
- 安全审计结果（Agent Trust Hub / Socket / Snyk 评级）
- 依赖项和集成方式

### 2.2 仓库活跃度

访问 GitHub 仓库主页获取：

```
https://github.com/{owner}/{repo}
```

记录：
- **Stars 数量**（社区关注度）
- **Forks 数量**（协作活跃度）
- **Issues 数量**（问题跟踪活跃度）

### 2.3 更新频率

调用 GitHub API 获取最近提交：

```
https://api.github.com/repos/{owner}/{repo}/commits?per_page=5
```

从返回的 JSON 中提取 `commit.author.date` 字段，判断：
- **最近一次提交时间**（是否还在维护）
- **提交间隔**（每日/每周/每月/已停止）

### 2.4 信息汇总表

| 指标 | Skill A | Skill B | Skill C |
|------|---------|---------|---------|
| 安装量 | | | |
| Stars | | | |
| 最近提交 | | | |
| 更新频率 | | | |
| Agent Trust Hub | | | |
| Socket | | | |
| Snyk | | | |

---

## 阶段 3：安全评估（核心）

**此阶段最为关键**，决定 skill 是否可安全使用。

### 3.1 读取源码

**策略：多路径尝试，优先获取完整 SKILL.md 内容。**

**第一步：尝试 skills.sh 页面**
skills.sh 详情页面通常包含完整的 SKILL.md 内容，优先读取：
```
https://skills.sh/{owner}/{repo}/{skill-name}
```

**第二步：如果 skills.sh 内容不完整，尝试 GitHub Raw 路径**
常见 skill 目录结构（按优先级尝试）：
```
.agents/skills/{name}/SKILL.md      # 新项目标准
.claude/skills/{name}/SKILL.md      # Claude 兼容
.opencode/skills/{name}/SKILL.md    # OpenCode 专用
skills/{name}/SKILL.md              # 传统结构
```

分支名尝试顺序：`main` → `master` → `dev`

**第三步：读取引用文件**
如果 SKILL.md 中引用了其他文件（如 `reference.md`、`patterns.md`、`scripts/` 下的脚本），一并读取。

### 3.2 安全审计（自主审计 + 平台结果结合）

**自主审计（核心）：**
逐行阅读获取到的 SKILL.md 内容，按照 `reference.md` 中的检查清单逐项审计。

**致命红线（立即拒绝）：**
- SKILL.md 中包含 Base64 编码的隐藏指令
- 引导 agent 读取并外传环境变量（如 `$ANTHROPIC_API_KEY`）
- 附带可执行文件（`.sh`、`.py`、二进制）且功能与 skill 声称不符
- 条件激活逻辑（"当 X 条件满足时执行 Y"，Y 与 skill 功能无关）

**高风险（需明确警告用户）：**
- API Key 通过 CLI 参数传递（会出现在 shell 历史和 `ps` 输出中）
- 第三方插件/扩展系统默认启用且无验证
- 向外部服务发送文档内容（如 AI API 调用）但未明确告知用户

**中风险（需提醒用户注意）：**
- 文件路径未做穿越防护（`../../` 攻击）
- 输出文件覆盖已有内容无确认
- 递归目录遍历可能暴露意外文件

**安全加分项：**
- 明确列出安全最佳实践
- 提供安全实现示例（如沙箱模式、MIME 验证、大小限制）
- 插件默认禁用
- 使用环境变量而非 CLI 参数传递密钥

**平台审计结果（辅助验证）：**
结合 skills.sh 页面显示的 Agent Trust Hub / Socket / Snyk 评级，与自主审计结果交叉验证。如自主审计与平台结果冲突，以自主审计为准。

### 3.3 仓库信誉检查

- **维护者身份**：个人/组织/官方（如 `anthropics`、`vercel-labs`、`microsoft` 更可信）
- **提交验证状态**：是否有 Verified commits（GPG 签名）
- **Issue/PR 响应**：维护者是否积极回应社区反馈
- **安全修复历史**：是否有过安全漏洞修复记录

### 3.4 安全评分表

对每个 skill 给出安全评分（1-10 分）和风险等级：

| 维度 | 权重 | Skill A | Skill B |
|------|------|---------|---------|
| Prompt 注入 | 高 | | |
| 凭证处理 | 高 | | |
| 代码执行 | 高 | | |
| 数据外泄 | 高 | | |
| 文件系统 | 中 | | |
| 插件系统 | 中 | | |
| 混淆内容 | 中 | | |
| **总分** | | **?/10** | **?/10** |

---

## 阶段 4：对比与推荐

### 4.1 生成综合对比表

合并所有阶段信息，生成**单一综合对比表**：

| 指标 | Skill A | Skill B | Skill C |
|------|---------|---------|---------|
| 安装量 | | | |
| Stars | | | |
| 更新频率 | | | |
| Agent Trust Hub | | | |
| Socket | | | |
| Snyk | | | |
| 自主安全评分 | | | |
| 功能定位 | | | |
| 核心风险点 | | | |

**说明：** 分析过程中可使用多张中间表格辅助判断，但最终输出只保留这一张综合表。

### 4.2 分级推荐

根据用户优先级给出推荐：

**安全优先型用户：**
> 推荐 [Skill X]，理由：安全评分最高，Agent Trust Hub 通过，有完整安全文档

**功能优先型用户：**
> 推荐 [Skill Y]，理由：功能最全，更新最活跃，社区验证最多

**组合安装策略：**
> 推荐同时安装 [Skill X] + [Skill Y]，日常使用 Y，安全参考用 X

### 4.3 执行安装

用户确认后执行安装：

```bash
npx skills add {owner}/{repo}@{skill-name} -g -y
```

### 4.4 安装后验证

安装完成后执行以下验证：

1. **检查安装路径**：确认 skill 文件存在于 `~/.agents/skills/{skill-name}/`
2. **读取已安装 SKILL.md**：确认内容与预期一致
3. **确认安全结果**：安全审计结果与评估时一致
4. **提醒用户**：审查 SKILL.md 内容后再使用

---

## 输出格式

评估完成后，按以下结构输出：

1. **搜索摘要**：找到 N 个候选 skills
2. **综合对比表**：合并所有关键指标（安装量、活跃度、安全、功能）
3. **安全评估详情**：每个 skill 的风险点和加分项
4. **分级推荐**：按安全/功能/组合三个维度
5. **安装命令**：用户可直接复制执行的命令
6. **安装后验证结果**：确认安装成功且内容一致

---

## 参考文件指引

- **reference.md** → 安全评估检查清单（威胁分类、攻击模式、审计清单）
- **examples.md** → 完整评估案例（6 个 markitdown skills 实战对比）
- **patterns.md** → 最佳实践、常见陷阱、工具速查表
