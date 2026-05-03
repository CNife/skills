---
name: skill-evaluator
description: >
  Evaluate, compare, recommend, discover, and install AI agent skills.
  Use whenever the user wants to find, assess, choose, or install skills — even if they don't explicitly say "evaluate".
  Triggers: "评估/找/对比/安装/推荐 skill", "skill 安全", "哪个 skill 好用", "找个技能",
  "给 agent 装技能", "safe skill", "evaluate/compare/install skill", or any request involving
  skill discovery, security assessment, installation, or cross-agent compatibility.
---

# Skill Evaluator

系统性地评估、对比、推荐、搜索和安装 AI agent skills 的完整流程指南。

## 参考文件

本 skill 依赖以下参考文件，按需读取：

- **references/reference.md** → 安全评估检查清单（威胁分类、攻击模式、审计清单、评分标准）
- **references/patterns.md** → 工具限制与绕过策略、常见陷阱、安装最佳实践
- **references/examples.md** → 完整评估案例（markitdown 对比 + fallback 策略演示）

**关键**：多个常用工具存在限制，在阶段 3 读取源码前务必查阅 `references/patterns.md` 中的绕过策略。

## 核心流程

整个流程分为五个阶段，按顺序执行：

```
来源分类 → 搜索候选 → 信息收集 → 安全评估 → 对比推荐与安装
```

阶段 0 利用 Hermes Curator 和技能仓库追踪文件，将每个已安装技能精准归类到来源，据此差异化审计深度。

---

## 阶段 0：来源分类（Curator 数据集成）

**目标**：在执行评估前，将每个已安装技能精确归类到来源，区分首次方（agent-created）和第三方（skills.sh / SkillHub / bundled）代码。

### 0.1 分类映射表

Hermes 中技能来源由安装路径 + 追踪文件共同确定：

| 来源 | 物理路径 | 追踪文件 | 示例 |
|------|---------|---------|------|
| **Skills.sh** | `~/.agents/skills/<name>/` | `~/.agents/.skill-lock.json` — 含 `source: "vercel-labs/skills"`、`sourceType: "github"`、`installedAt` | skills.sh 安装的社区技能 |
| **SkillHub** | `~/.hermes/skills/<name>/` | `~/.hermes/skills/.hub/lock.json` — 含 `source: "skills.sh"`、`identifier`、`scan_verdict` | SkillHub 来源的技能 |
| **Bundled** | `~/.hermes/skills/<name>/` | `~/.hermes/skills/.bundled_manifest` — 哈希映射表 | Hermes 内置技能 |
| **Agent-created** | `~/.hermes/skills/<name>/` | 不在以上任何文件中 | 用户/Agent 创建的自定义技能 |

### 0.2 分类执行脚本

执行以下命令一次性获取全部分类：

```bash
python3 << 'PYEOF'
import json
from pathlib import Path

hermes_skills = Path.home() / ".hermes" / "skills"
agents_skills = Path.home() / ".agents" / "skills"

# 1. Skills.sh 安装: ~/.agents/.skill-lock.json
skills_sh = {}
lock = Path.home() / ".agents" / ".skill-lock.json"
if lock.exists():
    data = json.loads(lock.read_text())
    for name, info in data.get("skills", {}).items():
        skills_sh[name] = {
            "source": info["source"], "source_type": info["sourceType"],
            "installed": info["installedAt"], "updated": info["updatedAt"]
        }

# 2. SkillHub 安装: .hub/lock.json
skillhub = {}
hub_lock = hermes_skills / ".hub" / "lock.json"
if hub_lock.exists():
    data = json.loads(hub_lock.read_text())
    for name, info in data.get("installed", {}).items():
        skillhub[name] = {
            "source": info["source"], "identifier": info["identifier"],
            "installed": info["installed_at"]
        }

# 3. Bundled: .bundled_manifest
bundled = set()
manifest = hermes_skills / ".bundled_manifest"
if manifest.exists():
    for line in manifest.read_text().strip().splitlines():
        name = line.split(":")[0]
        bundled.add(name)

# 4. Agent-created: ~/.hermes/skills/ 中剩余的技能
agent_created = {}
if hermes_skills.exists():
    for d in hermes_skills.iterdir():
        if d.is_dir() and (d / "SKILL.md").exists():
            name = d.name
            if name in bundled or name in skillhub:
                continue
            if name.startswith("."):
                continue
            agent_created[name] = {}

# 5. ~/.agents/skills/ 中的所有技能都是 skills.sh 安装
if agents_skills.exists():
    for d in agents_skills.iterdir():
        if d.is_dir() and (d / "SKILL.md").exists():
            name = d.name
            if name not in skills_sh:
                skills_sh[name] = {"source": "unknown", "installed": "unknown"}

print("=== Skills.sh 安装 ===")
for n in sorted(skills_sh):
    print(f"  {n:40s} source={skills_sh[n]['source']}")
print(f"\n=== SkillHub 安装 ===")
for n in sorted(skillhub):
    print(f"  {n:40s} source={skillhub[n]['source']}")
print(f"\n=== Bundled ===")
for n in sorted(bundled):
    print(f"  {n}")
print(f"\n=== Agent-created ({len(agent_created)}) ===")
for n in sorted(agent_created):
    print(f"  {n}")
PYEOF
```

### 0.3 分类规则

| 条件 | 结论 | 评估含义 |
|------|------|---------|
| 在 `~/.agents/skills/` 中 | Skills.sh 安装 | 标准第三方评估（完整审计） |
| 在 `.hub/lock.json` 中 | SkillHub 安装 | 标准第三方评估（完整审计） |
| 在 `.bundled_manifest` 中 | Bundled | 跳过审计，标注"Bundled" |
| 以上都不是 | Agent-created | 缩减审计（仅检查致命红线） |

### 0.4 Curator 活跃度数据

对 agent-created 技能，从 `hermes curator status` 获取活跃度指标：

```bash
hermes curator status 2>&1
```

输出中包含每个 agent-created 技能的 `activity`、`use`、`view`、`patches`、`last_activity`。这些数据进入评估表，作为"健康度"指标。技能被频繁使用和修补 → 高可信度。

也可以用结构化数据源 `~/.hermes/logs/curator/<latest>/run.json` 获取更完整的 consolidation 关系和归档历史。

---

## 阶段 1：搜索候选

### 1.0 前置检查：本地已安装技能

执行阶段 0 的来源分类，获取所有已安装技能的来源归属，然后：

- **如果有同类技能已安装**：直接读取已安装的 SKILL.md，标注其来源（agent-created / skills.sh / SkillHub / bundled），跳过外部搜索和完整安全评估（首次方技能仅检查致命红线）
- **如果是 agent-created 技能**：从 curator status 获取活跃度数据，作为 "健康度" 参考
- **如果是已归档的 umbrella 子技能**：告知用户该技能已被合并到 umbrella，推荐使用 umbrella

### 1.1 多源并行搜索

**同时发起两个搜索，不等彼此**，以最快找到候选：

- **Skills.sh**（全球生态，社区验证多）：
  ```bash
  bunx skills find [关键词]
  ```
  **注意**：经常超时（60s+）。Agent 的 shell/terminal 工具自带超时机制，并行发起 SkillHub 搜索即可，谁先完成用谁的结果。

- **SkillHub**（中国优化，速度快，中文技能多）：
  ```bash
  skillhub search [关键词]
  ```

### 1.2 记录候选列表

对每个候选 skill，记录：名称（`owner/repo@skill-name`）、安装量、来源（skills.sh / SkillHub）、GitHub 仓库 URL（从 `owner/repo` 直接推导：`https://github.com/owner/repo`）。

### 1.3 快速过滤

| 过滤条件 | 阈值 | 理由 |
|---------|------|------|
| 安装量 | < 20 | 太低可能不可靠或缺乏社区验证 |
| 最近提交 | > 4 个月 | 大概率已停止维护 |
| Agent Trust Hub | Fail | 明确安全问题，立即拒绝 |

**过滤后保留 2-5 个候选进入深度评估。** 如果过滤后只剩 1 个，同时搜索替代方案对比。

---

## 阶段 2：信息收集

**此阶段所有操作应并行执行**，以提高效率。

### 2.1 功能详情与仓库活跃度

从技能名字 `owner/repo@skill-name` 直接定位 GitHub 仓库：`https://github.com/{owner}/{repo}`

关注点：
- Stars/Forks/Issues 数量（社区关注度）
- 支持的文件格式/功能范围
- License 类型
- 依赖项和集成方式

### 2.2 更新频率

调用 GitHub API：`https://api.github.com/repos/{owner}/{repo}/commits?per_page=5`

从 `commit.author.date` 判断最近一次提交时间和提交间隔。详见 `references/patterns.md` 中的 GitHub API 元数据获取。

**注意**：如果 skill 是 SkillHub 独占（无公开 GitHub 仓库），更新频率和活跃度指标标记为 N/A，在可信度评级中相应降级。

### 2.3 信息汇总表

| 指标 | Skill A | Skill B | Skill C |
|------|---------|---------|---------|
| 安装量 | | | |
| Stars | | | |
| 最近提交 | | | |
| 更新频率 | | | |
| Agent Trust Hub | | | |
| Socket | | | |
| Snyk | | | |
| **来源分类** | | | |
| **Curator 活跃度** | | | |

新增的行含义：
- **来源分类**：Skills.sh / SkillHub / Bundled / Agent-created。从阶段 0 的映射表直接获取。
- **Curator 活跃度**：仅对 agent-created 技能生效，格式 `activity=X use=Y patches=Z last=Nd ago`。高活跃度（activity > 10）说明技能被频繁使用和修补，可信度更高。

---

## 阶段 3：安全评估（核心）

**此阶段最为关键**，决定 skill 是否可安全使用。

### 3.1 读取源码

**策略：根据来源选择不同的路径和审计深度。**

- **Skills.sh 技能**：直接用 `git clone --depth 1` 克隆 GitHub 仓库（`owner/repo` 已知），避免 `web_extract` 被拦截：

  ```bash
  TMPDIR=$(mktemp -d) && git clone --depth 1 "https://github.com/{owner}/{repo}.git" "$TMPDIR"
  ```

  克隆后查找 SKILL.md，常见目录结构（按优先级）：`.agents/skills/{name}/` → `.claude/skills/{name}/` → `.opencode/skills/{name}/` → `skills/{name}/` → 根目录。**完整安全审计（7 维）。**

- **SkillHub 技能**：默认下载到临时目录：

  ```bash
  TMPDIR="/tmp/skillhub-tmp-$$" && mkdir -p "$TMPDIR"
  skillhub --dir "$TMPDIR" install <slug>
  ```

  **完整安全审计（7 维）。**

- **Agent-created 技能**：已在本地安装，直接读取 `~/.hermes/skills/<category>/<name>/SKILL.md`。从 curator status 获取活跃度数据作为健康度参考。**缩减审计（仅检查致命红线）。**

- **Bundled 技能**：已在本地安装，跳过审计，标注 "Bundled — Hermes 内置"。

读取 SKILL.md 后，如果它引用了其他文件（如 `reference.md`、`scripts/` 下的脚本），一并读取。完成后清理临时目录。

### 3.2 检查硬编码路径

SkillHub 下载的 skill 常包含作者本机的硬编码路径。审计时必须检查 SKILL.md 和 scripts/ 中是否有 `find /mnt/c/Users/...`、`/root/.openclaw` 等路径。

如果路径硬编码为作者机器特有路径，在报告中注明"路径需适配当前环境"，不建议直接安装。

### 3.3 安全审计

**逐行阅读 SKILL.md，按照 `references/reference.md` 中的检查清单逐项审计。** 以下是要点摘要：

**致命红线（立即拒绝）：**
- Base64 编码的隐藏指令
- 引导 agent 读取并外传环境变量（如 `$ANTHROPIC_API_KEY`）
- 附带可执行文件且功能与 skill 声称不符
- 条件激活逻辑（"当 X 条件满足时执行 Y"，Y 与 skill 功能无关）

**高风险（需明确警告用户）：**
- API Key 通过 CLI 参数传递（会出现在 shell 历史和 `ps` 输出中）
- 第三方插件/扩展系统默认启用且无验证
- 向外部服务发送文档内容但未明确告知用户

**中风险（需提醒用户注意）：**
- 文件路径未做穿越防护（`../../` 攻击）
- 输出文件覆盖已有内容无确认
- 递归目录遍历可能暴露意外文件

**平台审计结果（辅助验证）：**
结合 GitHub 仓库 README、skills.sh 安装页面或其他渠道获取的 Agent Trust Hub / Socket / Snyk 评级，与自主审计结果交叉验证。如自主审计与平台结果冲突，以自主审计为准。

### 3.4 仓库信誉检查

- **维护者身份**：个人/组织/官方（如 `anthropics`、`vercel-labs` 更可信）
- **提交验证状态**：是否有 Verified commits（GPG 签名）
- **Issue/PR 响应**：维护者是否积极回应社区反馈
- **安全修复历史**：是否有过漏洞修复记录

### 3.5 安全评分

对每个 skill 给出安全评分（1-10 分）。评分维度、分数段含义详见 `references/reference.md` 的"安全评分标准"部分。核心维度：Prompt 注入、凭证处理、代码执行、数据外泄、文件系统安全、插件系统、混淆内容。

**根据来源调整评分策略：**

| 来源 | 评分策略 |
|------|---------|
| Skills.sh / SkillHub | 完整 7 维评分，所有维度加权计算 |
| Agent-created | 仅检查致命红线，有不通过项标记为"风险需排查"，默认标记为"非第三方，信任度较高" |
| Bundled | 不评分，直接标注"Bundled — 无需审计" |

---

## 阶段 4：对比推荐与安装

### 4.1 生成综合对比表

合并所有阶段信息，生成**单一综合对比表**，新增来源和 Curator 维度：

| 指标 | Skill A | Skill B | Skill C |
|------|---------|---------|---------|
| **来源** | | | |
| 安装量 | | | |
| Stars | | | |
| 更新频率 | | | |
| Agent Trust Hub | | | |
| Socket | | | |
| Snyk | | | |
| 自主安全评分 | | | |
| **Curator 活跃度** | | | |
| **被合并到** | | | |
| 功能定位 | | | |
| 核心风险点 | | | |

- **来源**：Skills.sh / SkillHub / Agent-created / Bundled。基础分类，直接决定评估策略。
- **Curator 活跃度**：仅 agent-created 技能有值。高活跃度 → 可信度高。格式：`activity=58 use=17 patches=24 last=1d ago`。
- **被合并到**：如果技能已被 curator 合并到 umbrella（如 `arch-wsl-install → wsl-operations`），此列显示 umbrella 名称，并在推荐中指引用户使用 umbrella。

### 4.2 分级推荐

**安全优先型：** 推荐安全评分最高、Agent Trust Hub 通过、有完整安全文档的 skill。Agent-created 技能在此维度优先（非第三方代码）。

**功能优先型：** 推荐功能最全、更新最活跃、社区验证最多的 skill。Skills.sh 高安装量技能在此维度有优势。

**组合安装：** 同时安装两个 skills，日常用一个，安全参考用另一个。

**Consolidation 感知推荐：**
- 如果用户查询的技能已被 curator 归档（如 `quantitative-backtest`），先提示归档状态，再推荐替代品
- 如果已被合并到 umbrella（如 `dida365-openapi` → `platform-integration`），直接推荐 umbrella，说明该技能已被整合到更全面的父技能中
- 如果技能是 umbrella（如 `wsl-operations`），优先推荐 umbrella 并列出其覆盖的子技能范围

### 4.3 执行安装

用户确认后，根据技能来源选择正确的安装命令。完整命令速查和注意事项详见 `references/patterns.md`。

**Skills.sh 技能：**
```bash
bunx skills add {owner}/{repo}@{skill-name} -g -y
```

**SkillHub 技能：**
```bash
skillhub --dir ~/.hermes/skills/ install {slug}
```
注意 `--dir` 是全局选项，必须放在子命令 `install` 之前。

### 4.4 多 Agent 兼容处理

`bunx skills add` 内置 `--agent` 参数，支持 40+ 个 Agent。

**安装策略：**
1. 从系统提示词识别当前运行的 Agent
2. 默认安装到当前 Agent 的目录
3. 安装后询问用户是否扩展到其它 Agent
4. 避免使用 `--all`（会创建 40+ 个目录）

**单一真相源原则：**
- Skills.sh 安装以 `~/.agents/skills/` 为主目录
- Hermes 通过 `skills.external_dirs` 配置扫描 `~/.agents/skills/`，无需软链接或副本
- SkillHub 安装以 `~/.hermes/skills/` 为主目录

### 4.5 安装后验证

1. 检查安装路径：确认 skill 文件存在于目标 Agent 的技能目录中
2. 读取已安装 SKILL.md：确认内容与预期一致
3. 确认安全审计结果与评估时一致
4. 提醒用户审查 SKILL.md 内容后再使用

---

## 输出格式

评估完成后，按以下结构输出：

1. **搜索摘要**：找到 N 个候选 skills
2. **综合对比表**：合并所有关键指标
3. **安全评估详情**：每个 skill 的风险点和加分项
4. **分级推荐**：按安全/功能/组合三个维度
5. **安装命令**：用户可直接复制执行的命令
6. **安装后验证结果**：确认安装成功且内容一致
