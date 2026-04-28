---
name: daily-publish
description: 从多个数据源收集用户活动轨迹 → 分析并区分工作与个人内容 → 排版为 PDF → 投递到邮箱。触发词：「发日报」「生成日报」「发我的今天」「今日汇总」「日记 PDF」「每天总结」「保存日志」「生成日报发邮件」。当你发现用户需要做每日回顾、日志汇总、生成日报 PDF 并发送时触发。
---

# Daily Publish：活动轨迹 → 排版 → 投递

端到端流水线：从多个数据源收集今日活动轨迹，自动区分工作与个人内容，排版为 PDF 文档，投递到邮箱。

## 流程概览

```
收集活动轨迹（4 个数据源）
       ↓
分析：区分工作 vs 个人内容
       ↓
结构化：写日志正文（含时间线 + 专业复盘 + 个人点评）
       ↓
排版：Kami 风格 PDF
       ↓
投递：邮件发送
```

---

## Step 0：确定时间范围

默认范围：**昨晚 8 点到今晚 8 点**（覆盖完整的一天，含睡前活动）。

如果用户指定的范围不同，使用用户提供的范围。

## Step 1：收集活动轨迹（4 个数据源并行）

### 数据源 1：OpenCode + Qwen Code

使用 `worklog` 技能的提取脚本：

```bash
uv run ~/personal_code/skills/skills/worklog/extract.py --since today
```

输出包含今日所有 OpenCode 和 Qwen Code 会话，标记了会话 ID、项目目录、用户提问序列和工具调用摘要。

### 数据源 2：Hermes 会话

```bash
# 查看近期 Hermes 会话
session_search()
```

根据时间范围筛选会话，记录每个会话的：时间、来源（Telegram/WebUI/TUI/飞书/Cron）、主题。

### 数据源 3 & 4：Obsidian 工作库 + 个人库

```bash
find /mnt/c/Obsidian/工作 -name "*.md" -newermt "2026-04-27 20:00" ! -newermt "2026-04-29 00:00" -type f
find /mnt/c/Obsidian/个人 -name "*.md" -newermt "2026-04-27 20:00" ! -newermt "2026-04-29 00:00" -type f
```

注意：时间条件根据 Step 0 确定的范围动态调整。用 `find -newermt`（按修改时间）获取今天变更的日记文件，读取关键内容。

### 时间线校准

数据收集完成后，**必须交叉验证时间线**：
- 将每个事件的时间戳对齐到北京时间
- 标记明显的休息断点（相邻活动间隔 > 45 分钟）
- 如果发现有持续到深夜（如 23:00+）的轻量活动，标注为「睡前碎片」而非「加班」

---

## Step 2：分析并区分工作与个人

### 分类标准

| 类别 | 归属 |
|------|------|
| 公司项目部署、K8s 运维、数据库操作、代码开发、正式会议、团队协作 | **工作** |
| 个人技术探索、技能开发、投资阅读、工具折腾、生活琐事、休息碎片 | **个人** |

**每一条活动记录都必须明确归入工作或个人，不能混淆。**

特殊规则：
- **OpenCode/Qwen Code 的会话**：根据项目目录判断。`aliyun-services`、`onereason-backend` 等公司项目 → 工作；`personal_code/skills`、`~/.qwen`、浏览器/社交媒体 → 个人
- **飞书消息**：定时提醒、日常沟通 → 个人；阿里云测试机、正式项目群聊 → 工作
- **Hermes 会话**：根据话题判断，技术学习归个人，项目运维归工作

### 正文组织

- 先写「工作日志」，后写「个人日记」
- 每个类别按时间线排列，标记时间段（如 `10:00-11:00`）
- 工作部分用 `###` 标题按子系统分组（如 `### aigene.org.cn 域名迁移`）
- 个人部分用 `###` 标题按主题分组（如 `### Honcho 记忆架构排查`）
- 结尾的待完成列表放在工作日志末尾

---

## Step 3：写日志正文

### 日志正文结构

```
> 潭渊的今天

# {{日期}} 星期X

覆盖范围：{{时间范围}}

## 工作日志

### {{子系统/项目名}}

{{时间线 + 核心事件}}

#### 待完成

| 优先级 | 项目 |
|--------|------|

## 个人日记

### {{主题}}

### {{主题}}

## 点评

### 工作线

（专业角度复盘：技术选型合理性、执行效率、值得注意的经验教训）

### 个人线

（朋友视角点评：节奏感、值得记录的小细节、建议）
```

### 写作规范

**工作线点评** — 从专业角度评判：
- 技术方案选型的合理性（如：`innodb_flush_log_at_trx_commit=0` 是生产级导入的标准方案）
- 执行效率（如：上午清阻塞、下午攻主线，决策顺序正确）
- 值得记录的经验教训（如：`autocommit=0` 单事务在 7.1G 量级下 undo 爆炸是经典教训）
- 给出明天的优先级建议

**个人线点评** — 从朋友角度评价：
- 节奏感：不是被工作压着的节奏还是自己在 push 进度
- 值得记住的小细节（如：自己动手修脚本、翻出旧结论纠正、生活琐事没落下）
- 保留人情味的语气，不用工作报告的调子
- 结尾给一条生活建议
- 用「你」而非「用户」

### 禁止行为

- 不要把 emoji（✅ 🐛 🚀 🔄 等）直接写入 HTML——WeasyPrint 渲染 emoji 会导致乱码。用纯 CSS 标签替代（如 `.done-tag`、`.bug-tag`）
- 不要把表单/决策的细节展开写入（如「3 轮试错后确定方案」）
- 不要写入 AI 工具操作细节（如「调用了 search_files 工具」）

---

## Step 4：排版为 PDF（Kami）

### 选用模板

使用 `long-doc` 模板（多页 A4 长文），但**去掉封面和目录**。直接从 `<h1>` 开始。

### 操作流程

1. **读取模板** → 复制 CSS 样式，只修改 body 内容
2. **替换 emoji 为 CSS 标签**：

```css
/* 用纯 CSS 标签替代 emoji */
.done-tag {
  display: inline-block;
  background: #E4ECF5;
  color: #1B365D;
  font-size: 9pt;
  font-weight: 500;
  padding: 1pt 5pt;
  border-radius: 3pt;
  margin-right: 3pt;
}
.bug-tag {
  display: inline-block;
  background: #faf0f0;
  color: #a83737;
  font-size: 9pt;
  font-weight: 500;
  padding: 1pt 5pt;
  border-radius: 3pt;
  margin-right: 3pt;
}
```

3. **复制字体文件**：Kami 的字体在 `~/.hermes/skills/kami/assets/fonts/`，用绝对路径 `@font-face` 或确保 HTML 在同目录
4. **字间距**设置为 `0.8pt` 避免中文拥挤
5. **生成 PDF**：

```bash
cd {{output_dir}}
uv run --with weasyprint --with pypdf python3 -c "
from weasyprint import HTML
HTML('{{html_file}}').write_pdf('{{pdf_file}}')
from pypdf import PdfReader
print(f'PDF: {len(PdfReader(\"{{pdf_file}}\").pages)} pages')
"
```

### 常见问题

| 问题 | 解决 |
|------|------|
| emoji 乱码 | 用纯 CSS 标签替代（见上方 `done-tag`/`bug-tag`） |
| 字距太挤 | `body { letter-spacing: 0.8pt; }` |
| 页面溢出 | 调小 `font-size` 或 `margin` |
| WeasyPrint 未安装 | `uv run --with weasyprint` 自动安装 |
| 内容太长单页装不下 | 多页是正常的，long-doc 模板支持分页 |

---

## Step 5：投递邮箱（Himalaya）

### 收件人规则

| 场景 | 收件地址 |
|------|----------|
| 工作日/综合内容 | `CNife@vip.qq.com`（用户个人邮箱） |
| 仅工作内容 | `CNife@vip.qq.com` |
| 用户指定了其他地址 | 按用户指定 |

### 发送命令

```bash
cat << 'MAIL_EOF' | himalaya template send
From: Hermes Agent <hermes-agent@cnife.cn>
To: {{收件地址}}
Subject: 潭渊的今天 — {{日期}}

<#multipart type=mixed>
<#part type=text/plain>
PDF 已生成，请查收附件。

内容概要：
{{2-3 行工作线概要}}
{{2-3 行个人线概要}}

此邮件由 Hermes Agent 自动生成。
<#part filename={{pdf_path}} name={{pdf_name}}><#/part>
<#/multipart>
MAIL_EOF
```

### 注意

- `template send` 使用管道输入，无需打开编辑器
- 腾讯企业邮箱的 `cannot find UID of appended IMAP message` 错误是已知兼容问题——邮件实际已发送，忽略即可
- PDF 文件优先用绝对路径

---

## Step 6：保存源文件

排版和投递完成后，保留以下文件，路径格式统一：

```
~/hermes-workspace/diary/YYYY/MM/
├── YYYY-MM-DD.md        # Markdown 源文件
├── diary-YYYY-MM-DD.html # HTML 排版文件
└── YYYY-MM-DD.pdf       # PDF 附件
```

如果目录不存在则创建。

---

## 数据源参考路径

| 数据源 | 位置 |
|--------|------|
| 工作日志 | `/mnt/c/Obsidian/工作/工作日志/YYYY/MM/YYYY年M月D日星期X.md` |
| 个人日记 | `/mnt/c/Obsidian/个人/个人日记/YYYY/MM/YYYY年M月D日星期X.md` |
| 迁移执行日志 | `/mnt/c/Obsidian/工作/工作文档/202604 aigene.org.cn域名迁移/` |
| OpenCode DB | `~/.local/share/opencode/opencode.db` |
| OpenCode 日志 | `~/.local/share/opencode/log/` |
| Qwen Code 会话 | `~/.qwen/tmp/*/logs.json` |
| Qwen Code 对话 | `~/.qwen/projects/*/chats/*.jsonl` |
| Hermes 会话 | `session_search` 工具 |
| Kami 字体 | `~/.hermes/skills/kami/assets/fonts/` |
| Worklog 脚本 | `~/personal_code/skills/skills/worklog/extract.py` |
