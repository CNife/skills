# 最佳实践与常见陷阱

## 信息收集速查表

### 什么信息去哪里找

| 信息类型 | 来源 | URL 模式 |
|---------|------|---------|
| skill 功能详情 | skills.sh | `https://skills.sh/{owner}/{repo}/{skill-name}` |
| 安全审计结果 | skills.sh 安全页面 | 同上，查看底部安全评估 |
| Stars/Forks/Issues | GitHub 仓库主页 | `https://github.com/{owner}/{repo}` |
| 最近提交日期 | GitHub API | `https://api.github.com/repos/{owner}/{repo}/commits?per_page=5` |
| SKILL.md 源码 | GitHub Raw | `https://raw.githubusercontent.com/{owner}/{repo}/main/{skill-path}/SKILL.md` |
| 引用文件源码 | GitHub Raw | `https://raw.githubusercontent.com/{owner}/{repo}/main/{skill-path}/{filename}` |
| 仓库提交历史 | GitHub Commits 页 | `https://github.com/{owner}/{repo}/commits/main` |

### 并行执行原则

- 阶段 2 的所有信息收集操作应**同时执行**，不要串行等待
- 多个 skill 的源码读取可并行
- 多个 skill 的安全审计可并行

---

## 常见陷阱

### 1. 只看安装量

**错误做法：** 安装量最高 = 最安全

**正确做法：** 安装量反映社区信任度，但不等于安全性。必须结合安全审计结果和源码审查。

**案例：** davila7 的 markitdown 安装量 645（最高），但 Agent Trust Hub Fail，安全评分 6.5/10。

### 2. 忽略更新频率

**错误做法：** 找到 skill 就直接推荐

**正确做法：** 检查最近提交时间，超过 4 个月未更新的 skill 大概率已停止维护，不建议使用。

**判断标准：**
- 今天/昨天 → 活跃维护
- 1-4 周前 → 维护中
- 1-4 月前 → 低维护
- 4 个月以上 → 可能已放弃

### 3. 被示例代码误导

**错误做法：** 示例中有 `api_key="your-api-key"` 就认为硬编码密钥

**正确做法：** 区分占位符示例和真实硬编码。占位符（如 `"your-api-key"`、`"sk-..."`）是文档惯例，真正的硬编码是实际密钥字符串。但要注意：占位符示例可能normalize不良习惯。

### 4. 忽视插件系统风险

**错误做法：** 插件系统是功能加分

**正确做法：** 插件系统是**安全风险**。任何通过 pip 安装的包都可注册为插件执行任意代码。默认启用的插件系统应视为高风险。

### 5. 只看 SKILL.md 不检查引用文件

**错误做法：** 读完 SKILL.md 就完成审计

**正确做法：** SKILL.md 经常引用 `reference.md`、`patterns.md`、`scripts/*.py` 等文件。安全关键代码可能在引用文件中。必须读取所有被引用的文件。

### 6. 过度分析简单 skill

**错误做法：** 对一个 50 行的简单 skill 做 30 分钟深度审计

**正确做法：** 根据 skill 复杂度调整审计深度。简单 skill 检查致命红线即可；复杂 skill（含脚本、插件、网络调用）才需要完整审计。

**经验法则：**
- SKILL.md < 100 行，无脚本 → 检查致命红线（5 分钟）
- SKILL.md 100-300 行 → 标准审计（15 分钟）
- SKILL.md > 300 行或有附带脚本 → 完整审计（30 分钟+）

---

## 何时停止分析

### 足够推荐的信号

- [x] 已找到 2-3 个安全评分 7+ 的候选
- [x] 已确认至少一个在活跃维护
- [x] 已覆盖用户的核心需求
- [x] 安全审计无致命红线

### 需要继续分析的信号

- [ ] 所有候选都有致命红线（Critical 风险）
- [ ] 所有候选都超过 3 个月未更新
- [ ] 用户明确要求生产级安全标准，但候选都未通过 Agent Trust Hub
- [ ] 功能覆盖不全，缺少用户需要的关键功能

---

## 生产环境安全建议

### 安装后

1. **审查源码**：安装后阅读 SKILL.md 和所有引用文件
2. **沙箱执行**：在 Docker 或受限环境中首次运行
3. **权限最小化**：只授予必要的权限
4. **监控日志**：记录所有 agent 操作和工具调用

### API 密钥管理

```bash
# 正确：使用环境变量
export OPENAI_API_KEY="sk-..."
export OPENROUTER_API_KEY="sk-or-..."

# 错误：不要通过 CLI 参数传递（会出现在 shell 历史和 ps 输出中）
markitdown --api-key "sk-..." document.pdf
```

### 插件使用

```python
# 正确：显式禁用插件（除非明确需要）
md = MarkItDown(enable_plugins=False)

# 谨慎：如需插件，从可信源安装
md = MarkItDown(enable_plugins=True)  # 确保已安装的插件来自可信源
```

### 路径安全

```python
from pathlib import Path

# 正确：验证路径在允许范围内
safe_path = Path(user_input).resolve()
allowed_dir = Path("/allowed/directory").resolve()
if not safe_path.is_relative_to(allowed_dir):
    raise ValueError("Path traversal detected")

# 错误：直接使用用户输入
md.convert(user_input)  # 可能被 ../../ 攻击
```

---

## 对比表格模板

复制此模板用于最终输出：

```markdown
| 指标 | Skill A | Skill B | Skill C |
|------|---------|---------|---------|
| 安装量 | | | |
| Stars | | | |
| 更新频率 | | | |
| 安全评分 | | | |
| 功能完整度 | | | |
| Agent Trust Hub | | | |
| Socket | | | |
| Snyk | | | |
```

---

## 推荐话术模板

### 安全优先

> 推荐 `[skill 名称]`
> 
> **理由：** 安全评分 [X]/10，Agent Trust Hub [通过/警告/失败]，[具体安全加分项，如"有独立安全文档"、"插件默认禁用"、"提供沙箱实现"]。
> 
> **注意：** [已知的中等风险点，如"AI 功能会发送文档到外部 API"]

### 功能优先

> 推荐 `[skill 名称]`
> 
> **理由：** 功能最全，[具体独特功能]，更新最活跃（[更新频率]），社区验证最多（[安装量] 安装，[stars] stars）。
> 
> **安全提醒：** [已知的安全风险，如"插件系统无验证"、"路径未做穿越防护"]

### 组合安装

> 推荐同时安装 [Skill A] + [Skill B]：
> - 日常使用 [Skill A]：[优势]
> - 安全参考 [Skill B]：[优势]

---

## 智能安装最佳实践

### 安装前检测

- **推荐**：安装前先识别当前运行的 Agent（从系统提示词中获取），默认只安装到当前 Agent 的目录
- **推荐**：执行 `ls ~/.agents/skills/` 检测其他可用 Agent 目录，安装后询问用户是否需要扩展到那些 Agent
- **陷阱**：使用 `--all` 会创建 40+ 个目录，其中很多用户从未安装过对应 Agent → 浪费磁盘空间且难以管理
- **陷阱**：忘记为 Hermes 做软链接（skills.sh 不原生支持 hermes）→ Skills.sh 技能安装后必须补充执行 `ln -s ~/.agents/skills/<name> ~/.hermes/skills/<name>`
- **陷阱**：同一技能在多个目录复制导致版本不同步 → 以 `~/.agents/skills/` 为主目录（Skills.sh 安装），Hermes 通过软链接引用
- **陷阱**：`skillhub search` 不支持 `--dir` 参数，只有 `skillhub install` 才需要 `--dir`
- **最佳实践**：检测当前 Agent → 默认安装到当前 Agent → 询问是否扩展到其他 Agent → 按需执行

### 命令速查

| 来源 | 搜索 | 安装 | 备注 |
|------|------|------|------|
| Skills.sh | `bunx skills find <query>` | `bunx skills add <owner/repo@skill> -g -y` | 需额外软链接给 Hermes |
| SkillHub | `skillhub search <query>` | `skillhub --dir ~/.hermes/skills/ install <slug>` | `--dir` 是全局选项，须在子命令之前 |
| ClawHub | `clawhub search <query>` | `clawhub install <slug>` | 需手动处理路径 |

```
用户需求：评估/选择 skill
    │
    ├─ 是否指定了具体 skill 名称？
    │   ├─ 是 → 跳到阶段 3（安全评估）
    │   └─ 否 → 阶段 1（搜索候选）
    │
    ├─ 找到几个候选？
    │   ├─ 1 个 → 评估是否可用，同时搜索替代方案
    │   ├─ 2-3 个 → 标准对比流程
    │   └─ 4+ 个 → 先筛除低安装量/低 stars 的，保留 3 个深度评估
    │
    ├─ 安全评估结果？
    │   ├─ 全部 Critical → 警告用户，搜索替代方案
    │   ├─ 有 High 风险 → 明确警告，提供缓解措施
    │   └─ 全部可接受 → 正常推荐
    │
    └─ 用户确认后 → 阶段 4（执行安装）
```
